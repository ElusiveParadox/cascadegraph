# PostgreSQL storage and safe local migration

The live Python API uses the runtime-managed `DATABASE_URL`. It stores only
normalized/redacted snapshots in `cg_sessions`, `cg_analyses`, and
`cg_simulations`. The dormant TypeScript database package is not used.
Guest ownership and 24-hour analysis retention are unchanged. Optional Clerk
accounts use a separate stable owner namespace in the same session tables; see
AUTHENTICATION.md. PostgreSQL itself does not add identity, private-team sharing
or distributed rate limiting.

## Development

```sh
uv sync --frozen
uv run --frozen python -m cascadegraph_runtime.setup_database
```

The explicit command applies `schema/postgresql.sql` to development. The
post-merge script also runs it when a database URL is present and the process
is not a published deployment. API startup only validates the existing schema;
it never creates or changes PostgreSQL tables.

Do not paste a real connection string in chat, repository files or logs.
Replit supplies it through Secrets. Outside Replit, configure a PostgreSQL URL
securely and apply the development schema before starting the app.

## Copy existing local data

Stop the API workflow first so no SQLite writes race the copy. The following
commands are for development only:

```sh
uv run --frozen python -m cascadegraph_runtime.migrate_sqlite cascadegraph.sqlite3
uv run --frozen python -m cascadegraph_runtime.migrate_sqlite cascadegraph.sqlite3 --apply
```

The first command reports counts only. The second copies unexpired sessions,
analyses, and their simulations in one PostgreSQL transaction. Original owner
tokens and IDs are unchanged, so existing browser cookies still work. Identical
imports are idempotent; differing records abort instead of overwriting. The
SQLite source is read-only and is never deleted. Keep it private and ignored
by Git. Restart the existing API workflow after the copy, with
`CASCADEGRAPH_DB_PATH` unset.

The isolated SQLite override remains available for local/unit/outage tests:
`CASCADEGRAPH_DB_PATH=/path/to/test.sqlite3`. A configured PostgreSQL failure
never silently falls back to SQLite.

## Production

Replit Publish applies the development-to-production schema diff. Do not add
DDL to the production build command, API startup, or a production migration
script. Publishing does not copy development records automatically; data
promotion, if needed, is an explicit user choice in the Publish interface.
The local-copy utility refuses a published deployment.

## Availability and verification

Each API lifecycle owns a pool of at most 8 connections, with at most 8 waiting
calls, a 1-second acquisition wait and 5-second operation budget. Connections
have a 2-second connect timeout, 1.5-second statement timeout, 500-ms lock wait,
and 3-second idle-in-transaction timeout. Overload returns a sanitized 503.
Liveness never touches storage; readiness checks schema without cookies or
cleanup. Failed readiness probes have a cooldown.

There are no automatic write retries. A commit whose response is lost returns
`STORAGE_OUTCOME_UNCERTAIN`; check history before replaying the action. Errors
never replace browser owner cookies or expose database exception text.

CI runs the real PostgreSQL integration tests and browser workflows against
an ephemeral PostgreSQL service, alongside isolated SQLite outage tests.
Test owners are unique and cleanup is scoped; tests never truncate a shared
development database.
