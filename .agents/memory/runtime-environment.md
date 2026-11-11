---
name: Replit runtime environment flags
description: Distinguish platform environment from a published app when guarding database setup.
---

`REPLIT_ENVIRONMENT=production` can be present in the development workspace.
Use `REPLIT_DEPLOYMENT=1` to recognize a published deployment instead.

**Why:** The platform production flag initially blocked authorized development
database setup and local data import. Official Replit documentation confirmed
that the flag describes the platform environment, not application publication.

**How to apply:** Keep development database tools disabled in published apps,
but do not classify the workspace as an app production database solely from
`REPLIT_ENVIRONMENT`. Production schema changes still belong to Publish.

Vite prebundles can retain an old React renderer after a dependency install and
an ordinary workflow restart, even when installed React/React DOM versions agree.

**Why:** A matching package tree still served a mismatched renderer from its
optimizer cache. Installed-version checks alone did not diagnose the browser.

**How to apply:** When a runtime version mismatch contradicts package resolution,
check the served optimized dependency, not just the package manifest. Treat
optimizer output as disposable; never work around a mismatch by ignoring peers.
