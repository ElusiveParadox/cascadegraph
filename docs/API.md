# HTTP API

Authoritative hand-maintained contract: `lib/api-spec/openapi.yaml`.
Generated consumers: `lib/api-client-react` and `lib/api-zod`. FastAPI's `/docs`
also exposes runtime route metadata; use the curated contract for stable schemas.

Base `/api`:
- GET `/healthz`, `/v1/health/live`, `/v1/health/ready`, `/v1/status`.
- GET/POST `/v1/analyses`; POST JSON `{source_type:"sample",use_ai:false}`.
- POST `/v1/analyses/archive` multipart ZIP `file` plus optional boolean `use_ai`
  and repository-relative `project_path`.
- POST `/v1/analyses/repository` JSON `repository_url`, optional `ref`,
  `project_path`, `use_ai`. Only public GitHub root URLs are accepted.
- POST `/v1/analyses/sources` multipart repeated `files` and matching `paths`,
  optional `repository_url`, `ref`, `project_path`, `use_ai`. Source files may
  supplement/override a public snapshot, but overrides are explicitly labelled.
- GET/DELETE `/v1/analyses/{id}`.
- PATCH `/v1/analyses/{id}/policies/{policyId}` with total attempts and reviewer
  note; optional per-attempt timeout and overall deadline in milliseconds.
- POST `/v1/analyses/{id}/edges/{edgeId}/confirm` with reviewer note.
- POST `/v1/analyses/{id}/simulations` with bounded scenario.
- GET `/v1/simulations/{id}`, `/v1/analyses/{id}/report`, `/v1/validation`.

Anonymous HttpOnly/SameSite-strict cookie ownership applies to every analysis/run
lookup. Unknown or other-session objects return 404. Mutation origins are checked
against the host; limits may return 413/429. Invalid/unsupported input returns
422; unavailable dependencies return explicit errors. Responses carry a
correlation ID and no-store headers; logs never contain source bodies.

ZIP/download cap: 50 MiB. Declared expanded archive: 200 MiB. Retained supported
source: 20 MiB, 512 KiB per file. Archive entries: 2,000. Direct source uploads:
100 files. Unsupported/binary/dependency assets are not parsed or retained.
JSON endpoints remain capped at 64 KiB; large bodies are admitted before buffering
under the same two-slot analysis limit. Upload reads and GitHub requests time out.

Analysis responses include optional `repository` provenance and `requested_files`
guidance. Missing/ambiguous input produces a partial analysis, not invented edges
or retry values. A corrected source submission creates a new analysis with fixed source provenance;
raw source is not stored for later recomputation.

## Storage availability and health

The execution checkout uses SQLite only (no credential vault, async database pool,
or alternate storage). Every HTTP database call, including session validation and
analysis persistence, uses the same dedicated process admission:

| Limit | Budget |
|---|---|
| Running storage calls per server process | 2 |
| Waiting queue / admission wait | 0 / immediate 503 when full |
| SQLite connection lock wait (`timeout` / busy timeout) | 100 ms |
| SQLite transaction / VM operation deadline | 400 ms, progress check every 100 VM instructions; check again before commit |
| Entire execution, including process start, acquisition/connect and commit | 800 ms |
| Stop/reap after deadline or cancellation | 200 ms TERM grace + 200 ms KILL/reap |
| Shutdown | 1 second to stop admission, terminate active workers and drain |
| Readiness | 1 in flight; 500 ms failure cooldown (including overload) |

These are storage-call budgets, not analysis/upload deadlines. A request can
perform session resolution plus separate read/write calls; existing 90-second
analysis and 30-second body-read limits still apply. No work waits in a database
queue. Spawned workers own their connections and transactions; killed SQLite
writers recover through SQLite's journal, not an application retry. Capacity is
held until the worker is reaped. On pathological uninterruptible kernel I/O,
reaping cannot be guaranteed by user-space code: shutdown fails explicitly and
retains accounting instead of falsely reporting a drained worker.

`GET /healthz` and `/v1/health/live` always bypass database/session/rate checks and
never create or refresh cookies. `/v1/health/ready` is a read-only, bounded query
of the existing schema: no session, DDL, retention cleanup or fallback. Startup
attempts bounded schema initialization but still serves liveness if it fails.
A new inaccessible/uninitialized database remains unready until initialization
succeeds through a normal history/session request. `/v1/validation` is also
storage-independent; `/v1/status` retains its existing session-bootstrap behavior.

Storage failures return **503**, `Cache-Control: no-store`, `X-Correlation-ID`,
and `{error, code, correlation_id}`. Codes are `STORAGE_UNAVAILABLE`,
`STORAGE_OVERLOADED` (both slots occupied), or `STORAGE_OUTCOME_UNCERTAIN`.
Availability failures do not imply an absent owner: never replace, clear,
refresh or create an owner cookie on a storage-error response. The original
cookie continues to authorize the original records after recovery.

A write interrupted while running, a worker lost before returning its result,
or a commit error can have an **uncertain outcome**: the mutation may already be
durable. Do not describe it as rolled back or blindly replay it. Check history
after recovery and reconcile manually. There are no automatic mutation retries,
idempotency guarantees, storage failovers or fallback sessions.

Read/health failures include `Retry-After: 2`; wait at least two seconds, add
jitter and bounded exponential backoff. Never apply this guidance to a mutation
or an uncertain session-creation outcome. Mutation failures omit Retry-After.
The server coalesces readiness by rejecting concurrent probes and cooling down
failed probes; it does not start a new query for every failing health request.
