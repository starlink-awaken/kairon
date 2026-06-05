#!/bin/bash
# ── cron-service start script ─────────────────────────────────────────
# Migrated to: ~/Workspace/projects/kairon/packages/cron-service
# SSOT:       ~/.cron-service/config.yaml
# Logs:       ~/.cron-service/logs/
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KAIRON_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

export CRON_SERVICE_CONFIG="${CRON_SERVICE_CONFIG:-$HOME/.cron-service/config.yaml}"

exec "$KAIRON_DIR/.venv/bin/python3" -m cron_service.server
