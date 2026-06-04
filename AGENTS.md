# AGENTS.md — kairon

> Knowledge & Research Operating Stack: 25 包 Python monorepo（原 31 包中的 6 包已归档）

如果你不是 Claude Code，从这里开始。Claude Code 会自动读取 `CLAUDE.md`。

## 快速安装

```bash
uv sync             # 安装所有包依赖
make test           # 全量测试
make lint           # Ruff 检查
```

## 项目概览

kairon 是一个 25 包的 Python monorepo，托管在 `projects/kairon/`。
包间依赖通过 uv workspace 管理（详见 `pyproject.toml` `[tool.uv.workspace]`）。
**`core-models` 是整个 monorepo 的依赖基座**，9 个包直接依赖它。

5 大分组：
- **L1 知识工程** — eidos, ontoderive, kos, minerva, sophia, iris, ssot, forge, codeanalyze, kronos, metaos, cron-service
- **L2 集成** — sharedbrain-bridge
- **L3 Agent** — agent-runtime, agora, llm-gateway, wksp
- **Infra** — shared-lib, core-models, engine-core, ecos
- **业务支撑** — kaironcloud-billing, kairon-assistant, kairon-voice, symphony-protocol

**已归档（原 31 包中消失的 6 包）**：sharedbrain-standalone, agent-hub, observability, gc-engine, eu-pricing, pontus（功能已合并或未实现）

## 架构文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 架构审计 | `docs/architecture_audit.md` | 2026-06-02 |
| 治理规划 | `docs/governance_plan.md` | Phase 1~4 目标 |
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
