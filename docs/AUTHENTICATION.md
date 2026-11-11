# Accounts and sidebar authentication

CascadeGraph uses Replit-managed Clerk for email and social authentication.
Sign in opens the branded `/sign-in` screen; `/sign-up` handles registration.
Both routes include OAuth callback subpaths. The public `/` remains a guest
workbench. Signed-in users land at `/workspace`.

Google and GitHub appear when enabled for the Clerk instance. In the workspace
Auth pane, use Configure → SSO providers → Development to enable both providers.
Configure Production separately for a published app. Email sign-in is the
default. Provider credentials and keys are managed securely, never in source.
Development and production users are separate.

The sidebar bottom replaces the old API/model/AI diagnostic text with guest
Sign in or the signed-in name/email and Sign out. The mobile drawer includes
the same controls and keyboard focus loop.

## Ownership and sign-out

The Python API verifies the Clerk session cookie's signature and authorized
origin against the application's public signing keys. Key fetching is async,
bounded and cached. Invalid, expired or unverifiable sessions do not become
guests silently. The browser never supplies user IDs or bearer tokens to the
application API.

Verified subjects map to stable, separate account owners. Browser guest cookies
cannot impersonate account owners. The existing PostgreSQL tables need no DDL
changes. The same account can retrieve its unexpired records on another device.
Every analysis, simulation and report lookup remains ownership-scoped.

Guest records are not automatically transferred when signing in. The sign-in
screen discloses this; export important guest reports first. All analyses still
expire after 24 hours. Accounts do not add team sharing, roles, or permanent
history.

Sign out first expires the guest browser cookie using
`POST /api/v1/auth/sign-out` (204, same-origin), then ends the Clerk session and
returns to `/`. Query caches are separated by identity and discarded on a
switch; selected analysis/simulation state is reset. Saved records are not
deleted. A failure is shown instead of falsely reporting a successful sign-out.

## Runtime

Replit provisions Clerk keys. They must not be printed or committed.
`/api/__clerk` is the production-only Frontend API proxy on the existing Python
server; no duplicate Express service is used. It forwards canonical managed
headers to a constant upstream, preserves raw response bytes and duplicate
cookies, and supplies Content-Length for the deployment edge. Request size,
response size, admission, network I/O and whole-operation duration are bounded.
Development calls Clerk directly. Never manually set the managed proxy URL.

Without auth keys in an isolated local/CI environment, the guest workbench
continues to work and account controls explicitly state that sign-in is
unavailable. This is not a fake authenticated state.
