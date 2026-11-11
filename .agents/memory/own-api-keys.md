---
name: End-user AI credentials
description: Keep user-owned AI billing credentials isolated from shared project configuration.
---

The own-API option is for individual application users, not a replacement of
the project's shared AI secrets. Keep each credential request-local, and keep
initial browser retention limited to the current tab's memory. Do not persist
keys without an explicit encrypted-storage and key-lifecycle decision.

**Why:** The user requested a way for users to add and use their own API.
Treating one user's key as a global server setting would expose its billing
scope to other users. Memory-only retention avoids introducing an unreviewed
credential database.

**How to apply:** Preserve explicit AI opt-in and clear credentials on refresh,
identity change and sign-out. Never fall back from a failed user key to shared
paid credentials without fresh consent.

Do not treat a client-side abort as proof that a server-side AI request never
ran. Credential transport tests must use a server-side stub or mock transport
when they must guarantee zero upstream requests.

**Why:** An aborted browser transport check still reached the server, which
sent its explicitly fake canary to the provider and received an unauthorized
response. No real key or successful generation was involved.

**How to apply:** Keep browser keys fake, verify server egress independently,
and label mocked transport, invalid-key checks and successful live inference
as different kinds of evidence.
