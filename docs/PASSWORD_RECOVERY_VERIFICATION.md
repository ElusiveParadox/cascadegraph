# Password recovery verification

## Scope and method

Verified the existing Clerk-managed flow mounted by
`artifacts/cascadegraph/src/pages/auth.tsx` on 2026-11-11. No authentication
implementation, password store, provider settings or production data was changed.

The browser used an isolated development identity with a reserved
`+clerk_test@example.com` address. Clerk documents that these addresses suppress
email delivery in test mode, with `424242` as the development verification code:

- [Test emails and phones](https://clerk.com/docs/guides/development/testing/test-emails-and-phones)
- [Clerk password reset flow and session activation](https://clerk.com/docs/guides/development/custom-flows/authentication/legacy/forgot-password)

The tester provisioned the identity programmatically, then signed out before
recovery. That setup login is **not** counted as evidence of successful recovery.

## Browser observations

| Check | Result | Evidence boundary |
| --- | --- | --- |
| Recovery navigation | “Forgot password?” opened recovery; Back returned to the password step | Real Clerk widget |
| Refresh recovery subroute | `/sign-in/factor-one` hydrated correctly but returned to the password step, not the recovery selection | Recovery can be restarted; unfinished recovery UI state is not preserved |
| Invalid challenge | Invalid code returned 422 and “Incorrect code”; clearing the input showed “Enter code.” | Real provider rejection |
| Expired challenge presentation | “Verification code expired. Please request a new code.” | One narrowly matched synthetic `verification_expired` response; **not** real provider expiration |
| Password reset | Test code accepted, new password accepted, password-change success shown | Real development provider, not a mocked success |
| Session restoration | `/workspace` showed the test identity, analyses GET returned 200, reload preserved signed-in state | Session created by real recovery, not by setup sign-in |
| Sign-out | Returned to guest state | Real session sign-out |

No documented supported mechanism was available to force a real development
challenge to expire. The expiry fixture was removed immediately after the
presentation check; no provider setting or application clock was changed.

### Supplemental transport evidence and test cleanup

The initial request-body detector did not recognize a password-bearing request.
A narrowly targeted follow-up generated an ephemeral password in a browser
closure and used Clerk's SDK directly, with temporary fetch/XHR observers
installed beforehand. It observed one canary-bearing request during
`resetPassword`, zero canary-bearing `/api/v1` requests, and zero canary matches
in response bodies/errors, console output, localStorage or sessionStorage.
Observers were removed afterward. The URL heuristic classified that request
as “other”; only counts were retained, so destination-level attribution could
not be independently confirmed. SDK-operation attribution is not a claim that
the destination was separately verified.

The initial browser tester's automatic accessibility snapshot exposed the first
disposable password value, despite masked screenshots and no explicit script
logging. This was **test evidence capture**, not an application log disclosure.
The supplemental SDK-only reset superseded that value without entering another
password into a DOM field. No password values or raw traces were saved in this
repository. Do not claim the entire browser run was free of credential capture.

The isolated test identity remains in development, signed out. Clerk refused
self-deletion with `session_reverification_required` (403); no undocumented
cleanup bypass or access to other identities was attempted.

## Credential handling regressions

`tests/test_auth.py` now checks:

- Unsupported login-password fields are rejected with 422, without echoing their
  values, logging them (including INFO logs), saving an analysis, or leaving
  them anywhere in the isolated test database dump.
- Local proxy fixtures cover successful, incorrect-code, expired-code and
  transport-error responses. Password bytes are forwarded to the constant Clerk
  upstream in memory, once, with no application persistence, log disclosure,
  response echo or cacheable response. Even transport exceptions containing the
  non-secret canary are not returned or logged.
- A newly signed session for the same account can retrieve existing history;
  another account, expired session and guest cannot retrieve that account's
  analysis. These locally signed fixtures check application ownership, **not**
  provider password reset.

Proxy fixtures run in a local test environment with a synthetic deployment flag
and a mocked upstream. They do **not** establish production provider readiness,
real email delivery, or the contents of the provider's own database.

The application middleware logs correlation ID, method, status and duration,
not request bodies. The proxy deliberately preserves provider response bytes;
the fixtures test safe provider error shapes, not arbitrary malicious upstream
responses. Neither provider-side storage nor every possible provider response
was independently audited.

## Production and delivery remain separate

Production email/password configuration, real challenge expiration, real
recipient delivery, sender/DNS setup, production session restoration and
production database contents were **not tested**. No emails to real recipients
were requested. Development success is not a production release gate.

## Executed local checks

- `uv run --frozen pytest`: 125 passed.
- `uv run --frozen ruff check src tests`: passed.
- `pnpm run typecheck`: passed.
- `pnpm --filter @workspace/cascadegraph test`: passed.
- Existing managed API/web workflows started cleanly; sign-in screenshot rendered.
