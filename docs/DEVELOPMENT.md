# Development
Read root AGENTS.md and relevant scoped instructions first. Keep Python core,
boundary, storage, parsers and AI separate. Do not execute uploads or install their
dependencies. Restore frozen pnpm/uv lockfiles; use managed workflows for preview.

Checks:
```
uv run --frozen ruff check src tests
uv run --frozen pytest -q
pnpm --filter @workspace/api-spec run codegen
pnpm run typecheck
pnpm --filter @workspace/cascadegraph test
```
Important browser journeys are in `artifacts/cascadegraph/e2e`. GitHub installs
Chromium and runs desktop/phone Playwright projects. Config starts isolated local
API/Vite processes and a server-side proxy; browser code uses relative URLs.
CI disables AI. Never make live LLM calls in automated tests.

Real-system tests belong in the sample's GitHub Compose workflow, never privileged
containers on Replit. Add regression tests for semantics before changing the
engine. Update model version when interpretations change. Preserve report
snapshots and source facts; document deliberate compatibility decisions.
