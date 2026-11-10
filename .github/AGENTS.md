# CI boundaries
Pin actions to verified full SHAs and use read-only permissions by default.
Never check out fork code with privileged pull_request_target or production
secrets. The Compose workflow runs only the committed sample on trusted branches.
Always tear down containers, even after failure. Upload safe JSON metrics, never
source archives, credentials or environment dumps. Never weaken required checks
to make a merge pass.
