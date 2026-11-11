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

The GitHub choice belongs in the same social-login section as Google, above
email entry. It must not appear on its own while the authentication form loads
or remain as a separate control beneath the card/footer.

**Why:** The user corrected the initial footer placement and the isolated
button appearing during widget loading.

**How to apply:** Preserve the provider grouping and synchronized loading
behaviour through auth-step changes, not just the final static screenshot.
