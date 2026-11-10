# Replit deployment and release gates
The workspace has managed web/API artifacts and preview workflows. Preview is
not a published URL. The user must approve Publish; no published URL or production
health is claimed in this repository.

Before publication: require passing Python/types/frontend/browser/Compose checks,
review safe validation artifacts, verify opt-in AI configuration with Secrets,
and visibly disclose ephemeral SQLite, retention, anonymous sessions and limits.
Do not put secrets in frontend builds or repository files.

For the initial public demo, publish only the bounded sample/ZIP functionality,
with no private multi-user promise. Writable SQLite may reset across deployment
changes; export reports. Long-lived private use needs separately approved durable
storage, authentication/authorization, centralized rate limits and operational
retention/backup procedures. Do not silently migrate this database.

After user-approved publication obtain the actual production URL from the platform,
then smoke-check health, sample analysis, simulation, export and deletion there.
Record real evidence before marking the production gate complete.
