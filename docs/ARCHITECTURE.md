# Architecture

The pnpm workspace contains the React artifact, an API specification, generated
React-query/Zod helpers and dormant Express/database scaffolds. The actual
backend is Python FastAPI under `src/cascadegraph_runtime`. PostgreSQL stores
normalized JSONB snapshots using parameterized psycopg queries and a bounded
lifecycle-owned async pool. SQLite remains an explicit isolated local/test mode.
The TypeScript database scaffold is not a second authoritative persistence layer.

Data flow: bounded in-memory ZIP/sample files → safe YAML/Python AST parsers →
normalized source-evidenced policies/graph → persisted redacted analysis →
reviewer corrections → pure deterministic simulation → immutable run snapshots →
comparison and JSON report. Optional AI proposes custom-loop structure, which
local source validation accepts or leaves unresolved.

Trust planes: untrusted upload data, pure local analysis, optional external LLM,
guest/account session store, and trusted sample-only CI. Uploads have no path to
execution, shell, Docker or arbitrary network targets. CI artifacts have no public
ingestion endpoint; maintainers review provenance before bundling safe metrics.

The single-process demo bounds body size, entries, source sizes, nodes, edges,
policies, requests, queue sizes, event count, sessions, saved runs and job
concurrency. This intentionally is not a distributed job system. PostgreSQL
does not introduce private-team sharing or distributed rate limiting. Optional
Clerk accounts now provide verified identity and account recovery independently
of the storage layer; guest sessions still have no recovery. Analyses still
expire after 24 hours. See AUTHENTICATION.md.
