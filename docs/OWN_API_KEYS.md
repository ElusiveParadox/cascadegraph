# Use your own AI API key

Open **AI settings** in the sidebar, select **OpenAI** or **OpenRouter**, enter
the provider's model ID and API key, then choose **Use API key**. The key input
is cleared immediately. This selects credentials; it does not claim the provider
has verified them. Select **Use AI-assisted extraction** on a sample, ZIP,
repository or source-file analysis to use them.

## Cost and scope

Custom-key requests go directly from the server to the selected provider and
are billed by that provider, not Replit AI Integrations. AI remains opt-in per
analysis. A key does not expand the supported source patterns: extraction is
still checked against original source evidence and may remain unresolved.
The model must support OpenAI-compatible strict JSON-schema output.

## Credential lifecycle

- Keys exist only in the current tab's memory and transient request handling.
- They are not saved in localStorage, sessionStorage, cookies, environment
  variables, PostgreSQL, analyses, simulations or exported reports.
- Refresh, tab close, identity changes and sign-out clear the key. **Remove key**
  clears it immediately. Other tabs do not receive it.
- Public UI snapshots expose only provider and model, never a key or suffix.
- Provider changes clear draft credentials so a key cannot accidentally carry
  across providers.
- Requests use HTTPS. Production deployment and development preview must keep
  TLS enabled; no custom API-key URL/query parameter is supported.

## Transport boundary

The API client adds `X-CascadeGraph-AI-Provider`, `X-CascadeGraph-AI-Model` and
`X-CascadeGraph-AI-Key` only to opted-in POSTs at `/api/v1/analyses`,
`/archive`, `/repository` and `/sources`, including artifact base paths.
It does not add them to GETs, deletes, simulations, auth, external URLs or
ordinary deterministic analyses.

The server validates the headers and constructs a request-local provider
object. OpenAI and OpenRouter have fixed allowlisted HTTPS origins; users
cannot supply an arbitrary base URL. No global server credentials are changed.
App ownership still comes from session cookies, never these headers.

The server's normal logger excludes headers and bodies. Credential, model,
quota, structured-output and connection failures become fixed safe messages,
not raw upstream payloads. Own-key calls do not automatically retry, follow
redirects or fall back to managed billing.

## Verification boundary

Automated tests use explicitly fake canaries and mocked provider transports to
check authorization/model forwarding, concurrent user isolation, opt-in, fixed
origins, clearing and non-disclosure in responses/logs/reports. These tests do
not establish acceptance of an end user's real key or spend their provider
credits. Those credentials are verified by their provider on an opted-in run.
