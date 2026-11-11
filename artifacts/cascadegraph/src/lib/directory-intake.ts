import type { SystemStatus } from "@workspace/api-client-react";
import { sourceSelectionError } from "./file-intake";

export type SourceFile = { file: File; path: string };
/** Minimal shape also permits deterministic discovery tests without a browser. */
export type SourceEntry = {
  name: string;
  isFile: boolean;
  isDirectory: boolean;
  file?: (success: (file: File) => void, error: (error: unknown) => void) => void;
  createReader?: () => { readEntries: (success: (entries: SourceEntry[]) => void, error: (error: unknown) => void) => void };
};
export type Discovery = { files: SourceFile[]; skipped: string[]; skippedCount: number };
const ignoredDirectories = new Set([".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".github"]);
const supported = /\.(py|yaml|yml|toml|txt)$/i;

/** Strip the selected repository root, not its nested directories. */
export function folderRelativePath(path: string): string {
  const parts = path.split("/");
  return parts.length > 1 ? parts.slice(1).join("/") : path;
}

function collector(limits: SystemStatus, existing: File[]) {
  if ([limits.max_source_files, limits.max_file_kb, limits.max_source_mb].some(n => n === undefined || !Number.isFinite(n) || n <= 0)) {
    throw new Error("Source-file limits are unavailable. Reload the workbench before selecting a folder.");
  }
  const result: Discovery = { files: [], skipped: [], skippedCount: 0 };
  let visited = 0;
  let bytes = existing.reduce((sum, file) => sum + file.size, 0);
  const entryLimit = limits.max_files ?? limits.max_source_files!;
  return {
    result,
    visit(path: string) {
      if (++visited > entryLimit) throw new Error(`Folder discovery exceeds ${entryLimit} entries; select a smaller folder or use a ZIP.`);
      if (path.split("/").length > 64) throw new Error("Folder nesting exceeds 64 levels; select a smaller folder.");
      if (path.split("/").some(p => !p || p === "." || p === ".." || p.includes("\\"))) {
        throw new Error("Folder paths must be relative, without traversal or backslashes.");
      }
    },
    skip(path: string, reason: string) {
      result.skippedCount++;
      if (result.skipped.length < 10) result.skipped.push(`${path}: ${reason}`);
    },
    add(file: File, path: string) {
      const error = sourceSelectionError([file], limits);
      if (error) throw new Error(error);
      if (existing.length + result.files.length + 1 > limits.max_source_files!) {
        throw new Error(`Select at most ${limits.max_source_files} source files; use a ZIP for larger sets.`);
      }
      bytes += file.size;
      if (bytes > limits.max_source_mb! * 1024 * 1024) throw new Error(`Selected source exceeds ${limits.max_source_mb} MiB; select only the relevant application.`);
      result.files.push({ file, path });
    },
  };
}

function ignoredPath(path: string): boolean {
  return path.split("/").some(part => ignoredDirectories.has(part) || part.startsWith(".env"));
}

/** Native directory pickers have already enumerated files; bound our own processing. */
export function collectFolderFiles(files: Iterable<File>, limits: SystemStatus, existing: File[] = []): Discovery {
  const c = collector(limits, existing);
  for (const file of files) {
    const path = folderRelativePath(file.webkitRelativePath || file.name);
    c.visit(path);
    if (ignoredPath(path)) c.skip(path, "ignored source path");
    else if (!supported.test(file.name)) c.skip(path, "unsupported file type");
    else c.add(file, path);
  }
  return c.result;
}

/** Sequential, batched reads stop immediately on limits; no file contents are read. */
export async function collectDirectoryEntries(entries: SourceEntry[], limits: SystemStatus, existing: File[] = []): Promise<Discovery> {
  const c = collector(limits, existing);
  async function walk(entry: SourceEntry, path: string) {
    c.visit(path);
    if (ignoredPath(path)) { c.skip(path, "ignored source path"); return; }
    if (entry.isDirectory && entry.createReader) {
      const reader = entry.createReader();
      while (true) {
        let batch: SourceEntry[];
        try {
          batch = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
        } catch {
          c.skip(path, "folder could not be read"); return;
        }
        if (!batch.length) return;
        for (const child of batch) await walk(child, `${path}/${child.name}`);
      }
    } else if (entry.isFile && entry.file) {
      if (!supported.test(entry.name)) { c.skip(path, "unsupported file type"); return; }
      let file: File;
      try {
        file = await new Promise((resolve, reject) => entry.file!(resolve, reject));
      } catch {
        c.skip(path, "file could not be read"); return;
      }
      c.add(file, path);
    } else c.skip(path, "unsupported entry");
  }
  for (const entry of entries) {
    const before = c.result.files.length;
    await walk(entry, entry.name);
    // Each dropped directory is a repository root. Loose dropped files keep their name.
    if (entry.isDirectory) {
      for (const source of c.result.files.slice(before)) source.path = folderRelativePath(source.path);
    }
  }
  return c.result;
}
