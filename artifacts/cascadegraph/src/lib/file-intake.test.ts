import assert from "node:assert/strict";
import { test } from "node:test";
import type { SystemStatus } from "@workspace/api-client-react";
import { archiveSelectionError, sourceSelectionError } from "./file-intake";

const limits = { max_archive_mb: 50, max_source_files: 100, max_file_kb: 512, max_source_mb: 20 } as SystemStatus;
const file = (name: string, size = 1) => ({ name, size });

test("archive types, single selection and exact server size boundary", () => {
  assert.equal(archiveSelectionError([file("repo.ZIP", 50 * 1024 ** 2)], limits), null);
  assert.match(archiveSelectionError([file("repo.zip", 50 * 1024 ** 2 + 1)], limits)!, /50 MiB/);
  assert.match(archiveSelectionError([file("repo.tar")], limits)!, /Only .zip/);
  assert.match(archiveSelectionError([file("a.zip"), file("b.zip")], limits)!, /one ZIP/);
});

test("source extensions and exact per-file, aggregate and count boundaries", () => {
  for (const name of ["a.py", "a.YAML", "a.yml", "a.toml", "a.txt"]) {
    assert.equal(sourceSelectionError([file(name, 512 * 1024)], limits), null);
  }
  for (const name of ["a.zip", "a.exe", "a.py.exe", "README", "a.js"]) {
    assert.match(sourceSelectionError([file(name)], limits)!, /supported source types/);
  }
  assert.match(sourceSelectionError([file("a.py", 512 * 1024 + 1)], limits)!, /512 KiB/);
  assert.equal(sourceSelectionError(Array.from({ length: 100 }, () => file("a.py")), limits), null);
  assert.match(sourceSelectionError(Array.from({ length: 101 }, () => file("a.py")), limits)!, /100 source files/);
  const full = Array.from({ length: 40 }, () => file("a.py", 512 * 1024));
  assert.equal(sourceSelectionError(full, limits), null);
  assert.match(sourceSelectionError([...full, file("more.py")], limits)!, /20 MiB/);
});

test("validation and error messages follow changed server limits", () => {
  const smaller = { ...limits, max_archive_mb: 1, max_file_kb: 2, max_source_files: 2, max_source_mb: 1 };
  assert.match(archiveSelectionError([file("a.zip", 1024 ** 2 + 1)], smaller)!, /1 MiB/);
  assert.match(sourceSelectionError([file("a.py", 2049)], smaller)!, /2 KiB/);
  assert.match(sourceSelectionError([file("a.py"), file("b.py"), file("c.py")], smaller)!, /2 source files/);
  assert.match(sourceSelectionError([file("a.py")], { ...limits, max_file_kb: undefined })!, /limits are unavailable/);
});
