# Security

Never execute uploaded repositories. Only bundled sample code runs in isolated CI.
Uploads are limited to 5 MiB compressed, 12 MiB expanded, 500 entries and 128 KiB
per file. YAML aliases, symlinks, traversal and encrypted archives are rejected.
There is no arbitrary URL-fetching endpoint.

AI extraction is opt-in. Only the bounded supported function is transmitted after
heuristic redaction. Do not upload secrets; redaction is not a guarantee. Provider
keys remain server-side. AI failure leaves unresolved evidence.

Analyses belong to anonymous HttpOnly-cookie sessions, expire after 24 hours and
can be deleted. SQLite files may reset on republication; do not use this demo as
the only copy of an important report. No persistent private multi-user mode is
offered. See docs/THREAT_MODEL.md for trust boundaries and residual risks.

Do not post credentials or private source in public issues. Report reproducible
vulnerabilities privately to the repository owner using GitHub private reporting
when enabled. No invented security contact or support address is provided.
