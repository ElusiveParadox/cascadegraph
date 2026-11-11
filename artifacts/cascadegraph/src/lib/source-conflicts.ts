import type { SourceFile } from "./directory-intake";

export type ConflictChoice = "keep" | "replace" | "cancel";

// Submission trims paths, so conflict detection must use the same identity.
const pathKey = (source: SourceFile) => source.path.trim();

export function sourceConflicts(existing: SourceFile[], incoming: SourceFile[]): string[] {
  const seen = new Set(existing.map(pathKey));
  const conflicts = new Set<string>();
  for (const source of incoming) {
    const path = pathKey(source);
    if (seen.has(path)) conflicts.add(path);
    seen.add(path);
  }
  return [...conflicts];
}

/** Pure, atomic merge: keep the current order and edited paths when replacing. */
export function resolveSourceConflicts(existing: SourceFile[], incoming: SourceFile[], choice: ConflictChoice): SourceFile[] {
  if (choice === "cancel") return existing;
  const result = [...existing];
  const positions = new Map(result.map((source, index) => [pathKey(source), index]));
  for (const source of incoming) {
    const key = pathKey(source);
    const index = positions.get(key);
    if (index === undefined) {
      positions.set(key, result.length);
      result.push(source);
    } else if (choice === "replace") {
      result[index] = { ...result[index], file: source.file };
    }
  }
  return result;
}
