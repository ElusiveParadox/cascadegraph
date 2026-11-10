# Threat model

## Assets and boundaries
Untrusted archives/source → bounded in-memory ingestion → safe parsers → normalized
session-owned snapshots. Optional redacted source → external LLM → untrusted
proposal → source/schema validation. Trusted committed sample → ephemeral GitHub
runner → measured artifact → maintainer-verified report. The browser never gets
provider or GitHub credentials. PostgreSQL retains only minimal redacted evidence.

## Threats and controls
| Threat | Control | Residual risk / verification |
|---|---|---|
| Code execution | AST and SafeLoader only; never import/eval source | Parser library bugs; dependency auditing and fixtures |
| ZIP traversal, symlinks, bombs | No filesystem extraction; reject unsafe names, links, duplicates, encrypted members; per-entry/count/ratio/expanded limits | 50 MiB compressed, 200 MiB declared expanded, 20 MiB retained supported source, 512 KiB/source file, 2,000 entries |
| YAML bombs and duplicate keys | Reject aliases, custom tags, duplicate keys, non-string keys and deep nesting | Parser recursion bounded by file-size checks |
| SSRF / credential confusion | Parse only public GitHub root URLs; construct API/codeload URLs ourselves, reject redirects and non-public DNS results, fixed HTTPS hosts, time/byte limits, no ambient proxy or OAuth credentials | Trusted GitHub DNS/TLS and upstream availability; adversarial regression tests required before release |
| Prompt injection | Source is data, no tools, bounded opt-in context, schema and local AST evidence checks | Source-understanding remains limited; unknown on failure |
| Secret disclosure | Drop env files, redact evidence/LLM context, never log input or provider errors | Heuristic redaction cannot guarantee detection of all secrets; review uploads |
| Cross-session access | Server-issued high-entropy HttpOnly SameSite cookie, ownership queries for every record; deletion cascades | No account recovery; cookie possession grants its session |
| CSRF | SameSite strict plus origin/netloc checks on mutations; no permissive CORS | Host/proxy configuration must remain trusted |
| Exhaustion | 2,000 archive entries, 100 direct uploads, 20 services, 40 edges, 100 policies, 200k simulation events; admission held before body buffering, bounded waiting/body-read time, rate limits and retention | Single-process limits are not distributed quotas; GitHub's unauthenticated public API quota is shared |
| CI compromise | Trusted branch/sample only, minimal permissions, pinned action SHAs, no production secrets, no Docker socket in app | Base image / dependency supply chain |
| Artifact forgery | No public upload endpoint trusts measurements; verified report bundled by maintainer with actual CI provenance | Maintainer verification is a trust boundary, not cryptographic remote attestation |
| Persistence loss | PostgreSQL transactional snapshots, explicit 24-hour retention, JSON export; read-only legacy-copy source | Anonymous sessions have no account recovery. Production publication and backups need explicit verification |
| Storage outage / lock exhaustion | Lifecycle-owned async PostgreSQL pool: 8 connections, 8 waiters, 1 s acquisition, 1.5 s statements, 500 ms locks, 5 s whole-call budget; no shared web-thread-pool work | Network failures remain possible. Local/test SQLite retains isolated terminable workers and strict deadlines |
| Health probe storm | Liveness bypasses database, cookies and rate limits; readiness is read-only, one in flight, 500 ms failure cooldown; read/health Retry-After 2 s with jitter/backoff guidance | Readiness tests availability of existing schema, not write success or durability |
| Owner replacement on outage | Session lookup/creation uses bounded atomic storage; any storage error leaves cookies untouched; never interpret failure as absent owner or fail over | Cookie possession remains authorization; original owner history is tested after recovery |
| Duplicate mutation after ambiguous commit | No transparent mutation retries; running-write deadline, lost worker or commit error reports uncertain outcome, no mutation Retry-After | Users must check history and reconcile after recovery; idempotency is not provided |

## Intended mode
An anonymous bounded demo, not a private repository collaboration product.
Add authentication before introducing private-team analyses. PostgreSQL does
not change the trust model. Never interpret random analysis UUIDs alone as authorization.

## Tests
Adversarial archive/parser fixtures, session isolation/deletion, provider failure,
strict input validation and simulator bounds are executable repository tests.
Actual scan and CI results belong in PROGRESS.md, not anticipated results here.
Isolated SQLite outage tests inject stalled acquisition/connect/query/commit,
verify event-loop heartbeats, excess-capacity responses, cancellation/reaping,
probe cooldown/recovery, cookie continuity and concurrent ownership/quota checks.
