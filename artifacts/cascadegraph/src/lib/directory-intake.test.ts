import assert from "node:assert/strict";
import { test } from "node:test";
import type { SystemStatus } from "@workspace/api-client-react";
import { collectDirectoryEntries, collectFolderFiles, type SourceEntry } from "./directory-intake";

const limits = { max_files: 2000, max_source_files: 100, max_file_kb: 512, max_source_mb: 20 } as SystemStatus;
function file(name: string, size = 1, relativePath = "") {
  const value = new File([new Uint8Array(size)], name);
  Object.defineProperty(value, "webkitRelativePath", { value: relativePath });
  return value;
}
function leaf(name: string, size = 1): SourceEntry {
  return { name, isFile: true, isDirectory: false, file: done => done(file(name, size)) };
}
function directory(name: string, ...batches: SourceEntry[][]): SourceEntry {
  return { name, isFile: false, isDirectory: true, createReader() {
    let i = 0;
    return { readEntries: done => done(batches[i++] ?? []) };
  } };
}

test("folder picker strips only the selected root and preserves nested repository paths", () => {
  const result = collectFolderFiles([
    file("client.py", 1, "repo/services/gateway/client.py"),
    file("compose.yaml", 1, "repo/compose.yaml"),
  ], limits);
  assert.deepEqual(result.files.map(f => f.path), ["services/gateway/client.py", "compose.yaml"]);
  assert.equal(result.skippedCount, 0);
});

test("directory drops read every browser batch and preserve mixed loose files and nested paths", async () => {
  const result = await collectDirectoryEntries([
    directory("repo", [directory("services", [leaf("client.py")])], [leaf("compose.yml")]),
    leaf("settings.toml"),
    directory("other-repo", [directory("nested", [leaf("retry.py")])]),
  ], limits);
  assert.deepEqual(result.files.map(f => f.path), ["services/client.py", "compose.yml", "settings.toml", "nested/retry.py"]);
});

test("unsupported files, ignored directories, unreadable files and special entries are reported", async () => {
  const ignored = directory("node_modules");
  ignored.createReader = () => { throw new Error("must not traverse ignored tree"); };
  const result = await collectDirectoryEntries([directory("repo", [
    leaf("README.md"), ignored, leaf(".env.txt"),
    { ...leaf("private.py"), file: (_done, fail) => fail(new Error("denied")) },
    { name: "special", isFile: false, isDirectory: false },
    { ...directory("denied"), createReader: () => ({ readEntries: (_done, fail) => fail(new Error("denied")) }) },
    leaf("good.py"),
  ])], limits);
  assert.deepEqual(result.files.map(f => f.path), ["good.py"]);
  assert.equal(result.skippedCount, 6);
  for (const reason of ["unsupported file type", "ignored source path", "file could not be read", "unsupported entry", "folder could not be read"]) {
    assert.ok(result.skipped.some(message => message.includes(reason)));
  }
});

test("native folder picks skip unsupported and ignored paths with bounded reporting", () => {
  const result = collectFolderFiles([
    file("x.py", 1, "repo/.git/x.py"),
    ...Array.from({ length: 15 }, (_, i) => file(`x${i}.js`, 1, `repo/src/x${i}.js`)),
    file("ok.py", 1, "repo/src/ok.py"),
  ], limits);
  assert.equal(result.skippedCount, 16);
  assert.equal(result.skipped.length, 10);
  assert.equal(result.files[0].path, "src/ok.py");
});

test("source count includes existing selection and halts discovery before later reads", async () => {
  let laterRead = false;
  const later = { ...leaf("later.py"), file: () => { laterRead = true; } };
  await assert.rejects(collectDirectoryEntries([
    directory("repo", [leaf("a.py"), leaf("b.py"), later]),
  ], { ...limits, max_source_files: 2 }, [file("existing.py")]), /at most 2 source files/);
  assert.equal(laterRead, false);
});

test("ignored-only and empty directory trees cannot evade the discovery entry budget", async () => {
  let reads = 0;
  const tree = directory("repo");
  tree.createReader = () => ({ readEntries: done => { reads++; done([directory("empty")]); } });
  await assert.rejects(collectDirectoryEntries([tree], { ...limits, max_files: 4 }), /4 entries/);
  assert.equal(reads, 4);
  assert.throws(() => collectFolderFiles(Array.from({ length: 5 }, () => file("skip.js")), { ...limits, max_files: 4 }), /4 entries/);
});

test("per-file and aggregate byte limits reject the new batch including existing bytes", async () => {
  await assert.rejects(collectDirectoryEntries([directory("repo", [leaf("big.py", 2049)])],
    { ...limits, max_file_kb: 2 }), /2 KiB/);
  const small = { ...limits, max_file_kb: 1024, max_source_mb: 1 };
  const existing = [file("existing.py", 1024 * 1024 - 1)];
  assert.equal((await collectDirectoryEntries([directory("repo", [leaf("a.py")])], small, existing)).files.length, 1);
  await assert.rejects(collectDirectoryEntries([directory("repo", [leaf("a.py", 2)])], small, existing), /1 MiB/);
  assert.throws(() => collectFolderFiles([file("big.py", 2049)], { ...limits, max_file_kb: 2 }), /2 KiB/);
});

test("invalid limits, unsafe paths and excessive nesting fail explicitly", async () => {
  assert.throws(() => collectFolderFiles([], { ...limits, max_source_files: undefined }), /limits are unavailable/);
  assert.throws(() => collectFolderFiles([file("x.py", 1, "repo/../x.py")], limits), /without traversal/);
  let tree = leaf("x.py");
  for (let i = 0; i < 65; i++) tree = directory(`d${i}`, [tree]);
  await assert.rejects(collectDirectoryEntries([tree], limits), /64 levels/);
});
