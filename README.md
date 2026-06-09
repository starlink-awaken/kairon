# kairon

> kairon 已从 25 包收敛至 16 包。agora/metaos/ecos/runtime/cockpit 已拆分为独立项目，agent-runtime/sharedbrain-bridge 等已归档。详见 `docs/live_inventory.md`

> Knowledge & Research Operating Stack — 16 包 Python monorepo

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)]()
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![lint](https://img.shields.io/badge/lint-0%20errors-brightgreen)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

kairon 是一个基于 uv workspace 的 Python 知识工程与研究栈，覆盖知识提取、本体推导、研究管线和桥接能力。

## 快速开始

```bash
# 安装所有包
uv sync

# 全量测试
make test

# 快速测试（跳过集成测试）
make test-fast

# Lint + 格式化
make lint
make format
```

## 项目结构

```
kairon/
├── packages/              # 16 个活跃 Python 包
│   ├── codeanalyze/       # 代码结构分析
│   ├── core-models/       # 核心数据模型（依赖基座）
│   ├── eidos/             # 知识建模 (7 MCP tools)
│   ├── forge/             # 工具与集市面
│   ├── health-profile/    # 健康摘要辅助
│   ├── iris/              # 研究/连接器支持
│   ├── kairon-lib-events/ # 事件原语
│   ├── kairon-observability/ # 可观测性辅助
│   ├── kairon-pipeline/   # 管线辅助
│   ├── kairon-plugin-sdk/ # 插件集成面
│   ├── kairon-utils/      # 共享工具层
│   ├── kos/               # 跨域搜索与检索 (26 tools)
│   ├── kronos/            # 摄取管线
│   ├── minerva/           # 深度研究与知识管线 (5 super-tools)
│   ├── ontoderive/        # 本体推导
│   └── sophia/            # 符号化研究运行时
├── Makefile               # 构建/测试/格式化
├── pyproject.toml         # 项目配置和依赖
├── CLAUDE.md              # Claude Code 入口
└── AGENTS.md              # 非 Claude Agent 入口
```

## 文档

| 文档 | 说明 |
|------|------|
| [docs/architecture_audit.md](docs/architecture_audit.md) | 架构审计 |
| [docs/governance_plan.md](docs/governance_plan.md) | 治理规划 |
| [docs/api_reference.md](docs/api_reference.md) | API 参考 |
| [CHANGELOG.md](CHANGELOG.md) | 变更日志 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |

## 依赖

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — 包管理器
- ruff — 格式化和 lint
- pytest — 测试框架

## License

MIT © [starlink-awaken](LICENSE)
