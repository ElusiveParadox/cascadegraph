# Threat model

## Assets and boundaries
Untrusted archives/source → bounded in-memory ingestion → safe parsers → normalized
session-owned snapshots. Optional redacted source → external LLM → untrusted
proposal → source/schema validation. Trusted committed sample → ephemeral GitHub
runner → measured artifact → maintainer-verified report. The browser never gets
provider or GitHub credentials. SQLite retains only minimal redacted evidence.

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
| Persistence loss | Explicit ephemeral demo warning, JSON export, local SQLite transactions | Durable public analyses are not supported until production storage is verified |

## Intended mode
An anonymous bounded demo, not a private repository collaboration product.
Add authentication and ownership-preserving durable storage before introducing
persistent private analyses. Never interpret random analysis UUIDs alone as authorization.

## Tests
Adversarial archive/parser fixtures, session isolation/deletion, provider failure,
strict input validation and simulator bounds are executable repository tests.
Actual scan and CI results belong in PROGRESS.md, not anticipated results here.
