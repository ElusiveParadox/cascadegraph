# HTTP API

Authoritative hand-maintained contract: `lib/api-spec/openapi.yaml`.
Generated consumers: `lib/api-client-react` and `lib/api-zod`. FastAPI's `/docs`
also exposes runtime route metadata; use the curated contract for stable schemas.

Base `/api`:
- GET `/healthz`, `/v1/health/live`, `/v1/health/ready`, `/v1/status`.
- GET/POST `/v1/analyses`; POST JSON `{source_type:"sample",use_ai:false}`.
- POST `/v1/analyses/archive` multipart ZIP `file` plus boolean `use_ai`.
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
