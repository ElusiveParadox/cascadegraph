# Architecture

The pnpm workspace contains the React artifact, an API specification, generated
React-query/Zod helpers and dormant Express/database scaffolds. The actual
backend is Python FastAPI under `src/cascadegraph_runtime`; SQLite is accessed
directly with parameterized SQL. SQLAlchemy and PostgreSQL are unnecessary here.

Data flow: bounded in-memory ZIP/sample files → safe YAML/Python AST parsers →
normalized source-evidenced policies/graph → persisted redacted analysis →
reviewer corrections → pure deterministic simulation → immutable run snapshots →
comparison and JSON report. Optional AI proposes custom-loop structure, which
local source validation accepts or leaves unresolved.

Trust planes: untrusted upload data, pure local analysis, optional external LLM,
anonymous session store, and trusted sample-only CI. Uploads have no path to
execution, shell, Docker or arbitrary network targets. CI artifacts have no public
ingestion endpoint; maintainers review provenance before bundling safe metrics.

The single-process demo bounds body size, entries, source sizes, nodes, edges,
policies, requests, queue sizes, event count, sessions, saved runs and job
concurrency. This intentionally is not a distributed job system. A durable
multi-user deployment requires a separately approved storage/auth architecture.
