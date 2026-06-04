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

5 大分组：
- **L1 知识工程** — eidos, ontoderive, kos, minerva, sophia, iris, ssot, forge, codeanalyze, kronos, metaos, cron-service
- **L2 集成** — sharedbrain-bridge, sharedbrain-standalone
- **L3 Agent** — agent-runtime, agent-hub, agora, llm-gateway, wksp
- **Infra** — shared-lib, core-models, engine-core, observability, gc-engine, ecos
- **业务支撑** — eu-pricing, kaironcloud-billing, kairon-assistant, kairon-voice, symphony-protocol, pontus

## 入口文档

| 受众 | 文档 |
|------|------|
| Claude Code | `CLAUDE.md` |
| 其他 Agent | 本文件 |
| 包配置 | `packages/*/pyproject.toml` |
| 测试运行 | `make test` / `make test-fast` |
