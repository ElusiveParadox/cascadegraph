---
name: Visible authentication entry points
description: Why the GitHub choice must remain visible independently of provider enablement.
---

Keep an explicit GitHub sign-in choice visible alongside Google and email.
Provider configuration instructions are not a substitute for the requested
button. Connect it to real OAuth and show a clear failure if the service refuses
the provider; never manufacture successful authentication.

**Why:** The user repeatedly clarified that the missing GitHub button itself
needed fixing, after a discussion focused only on provider settings.

**How to apply:** Preserve this requirement when replacing or restyling the
prebuilt sign-in widget. Avoid duplicating GitHub controls if the provider's
own widget later starts rendering it.
