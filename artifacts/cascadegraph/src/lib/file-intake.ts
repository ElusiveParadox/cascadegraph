import type { SystemStatus } from "@workspace/api-client-react";

export const SOURCE_ACCEPT = ".py,.yaml,.yml,.toml,.txt";
type FileInfo = Pick<File, "name" | "size">;

export function archiveSelectionError(files: FileInfo[], limits: SystemStatus): string | null {
  if (files.length !== 1) return "Choose one ZIP archive at a time.";
  if (!/\.zip$/i.test(files[0].name)) return "Only .zip archives are accepted. Choose source/configuration files in the source panel instead.";
  if (files[0].size > limits.max_archive_mb * 1024 * 1024) return `${files[0].name} exceeds the ${limits.max_archive_mb} MiB archive limit.`;
  return null;
}

export function sourceSelectionError(files: FileInfo[], limits: SystemStatus): string | null {
  if (!files.length) return null;
  const { max_source_files, max_file_kb, max_source_mb } = limits;
  if (max_source_files === undefined || max_file_kb === undefined || max_source_mb === undefined) {
    return "Source-file limits are unavailable. Reload the workbench before selecting source files.";
  }
  const unsupported = files.find(file => !/\.(py|yaml|yml|toml|txt)$/i.test(file.name));
  if (unsupported) return `${unsupported.name}: supported source types are ${SOURCE_ACCEPT}. Use the ZIP panel for archives.`;
  if (files.length > max_source_files) return `Select at most ${max_source_files} source files; use a ZIP for larger sets.`;
  const oversized = files.find(file => file.size > max_file_kb * 1024);
  if (oversized) return `${oversized.name} exceeds the ${max_file_kb} KiB per-file limit.`;
  if (files.reduce((sum, file) => sum + file.size, 0) > max_source_mb * 1024 * 1024) {
    return `Selected source exceeds ${max_source_mb} MiB; select only the relevant application.`;
  }
  return null;
}
