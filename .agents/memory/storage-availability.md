---
name: Storage availability boundaries
description: Why the demo uses terminable execution and conservative uncertain-write errors.
---

Bound storage work with execution that can actually be stopped; a timeout on a
thread wait does not cancel SQLite connect/commit or release worker capacity.
Keep admission occupied until execution is reaped, and fail explicitly if the OS
cannot terminate uninterruptible I/O.

**Why:** Storage outages must not block liveness or replace anonymous owners.
The original outage fixes targeted the local SQLite demo. The user subsequently
authorized PostgreSQL live storage; do not use that old demo constraint to reject
the migration. Ownership continuity and uncertain-outcome semantics still apply.

**How to apply:** When changing storage execution, retain hard acquisition/commit
boundaries, unchanged cookies on failure, and conservative uncertain-write
semantics. Never infer rollback from a request timeout or add automatic mutation
retries. Use lightweight spawn-safe fault fixtures: importing the complete API in
a spawned fault fixture can consume the operation budget before the fault runs.
