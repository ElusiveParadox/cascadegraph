import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { getOwnAiState, ownAiHeaders, setOwnAiConnection, subscribeOwnAi } from "../../../../lib/api-client-react/src/own-ai";

const key = "test-only-key-not-a-real-credential";
const config = { provider: "openai" as const, model: "gpt-5.4-mini", apiKey: key };
function count(headers: Headers) { return Array.from(headers.keys()).length; }
afterEach(() => setOwnAiConnection(null));

test("invalid model or credential cannot replace an existing valid connection", () => {
  setOwnAiConnection(config);
  for (const invalid of [{ ...config, model: "" }, { ...config, model: "bad model" }, { ...config, apiKey: "short" }]) {
    assert.throws(() => setOwnAiConnection(invalid));
    assert.deepEqual(getOwnAiState(), { provider: "openai", model: "gpt-5.4-mini" });
  }
});

test("only safe metadata is public; clear removes the credential", () => {
  let notifications = 0;
  const unsubscribe = subscribeOwnAi(() => notifications++);
  setOwnAiConnection(config);
  assert.deepEqual(getOwnAiState(), { provider: "openai", model: "gpt-5.4-mini" });
  assert.ok(!JSON.stringify(getOwnAiState()).includes(key));
  setOwnAiConnection(null);
  assert.equal(getOwnAiState(), null);
  assert.equal(count(ownAiHeaders("/api/v1/analyses", "POST", '{"use_ai":true}')), 0);
  assert.equal(notifications, 2);
  unsubscribe();
});

test("only opted-in analysis requests receive the key, including multipart and base paths", () => {
  setOwnAiConnection(config);
  const forms = new FormData();
  forms.set("use_ai", "true");
  for (const path of ["/api/v1/analyses", "/base/api/v1/analyses/sources", "/api/v1/analyses/archive", "/api/v1/analyses/repository"]) {
    const hdr = ownAiHeaders(path, "POST", path.endsWith("/sources") ? forms : '{"use_ai":true}');
    assert.equal(hdr.get("x-cascadegraph-ai-key"), key);
    assert.equal(hdr.get("x-cascadegraph-ai-provider"), "openai");
  }
});

test("no credential reaches external targets, status/auth/deletes or analyses without opt-in", () => {
  setOwnAiConnection(config);
  for (const target of ["https://attacker.example/api/v1/analyses", "//attacker.example/api/v1/analyses",
    "/\\attacker.example/api/v1/analyses", "/api/v1/status", "/api/v1/auth/sign-out", "/api/v1/analyses/id/simulations"]) {
    assert.equal(count(ownAiHeaders(target, "POST", '{"use_ai":true}')), 0);
  }
  assert.equal(count(ownAiHeaders("/api/v1/analyses", "DELETE", '{"use_ai":true}')), 0);
  assert.equal(count(ownAiHeaders("/api/v1/analyses", "POST", '{"use_ai":false}')), 0);
  assert.equal(count(ownAiHeaders("/api/v1/analyses", "POST", "malformed")), 0);
});
