# Progress

## Password recovery verification — 2026-11-11
- Verified the existing Clerk widget with an isolated reserved development test
  identity: recovery/back navigation, real invalid-code rejection, real password
  change, authenticated history GET and signed-in identity after reload.
- Expired-code presentation used a single targeted provider-response fixture,
  not a real expired challenge. Refreshing the recovery subroute returns to the
  password step; recovery can be restarted.
- Added five authentication regressions for transient proxy credential handling
  (success/invalid/expired/transport), unchanged isolated database contents and
  original-account history access with a replacement signed session. Strengthened
  the existing rejected-password-field test with INFO logs and a database dump.
- Targeted SDK-only browser evidence found one password-bearing request during
  Clerk reset, no password-bearing application API requests, and no canary in
  response/error/console/browser storage. Request destination was not independently
  classified; report does not claim stronger evidence.
- The first disposable test password appeared in an automatic browser accessibility
  snapshot, not app logs; a subsequent SDK-only reset replaced it. The test
  identity remains signed out in development because self-delete required
  additional verification. No user credentials or real recipients were used.
- Passed `uv run --frozen pytest` (125), `uv run --frozen ruff check src tests`,
  `pnpm run typecheck` and frontend unit checks. Managed services started cleanly;
  sign-in screenshot rendered. See `docs/PASSWORD_RECOVERY_VERIFICATION.md`.
- No second password store, application authentication changes, provider setting
  changes or production publication. Production configuration, actual expiration
  and real email delivery remain separate unverified gates.

## Explicit GitHub entry point and password review — 2026-11-11
- Added a visible Continue with GitHub control on both sign-in and sign-up,
  wired to real Clerk SDK SSO with loading, retry/error feedback and an
  artifact-relative OAuth callback. Avoided duplicate prebuilt GitHub controls.
- Browser follow-up confirmed exactly one GitHub control, Google/email
  availability, keyboard access and mobile fit. The real provider request
  returned 422 because GitHub is still absent from its enabled strategies;
  the page now says so clearly and leaves other login methods usable. No
  successful GitHub consent/login is claimed.
- Reviewed application schema, credential routes and logging. CascadeGraph
  stores neither passwords nor password hashes and has no plaintext password
  comparison. Clerk's published password design describes bcrypt hashing;
  its internal database was not independently inspected. Production proxy
  credential bytes are transient, not persisted/logged.
- A non-secret password canary regression verifies unsupported password/hash
  inputs are rejected without value echo, logging or analysis creation.
  Seven auth regressions, 26 frontend helper tests, type checking, Ruff and
  production frontend build passed.
- Dependency/privacy scanners reported no findings. Static scanning flagged
  request-derived proxy paths as potential SSRF. Hardened construction to
  copy path/query into a fixed HTTPS origin with an explicit host/port allowlist;
  added adversarial URL regression checks, all passing. The static warning
  remains reported and reviewed in SECURITY.md, not suppressed.

## Sidebar authentication — 2026-11-11
- Added Replit-managed Clerk SignIn/SignUp with the existing Poppins/red theme,
  branded mark, OAuth callback routes and a public guest workbench.
- Replaced sidebar API/model/AI diagnostics with Sign in or name/email and
  Sign out. Mobile keyboard focus includes the account button.
- Added cookie-verified account ownership on the Python API with bounded async
  signing-key retrieval. Stable account owners are separate from unforgeable
  guest ownership; no automatic guest transfer or schema changes.
- Added same-origin cookie cleanup before SDK sign-out, identity-scoped query
  caches and selection reset. Kept all records' existing 24-hour expiry.
- Verification: 119 Python tests passed; Ruff, workspace type checks, 23 frontend
  helper tests and frontend production build passed; dependency audit found no
  known vulnerabilities. A targeted production-proxy regression also passed
  after adding admission and total-duration limits.
- A real programmatic Clerk browser journey verified signed-in footer, sample
  graph, reload persistence, sign-out/404 isolation, same-account history
  recovery, deletion and mobile keyboard sign-out. OAuth provider consent and
  real email delivery were not exercised.
- Google and email were visible. The user reported enabling GitHub; a fresh
  sign-in capture still showed no GitHub button, so environment/provider
  configuration needs confirmation. No fake provider button was added.
- Follow-up: the user confirmed GitHub was enabled in both environments.
  Verified canonical frontend wiring, checked current allowed SDK versions,
  and restarted both services. A fresh browser response from Clerk returned
  HTTP 200 with `Cache-Control: no-store` and only `oauth_google` in its live
  social configuration; `oauth_github` was absent. The remaining mismatch is
  not a hidden UI button or a browser cache. Provider-panel evidence is needed
  to check save/validation state or a managed-instance mismatch.

## Repeated source-path conflict resolution — 2026-11-11
- Source picks and folder discovery stage conflicting batches before changing
  the selection. Explicit Keep existing, Replace and Cancel choices retain edited
  paths, unaffected files and manual Analyze submission.
- Conflict identity uses the trimmed repository-relative path sent to the API.
  Discovery remains bounded independently; final count and byte limits apply
  atomically to the resolved selection, allowing replacement at capacity.
- Five focused unit checks cover single-file decisions, edited paths, nested
  folder reselection, conflicts between dropped roots and resolved byte limits.
  Frontend unit suite passed (23 tests plus workspace helper checks).
- Desktop and phone single-file browser checks passed. The initial nested-folder
  checks reached submission but Chromium did not expose disk-backed request
  bodies to Playwright. Test-only FormData capture and independent incoming disk
  fixtures fixed that limitation; the narrow nested-folder rerun passed on both
  viewports, including content/path assertions and atomic overflow rejection.
- Passed workspace type checks, a separate browser-spec TypeScript check,
  `uv run --frozen ruff check src tests`, and `uv run --frozen pytest` (112 passed).
  Managed web/API workflows started cleanly; overview screenshot rendered without
  browser errors. No production publication.

## Repository folder intake — 2026-11-11
- Added an optional native directory picker and directory drops alongside the
  unchanged individual-file picker. The selected root name is removed, nested
  paths are retained, and the optional project prefix is applied consistently.
- Sequential browser directory reads stop at advertised entry/source-count,
  per-source and total-byte limits, including the existing selection. Failed
  batches leave previous files untouched; discovery never submits an analysis.
- Unsupported, ignored and unreadable entries are reported with bounded details.
  Ignored directories are not traversed; recursion has a depth guard.
- Passed `pnpm run typecheck`, frontend helper checks (18 tests plus workspace
  helpers), `uv run --frozen pytest` (112 tests), and
  `uv run --frozen ruff check src tests`. Folder checks cover nested/batched
  discovery, mixed roots, ignored/unreadable entries, oversized trees and exact
  byte/count boundaries. No interactive browser journey is claimed.
- Production frontend build passed with the required temporary `PORT` and
  `BASE_PATH` values (existing source-map/chunk-size warnings only). Managed
  web/API workflows started cleanly; overview screenshot showed both native
  pickers and explicit Analyze control, with no browser errors.

## PostgreSQL migration and usability verification — 2026-11-10
- Replaced live SQLite process calls with a lifecycle-owned bounded async
  PostgreSQL pool. Preserved owner checks, cookies, retention, quotas,
  simulation snapshots and cascading deletion; no automatic mutation retries.
- Applied the development schema and copied 131 live browser sessions. There
  were no unexpired analyses/simulations to copy. Original SQLite remains
  untouched and ignored by Git. Preview status/readiness report PostgreSQL.
- Added real PostgreSQL integration coverage and an ephemeral PostgreSQL
  service for GitHub Python/browser checks. Schema setup is explicit/development
  only; production schema belongs to Replit Publish.
- Fixed local SQLite interpreter overhead using a clean forkserver where
  available; existing outage/shutdown/ownership checks pass without relaxed
  timeouts or disabled assertions.
- Executed 110 Python tests, Ruff, workspace TypeScript, frontend helper/retry/
  file-intake tests and production frontend build successfully. JavaScript
  audit has no known vulnerabilities; static/privacy scans report no findings.
- Added two further PostgreSQL cancellation/ambiguous-commit regressions; all
  eight PostgreSQL integration tests passed. A real desktop/mobile browser
  journey passed sample analysis, correction/reload, simulation (baseline 8x,
  candidate 2x), actual report download, history and cancel/confirm deletion.
  It observed no 503 responses.
- The first GitHub run passed Python/security and the real Compose experiment,
  but caught clipped keyboard focus on the history delete action in the wide
  desktop layout. Added focused-control scrolling inside the table scroller;
  all three targeted desktop/compact/zoom-reflow regressions pass locally.
- GitHub PR: https://github.com/ElusiveParadox/cascadegraph/pull/3 .
  Required checks and merge status remain authoritative remotely; no production
  publication or external developer feedback is claimed.

## Compact navigation keyboard containment — 2026-11-10
- Added expanded/control announcements, focus entry and a bidirectional loop over
  the compact toggle and enabled navigation links. Covered intake and skip-link
  content is inert while navigation is open.
- Escape, the toggle and link activation close navigation and restore toggle
  focus. Switching to the persistent desktop sidebar removes the focus trap
  without trying to focus its now-hidden toggle.
- Extended the existing desktop-layout suite: **10 passed**, including explicit
  state, visible focus, disabled-link skipping, forward/reverse wrap, Escape,
  reopen, same-route and changed-route dismissal, and desktop resize assertions.
  Zoom coverage is reduced-CSS-viewport/double-density reflow emulation, not
  native browser-UI zoom. Fixtures remain presentation-only; no ownership,
  analysis or intake behavior changes.
- Passed `pnpm run typecheck`, frontend unit checks,
  `uv run --frozen ruff check src tests`, `uv run --frozen pytest` (**104 passed**)
  and `git diff --check`. Browser command:
  `E2E_API_PORT=28080 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/repl/tools/bin/chromium
  pnpm --filter @workspace/cascadegraph test:e2e --project=desktop-layout`.

## Repository file drag-and-drop — 2026-11-10
- Added file drop feedback to the existing ZIP and direct-source panels while
  retaining native keyboard file pickers. Selecting or dropping never submits;
  existing analysis payloads, public-snapshot supplementation, path editing and
  unchecked AI opt-in are unchanged.
- Rejected batches leave previous selections and edited paths intact. Extension,
  archive count, per-source size, cumulative source count and total source size
  checks use advertised server limits; absent optional source limits fail
  explicitly instead of guessing. Selected file/count/size summaries, ZIP removal
  and immediate validation errors are visible.
- Eight focused desktop/phone browser checks passed for drag feedback, rejection,
  size/count limits, keyboard pickers, retained selections and source payloads.
  Three new unit tests cover exact byte/count boundaries and changed server
  limits; all frontend unit checks pass.
- Passed workspace typechecking, frontend build, Python tests (104 passed),
  Python lint and whitespace checks. Build retains existing UI component
  sourcemap warnings. Managed web/API workflows started cleanly.

## Real-server storage shutdown regression — 2026-11-10
- Added separate Linux integration coverage through the production Uvicorn entry
  point, with an OS-selected loopback port and a per-test temporary SQLite file.
  Test-only, spawn-safe faults block immediately before or after a real commit.
- Verified real HTTP uncertain-write responses, caller disconnect while a known
  database child is blocked, and real SIGTERM to only the isolated server process.
  Asserted the one-second storage shutdown budget separately from HTTP draining,
  clean lifespan completion, and no surviving process-group members or DB child.
- Restarted against the same temporary database and recovered original records
  with the original cookie. Exact history reconciles committed/uncommitted writes;
  invocation counts rule out transparent replay, and foreign owners remain denied.
- Executed `uv run --frozen pytest -q`: **104 passed**.
  `uv run --frozen ruff check src tests`, `pnpm run typecheck`,
  `pnpm --filter @workspace/cascadegraph test`, and `git diff --check` passed.
  No production code, managed preview process or shared database was changed.

## Product theme and desktop layout — 2026-11-10
- Applied the requested five-color palette, Poppins interface typography and a
  restrained Georgia accent through the shared theme, navigation and panels.
- Placed repository intake beside sample/ZIP options on wide desktop screens;
  retained stacked layouts on smaller screens, all existing forms and notices.
- Added visible keyboard focus, active-page navigation semantics, skip-to-content,
  reduced-motion support and unrestricted viewport zoom.
- Workspace TypeScript, frontend helper/retry tests and the frontend production
  build passed. Verified 1440px desktop and 390px mobile overview screenshots;
  no application errors appeared in those captures. The build reports existing
  non-blocking sourcemap warnings in shared tooltip/select components.

## Imported preview startup repair — 2026-11-10
- Startup logs showed `vite: not found` because JavaScript dependencies were
  absent. Restored them using the unchanged frozen pnpm lockfile and restarted
  the existing CascadeGraph and component-preview workflows.
- Verified all three managed workflows running, proxied API health/readiness
  responses successful, and the CascadeGraph overview screenshot rendering
  without browser errors.
- Workspace TypeScript, frontend helper tests, all 86 Python tests and Ruff
  passed. Optional AI remains unconfigured in this imported environment;
  local analysis does not require it.
- Corrected imported runtime modules from Node 20/Python 3.12 to Node 24/Python
  3.13. Reinstalled frozen JavaScript dependencies with `--force`, recreated
  Python dependencies with `uv sync --frozen --python 3.13`, and repeated the
  checks successfully on Node 24.22.1/Python 3.13.11. All three workflows
  restarted successfully; proxied readiness and the overview screenshot passed.

## 2026-11-10 — Foundation and repository inspection
- Reviewed both supplied requirements documents and the merged workspace setup.
- Verified the platform GitHub CLI proxy account and target repository permissions;
  the target has no branches yet. No remote push or PR has occurred.
- Preserved Python 3.13, managed artifact workflows, platform remotes, and dormant
  database scaffold. Created an implementation feature branch.
- Provisioned Replit AI Integrations for optional OpenAI-compatible extraction.
- Initial readiness checks were superseded by the implementation evidence below.

## Implemented and verified — 2026-11-10
- Completed safe sample/ZIP ingestion, supported AST/YAML parsers, evidence-backed
  graph, policy/edge review, session-owned SQLite history/deletion and immutable
  simulation/report snapshots.
- Implemented a seeded discrete-event engine with capacity/queues, nested retries,
  eligibility/category limits, timeouts/deadlines, fixed/exponential waits, jitter
  and controlled independent/correlated faults.
- Built the complete React multi-page workbench against generated API hooks.
- Verified one actual provisioned-provider custom-loop extraction: three attempts,
  source-checked exponential base delay and exception behavior. Automated tests
  use only deterministic mocks; per-analysis AI is opt-in and credit-billed.
- Local Python: **52 tests passed** (including corrected-finding/snapshot regression); Ruff passed. Workspace TypeScript and frontend
  helper tests passed. GitHub also verified codegen drift and production build.
- Real first experiment passed at commit
  `214dc52ae08ca11e9e032815555179a44e51791d`:
  https://github.com/ElusiveParadox/cascadegraph/actions/runs/42805345828 .
  Six scenarios / ten logical requests each. Predicted and measured downstream
  amplification: 2.0, 2.0, 2.2, 12.0, 2.0, 12.0 respectively; success counts also
  matched. This is count-focused low-load calibration, not production accuracy.
- A subsequent real run adds workload-budget deadline comparisons and derived
  outgoing/retry counts; its reviewed artifact is bundled under `validation/`.
- The final JavaScript audit reports zero advisories of every severity. Static scan and
  privacy scan passed. SafeLoader restrictions, ZIP traversal/alias/bomb defenses,
  ownership tests, origin checks, retention and bounded workloads are implemented.
- Feature PR: https://github.com/ElusiveParadox/cascadegraph/pull/1 .
  Required checks and protected merge status are authoritative on GitHub; no merge
  commit is fabricated in advance. Public history excludes uploaded screenshots
  and platform migration backups.
- Browser CI includes desktop/phone Playwright checks. Final verdicts are recorded
  by the required workflow, not inferred from a workflow definition.

## Final implementation gate
- **52 Python tests** and both **desktop/phone Playwright journeys** passed.
  Browser CI also checks actual downloaded report JSON, preserved source facts,
  current findings after correction, mobile overflow and cancel/confirm deletion.
- The stale-finding bug and mobile intrinsic-width overflow found during testing
  were fixed and regression-covered. No browser failure was waived.
- All nine required checks passed. The protected PR was squash-merged as
  `0b326d6e193311c1c5678be7e748bfca7edac5f7`; no admin bypass or force push.
- Final feature-commit quality run:
  https://github.com/ElusiveParadox/cascadegraph/actions/runs/42807661059 .
  Final feature-commit real experiment:
  https://github.com/ElusiveParadox/cascadegraph/actions/runs/42807654826 .
- Preview workflows restarted cleanly, readiness returned 200, and desktop/home
  plus phone/validation screenshots rendered without application errors.

## Release gates not yet claimed
- Replit **Preview** runs; production **Publish** requires the user's approval.
- No production URL, durable private-team storage or real developer feedback is
  claimed. Three to five actual developer participants still need to be recruited.
- See KNOWN_LIMITATIONS and VALIDATION_PROTOCOL for model and measurement limits.

## Public repository and source-file intake — 2026-11-10
- Increased ZIP/download cap to 50 MiB, archive expansion to 200 MiB and entries
  to 2,000. Supported source is bounded at 20 MiB / 512 KiB per file; direct
  uploads at 100 files. Admission happens before large-body buffering.
- Added strict public GitHub URL ingestion, optional ref/project folder, immutable
  commit provenance, and labelled source-file supplements. No arbitrary hosts,
  redirects, creator credentials, raw-source persistence or code execution.
- Added explicit missing-file guidance and resubmission; corrected Compose
  build-context resolution relative to nested Compose files.
- 86 Python tests, Ruff, frontend types and helper tests pass. A real URL-only
  browser import produced the three-service/two-edge graph, persisted its exact
  commit after reload, exported matching report provenance and deleted cleanly.
  Policies/edges still require explicit human confirmation; ingestion is not
  a claim of verified production safety.
- Static security and privacy scans report no findings. Feature evidence:
  https://github.com/ElusiveParadox/cascadegraph/pull/2
- Protected CI requires Python checks, frontend types/helpers/build plus four
  desktop/phone browser journeys, JavaScript audit, unsafe-execution guard and
  real six-scenario Compose validation. The source journey deliberately delays
  initial history loading to check ownership readiness. Delete-dialog content
  has explicit precedence over its overlay; no forced-click test bypass is used.

## Bounded storage outage execution — 2026-11-10
- Audited the execution checkout: SQLite only, no storage-connection/vault modules
  or prior uncertain-write contract. Kept the backend and existing retention mode.
- All HTTP database calls now share immediate two-process admission with no queue,
  100 ms SQLite lock waits, 400 ms transaction/VM limits and 800 ms whole-operation
  deadlines. Running workers remain accounted for until reaped; cancellation and
  one-second shutdown terminate work instead of abandoning threads.
- Session resolution, quotas and simulation-parent ownership checks are atomic.
  Storage failures never alter owner cookies or select fallback storage.
  Ambiguous writes return explicit uncertain outcomes and are not retried.
- Liveness bypasses storage, session creation and rate state. Readiness is
  non-mutating, bounded, one-at-a-time and failure-cooled-down. API/ADR/threat-model
  documentation includes exact budgets, OS termination limits and retry guidance;
  curated OpenAPI and generated clients include health/error contracts.
- Executed `uv run --frozen pytest`: **102 passed**, including **16 isolated
  storage regressions** covering stalled acquisition/connect/query/commit,
  event-loop heartbeat, HTTP saturation/liveness, pre-start/repeated cancellation,
  shutdown/drained workers, actual SQLite locks/VM interruption, read-only probes,
  cookie continuity/recovery, uncertain committed writes and concurrent quotas.
- Executed `uv run --frozen ruff check src tests`, API code generation,
  `pnpm run typecheck`, `pnpm --filter @workspace/cascadegraph test`, and
  `git diff --check`: all passed.
- Restarted the managed API workflow: clean startup. Proxied liveness/readiness
  returned 200 with no-store/correlation headers and no Set-Cookie. App screenshot
  rendered the existing overview without browser errors. No production publication
  or external browser-journey test is claimed.

## Frontend storage-outage retries — 2026-11-10
- Query defaults honor ApiError Retry-After seconds/dates as a minimum, use
  bounded exponential delay with positive jitter, and limit temporary storage
  errors to three retries. Delays cap at 30 seconds; longer server hints stop
  automatic retries instead of shortening the server's requested wait.
- Uncertain storage outcomes never retry, including session-bootstrap GETs.
  Mutation retries are explicitly disabled. Other errors retain the existing
  one-retry limit and 404 exclusion. No storage backend changes.
- Seven focused frontend tests cover timing/header parsing, caps, retry counts,
  actual generated history/status requests, uncertain sessions, and mutations;
  all pass alongside existing workspace helper tests.
- Executed `pnpm run typecheck`, `uv run --frozen pytest` (104 passed),
  `uv run --frozen ruff check src tests`, and `git diff --check`: passed.
- Managed web workflow restarted cleanly and overview rendered. Preview observed
  a temporary storage-overload 503; a subsequent proxied status request returned
  200. No production publication or external browser-journey test is claimed.

## Desktop layout and keyboard regressions — 2026-11-10
- Added nine deterministic Playwright regressions at 1600×1000, 1024×768 and
  720×450 CSS pixels with double density (200% layout-zoom emulation of a
  1440×900 desktop, not native browser-UI zoom or pinch magnification).
- Browser assertions cover computed theme colors/font families, intake panel
  geometry, long uploaded filenames/editable relative paths, skip-link order and
  destination, visible keyboard outlines and viewport bounds, disabled navigation,
  unique current-page semantics after navigation, and local history/evidence
  overflow with keyboard access to the final history column.
- The zoom test exposed focused navigation below the fixed menu's visible bounds;
  made the navigation surface vertically scrollable. No analysis ownership or
  workflow test changes; new presentation fixtures never write server data.
- Full browser suite: **13 passed**, including all four existing desktop/phone
  source intake and inspect/correct/simulate/export/delete journeys. Ran with
  `E2E_API_PORT=28080 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/repl/tools/bin/chromium
  pnpm --filter @workspace/cascadegraph test:e2e`; defaults remain unchanged for CI.
- Passed `pnpm run typecheck`, frontend unit checks, a separate TypeScript check
  for the new browser tests/config, `uv run --frozen ruff check src tests`,
  `uv run --frozen pytest` (**104 passed**) and `git diff --check`.
- Managed web/API services started cleanly; overview screenshot rendered without
  browser errors. No production publication.
