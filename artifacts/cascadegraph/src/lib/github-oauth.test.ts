import assert from "node:assert/strict";
import { test } from "node:test";
import { githubOAuthError, githubOAuthParams } from "./github-oauth";

test("GitHub OAuth uses the real strategy and full artifact-relative callback", () => {
  assert.deepEqual(githubOAuthParams("https://app.example", "/"), {
    strategy: "oauth_github",
    redirectCallbackUrl: "https://app.example/auth/callback",
    redirectUrl: "https://app.example/workspace",
  });
  assert.equal(githubOAuthParams("https://app.example", "/workbench/").redirectCallbackUrl,
    "https://app.example/workbench/auth/callback");
});

test("provider-disabled errors show an honest actionable message without provider payloads", () => {
  const result = githubOAuthError({ cause: { errors: [{
    code: "form_param_value_invalid", meta: { paramName: "strategy" },
    message: "canary-sensitive-token-must-not-render",
  }] } });
  assert.match(result, /not enabled/);
  assert.doesNotMatch(result, /canary|token-must/);
});

test("network and unrelated validation failures never become a false provider-disabled diagnosis", () => {
  assert.match(githubOAuthError(new Error("canary-sensitive-password-must-not-render")), /could not start/);
  assert.match(githubOAuthError({ code: "form_param_value_invalid", meta: { paramName: "redirect_url" } }), /could not start/);
  assert.doesNotMatch(githubOAuthError({ message: "canary-sensitive-password-must-not-render" }), /canary/);
});
