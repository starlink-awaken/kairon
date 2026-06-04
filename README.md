# kairon

> Knowledge & Research Operating Stack — 25 包 Python monorepo（以当前 checkout 为准）

kairon 是一个基于 uv workspace 的 Python 知识工程与研究栈，覆盖知识提取、本体推导、MCP 服务、Agent 运行时、研究管线和桥接能力。

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
├── packages/              # 25 个活跃 Python 包
│   ├── eidos/             # 知识建模 (7 MCP tools)
│   ├── kos/               # 搜索索引 (26 tools)
│   ├── agora/             # MCP 服务发现 + 断路器
│   ├── minerva/           # 推理引擎 (5 super-tools)
│   ├── agent-runtime/     # Agent 执行引擎
│   ├── core-models/       # 核心数据模型（依赖基座）
│   ├── shared-lib/        # 共享工具库 (~120 模块)
│   └── ...                # 详见 docs/architecture_audit.md
├── Makefile               # 构建/测试/格式化
├── pyproject.toml         # 项目配置和依赖
├── CLAUDE.md              # Claude Code 入口
└── AGENTS.md              # 非 Claude Agent 入口
```

当前包清单、跨项目接缝和整改路线见：

- [docs/architecture_audit.md](docs/architecture_audit.md)
- [docs/cross_project_boundary_audit.md](docs/cross_project_boundary_audit.md)
- [docs/governance_plan.md](docs/governance_plan.md)

## 依赖

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — 包管理器
- ruff — 格式化和 lint
- pytest — 测试框架

## License

MIT
