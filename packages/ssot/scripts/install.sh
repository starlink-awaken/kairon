#!/bin/bash
# SSOT Kernel 一键安装脚本
# 用法: bash install.sh [--user]

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "═══ SSOT Kernel 安装 ═══"
echo ""

# 检查 Python
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "❌ 需要 Python 3.10+"
    exit 1
fi
echo "✅ Python: $($PYTHON --version)"

# 安装
echo ""
echo "安装 ssot-kernel..."
PIP_ARGS="--no-build-isolation"
if [ "$1" == "--user" ]; then
    PIP_ARGS="$PIP_ARGS --user"
fi
pip install -e . $PIP_ARGS --break-system-packages 2>/dev/null || \
pip install -e . --break-system-packages 2>/dev/null || {
    echo "⚠️ pip install 失败，使用直接运行模式"
    echo "   运行: ./ssot-kernel --help"
    exit 0
}

echo ""
echo "✅ 安装完成"
echo ""
echo "快速开始:"
echo "  ssot-kernel check --dir domains/guozhuan"
echo "  ssot-kernel evolve --dir domains/guozhuan"
echo ""
echo "MCP Server (用于 Claude 集成):"
echo "  python3 mcp_server.py"
echo ""
echo "配置 Claude Desktop — 将以下内容加入 ~/.claude/settings.json 或 claude_desktop_config.json:"
MCP_PATH="$DIR/mcp_server.py"
cat << CONF
{
  "mcpServers": {
    "ssot-kernel": {
      "command": "python3",
      "args": ["$MCP_PATH"]
    }
  }
}
CONF
