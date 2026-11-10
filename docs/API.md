# HTTP API

Authoritative hand-maintained contract: `lib/api-spec/openapi.yaml`.
Generated consumers: `lib/api-client-react` and `lib/api-zod`. FastAPI's `/docs`
also exposes runtime route metadata; use the curated contract for stable schemas.

Base `/api`:
- GET `/healthz`, `/v1/health/live`, `/v1/health/ready`, `/v1/status`.
- GET/POST `/v1/analyses`; POST JSON `{source_type:"sample",use_ai:false}`.
- POST `/v1/analyses/archive` multipart ZIP `file` plus boolean `use_ai`.
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
or retry values. A corrected source submission creates a new immutable analysis;
raw source is not stored for later recomputation.
