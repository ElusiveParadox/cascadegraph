# Replit deployment and release gates
The workspace has managed web/API artifacts and preview workflows. Preview is
not a published URL. The user must approve Publish; no published URL or production
health is claimed in this repository.

Before publication: require passing Python/types/frontend/browser/Compose checks,
review safe validation artifacts, verify opt-in AI configuration with Secrets,
and visibly disclose retention, anonymous sessions and limits.
Do not put secrets in frontend builds or repository files.

The API now uses managed PostgreSQL through `DATABASE_URL`; see POSTGRESQL.md.
Apply the schema to development and let Publish apply the production diff.
Never add startup/build-time production DDL. Explicit SQLite mode is local/test
only. Public GitHub, source-file and ZIP intake remain bounded and never execute
source. No private multi-user promise is made. Long-lived private use still
requires authentication, centralized rate limits and retention/backup procedures.

After user-approved publication obtain the actual production URL from the platform,
then smoke-check health, sample analysis, simulation, export and deletion there.
Record real evidence before marking the production gate complete.
