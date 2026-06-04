# Workspace 架构文档

> 4+1+3 架构 — 自我 · 协作 · 能力 · 契约 + 治理 · 抗熵 · 价值

---

## 架构图示

```
┌─────────────────────────────────────────────────────┐
│                    P0 产品界面层                      │
│               workspace CLI (cli.py)                 │
│       用户唯一入口 · 所有层的翻译代理                 │
├─────────────────────────────────────────────────────┤
│  L4  自我层  │  profile (身份档案 / persona)          │
├──────────────┼───────────────────────────────────────┤
│  L3  协作层  │  Agent 标记、跨 Agent 工作流          │
├──────────────┼───────────────────────────────────────┤
│  L2  能力层  │  research (研究引擎调用 + 存储管理)   │
├──────────────┼───────────────────────────────────────┤
│  L1  契约层  │  contracts (WorkspaceObject / Schema) │
├──────────────┴───────────────────────────────────────┤
│  X1 治理     │  governance (arcnode-* 委派)          │
│  X2 抗熵     │  archive / quarantine / 保鲜归档       │
│  X3 价值堆栈 │  heatmap / half-life / freshness      │
└─────────────────────────────────────────────────────┘
```

---

## P0 产品界面层

**Workspace CLI** 定义在 `cli.py`（~330 行），是所有架构层与用户之间的翻译层。用户通过 workspace 命令与系统交互，CLI 负责：

- 解析命令、路由到对应 handler
- 调用 `storage.py`（SQLite 封装）读写数据
- 委派外部工具（minerva 研究引擎、ollama 降级）
- 使用 `rich` 库渲染终端界面（Panel、Table、Progress）
- 委派 governance 到 `arcnode-*` 脚本
- 委派 dashboard 到 `agora` Web 服务
- 以 FastMCP server 暴露能力（`scripts/wksp_mcp.py`，可通过 `workspace mcp` 启动）

**核心原则**：CLI 不做深层逻辑，只做翻译和编排。研究引擎由 `minerva` CLI 提供，存储由 `storage.py` 提供，治理由独立脚本提供。

---

## 各层覆盖度现状

| 层 | 状态 | 说明 |
|----|------|------|
| **L4 自我层** | ✅ 基础 | `workspace profile` 读/编辑 `~/.workspace/persona.yaml` |
| **L3 协作层** | ✅ 基础 | `workspace research --agent <name>` 标记处理 Agent |
| **L2 能力层** | ✅ 完整 | `workspace research` 全命令集，含发起/追问/追问工作流/健康报告/发布/对比/合并/提炼/归档/隔离/备份恢复 |
| **L1 契约层** | ✅ 基础 | `workspace contracts validate/list/export-research/export identity/export event` |
| **X1 治理** | ✅ 基础 | `workspace governance calibrate/rechain/evolve/report/drift-check/validate`，委派到 `arcnode-*` |
| **X2 抗熵** | ✅ 完整 | archive / quarantine 机制，数据保鲜与异常隔离；backup/restore 全量备份 |
| **X3 价值堆栈** | ✅ 完整 | `--heatmap` 活跃度热力图，`--health` 半衰期健康报告，`compute_half_life()` 半衰期计算 |

---

## 项目结构

```
wksp/
├── cli.py                 # P0 界面层 ~330 行，命令路由与分发
├── storage.py             # SQLite 持久化 ~770 行，研究/事件/关系/发布
├── __init__.py            # 包标识
├── __main__.py            # python -m wksp 入口
├── pyproject.toml         # 构建配置 (setuptools + pytest + ruff + pyright + bandit)
├── Makefile               # 开发任务快捷入口（lint/test/format/clean）
├── .editorconfig          # 跨编辑器编码风格统一
├── .pre-commit-config.yaml # 自动化代码质量门禁
├── .gitignore
├── LICENSE                # MIT 协议
├── CHANGELOG.md           # 版本变更记录
├── README.md              # 项目说明
├── CONTRIBUTING.md        # 贡献指南
├── CODE_OF_CONDUCT.md     # 贡献者行为准则
├── SECURITY.md            # 安全策略
├── commands/              # 子命令 handler 模块（按命令分离）
│   ├── base.py            # 公共辅助函数（_run_ollama、_strip_thinking、_panel 等）
│   ├── research.py        # research 全命令集（含 follow-up/health/backup-restore）
│   ├── quickstart.py      # 快速开始向导（含 --fix 自动修复模式）
│   ├── mcp.py             # MCP server 启动/工具列表命令
│   ├── status.py          # 工作台仪表盘（含 --watch 模式）
│   └── contracts.py       # 契约验证/导出
├── scripts/               # 项目内脚本（通过软链兼容 Hermes cron，见 scripts/INDEX.md）
│   ├── wksp_mcp.py        # FastMCP server 实现
│   ├── agora-register-workspace  # Agora 注册
│   ├── arcnode-*          # 架构治理脚本（dep-aging/drift-check/evolve 等）
│   ├── freshness-watch*   # 研究保鲜监控
│   ├── health-monitor     # 系统健康监控
│   ├── product-health     # 产品健康度计算
│   ├── auto-archive       # 自动归档
│   ├── dual-baseline      # 双基线对比
│   ├── install-hermes-bridge.sh  # 桥接安装
│   ├── workspace-commit.sh       # 批量 git 提交
│   └── INDEX.md            # 完整脚本索引
├── tests/                 # 39 个测试文件，覆盖 CLI 功能与存储层
│   ├── conftest.py        # 测试配置 + MockDataAccess
│   ├── test_cli_*.py      # CLI 功能测试
│   ├── test_storage_*.py  # 存储层测试
│   └── test_e2e_journey.py  # 端到端旅程测试
├── .github/               # CI/CD 工作流
│   └── workflows/
│       └── ci.yml         # lint / type-check / test (3.10–3.13) / security
└── docs/
    ├── ARCHITECTURE.md
    ├── COMMANDS.md
    └── PLAN.md
```

---

## 解耦说明：scripts/ 软链机制

`scripts/` 目录下的多个脚本是独立可执行文件，通过软链兼容 Hermes Agent 的 cron 机制：

```
~/.hermes/scripts/product-health  →  ~/Workspace/wksp/scripts/product-health
~/.hermes/scripts/freshness-watch →  ~/Workspace/wksp/scripts/freshness-watch
```

**设计意图**：脚本可以被两种方式调用：
1. **通过 CLI**：`workspace product-health` 委派执行
2. **通过 Hermes cron**：定时任务以 `product-health` 直接执行

这种方式避免了将调度逻辑耦合到 CLI 中，脚本本身可独立测试和演化。

**`storage.py`** 同样与 CLI 解耦 — 它是纯 SQLite 封装，不依赖 `rich` 或其他 CLI 库，可在其他 Python 脚本中直接 import 使用。
