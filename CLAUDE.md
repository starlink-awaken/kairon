# CLAUDE.md — kairon

> 知识工程与研究栈 · 31 包 Python monorepo
> 根工作区文档：`../CLAUDE.md`（全局）、`../AGENTS.md`（开发指南）、`../LAYER-INDEX.md`（架构分层）

---

## 快速开始

```bash
# 安装依赖
uv sync

# 全量测试（遍历所有包）
make test

# 快速测试（跳过 integration/benchmarks）
make test-fast

# Lint + 格式化
make lint
make format
```

## 包结构（31 包）

### L1 — 知识工程核心

| 包 | 路径 | 说明 |
|----|------|------|
| eidos | `packages/eidos/` | 7 MCP 工具 |
| ontoderive | `packages/ontoderive/` | 本体推导（含 1,920 JSON 推导日志） |
| kos | `packages/kos/` | KOS 搜索索引（26 tools） |
| minerva | `packages/minerva/` | 5 super-tools |
| sophia | `packages/sophia/` | 8 tools |
| iris | `packages/iris/` | 8 tools |
| ssot | `packages/ssot/` | 单一事实源（6 tools） |
| forge | `packages/forge/` | 89 tools（无 MCP @tool） |
| codeanalyze | `packages/codeanalyze/` | 代码分析 |
| kronos | `packages/kronos/` | 9 tools |
| metaos | `packages/metaos/` | 基础工具（sys.path 已修复） |

### L2 — 集成层

| 包 | 路径 | 说明 |
|----|------|------|
| sharedbrain-bridge | `packages/sharedbrain-bridge/` | × SharedBrain 桥接（EU/免疫/同步） |
| sharedbrain-standalone | `packages/sharedbrain-standalone/` | SharedBrain 独立运行壳（零测试） |

### L3 — Agent 层

| 包 | 路径 | 说明 |
|----|------|------|
| agent-runtime | `packages/agent-runtime/` | Agent 执行引擎（原 agentmesh Engine） |
| agent-hub | `packages/agent-hub/` | Agent 注册中心 |
| agora | `packages/agora/` | MCP 服务发现 + 代理 + 断路器（7430/7431） |
| llm-gateway | `packages/llm-gateway/` | LLM 路由 + 配额管理 |
| wksp | `packages/wksp/` | 工作区管理 |

### L4/Infra — 支撑层

| 包 | 路径 | 说明 |
|----|------|------|
| shared-lib | `packages/shared-lib/` | 共享工具库（273 文件，26 测试） |
| core-models | `packages/core-models/` | 核心数据模型 |
| engine-core | `packages/engine-core/` | 引擎核心 |
| observability | `packages/observability/` | 可观测性 |
| gc-engine | `packages/gc-engine/` | 垃圾回收引擎 |
| ecos | `packages/ecos/` | 生态系统管理 |
| cron-service | `packages/cron-service/` | 定时任务调度 |
| eu-pricing | `packages/eu-pricing/` | EU 定价 |
| kaironcloud-billing | `packages/kaironcloud-billing/` | 云计费 |
| kairon-assistant | `packages/kairon-assistant/` | 助手 |
| kairon-voice | `packages/kairon-voice/` | 语音 |
| symphony-protocol | `packages/symphony-protocol/` | 协议层 |
| pontus | `packages/pontus/` | Pontus 模块 |

### 已归档（former agentmesh）

agentmesh 的 5 个子系统已 100% 迁移至 kairon：

| 原 agentmesh 组件 | kairon 对应包 |
|-------------------|---------------|
| Engine | `agent-runtime` |
| Agent Hub | `agent-hub` |
| MCP 网关 | `agora` |
| Orchestrator | `llm-gateway` |
| Forge | `forge` |

## 测试惯例

- **框架**: pytest + uv
- **运行**: `make test`（遍历 `packages/*/` 执行 `python3 -m pytest tests/ -q`）
- **快速模式**: `make test-fast`（跳过 `tests/integration/` 和 `tests/benchmarks/`）
- **配置**: `pyproject.toml` 中的 `[tool.pytest.ini_options]` → `testpaths = ["packages/*/tests"]`
- **命名**: `test_*.py` 模式

## 编码规范

| 规则 | 值 |
|------|-----|
| Python 版本 | 3.13+ |
| 行宽 | 120 |
| 格式化 | `ruff format` (双引号) |
| 检查 | `ruff check`（select: E,F,W,I,N,UP,S,PLE,RUF100） |
| 导入排序 | isort（通过 ruff 启用） |
| 自定义忽略 | S101,S603,S607,S108,S110,S314,S608,E402,E501,SIM115,N806,N813,UP047 |
| 类型检查 | mypy（namespace_packages + explicit_package_bases） |
| 覆盖率 | fail_under 70%（`[tool.coverage.report]`） |
| 包管理 | uv（非 pip/poetry） |

## 关键文件

| 文件 | 作用 |
|------|------|
| `pyproject.toml` | SSOT: 包清单、依赖、工具配置、mypy 路径 |
| `Makefile` | 测试/格式化/清理命令 |
| `packages/*/pyproject.toml` | 各包独立配置和依赖 |
| `packages/*/tests/` | 各包测试目录 |

## Gotchas

1. **uv 是唯一包管理器** — 不要用 pip/poetry，`uv sync` 安装，`uv add <pkg>` 添加
2. **ontoderive 有 1,920 JSON 推导日志** — `_derivation_logs/` 在 git 中但不是核心代码
3. **agora 依赖运行中服务** — 测试需要 MCP 端点，部分测试跳过
4. **mypy 严格模式** — namespace_packages 需要显式配置 mypy_path
5. **包间依赖通过 workspace 引用** — `[tool.uv.sources]` 定义内部包来源
