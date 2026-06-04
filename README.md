# kairon

> Knowledge & Research Operating Stack — 31 包 Python monorepo

kairon 是一个基于 uv workspace 的 Python 知识工程与研究栈，包含知识提取、本体推导、MCP 服务、Agent 运行时、LLM 网关等能力。

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
├── packages/              # 31 个 Python 包
│   ├── eidos/             # 知识建模 (7 MCP tools)
│   ├── kos/               # 搜索索引 (26 tools)
│   ├── agora/             # MCP 服务发现 + 断路器
│   ├── minerva/           # 推理引擎 (5 super-tools)
│   ├── agent-runtime/     # Agent 执行引擎
│   ├── core-models/       # 核心数据模型（依赖基座）
│   ├── shared-lib/        # 共享工具库 (~120 模块)
│   └── ...                # 见 CLI 文档
├── Makefile               # 构建/测试/格式化
├── pyproject.toml         # 项目配置和依赖
├── CLAUDE.md              # Claude Code 入口
└── AGENTS.md              # 非 Claude Agent 入口
```

详细包列表和架构说明见 [CLAUDE.md](CLAUDE.md)。

## 依赖

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — 包管理器
- ruff — 格式化和 lint
- pytest — 测试框架

## License

MIT
