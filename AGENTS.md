# AGENTS.md — kairon

> Knowledge & Research Operating Stack: 16 个 live installable Python packages · 5+3+1 架构 L2 引擎面

如果你不是 Claude Code，从这里开始。Claude Code 会自动读 `CLAUDE.md`。

## 快速安装

```bash
uv sync             # 安装所有包依赖
make test           # 全量测试
make test-fast      # 单元测试 (跳过集成/基准)
make test-diff      # 差异测试 (仅修改的包)
make test-e2e       # E2E 测试 (Postgres+gbrian+kairon 容器化)
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

> 当前 live inventory 以 `packages/*/pyproject.toml` 为准。详见 [docs/live_inventory.md](docs/live_inventory.md)。

## 测试与 CI

- 框架: pytest + uv
- `make test` — 全量测试 (packages/*/)
- `make test-fast` — 仅单元测试
- `make test-diff` — 仅测试修改的包
- `make lint` — Ruff 检查
- `make typecheck` / `uv run mypy` — mypy strict 试点 (当前 kairon-lib-events / health-profile / kairon-pipeline / plugin-sdk / sophia 等包已启用)
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
  - [docs/architecture_audit.md](docs/architecture_audit.md)
  - [docs/agora_route_drift_audit.md](docs/agora_route_drift_audit.md)
  - [docs/cross_project_boundary_audit.md](docs/cross_project_boundary_audit.md)


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


## Bus foundation (跨仓依赖)

本项目通过 `kairon_pipeline/bus_adapter.py` 接入 [bus-foundation](https://github.com/starlink-awaken/omostation/tree/main/projects/bus-foundation) (R66 独立仓):

```python
from bus_foundation import publish, subscribe, schedule, BusEnvelope
```

- **Public API**: `publish` / `subscribe` / `schedule` / `BusEnvelope` / `EventType`
- **零 agora 依赖**: bus-foundation 是 standalone Python package
- **公共 API 冻结 6 月** (从 2026-06-12 起)
- **L0 协议层提升**: 评估 R70-R72, 决策 **Path C: Defer Indefinitely** (见 `projects/bus-foundation/docs/ADR-0003-no-l0-promotion.md`)
- **修改 bus-foundation**: 提 PR 到 `projects/bus-foundation/`, 改完跑该项目的 `uv run pytest -q` 验证

> 不要直接 import `agora.bus` (那是 backward-compat shim)。新代码用 `from bus_foundation import ...`。
