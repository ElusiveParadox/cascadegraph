---
name: Folder upload test fixtures
description: Browser limitations when verifying source replacement using native directory uploads
---

Use separate original and incoming directory trees when testing folder replacement.
Do not overwrite or delete the original disk files while their browser File objects
remain selected.

**Why:** Native directory selections retain disk-backed handles. Changing the
underlying fixture can make a retained file unreadable rather than model a normal
selection-state update. Chromium can also return null from Playwright's
postDataBuffer for multipart requests containing disk-backed folder files.

**How to apply:** For folder upload content assertions, inspect the actual FormData
at the browser fetch boundary and forward the request unchanged. Keep original
fixtures intact until submission and cleanup. In-memory single-file uploads may
still expose their request bodies normally.
