# MetaOS — 编排/治理层

决策门控、免疫监控、路由、数字资产引擎。

## CLI

```bash
metaos --help                  # 查看所有命令
metaos status                  # 体系健康度
metaos trace                   # 最近决策日志
metaos gate <decision_desc>    # 决策门控
metaos review <action> <exp> <act>  # 微粒复盘
metaos ssot-scan               # SSOT 覆盖扫描
```

## MCP

```bash
metaos-mcp                     # 启动 MCP stdio 服务 (JSON-RPC)
```

多 session 隔离版，每个 MCP 连接使用独立 H + token。
