# AGENTS.md — kairon

> Knowledge & Research Operating Stack: 31 包 Python monorepo

如果你不是 Claude Code，从这里开始。Claude Code 会自动读取 `CLAUDE.md`。

## 快速安装

```bash
uv sync             # 安装所有包依赖
make test           # 全量测试
make lint           # Ruff 检查
```

## 项目概览

kairon 是一个 31 包的 Python monorepo，托管在 `projects/kairon/`。
包间依赖通过 uv workspace 管理（详见 `pyproject.toml` `[tool.uv.workspace]`）。
**`core-models` 是整个 monorepo 的依赖基座**，9 个包直接依赖它。

5 大分组：
- **L1 知识工程** — eidos, ontoderive, kos, minerva, sophia, iris, ssot, forge, codeanalyze, kronos, metaos, cron-service
- **L2 集成** — sharedbrain-bridge, sharedbrain-standalone
- **L3 Agent** — agent-runtime, agent-hub, agora, llm-gateway, wksp **（零测试）**
- **Infra** — shared-lib, core-models, engine-core, observability, gc-engine, ecos
- **业务支撑** — eu-pricing, kaironcloud-billing, kairon-assistant, kairon-voice, symphony-protocol, pontus

## 架构文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 架构审计 | `docs/architecture_audit.md` | 2026-06-02，26 包覆盖 |
| 治理规划 | `docs/governance_plan.md` | Phase 1~4 目标 |
| 安全审计 | `docs/security-audit-report-phase2-red-team.md` | Red Team 报告 |

## CI

- **kairon 内部 CI**: `.github/workflows/ci.yml` — lint + codeanalyze 多版本测试
- **根工作区 CI**: `.github/workflows/pytest.yml` + `phase11-ci.yml` — kairon 全包测试

## 入口文档

| 受众 | 文档 |
|------|------|
| Claude Code | `CLAUDE.md` |
| 其他 Agent | 本文件 |
| 包配置 | `packages/*/pyproject.toml` |
| 测试运行 | `make test` / `make test-fast` |
