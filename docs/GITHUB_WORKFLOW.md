# GitHub workflow
Feature branch → pull request → passing required checks → squash merge to main.
No force pushes, secret-bearing workflow files, fake review or bypassing checks.
Review and update against latest remote main before merging.

The platform checkpoint history contains uploaded account screenshots/backups.
It must not be pushed into the public repository. `scripts/export-github.py`
copies a filtered source snapshot into an ignored separate clone. It never
commits/pushes or handles credentials. Perform GitHub branch/commit/PR operations
in that clone through the authorized secure GitHub CLI. Keep platform history
unchanged. Do not export uploads, session data or local agent context.

Quality checks run Python tests/lint, codegen drift, workspace types, helper tests,
build and desktop/phone Playwright. Security CI audits JavaScript dependencies and
guards against source execution/environment-data commits. Real Compose runs on
trusted branches/manual dispatch, uploads safe measurements and always cleans up.
Actions are pinned to full SHAs and default permissions are read-only.
