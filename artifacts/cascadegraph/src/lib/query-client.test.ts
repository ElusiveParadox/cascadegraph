import assert from "node:assert/strict";
import { test } from "node:test";
import { timeoutManager } from "@tanstack/react-query";
import { ApiError, getSystemStatus, listAnalyses } from "@workspace/api-client-react";
import { createQueryClient, queryRetryDelay, shouldRetryQuery } from "./query-client";

function apiError(code = "STORAGE_UNAVAILABLE", retryAfter?: string, method = "GET", status = 503) {
  const headers = new Headers();
  if (retryAfter !== undefined) headers.set("Retry-After", retryAfter);
  return new ApiError(new Response(null, { status, headers }), { code }, { method, url: "/api/v1/analyses" });
}

test("Retry-After seconds and HTTP dates are minimum waits with positive jitter", (t) => {
  t.mock.method(Date, "now", () => Date.UTC(2026, 10, 10));
  const random = t.mock.method(Math, "random", () => 0);
  const error = apiError("STORAGE_UNAVAILABLE", "2");
  assert.equal(queryRetryDelay(0, error), 2000);
  random.mock.mockImplementation(() => 0.5);
  assert.equal(queryRetryDelay(0, error), 2250);
  assert.equal(queryRetryDelay(2, error), 4500);
  const date = new Date(Date.now() + 5000).toUTCString();
  assert.equal(queryRetryDelay(0, apiError("STORAGE_OVERLOADED", date)), 5625);
});

test("missing, malformed and expired hints use bounded exponential backoff", (t) => {
  t.mock.method(Math, "random", () => 0.5);
  for (const value of [undefined, "", "garbage", "-2", "1.5", "Infinity", "Tue, 10 Nov 2020 00:00:00 GMT"]) {
    const error = apiError("STORAGE_UNAVAILABLE", value);
    assert.equal(queryRetryDelay(0, error), 1125);
    assert.equal(queryRetryDelay(1, error), 2250);
    assert.equal(queryRetryDelay(2, error), 4500);
    assert.equal(queryRetryDelay(1000, error), 27_000);
  }
  assert.equal(queryRetryDelay(1000, new TypeError("network")), 27_000);
});

test("delay cap never overrides a longer server wait", (t) => {
  t.mock.method(Math, "random", () => 0.999);
  t.mock.method(Date, "now", () => Date.UTC(2026, 10, 10));
  const capped = apiError("STORAGE_UNAVAILABLE", "30");
  assert.equal(queryRetryDelay(10, capped), 30_000);
  assert.equal(shouldRetryQuery(0, capped), true);
  for (const value of ["31", "9".repeat(400), new Date(Date.now() + 60_000).toUTCString()]) {
    assert.equal(shouldRetryQuery(0, apiError("STORAGE_UNAVAILABLE", value)), false);
    assert.equal(queryRetryDelay(0, apiError("STORAGE_UNAVAILABLE", value)), 30_000);
  }
});

test("storage retries are finite; ordinary errors retain the single retry and 404 exclusion", () => {
  for (const code of ["STORAGE_UNAVAILABLE", "STORAGE_OVERLOADED"]) {
    assert.deepEqual([0, 1, 2, 3].map((n) => shouldRetryQuery(n, apiError(code, "2"))), [true, true, true, false]);
  }
  for (const error of [new TypeError("network"), apiError("OTHER"), { status: 500 }, null]) {
    assert.equal(shouldRetryQuery(0, error), true);
    assert.equal(shouldRetryQuery(1, error), false);
  }
  assert.equal(shouldRetryQuery(0, apiError("OTHER", undefined, "GET", 404)), false);
  assert.equal(shouldRetryQuery(0, { status: 404 }), false);
  for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
    assert.equal(shouldRetryQuery(0, apiError("STORAGE_UNAVAILABLE", "2", method)), false);
  }
});

test("real QueryClient schedules storage read retries using response headers", async (t) => {
  t.mock.method(Math, "random", () => 0.5);
  const delays: number[] = [];
  // Record and immediately advance retry timers; no wall-clock sleeps.
  t.mock.method(timeoutManager, "setTimeout", (callback: () => void, delay: number) => {
    delays.push(delay);
    return setTimeout(callback, 0);
  });
  const client = createQueryClient();
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => {
    calls++;
    return Response.json({ code: "STORAGE_UNAVAILABLE", error: "storage unavailable" }, {
      status: 503, headers: { "Retry-After": "2" },
    });
  });
  try {
    await assert.rejects(client.fetchQuery({ queryKey: ["history"], queryFn: () => listAnalyses() }), ApiError);
    assert.equal(calls, 4);
    // TanStack computes delay before checking retry eligibility, but only schedules three.
    assert.deepEqual(delays, [2250, 2250, 4500]);
  } finally {
    client.clear();
  }
});

test("uncertain session-bootstrap GETs are never retried even with Retry-After", async (t) => {
  const client = createQueryClient();
  let calls = 0;
  t.mock.method(timeoutManager, "setTimeout", () => {
    assert.fail("An uncertain session response must not schedule a retry");
  });
  t.mock.method(globalThis, "fetch", async () => {
    calls++;
    return Response.json({ code: "STORAGE_OUTCOME_UNCERTAIN", error: "Check history after recovery" }, {
      status: 503, headers: { "Retry-After": "2" },
    });
  });
  try {
    for (const [key, queryFn] of [["status", getSystemStatus], ["history", listAnalyses]] as const) {
      await assert.rejects(client.fetchQuery({ queryKey: [key], queryFn: () => queryFn() }), (error: unknown) => {
        assert.ok(error instanceof ApiError);
        assert.equal(error.method, "GET");
        assert.equal(error.headers.get("Retry-After"), "2");
        assert.equal(shouldRetryQuery(0, error), false);
        return true;
      });
    }
    assert.equal(calls, 2);
  } finally {
    client.clear();
  }
});

test("mutations never replay after ordinary or uncertain storage failures", async () => {
  const client = createQueryClient();
  try {
    assert.equal(client.getDefaultOptions().mutations?.retry, false);
    for (const code of ["STORAGE_UNAVAILABLE", "STORAGE_OUTCOME_UNCERTAIN"]) {
      let calls = 0;
      const mutation = client.getMutationCache().build(client, {
        mutationFn: async () => {
          calls++;
          throw apiError(code, "2", "POST");
        },
      });
      await assert.rejects(mutation.execute(undefined), ApiError);
      assert.equal(calls, 1);
    }
  } finally {
    client.clear();
  }
});
