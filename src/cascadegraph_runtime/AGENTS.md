# Python boundary and engine rules
The simulator must remain pure and deterministic. Source ingestion never imports,
executes or writes uploaded source. YAML loaders must derive from SafeLoader.
Normalize retries vs total attempts per framework and preserve source facts.
AI output is untrusted proposed structure until local source validation succeeds.
Every object lookup must check session ownership; report routes are not exceptions.
Bound resource use before expensive parsing. Redact before logging/storing/provider
submission; never log full exceptions that may contain source or credentials.
HTTP storage calls must use the lifecycle-owned bounded process executor, never
direct SQLite or the shared web thread pool. Keep workers accounted for until
reaped. Never retry mutations; commit/deadline ambiguity is an uncertain outcome,
not proof of rollback. Failed storage checks must not change owner cookies.
