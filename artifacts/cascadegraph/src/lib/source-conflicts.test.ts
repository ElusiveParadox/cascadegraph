import assert from "node:assert/strict";
import { test } from "node:test";
import type { SystemStatus } from "@workspace/api-client-react";
import { collectDirectoryEntries, collectFolderFiles, type SourceEntry, type SourceFile } from "./directory-intake";
import { sourceSelectionError } from "./file-intake";
import { resolveSourceConflicts, sourceConflicts } from "./source-conflicts";

const limits = { max_files: 100, max_source_files: 3, max_file_kb: 2, max_source_mb: 1 } as SystemStatus;
function source(path: string, content = "old"): SourceFile {
  return { path, file: new File([content], path.split("/").pop()!) };
}

test("single-file conflicts keep existing bytes, replace explicitly, or cancel the whole batch", async () => {
  const existing = [source("client.py"), source("custom/compose.yaml")];
  const incoming = [source("client.py", "new"), source("retry.py")];
  assert.deepEqual(sourceConflicts(existing, incoming), ["client.py"]);
  const kept = resolveSourceConflicts(existing, incoming, "keep");
  assert.equal(kept[0], existing[0]);
  assert.equal(kept[1], existing[1]);
  assert.equal(kept[2], incoming[1]);
  const replaced = resolveSourceConflicts(existing, incoming, "replace");
  assert.equal(await replaced[0].file.text(), "new");
  assert.equal(replaced[1], existing[1]);
  assert.equal(replaced.length, 3);
  assert.equal(resolveSourceConflicts(existing, incoming, "cancel"), existing);
  assert.equal(await existing[0].file.text(), "old");
});

test("edited paths, not original filenames, define conflicts using submitted path identity", () => {
  const edited = source("  services/custom.py  ");
  const existing = [edited, source("Other.py")];
  const incoming = [source("custom.py"), source("services/custom.py", "replacement"), source("other.py")];
  assert.deepEqual(sourceConflicts(existing, incoming), ["services/custom.py"]);
  const result = resolveSourceConflicts(existing, incoming, "replace");
  assert.equal(result[0].path, edited.path);
  assert.equal(result[0].file, incoming[1].file);
  assert.equal(result[1], existing[1]);
  assert.deepEqual(result.slice(2).map(s => s.path), ["custom.py", "other.py"]);
});

test("nested folder reselection at capacity validates the resolved selection, not old plus new", () => {
  const picked = ["repo/services/client.py", "repo/compose.yaml"].map(path => {
    const { file } = source(path);
    Object.defineProperty(file, "webkitRelativePath", { value: path });
    return file;
  });
  const discovery = collectFolderFiles(picked, limits);
  const existing = [...discovery.files, source("edited/keep.py")];
  const incoming = collectFolderFiles(picked, limits).files;
  assert.deepEqual(sourceConflicts(existing, incoming), ["services/client.py", "compose.yaml"]);
  for (const choice of ["keep", "replace"] as const) {
    const merged = resolveSourceConflicts(existing, incoming, choice);
    assert.equal(merged.length, 3);
    assert.equal(merged[2], existing[2]);
    assert.equal(sourceSelectionError(merged.map(s => s.file), limits), null);
  }
  const tooMany = resolveSourceConflicts(existing, [source("new.py")], "keep");
  assert.match(sourceSelectionError(tooMany.map(s => s.file), limits)!, /at most 3/);
});

test("multiple dropped directories with the same relative path resolve within the incoming batch", async () => {
  function directory(name: string, content: string): SourceEntry {
    return { name, isDirectory: true, isFile: false, createReader: () => {
      let read = false;
      return { readEntries: done => {
        done(read ? [] : [{ name: "client.py", isFile: true, isDirectory: false,
          file: success => success(source("client.py", content).file) }]);
        read = true;
      } };
    } };
  }
  const batch = await collectDirectoryEntries([directory("repo-a", "first"), directory("repo-b", "last")], limits);
  assert.deepEqual(sourceConflicts([], batch.files), ["client.py"]);
  assert.equal(await resolveSourceConflicts([], batch.files, "keep")[0].file.text(), "first");
  assert.equal(await resolveSourceConflicts([], batch.files, "replace")[0].file.text(), "last");
  assert.deepEqual(resolveSourceConflicts([], batch.files, "cancel"), []);
});

test("resolved replacements still enforce per-file and aggregate byte limits without mutating existing", () => {
  const existing = [source("client.py")];
  const incoming = [source("client.py", "x".repeat(2049))];
  assert.match(sourceSelectionError(resolveSourceConflicts(existing, incoming, "replace").map(s => s.file), limits)!, /2 KiB/);
  const byteLimits = { ...limits, max_file_kb: 1024 };
  const batch = [source("client.py", "x".repeat(600 * 1024)), source("other.py", "x".repeat(600 * 1024))];
  assert.match(sourceSelectionError(resolveSourceConflicts(existing, batch, "replace").map(s => s.file), byteLimits)!, /1 MiB/);
  assert.equal(existing.length, 1);
  assert.equal(existing[0].file.size, 3);
});
