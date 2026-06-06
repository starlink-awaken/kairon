# AGENTS.md — kairon

> Knowledge & Research Operating Stack: 30 包 Python monorepo（2026-06-06 shared-lib 拆出 5 子包）

如果你不是 Claude Code，从这里开始。Claude Code 会自动读取 `CLAUDE.md`。

## 快速安装

```bash
uv sync             # 安装所有包依赖
make test           # 全量测试
make lint           # Ruff 检查
```

## 项目概览

kairon 是一个 30 包的 Python monorepo，托管在 `projects/kairon/`。
包间依赖通过 uv workspace 管理（详见 `pyproject.toml` `[tool.uv.workspace]`）。
**`core-models` 是整个 monorepo 的依赖基座**，当前 checkout 中 8 个活跃包直接依赖它。

6 大分组：
- **L0 基础** — kairon-lib-events, kairon-utils, kairon-plugin-sdk, kairon-observability, kairon-pipeline（2026-06-06 从 shared-lib 拆出）
- **L1 知识工程** — eidos, ontoderive, kos, minerva, sophia, iris, ssot, forge, codeanalyze, kronos, metaos, cron-service
- **L2 集成** — sharedbrain-bridge, llm-gateway
- **L3 Agent** — agent-runtime, agora, llm-gateway
- **Infra** — shared-lib, core-models, engine-core
- **业务支撑** — kaironcloud-billing, symphony-protocol
- **P28-W2 已归档** — kairon-assistant, kairon-voice（2026-06-05 移入 `projects/_archived/`）

当前 checkout 之外，近期文档和历史中仍引用过 `agent-hub`、`eu-pricing`、`gc-engine`、`observability`、`pontus`、`sharedbrain-standalone`。不要默认这些包在当前树中仍然存在，先以 live 目录为准。

## 架构文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 架构审计 | `docs/architecture_audit.md` | 2026-06-04 v2 |
| 跨项目接缝 | `docs/cross_project_boundary_audit.md` | kairon / agentmesh / SharedBrain / .omo |
| 整改路线 | `docs/governance_plan.md` | P0 / P1 / P2 |
| 债务台账 | `.omo/kairon-debt-registry.yaml` | 实时债务追踪 |

## CI

- **kairon 内部 CI**: `.github/workflows/ci.yml` — lint + codeanalyze + test-all
- **根工作区 CI**: `.github/workflows/pytest.yml` + `phase11-ci.yml`

## 入口文档

| 受众 | 文档 |
|------|------|
| Claude Code | `CLAUDE.md` |
| 其他 Agent | 本文件 |
| 包配置 | `packages/*/pyproject.toml` |
| 测试运行 | `make test` / `make test-fast` |
