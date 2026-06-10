# AGENTS.md — kairon

> Knowledge & Research Operating Stack: 16 个 live installable Python packages · 5+3+1 架构 L2 引擎面

如果你不是 Claude Code，从这里开始。Claude Code 会自动读取 `CLAUDE.md`。

## 快速安装

```bash
uv sync             # 安装所有包依赖
make test           # 全量测试
make lint           # Ruff 检查
```

## 5+3+1 架构位置

kairon 是 **L2 知识引擎面**，与以下项目协同：

```
L3 cockpit ── 统一入口 (CLI + Web)
   │
I0 agora ──── MCP Hub (独立项目)
   │
L2 ┌ omo · 治理面
   ├ kairon · 引擎面 (本仓库)
   ├ metaos · 编排引擎
   └ gbrain · 知识数据库
   │
L1 runtime ── 运行时基础设施
   │
L0 ┌ protocols · 协议 YAML
   └ ecos · SSB 协议核心
```

## 包清单 (16 live installable packages)

### 基础与共用 primitives (7)
- `core-models`
- `health-profile`
- `kairon-lib-events`
- `kairon-observability`
- `kairon-pipeline`
- `kairon-plugin-sdk`
- `kairon-utils`

### 知识与研究引擎 (8)
- `codeanalyze`
- `eidos`
- `iris`
- `kos`
- `kronos`
- `minerva`
- `ontoderive`
- `sophia`

### 对外能力面 (1)
- `forge`

> 当前 live inventory 以 `packages/*/pyproject.toml` 为准。详见 [docs/live_inventory.md](/Users/xiamingxing/Workspace/projects/kairon/docs/live_inventory.md:1)。

## 测试与 CI

- 框架: pytest + uv
- `make test` — 全量测试 (packages/*/)
- `make test-fast` — 仅单元测试
- `make test-diff` — 仅测试修改的包
- `make lint` — Ruff 检查
- 覆盖率门禁: 70%

## 已归档 (P28-W2 ~ P31-W0)

| 包 | 去向 |
|----|------|
| agora | → `projects/agora/` (I0 MCP Hub) |
| metaos | → `projects/metaos/` (L2 编排引擎) |
| ecos | → `projects/ecos/` (L0 SSB 协议) |
| wksp | → `projects/cockpit/` (L3 统一入口) |
| cron-service | → `projects/runtime/` (L1 调度器) |
| agent-runtime | → `projects/runtime/` + `projects/cockpit/` |
| kairon-assistant | → `projects/_archived/` |
| kairon-voice | → `projects/_archived/` |
| kaironcloud-billing | → `projects/_archived/` |

## 当前边界说明

- `kairon` 现在主要承担知识引擎职责，不再是完整 runtime/gateway/bridge 大一统仓库。
- LLM gateway 正在收敛到 `projects/aetherforge/`，不要再把 `llm-gateway` 当成 live package truth。
- Agora POC_SERVICES 路由表中仍保留 `sot-bridge`、`sot-bridge-persona`、`protocols-layer` 等历史 BOS URI（指向 poc/stdio 传输层），它们不是当前 `kairon` live installable package。
- 架构与跨项目边界请优先看：
  - [docs/architecture_audit.md](/Users/xiamingxing/Workspace/projects/kairon/docs/architecture_audit.md:1)
  - [docs/agora_route_drift_audit.md](/Users/xiamingxing/Workspace/projects/kairon/docs/agora_route_drift_audit.md:1)
  - [docs/cross_project_boundary_audit.md](/Users/xiamingxing/Workspace/projects/kairon/docs/cross_project_boundary_audit.md:1)


## BOS Services

kairon 通过 Agora Service Mesh 对外提供的 BOS URI 服务。
Agent 通过 `resolve_bos_uri()` 或 `read_resource()` 调用。

### 记忆域 (memory)
- `bos://memory/kos/search` — KOS 跨域语义搜索 (poc, stdio)
- `bos://memory/kos/query` — KOS 精确查询 (poc, stdio)
- `bos://memory/kronos/ingest` — Kronos 知识摄取 (poc, stdio)

### 分析域 (analysis)
- `bos://analysis/minerva/research` — Minerva 深度研究 (poc, stdio)
- `bos://analysis/minerva/draft` — Minerva 草稿 (poc, stdio)
- `bos://analysis/minerva/audit` — Minerva 审计 (poc, stdio)
- `bos://analysis/ontoderive/align` — Ontoderive 文档对齐 (poc, stdio)
- `bos://analysis/codeanalyze/scan` — CodeAnalyze 代码扫描 (poc, stdio)
- `bos://analysis/eidos/validate` — Eidos Schema 校验 (poc, stdio)

### 人格域 (persona)
- `bos://persona/sot-bridge/` — SSOT 桥接 (poc, stdio)

### 治理域 (omo)
- `bos://omo/eidos/pipeline` — Eidos 多工具编排链 (poc, stdio)