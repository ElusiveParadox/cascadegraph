import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@workspace/api-client-react";

const MAX_DELAY_MS = 30_000;
const MAX_STORAGE_RETRIES = 3;

function storageCode(error: unknown): unknown {
  const data = error instanceof ApiError ? error.data : null;
  return data && typeof data === "object" && "code" in data ? data.code : undefined;
}

function isStorageUnavailable(error: unknown): boolean {
  const code = storageCode(error);
  return code === "STORAGE_UNAVAILABLE" || code === "STORAGE_OVERLOADED";
}

/** Retry-After is a minimum, including when it is an HTTP date. */
function retryAfterMs(error: unknown): number {
  const value = error instanceof ApiError ? error.headers.get("Retry-After")?.trim() : null;
  if (!value) return 0;
  if (/^\d+$/.test(value)) return Number(value) * 1000;
  // Reject malformed numeric values rather than letting Date.parse reinterpret them.
  if (!/^[A-Za-z]/.test(value)) return 0;
  const date = Date.parse(value);
  return Number.isFinite(date) ? Math.max(0, date - Date.now()) : 0;
}

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  // GETs may bootstrap a session: the outcome code takes precedence over method
  // and Retry-After. Replaying one could create another anonymous owner.
  if (storageCode(error) === "STORAGE_OUTCOME_UNCERTAIN") return false;
  if (error instanceof ApiError && !["GET", "HEAD"].includes(error.method)) return false;
  if ((error as { status?: number } | null)?.status === 404) return false;
  // Do not shorten a server wait to our cap; leave longer waits to manual recovery.
  if (retryAfterMs(error) > MAX_DELAY_MS) return false;
  return failureCount < (isStorageUnavailable(error) ? MAX_STORAGE_RETRIES : 1);
}

export function queryRetryDelay(attemptIndex: number, error: unknown): number {
  const exponential = Math.min(24_000, 1000 * 2 ** Math.min(attemptIndex, 5));
  const minimum = Math.min(MAX_DELAY_MS, Math.max(exponential, retryAfterMs(error)));
  // Positive jitter never undercuts Retry-After and leaves room under the cap.
  return Math.min(MAX_DELAY_MS, minimum + Math.random() * Math.min(minimum * 0.25, MAX_DELAY_MS - minimum));
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetryQuery,
        retryDelay: queryRetryDelay,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}
