# Engineering decisions

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
