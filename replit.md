# CascadeGraph

Evidence-backed retry-policy analyzer and deterministic simulator. Read AGENTS.md
for engineering rules and PROGRESS.md for executed verification and release gates.

## Scope and architecture

- Keep Python 3.13 and the planned FastAPI/Pydantic computational backend.
- React/Vite is the web frontend, not a replacement for the Python engine.
- PostgreSQL is now the live store, explicitly requested by the user. The
  pre-existing TypeScript `lib/db` scaffold remains dormant; Python owns storage.
  Development schema is `schema/postgresql.sql`; production schema uses Publish.
- There was no legacy app or UI to migrate. Do not claim visual parity.
- Preserve `.migration-backup/attached_assets/`, task plans, and Git history/remotes.

## Run

Use the managed workflows (they supply service ports and routing):

- `artifacts/cascadegraph: web` — React workbench at `/`.
- `artifacts/api-server: API Server` — Python service at `/api`.

The API workflow uses `uv run --frozen python -m cascadegraph_runtime` and
requires `PORT`. Health is `/api/healthz`; analysis/simulation APIs are `/api/v1`.
The retained Express files are unused template files, not the active backend.
PostgreSQL uses the runtime-managed `DATABASE_URL` with a bounded async pool.
An explicit `CASCADEGRAPH_DB_PATH` selects isolated local/test SQLite, never
an automatic fallback after a PostgreSQL failure. AI is optional, provisioned through
Replit AI Integrations and unchecked by default. Do not expose credentials.

## Layout and setup

- `artifacts/cascadegraph/` — web artifact for the approved implementation.
- `src/cascadegraph_runtime/` — FastAPI, safe parsers, AI, simulation and storage.
- `pyproject.toml`, `uv.lock` — reproducible Python dependencies.
- `.migration-backup/attached_assets/` — original architecture, execution prompt,
  and screenshot (unchanged).
- `scripts/post-merge.sh` — restores dependencies and applies development schema.

Install JavaScript dependencies with `pnpm install --frozen-lockfile`; Python
dependencies use the platform package tool and `uv sync --frozen` for restoration.
The package tool manages `.pythonlibs`; do not create a separate virtualenv.

If an imported frontend fails with `vite: not found` or `node_modules missing`,
restore JavaScript dependencies using the command above, then restart the
existing managed frontend workflow. Do not replace the workflow or upgrade
packages to resolve a missing installation.

## Verification record

See PROGRESS.md, docs/VALIDATION_PROTOCOL.md and GitHub required checks. Actual
Compose experiments run on GitHub, never in Replit. Do not push platform history:
it contains uploaded account screenshots. Use the filtered export described in
docs/GITHUB_WORKFLOW.md. Production publication and real developer feedback remain
explicit user-dependent gates; Preview is not a published deployment.
