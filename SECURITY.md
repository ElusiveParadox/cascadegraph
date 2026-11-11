# Security

## Password handling

CascadeGraph does not persist passwords or password hashes. Clerk owns password
hashing and verification; its published design describes one-way bcrypt hashes.
The application checks signed session cookies, not plaintext passwords. The
production auth proxy forwards credential bytes only in memory and never logs
bodies, cookies or credential headers. Do not add a parallel password store.
See docs/AUTHENTICATION.md for the provider source and verification boundaries.

## Reviewed proxy scan warning

Static analysis flags the Clerk proxy's request-derived path/query as potential
SSRF. The destination scheme/host/port are fixed and explicitly allowlisted;
path/query are copied as URL components, never joined as an arbitrary origin.
Redirect following is disabled. Regression tests cover protocol-relative,
host-like and attacker-URL query inputs and confirm the destination remains the
Clerk Frontend API. The scanner still reports this dataflow warning; it has not
been suppressed or represented as a clean scan.

## Repository handling

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
