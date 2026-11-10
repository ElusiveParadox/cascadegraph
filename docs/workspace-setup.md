# CascadeGraph workspace setup

Verified on 2026-11-10. This is a greenfield setup, not an application port.

## Preserved inputs

- All three original uploads remain unchanged under
  `.migration-backup/attached_assets/`: architecture document, execution prompt,
  and screenshot.
- Original Python-only `.replit` remains in `.migration-backup/`.
- No migration detection/copy scripts were run: no application code was present.
- Git history and the existing remote configuration were not changed.
- Task plans were not edited and no duplicate implementation task was created.

## Active services

| Service | Managed workflow | Preview route |
| --- | --- | --- |
| React/Vite scaffold | `artifacts/cascadegraph: web` | `/` |
| Python/FastAPI readiness scaffold | `artifacts/api-server: API Server` | `/api/healthz` |

The API service runs `uv run --frozen python -m cascadegraph_runtime`, binds
`0.0.0.0`, and requires the artifact's `PORT`. Its response is validated through
a Pydantic model and matches the pre-existing health contract:
`{"status":"ok"}`. FastAPI's generated schema is at `/api/openapi.json`.
Access logging is disabled so future sensitive query strings are not logged.

The React page is explicitly labeled as workspace readiness, not product UI.
The original API server's Express source and database packages are retained as
unused scaffold files, not used by the Python service. The mockup sandbox is
unchanged.

## Checks performed

- `pnpm install` succeeded; the React artifact's dependencies installed too.
- `pnpm run typecheck` passed for shared libraries, the API template, React
  artifact, mockup sandbox, and scripts.
- The post-merge setup completed successfully: JavaScript frozen-lock install
  and Python frozen-lock sync. No database schema commands were run.
- Both managed service workflows restarted successfully and logs showed clean
  Vite and Uvicorn startup.
- Shared-proxy HTTP request to `/` returned the CascadeGraph HTML.
- Shared-proxy HTTP request to `/api/healthz` returned the exact expected JSON.
- Shared-proxy HTTP request to `/api/openapi.json` contained the health route.
- Runtime import and model serialization checks succeeded with Python 3.13.11,
  FastAPI 0.162.2, and Pydantic 2.14.3.
- Screenshot of `/` showed the readiness placeholder rendered without browser
  errors.
- `git diff --check` passed; a diff check confirmed original uploads and original
  Python configuration were unchanged.

## Limitations and handoff

- No CascadeGraph engine, domain API, persistence, or product UI is implemented.
  Continue the already-approved **Build and validate CascadeGraph** task and its
  acceptance gates. No separate follow-ups are proposed because that task covers
  the remaining implementation.
- No existing UI existed, so there is no visual-parity claim.
- No PostgreSQL database was introduced or queried. The unused database package
  is a platform scaffold, not an architectural decision for CascadeGraph.
- Production publishing and production runtime have not been tested; nothing
  was published or pushed. Only local managed workflows and the shared preview
  proxy were verified.
- Python and JavaScript dependencies are locked by `uv.lock` and
  `pnpm-lock.yaml`. Platform-managed `.pythonlibs` and Python bytecode are ignored.
- Python production service metadata now points to the same Python entry point,
  but production configuration must be validated as part of the later build
  task before release.
