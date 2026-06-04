# agent-runtime — MCP Agent Execution Runtime

运行和管理 MCP agent 的运行时环境，支持 FastAPI HTTP 服务和 CLI 模式。

## CLI

```bash
agent-runtime --help
agent-runtime --server     # 启动 HTTP 服务 (端口 8082)
agent-runtime --mcp        # 启动 MCP stdio 服务
```

## MCP Tools

- `agent_mcp_tools` — 列出所有可用 MCP 工具
- `agent_mcp_execute` — 远程执行 MCP 工具调用
