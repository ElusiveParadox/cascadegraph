# Security

Never execute uploaded repositories. Only bundled sample code runs in isolated CI.
Uploads are limited to 50 MiB compressed, 200 MiB expanded, 2,000 entries and
512 KiB per supported source file (20 MiB retained source). YAML aliases,
symlinks, traversal and encrypted archives are rejected. Public GitHub fetching
uses fixed allowlisted hosts; arbitrary URL fetching is not supported.

AI extraction is opt-in. Only the bounded supported function is transmitted after
heuristic redaction. Do not upload secrets; redaction is not a guarantee. Provider
keys remain server-side. AI failure leaves unresolved evidence.

Analyses belong to anonymous HttpOnly-cookie sessions or verified Clerk accounts,
expire after 24 hours and
can be deleted. PostgreSQL persists snapshots; explicit local/test SQLite files
may reset. Export important reports. Verified Clerk accounts have separate
history; guest cookies cannot claim account owners. This does not provide
private-team collaboration or role-based sharing. See docs/AUTHENTICATION.md
and docs/THREAT_MODEL.md for trust boundaries and residual risks.

Do not post credentials or private source in public issues. Report reproducible
vulnerabilities privately to the repository owner using GitHub private reporting
when enabled. No invented security contact or support address is provided.
