# Agora 外部接入指南

## 概述
Agora 作为 MCP 服务汇聚枢纽，提供三种外部接入模式：
1. Manifest 获取 — 通过 `proxy_list_tools` 获取所有下游工具的完整清单
2. 直接执行 — 通过 `proxy_call` 精确定位并调用工具
3. 语义路由 — 通过 `agora_execute` 由系统智能匹配

## 接入方式

### MCP 协议接入（推荐）
Agora 支持三种 MCP 传输协议：
- **stdio**：`agora-mcp` 命令，通过标准输入输出
- **HTTP (SSE)**：`agora-web` 或端口 7422，通过 HTTP SSE
- **SSE 专用**：端口 7431，专用 SSE 传输

```bash
# 启动 SSE 模式
python -m agora.server.mcp sse
# 启动 HTTP 模式
agora-web
```

### 认证
- 环境变量 `AGORA_API_KEY` 设置时启用 Bearer Token 认证
- 未设置时为宽松模式（本地开发）

## 三种调用模式详解

### 模式一：Manifest 获取
调用 `proxy_list_tools` 获取完整工具清单（含 name/description/inputSchema），供外部 LLM 自主选择。

```python
# 示例：获取 manifest 后由 LLM 决策
manifest = await mcp_client.call_tool("proxy_list_tools", {})
tools = manifest["tools"]
```

返回格式：`{"status": "ok", "data": {"format_version": "agora-v1", "tools": [...], "count": N}}`

### 模式二：直接执行
通过 `proxy_call(tool_name, arguments)` 精确定位并执行工具。

```python
# 精确匹配：tool_name 完全匹配
result = await mcp_client.call_tool("proxy_call", {
    "tool_name": "research_now",
    "arguments": '{"query": "量子计算"}'
})
```

支持前缀匹配，如 "minerva.research_now" 可匹配到 minerva 服务的 research_now 工具。

### 模式三：语义路由
通过 `agora_execute(query, mode)` 让系统自动匹配最佳工具。

```python
# auto 模式：级联执行 direct→recommend→auto_discover
result = await mcp_client.call_tool("agora_execute", {
    "query": "帮我搜索量子计算的最新论文",
    "mode": "auto"
})
```

三种 mode：
- `direct`：仅解析工具名直接匹配
- `recommend`：语义搜索 + 质量评分
- `auto`（默认）：先 direct，失败则 recommend，再失败则自动发现

## 完整接入示例

### Python Agent 接入
```python
import json
from mcp import ClientSession, StdioServerParameters

async def connect_to_agora():
    """通过 stdio 连接 Agora MCP 服务器"""
    server_params = StdioServerParameters(
        command="agora-mcp",
        args=[]
    )
    # 建立连接
    async with ClientSession(server_params) as session:
        # 1. 获取工具清单
        manifest = await session.call_tool("proxy_list_tools", {})
        print(f"可用工具: {manifest['data']['count']} 个")
        
        # 2. LLM 选择工具后直接调用
        result = await session.call_tool("proxy_call", {
            "tool_name": "research_now",
            "arguments": json.dumps({"query": "人工智能发展趋势"})
        })
        print(f"执行结果: {result}")
```

### SSE 连接（HTTP 方式）
```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async def connect_via_sse():
    async with sse_client("http://127.0.0.1:7431/sse") as (read, write):
        async with ClientSession(read, write) as session:
            manifest = await session.call_tool("proxy_list_tools", {})
            # ...
```

## 工具清单格式
`proxy_list_tools` 返回的每个工具条目包含：
- `name`: 工具在 Agora 中的注册名
- `description`: 工具功能描述
- `inputSchema`: JSON Schema 格式的入参描述
- `service_name`: 所属下游服务
- `original_name`: 工具在原服务中的名称

## 评测工具
项目提供 `eval_agent.py` 评测脚本，模拟外部 Agent 对 Agora 的全面接入评测：

```bash
cd packages/agora
uv run python eval_agent.py
```

覆盖 7 大场景 28 项测试：Manifest 获取、智能路由、直接执行、质量评分、边缘情况、端到端流程、自动注册。

## 注意事项
- 确保 Agora 已正确启动（`agora-mcp`/`agora-web`/SSE）
- 代理工具（proxy_call）需要下游服务已注册并连接可用
- manifest 中的 tools 列表随动态加载/卸载实时变化
