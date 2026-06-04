#!/bin/bash
# codexbar-quota.sh — CodexBar 配额刷新
# 如果 SharedBrain 环境有问题，输出清晰信息
set -euo pipefail
cd "$HOME/Workspace/SharedBrain"
if [ -d ".venv" ]; then
    .venv/bin/python3 organs/D_Execution/organs/llm/_refresh_codexbar.py "$@" 2>&1 || {
        echo "[codexbar-quota] SharedBrain import chain broken: quota_router module needs PYTHONPATH fix"
        exit 0
    }
else
    echo "[codexbar-quota] No .venv found, skip refresh"
    exit 0
fi
