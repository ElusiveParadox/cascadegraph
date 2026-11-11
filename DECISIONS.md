# Engineering decisions

## ADR-012 — Managed accounts and separate guest ownership

The user requested Google, GitHub and email sign-in and a sidebar Sign out
control. Replit-managed Clerk handles credentials, recovery, social OAuth and
cookie sessions; provider enablement belongs to the Auth pane.
The existing Python API remains the active server. Its production Frontend API
proxy implements the canonical managed Clerk proxy headers and byte-preserving,
length-delimited responses rather than introducing a second Express server.

The API validates session cookies against app-specific verification keys using
bounded async key retrieval, RS256 signatures and an authorized-origin check.
Client bearer/identity headers are not accepted. Verification failures never
silently downgrade into guest ownership.

JWKS retrieval has a three-second whole-operation deadline in addition to
HTTPX's I/O timeouts, so a trickling response cannot keep verification pending.
One-second lock admission and a two-second failure cooldown also apply to
already-queued callers. Cancellation propagates and releases only acquired
admission; cached, still-valid keys remain usable during a refresh failure.
The managed proxy retains eight slots, one-second admission, a 30-second total
deadline and a 20 MiB response cap, without replaying credential-bearing requests.

Verified account subjects map to a separate stable owner namespace, allowing
the same account to retrieve unexpired history from another browser. Anonymous
cookies cannot select that namespace. Existing session tables support this
without schema changes. All analysis/simulation/report lookups still check
ownership, with the existing 24-hour expiry. This is not team sharing or RBAC.

Guest work stays public and separate; signing in never implicitly claims or
transfers guest records. The auth screen tells users to export guest reports.
Sign-out clears the guest cookie, ends Clerk's session, resets selection and
uses identity-scoped query caches. It never deletes saved records.
Development and production Clerk users remain separate.

## ADR-011 — PostgreSQL live storage (2026-11-10)
Accepted at the user's explicit request. The current two-process SQLite executor
rejects concurrent browser reads and spawns a new interpreter for every operation.
Use the existing managed PostgreSQL database through a lifecycle-owned async
psycopg pool instead. Alternatives were increasing SQLite worker limits (retains
filesystem durability and process overhead issues) or moving the backend to
TypeScript (unnecessary disruption); both were rejected.

Bound the pool, acquisition wait, database statements and lock waits. Never
automatically retry writes; a failed commit response remains an uncertain outcome.
Retain anonymous owners, cookie scope, 24-hour retention, quotas, cascading
deletion, normalized JSON snapshots and original simulation provenance.
PostgreSQL changes persistence, not authentication or model accuracy.

An explicit SQLite file remains available for isolated local/tests only. Once
PostgreSQL is selected, an outage must not fall back to SQLite or invent an owner.
Apply schema to development explicitly/from post-merge; Replit Publish owns the
production schema diff. No API startup or production build DDL is allowed.
Copy unexpired local data transactionally with unchanged session tokens and IDs;
leave the source file untouched and reject conflicts rather than overwrite.
Local SQLite uses a clean forkserver where supported (spawn otherwise), avoiding
per-operation interpreter startup overrunning existing fault-test budgets.
Neither mode inherits application pool connections.

## ADR-001 — Python computational core (2026-11-10)
Accepted. FastAPI/Pydantic and Python AST/safe YAML implement the analysis engine;
React/Vite renders it through the shared path proxy. This preserves the requested
architecture and avoids a second authoritative TypeScript simulation.

## ADR-002 — Independent product and validation planes (2026-11-10)
Accepted. The web server never executes uploaded code. Only the repository-owned
three-service sample runs on an ephemeral GitHub Actions Linux runner. Measured
artifacts retain commit, scenario and workflow provenance, not simulated substitutes.

## ADR-003 — Bounded synchronous analysis and demo persistence (2026-11-10)
Accepted for the MVP. Small inputs run synchronously with hard limits, avoiding
false durable-background-job claims. SQLite stores normalized results, never raw
archives. Anonymous sessions own analyses; random record IDs alone are not auth.
Production persistence requires a separately verified durable store. If no
durable store is configured, show the ephemeral demo limitation explicitly.

## ADR-004 — Contract-first Python adapter (2026-11-10)
Accepted. The workspace OpenAPI contract generates React hooks and Zod types.
The Python server validates equivalent Pydantic inputs, tested against the
contract. The unused Express/database scaffolds stay dormant.

## ADR-005 — Evidence and provider failure (2026-11-10)
Accepted. Explicit topology declarations may bind policies but remain declared,
not observed. Custom-loop AI extraction is bounded to the sample pattern,
opt-in for source transmission, and validated against AST/source spans.
Provider failure leaves the result unresolved, never silently replaced by a
mock. Tests use an explicit deterministic mock.

## ADR-006 — GitHub credential route (2026-11-10)
Verified: connector credentials are unavailable through the connection sandbox,
but the platform-configured GitHub CLI proxy authenticates as the intended
repository owner with admin/push permission. Use that existing secure route;
do not request another token or repeat OAuth.

## ADR-007 — Clean public Git history (2026-11-10)
Accepted. The platform checkpoint history contains an uploaded wrong-account
screenshot and migration backups. Do not push that history into the public
repository. A separate clone receives an allow-filtered current source snapshot,
then feature commits/PRs against its real remote main. This preserves both
platform history and repository privacy without rewriting either main branch.
The helper excludes uploads, backups, local context, images, data and credentials.

## ADR-008 — Patched schema/codegen dependencies (2026-11-10)
Accepted. Upgrade the inherited Orval/Express packages and move the shared Zod
catalog to its patched 4.x release with matching generation syntax. The generated
code is the only authoritative TS validation layer; Python remains the actual
API runtime. This addresses inherited high-severity advisories rather than
introducing a new validation library.

## ADR-009 — Public repository URLs and source fallback (2026-11-10)
Accepted. Add read-only public GitHub snapshot import and direct source uploads.
Alternatives were using the creator's connected OAuth credentials, cloning and
running repositories, or accepting arbitrary download URLs; all are rejected.
Public app users must not inherit access to the creator's private repositories.
Construct fixed GitHub API/codeload URLs, resolve an immutable commit using the
SHA media type, prohibit redirects/non-public destinations, and bound all reads.
Retain only normalized results, minimal redacted evidence and provenance—not raw
source. Missing/ambiguous files produce explicit requests; supplementation creates
a new analysis and identifies user-overridden paths separately from GitHub source.
Private OAuth access remains a later, per-user authorization feature.

## ADR-010 — Larger archives without unbounded source parsing (2026-11-10)
Accepted in response to the user's request for larger uploads. Raise compressed
ZIP/download size from 5 to 50 MiB, declared expansion to 200 MiB, entry count to
2,000 and supported per-file size to 512 KiB. Retained supported source remains
bounded at 20 MiB; direct uploads at 100 files. Large ignored/binary assets are
skipped before per-source checks but still count toward declared archive limits.
Acquire two-slot admission before buffering, bound waiting and upload reads, and
keep small JSON routes at 64 KiB. This trades general large-repository coverage
for predictable demo resource use; large/private applications can supply a subset.

## ADR-011 — Hard-bounded SQLite execution and uncertain writes (2026-11-10)
Accepted. The actual checkout has SQLite, not the newer storage/credential
modules mentioned in an external plan. Preserve that backend; do not create a
vault, async pool, migration, fallback store or background-job system.

Use at most two spawned, dedicated storage processes and zero queued jobs.
Unlike a thread executor, a process can be terminated if filesystem acquisition,
connect or commit ignores a SQLite VM interrupt. All HTTP storage callers share
this admission, including middleware and async analysis saves; unrelated health
and validation requests never enter it. Per-call process creation has overhead,
accepted for this small demo in exchange for explicit ownership and cancellation.

Budgets: immediate overload rejection; SQLite busy timeout 100 ms, transaction
400 ms (100-instruction progress checks plus pre-commit check); whole operation
800 ms including spawn/connect/commit; TERM/reap 200 ms then KILL/reap 200 ms;
shutdown 1 second. Admission stays occupied until the worker actually exits.
No queued mutation can start after cancellation because there is no queue.
Connections close on normal errors; killed processes release handles and SQLite
journaling handles rollback/recovery. No transparent mutation retries.
Uninterruptible kernel I/O is an OS boundary: report failed shutdown explicitly,
never release accounting and pretend the worker stopped.

BEGIN IMMEDIATE serializes ownership/quota checks and writes, including session
creation and simulation-parent checks. Existing opportunistic retention remains
inside normal transactions; there is no new retention scheduler. Readiness is
read-only, one probe at a time with a 500 ms failure cooldown. Liveness bypasses
sessions, storage and client rate limits. Startup initialization is bounded and
nonfatal so a storage outage cannot suppress liveness.

503 errors have safe codes, correlation IDs and no-store headers, with no cookie
changes. A deadline/lost worker/commit exception may follow a committed mutation:
report STORAGE_OUTCOME_UNCERTAIN and require history reconciliation, not replay.
Read/health retries wait at least 2 seconds with jitter and bounded exponential
backoff; mutation responses never include retry guidance. Tests use temporary
SQLite files and spawn-local fault injection, never a shared database outage.
