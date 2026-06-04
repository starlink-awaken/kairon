#!/bin/bash
# =============================================================
# install-hermes-bridge.sh
# 将 agent-runtime/scripts/ 下的工具脚本桥接到 Hermes Agent 目录
#
# 运行后:
#   源码维持 ~/Workspace/agent-runtime/scripts/ 下
#   软链创建到 ~/.hermes/scripts/ 供 Hermes cron 使用
#
# 反安装: 见 uninstall-hermes-bridge.sh
# =============================================================

set -euo pipefail

SRC_SCRIPTS="${HOME}/Workspace/agent-runtime/scripts"
HERMES_SCRIPTS="${HOME}/.hermes/scripts"

# ── 需要桥接的脚本清单 ─────
# 格式: "源文件名:目标文件名"
# 如果两者同名，直接写 "filename"
BRIDGE_SCRIPTS=(
  "codexbar-quota.sh"
  "run-agent-task.sh"
  "agent_autonomy.py"
  "agent-inject-budget"
  "agent-read-budget"
  "cost_digest.sh"
)

COUNT_OK=0
COUNT_FAIL=0
COUNT_SKIP=0

echo "━━━ install-hermes-bridge.sh (agent-runtime) ━━━"
echo "  源码: ${SRC_SCRIPTS}"
echo "  目标: ${HERMES_SCRIPTS}"
echo ""

for entry in "${BRIDGE_SCRIPTS[@]}"; do
  # 解析 source:target 格式
  if echo "$entry" | grep -q ":"; then
    SOURCE="${entry%%:*}"
    TARGET="${entry##*:}"
  else
    SOURCE="$entry"
    TARGET="$entry"
  fi

  SOURCE_PATH="${SRC_SCRIPTS}/${SOURCE}"
  TARGET_PATH="${HERMES_SCRIPTS}/${TARGET}"

  # 检查源文件是否存在
  if [ ! -f "$SOURCE_PATH" ] && [ ! -x "$SOURCE_PATH" ]; then
    echo "  ⚠  ${SOURCE} → 源文件不存在，跳过"
    COUNT_SKIP=$((COUNT_SKIP + 1))
    continue
  fi

  # 创建软链
  ln -sf "$SOURCE_PATH" "$TARGET_PATH"
  echo "  ✓  ${SOURCE} → ${TARGET}"
  COUNT_OK=$((COUNT_OK + 1))
done

echo ""
echo "━━━ 完成 ━━━"
echo "  ${COUNT_OK} installed"
echo "  ${COUNT_SKIP} skipped"
echo "  ${COUNT_FAIL} failed"
echo ""
echo "检查: ls -la ${HERMES_SCRIPTS}/ | grep agent-runtime"
