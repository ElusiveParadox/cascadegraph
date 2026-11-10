# Progress

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
