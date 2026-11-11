# Accounts and sidebar authentication

CascadeGraph uses Replit-managed Clerk for email and social authentication.
Sign in opens the branded `/sign-in` screen; `/sign-up` handles registration.
Both routes include OAuth callback subpaths. The public `/` remains a guest
workbench. Signed-in users land at `/workspace`.

The sign-in and sign-up pages include an explicit GitHub OAuth button, so it
does not disappear when Clerk's prebuilt component omits that provider. It calls
the real SDK SSO flow and finishes at `/auth/callback`; failures remain signed
out with a safe, visible message. This button does not bypass disabled provider
settings or manufacture a successful login.

Google and GitHub can authenticate when enabled for the Clerk instance. In the workspace
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

## Password storage and verification

Password handling belongs to Clerk, not the application database. CascadeGraph
has no password or password-hash table/column and no local plaintext-password
comparison. Its API verifies the signed session cookie after Clerk authenticates
the user. The SHA-256 operation in account ownership maps a Clerk subject to an
owner ID; it is not password hashing.

Clerk documents one-way bcrypt password hashing before database storage and
provider-side password verification, including support for migrated password
hashes. See [Clerk's password storage explanation](https://clerk.com/blog/how-we-roll-passwords).
We cannot independently inspect the provider's internal password database.

Email/password input is handled by Clerk over HTTPS. In a published app its
managed proxy may forward credential request bytes in memory, but does not
persist or log bodies, cookies or credential headers. Hashing does not mean the
password never exists temporarily in a form or during verification; the rule
is no plaintext persistence/logging. Google/GitHub use OAuth, not provider
passwords collected by CascadeGraph.

A regression sends a non-secret password canary in unsupported application API
fields and verifies a 422 response, no value echo, no log disclosure and no
saved analysis. OAuth errors are classified by stable codes only, never raw
provider error payloads.
