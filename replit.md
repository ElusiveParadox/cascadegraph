# CascadeGraph

Greenfield computational application. This workspace preparation does not
implement product features; continue the existing approved build task rather
than creating a duplicate.

## Scope and architecture

- Keep Python 3.13 and the planned FastAPI/Pydantic computational backend.
- React/Vite is the web frontend, not a replacement for the Python engine.
- No PostgreSQL requirement has been established. The pre-existing `lib/db`
  scaffold is dormant: do not push schemas or require `DATABASE_URL` for setup.
- There was no legacy app or UI to migrate. Do not claim visual parity.
- Preserve `.migration-backup/attached_assets/`, task plans, and Git history/remotes.

## Run

Use the managed workflows (they supply service ports and routing):

- `artifacts/cascadegraph: web` — React scaffold at `/`.
- `artifacts/api-server: API Server` — Python service at `/api`.

The API workflow uses `uv run --frozen python -m cascadegraph_runtime` and
requires `PORT`. Its only endpoint is setup readiness at `/api/healthz`.
The retained Express files are unused template files, not the active backend.
No database or external credentials are needed for these checks.

## Layout and setup

- `artifacts/cascadegraph/` — web artifact for the approved implementation.
- `src/cascadegraph_runtime/` — minimal Python runtime readiness scaffold.
- `pyproject.toml`, `uv.lock` — reproducible Python dependencies.
- `.migration-backup/attached_assets/` — original architecture, execution prompt,
  and screenshot (unchanged).
- `scripts/post-merge.sh` — installs JavaScript and Python dependencies, no DB push.

Install JavaScript dependencies with `pnpm install --frozen-lockfile`; Python
dependencies use the platform package tool and `uv sync --frozen` for restoration.
The package tool manages `.pythonlibs`; do not create a separate virtualenv.

## Verification record

See `docs/workspace-setup.md` for actual checks and limitations. Product acceptance
gates, engine implementation, and product UI belong to the existing build task.
