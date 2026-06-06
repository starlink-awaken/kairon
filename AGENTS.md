# AGENTS.md — kairon

> Knowledge & Research Operating Stack: 25 包 Python monorepo · 5+3+1 架构 L2 引擎面

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

## 包清单 (25 包)

### L0 基础 (5 包, 从 shared-lib 拆出)
- kairon-lib-events, kairon-utils, kairon-plugin-sdk, kairon-observability, kairon-pipeline

### L1/2 知识工程 (20 包)
- eidos (35K), kos (14K), minerva (25K), ontoderive (6K), sophia (1.4K), kronos, iris
- ssot (14K), forge (8K), codeanalyze, core-models (1.6K), llm-gateway, llm-gateway-kernel
- shared-lib, engine-core, sharedbrain-bridge, health-profile
- symphony-protocol, sot-bridge, protocols-layer

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
