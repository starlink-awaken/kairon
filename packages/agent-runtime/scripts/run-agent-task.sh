#!/bin/bash
# run-agent-task.sh — 调用 Agent Runtime 执行预定义任务
set -euo pipefail
TASK_NAME="${1:-}"
AGENT_HOME="${AGENT_RUNTIME_HOME:-$HOME/Workspace/agent-runtime}"
AGENT_URL="http://localhost:9876"
AGENT_TOKEN="${AGENT_RUNTIME_AUTH_TOKEN:-$(grep '^AGENT_RUNTIME_AUTH_TOKEN=' "$AGENT_HOME/.env" 2>/dev/null | cut -d= -f2-)}"

if [ -z "$TASK_NAME" ]; then
  echo "Usage: run-agent-task.sh <task-name>"
  exit 1
fi

# 使用 /run-task 端点，不需要构造 prompt
RESPONSE=$(curl -s -m 180 \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"task\":\"$TASK_NAME\"}" \
  "$AGENT_URL/run-task" 2>/dev/null || echo "")

if [ -n "$RESPONSE" ]; then
  echo "$RESPONSE" | python3 -c "
import sys, json
r = json.load(sys.stdin)
if 'error' in r:
    print(f'[ERROR] {r[\"error\"]}')
else:
    print(r.get('result', ''))
" 2>/dev/null
else
  echo "[run-agent-task] API request failed for task: $TASK_NAME"
fi
