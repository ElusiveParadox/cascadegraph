---
name: Safe recovery verification
description: Development-only recovery identities and avoiding password disclosure in browser evidence.
---

Use reserved `+clerk_test@example.com` identities and Clerk's documented test
codes for recovery checks; distinguish actual provider reset/session creation
from fixtures that only exercise error presentation.

**Why:** Programmatic test sign-in does not prove password recovery works.
Development test addresses suppress delivery and avoid sending email to real
recipients. A mocked expiry response does not establish actual provider expiry.

**How to apply:** Verify real session creation independently and label fixture
coverage and unverified production/email behavior explicitly.

Do not type generated test passwords into DOM inputs when automatic browser
evidence is enabled. Use a transient in-memory SDK operation for password-bearing
checks and report only sanitized codes, counts and booleans.

**Why:** The browser tester's automatic accessibility snapshot can include a
password input's value even when its screenshot visually masks the characters.
Avoiding explicit logging alone does not prevent evidence disclosure.

**How to apply:** Use navigation and code-entry UI checks without password
fields; exercise credential transport in a memory-only provider SDK call.
Never save request bodies, session tokens or raw traces containing credentials.
