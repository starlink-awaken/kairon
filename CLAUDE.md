# CLAUDE.md — kairon

> 知识工程与研究栈 · 20 包 Python monorepo（治理中，原 31 包名册中的 13 包已拆出/归档：6 包早期 + kairon-assistant/kairon-voice 于 P28-W2 + kaironcloud-billing 于 P28-W6 + metaos/cron-service/wksp 于 P30 拆出 + ecos 于 P31-W0 拆出）
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

## 包结构（20 包）

### L1 — 知识工程核心（10 包）

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
| ~~metaos~~ | **已拆出 (P30-W1)** | 移至 `projects/metaos/` 独立项目（编排引擎） |

### L2 — 集成层（1 包）

| 包 | 路径 | 说明 |
|----|------|------|
| sharedbrain-bridge | `packages/sharedbrain-bridge/` | × SharedBrain 桥接（EU/免疫/同步） |
| ~~sharedbrain-standalone~~ | 已归档 | 代码合入 sharedbrain-bridge |

### L3 — Agent 层（4 包）

| 包 | 路径 | 说明 |
|----|------|------|
| agent-runtime | `packages/agent-runtime/` | Agent 执行引擎（原 agentmesh Engine） |
| agent-hub | `packages/agent-hub/` | Agent 注册中心 |
| agora | `packages/agora/` | MCP 服务发现 + 代理 + 断路器（7430/7431） |
| llm-gateway | `packages/llm-gateway/` | LLM 路由 + 配额管理 |
| ~~wksp~~ | **已拆出 (P30-W1)** | 移至 `projects/cockpit/` 独立项目（CLI + Web UI 统一研究驾驶舱，吸收 hermes-console 为 web/） |

> 注：kairon-assistant / kairon-voice 已于 P28-W2 归档（见下方"已归档（P28-W2）"段）。

### L4/Infra — 支撑层

| 包 | 路径 | 说明 |
|----|------|------|
| shared-lib | `packages/shared-lib/` | 共享工具库（273 文件，26 测试） |
| core-models | `packages/core-models/` | 核心数据模型 |
| engine-core | `packages/engine-core/` | 引擎核心 |
| observability | `packages/observability/` | 可观测性 |
| gc-engine | `packages/gc-engine/` | 垃圾回收引擎 |
| ~~ecos~~ | **已拆出 (P31-W0)** | 移至 `projects/ecos/` 独立项目（SSB 协议 + 涌现计算，v3 0 依赖 0 被依赖） |
| cron-service | `packages/cron-service/` | 定时任务调度（P30-M2.1 物理迁移至 runtime，目录占位待清理） |
| eu-pricing | `packages/eu-pricing/` | EU 定价 |
| ~~kaironcloud-billing~~ | **已归档 (P28-W6)** | 1 软依赖（agora try/except）|
| ~~kairon-assistant~~ | **已归档 (P28-W2)** | 0 外部 import、whisper 缺依赖 |
| ~~kairon-voice~~ | **已归档 (P28-W2)** | 0 外部 import、自包含 |
| symphony-protocol | `packages/symphony-protocol/` | 协议层 |
| pontus | `packages/pontus/` | Pontus 模块 |

### 已归档（P28-W2 · 2026-06-05）

| 原包 | 归档位置 | 原因 |
|------|---------|------|
| kairon-assistant | `projects/_archived/kairon-archived-pkg-kairon-assistant-2026-06-05/kairon-assistant/` | 0 外部 import、whisper 缺依赖、3 tests、孤儿包 |
| kairon-voice | `projects/_archived/kairon-archived-pkg-kairon-voice-2026-06-05/kairon-voice/` | 0 外部 import、自包含、3 tests、孤儿包 |

### 已归档（P28-W6 · 2026-06-05）

| 原包 | 归档位置 | 原因 |
|------|---------|------|
| kaironcloud-billing | `projects/_archived/kairon-archived-pkg-kaironcloud-billing-2026-06-05/kaironcloud-billing/` | 1 软依赖（agora/router.py:406 try/except）、5 tests、28 src、孤儿包 |

### 已归档（former agentmesh）

agentmesh 的 5 个子系统已 100% 迁移至 kairon：

| 原 agentmesh 组件 | kairon 对应包 |
|-------------------|---------------|
| Engine | `agent-runtime` |
| Agent Hub | `agent-hub` |
| MCP 网关 | `agora` |
| Orchestrator | `llm-gateway` |
| Forge | `forge` |

### 已拆出（P30-W1 · 2026-06-06）

| 原包 | 新位置 | 原因 |
|------|--------|------|
| metaos | `projects/metaos/` | 编排引擎（决策门控/免疫/路由），非知识工程功能，拆为独立项目（v3 架构方案） |
| wksp | `projects/cockpit/` | 工作区管理 + 吸收 hermes-console 为 web/，统一为 cockpit 独立项目 |

### 已拆出（P31-W0 · 2026-06-06）

| 原包 | 新位置 | 原因 |
|------|--------|------|
| ecos | `projects/ecos/` | L0 协议编织层（SSB 协议 + 涌现计算）。v3 终态标注"0 依赖、0 被依赖"，纯自包含协议核心，6,288 行源码独立。P30 决策文档未列，补做。 |

## 架构主线

### 依赖根：core-models

`core-models` 是整个 monorepo 的依赖基座，9 个包直接依赖它：

```
agora, codeanalyze, eidos, eu-pricing, kronos,
minerva, ontoderive, sharedbrain-bridge, sharedbrain-standalone
```

包间交叉依赖较少，多数通过 core-models 间接耦合。

### 成熟度梯队

| 梯队 | 包 | 特征 |
|------|-----|------|
| 🟢 成熟 | agora (v2.0.0), minerva (v0.11.0), forge (v1.3.0), ssot (v1.0.0) | 独立版本号，测试完备 |
| 🟡 发展中 | kos (v2.0.0), ontoderive (v3.6.4), sophia (v0.2.1) | 活跃迭代 |
| 🔴 早期 | core-models (v0.1.0), shared-lib (v0.1.0) | 快速变化，接口不稳定 |
| ⚪ 待评估 | kairon-assistant, kairon-voice | 来自外部集成，需验证 |

### LLM 统一

4 路 LLM 抽象已统一为 **`llm-gateway`**（2026-06-04）：

| 旧实现 | 适配器 | 状态 |
|--------|--------|------|
| ontoderive `BaseProvider` | `OntoderiveProvider` | ✅ |
| minerva `OpenAICompatibleClient` | `MinervaProvider` | ✅ |
| ssot `LLMBackend` | `SSOTProvider` | ✅ |

新代码优先使用 `from llm_gateway.providers.legacy_*_adapter import *`。

## 测试惯例

- **框架**: pytest + uv
- **运行**: `make test`（遍历 `packages/*/` 执行 `python3 -m pytest tests/ -q`）
- **快速模式**: `make test-fast`（跳过 `tests/integration/` 和 `tests/benchmarks/`）
- **配置**: 根 `pyproject.toml` 中 `[tool.pytest.ini_options]` → `testpaths = ["packages/*/tests"]`；各包另有独立 `[tool.pytest.ini_options]`
- **命名**: 统一 `test_*.py` 模式
- **conftest**: 6 个包有 conftest.py（agora, engine-core, eu-pricing, kos, minerva, ontoderive）— *2026-06-06: ecos 拆出后移除*
- **覆盖率门禁**: fail_under 70%
- **wksp 是唯一无 tests/ 目录的包** — 测试覆盖为零
  - *2026-06-06 更新：wksp 已拆出至 `projects/cockpit/`，kairon 改为 23 包（移除 wksp）*

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
| Lint 状态 | **`ruff check packages/` → 0 errors**（2026-06-04 归零） |

## 关键文件

| 文件 | 作用 |
|------|------|
| `pyproject.toml` | SSOT: 包清单、依赖、工具配置、mypy 路径 |
| `Makefile` | 测试/格式化/清理命令 |
| `packages/*/pyproject.toml` | 各包独立配置和依赖 |
| `packages/*/tests/` | 各包测试目录 |
| `docs/architecture_audit.md` | 架构审计报告（2026-06-02） |
| `docs/governance_plan.md` | 治理规划 |
| `docker/docker-compose.e2e.yml` | E2E 测试环境编排 |

## CI

kairon 拥有独立于根工作区的 CI 流水线：

| 配置 | 路径 | 说明 |
|------|------|------|
| CI | `.github/workflows/ci.yml` | lint + codeanalyze 多版本矩阵（3.10–3.13） |

根工作区的 `.github/workflows/` 有 11 个全局 workflow（pytest.yml, phase11-ci.yml, integration.yml 等），与 kairon 内部 CI 相互独立。

## Gotchas

1. **uv 是唯一包管理器** — 不要用 pip/poetry，`uv sync` 安装，`uv add <pkg>` 添加
2. **ontoderive 有 1,920 JSON 推导日志** — `_derivation_logs/` 在 git 中但不是核心代码
3. **agora 依赖运行中服务** — 测试需要 MCP 端点，部分测试跳过
4. **mypy 严格模式** — namespace_packages 需要显式配置 mypy_path
5. **包间依赖通过 workspace 引用** — `[tool.uv.sources]` 定义内部包来源
6. **wksp 包零测试** — `packages/wksp/` 没有 `tests/` 目录
   - *2026-06-06：wksp 已拆出至 `projects/cockpit/`，kairon 不再 ship wksp*
7. **根目录遗留修复脚本** — 约 8 个 `_fix_*.py` 脚本（fix_imports, mypy_suppress 等），是 mypy 迁移残留
8. **CI 薄弱** — kairon 内部 CI 仅覆盖 lint + codeanalyze 单包测试，无全包测试门禁
