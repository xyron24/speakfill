#!/usr/bin/env bash
# Production deploy entrypoint.
set -euo pipefail
echo "Production deploy is handled separately. For local runs use 'docker compose up --build'." >&2
exit 1
