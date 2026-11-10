#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
pnpm install --frozen-lockfile
uv sync --frozen
if [[ -n "${DATABASE_URL:-}" && "${REPLIT_DEPLOYMENT:-}" != "1" ]]; then
  uv run --frozen python -m cascadegraph_runtime.setup_database
fi
