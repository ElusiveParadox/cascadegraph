# CascadeGraph

An evidence-backed, pre-deployment retry-policy analyzer for backend and platform
engineers. Safely inspect a public GitHub URL, supported source files, bundled sample or bounded repository ZIP, review
source-backed policies and call edges, then run deterministic what-if simulations.

## Working scope
- Public GitHub URLs with pinned-commit provenance, ZIPs up to 50 MiB, and
  supported individual source/configuration files with missing-file guidance.
- Compose service definitions and explicit `cascadegraph.yaml` call topology.
- Evidence-labelled supported environment/client references; startup ordering is
  never treated as proof of request traffic.
- Python AST extraction for supported Tenacity and urllib3/requests patterns.
- Istio retry/timeout extraction, with unknown proxy backoff kept unresolved.
- Optional real AI extraction of the bundled custom loop, with schema and local
  source checks. Disabled by default per analysis; no mock fallback in production.
- Seeded discrete-event simulation of retries, backoff, jitter, timeouts,
  deadlines, worker concurrency, FIFO queues and controlled leaf failures.
- Policy correction, baseline/candidate comparison, session history, deletion,
  source evidence inspection and JSON report export.
- A real three-service Compose experiment and least-privilege GitHub Actions.

## Run in Replit
Use the managed workflows:
`artifacts/cascadegraph: web` and `artifacts/api-server: API Server`.
They provide ports/routing. The Python API lives under `/api`; React under `/`.
The unused Express and PostgreSQL scaffolds are not the runtime backend.

Restore dependencies with `pnpm install --frozen-lockfile` and `uv sync --frozen`.
Python 3.13 and Node 24 are used. Do not install uploaded project dependencies.

## Verify
```sh
uv run --frozen pytest -q
uv run --frozen ruff check src tests
pnpm --filter @workspace/api-spec run codegen
pnpm run typecheck
pnpm --filter @workspace/cascadegraph test
```
Generated API helpers come from the workspace OpenAPI specification. Production
builds receive `PORT` and `BASE_PATH` from the managed artifact workflow.

## Real validation
Run **Real Compose validation** in GitHub Actions. It starts three actual services,
injects faults, collects independent HTTP counters, runs equivalent simulation
scenarios, compares counts and uploads JSON results. See
[the protocol](docs/VALIDATION_PROTOCOL.md). A workflow definition alone is not
proof of a successful run; actual evidence is recorded in PROGRESS.md.

## Security and limitations
No uploaded or downloaded source is executed. Public imports use fixed GitHub
hosts, reject redirects/non-public destinations, and never use the creator's
connected account. No Docker socket or privileged workload is used
in the Replit application. AI transmission is opt-in and redacted heuristically,
not guaranteed secret-free. No arbitrary-host URL ingestion or private multi-user
mode. Private repositories require an archive or source-file upload.

SQLite is ephemeral demo storage with anonymous cookie ownership and 24-hour
retention, not durable production storage. Export important reports. Model output
is a prediction under explicit assumptions, never a production safety guarantee.
See [security](SECURITY.md), [threat model](docs/THREAT_MODEL.md), and
[limitations](docs/KNOWN_LIMITATIONS.md).
