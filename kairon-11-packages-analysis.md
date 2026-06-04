# Kairon 10 包分析 (observability → wksp)

> 说明：用户提及 11 个包，实列 10 个 (observability→wksp，中间无缺)。以下逐包分析。

---

## 1. observability

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | observability v0.1.0 — SLO tracking, alerts, metrics, health checks |
| **源文件数/代码行/测试** | 6 src / 1,560 LOC / 1 test file (393 LOC) |
| **核心模块/入口** | `src/observability/{slo,metrics,alerts,anomaly,dashboard}.py` |
| **声依 vs 实依** | 声明 `dependencies = []`；实际仅用 Python stdlib (无第三方依赖) |
| **测试通过/风格** | 1 个 test_basic.py, 202 行 import sanity 测试 |
| **健康标记** | 🔴骨架 — Alpha, 6 个模块只有 1 个简单 import 测试 |
| **关键债务** | 无第三方集成 (无 fastapi/prometheus)，无集成测试，功能模块无真实行为验证 |

---

## 2. ontoderive

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | ontoderive v3.6.4 — 渊衍框架：事实驱动的一体化知识工程与方案推导 |
| **源文件数/代码行/测试** | 129 src (engine/114 + src/15) / 6,485 LOC / 48 测试 (19,156 LOC) |
| **核心模块/入口** | `engine/` 五层架构 (core/foundation/intelligence/reasoners/theories)；入口 `engine.cli:main` |
| **声依 vs 实依** | 声明 `pyyaml, fastmcp>=1.0, core-models`；实际大量使用 stdlib (json/uuid/hashlib)，另 use yaml、fastmcp |
| **测试通过/风格** | 48 测试文件，采用 unittest class-based, pytest-conftest，测试/源码 LOC 比 ~3:1 |
| **健康标记** | 🟢成熟 — Beta, v3.6.4, 架构成熟, 测试覆盖全面 |
| **关键债务** | 存在 engine/ 和 src/ 双目录代码冗余 (如 frontmatter_merger, fault_tolerance_policy 等文件重复) |

---

## 3. pontus

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | pontus v0.1.0 — Knowledge Pipeline Engine: DSL, DAG scheduler, checkpointing, data quality |
| **源文件数/代码行/测试** | 5 src / 909 LOC / 1 测试 (748 LOC) |
| **核心模块/入口** | `src/pontus/{dsl,scheduler,checkpoint,quality}.py` |
| **声依 vs 实依** | 声明 `pyyaml`；实际 import `yaml, sqlite3, asyncio` — 缺 sqlite3 声明 |
| **测试通过/风格** | 1 个 test_pontus.py (327 行)，class-based test, 覆盖 DSL/Quality/Scheduler |
| **健康标记** | 🟡存在 — Alpha, 功能完整但仅 1 个测试文件 |
| **关键债务** | 未声明 sqlite3 (stdlib 可忽略但应确认)，无集成测试，版本号 0.1.0 |

---

## 4. shared-lib

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | shared-lib v0.1.0 — 全局共享工具库 (事件、治理、审计、SDK、工具) |
| **源文件数/代码行/测试** | 147 src / 35,251 LOC / 24 测试 (9,547 LOC) |
| **核心模块/入口** | `src/kairon_lib/` 含 events/governance/plugin_sdk/utils 等子模块 |
| **声依 vs 实依** | **声明 `dependencies = []`**；实际 import `click, pytest, asyncio` 等第三方 (大量严重) |
| **测试通过/风格** | 24 测试文件，pytest class-based, 测试主要覆盖 utils/governance 模块 |
| **健康标记** | 🟡存在 — 体量最大(35K LOC)但无声明依赖、测试比例低(147:24) |
| **关键债务** | 🔴**缺失依赖声明** (`pyproject.toml` 无 dependencies, 实际依赖 click/pytest 等)；测试覆盖率不足；147 个源文件体量过大需拆分 |

---

## 5. sharedbrain-bridge

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | sharedbrain-bridge v0.1.0 — kairon 与 SharedBrain 桥梁：EU pricing, immune audit, batch sync |
| **源文件数/代码行/测试** | 6 src / 165 LOC / 1 测试 (525 LOC) |
| **核心模块/入口** | `src/sharedbrain_bridge/{eu,immune,sync,cli}.py`；入口 `sharedbrain_bridge.cli:main` |
| **声依 vs 实依** | 声明 `core-models`；实际使用 `urllib.request, hashlib, json` — 无 HTTP 客户端声明 |
| **测试通过/风格** | 1 个 test_bridge.py, unittest class-based |
| **健康标记** | 🟡存在 — 小巧简洁，功能单一，测试行数 > src |
| **关键债务** | 可能缺 httpx/requests 声明 (使用 urllib.request)；文档无集成说明 |

---

## 6. sharedbrain-standalone

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | sharedbrain-standalone v0.1.0 — sharedbrain-core 的可部署 HTTP/MCP 服务 wrapper |
| **源文件数/代码行/测试** | 2 src / 276 LOC / 2 测试 (158 LOC) |
| **核心模块/入口** | `src/sharedbrain_standalone/{server,__init__}.py` |
| **声依 vs 实依** | 声明 `core-models, fastapi, fastmcp, httpx`；实际 import `fastapi, fastmcp, core_models.*` (无 httpx) |
| **测试通过/风格** | 2 个测试文件，test_server.py 和 test_init.py |
| **健康标记** | 🔴骨架 — 仅 2 源文件, 基础测试, 功能太薄 |
| **关键债务** | 声依 httpx 未使用(dead dep)；无集成测试；core_models 的运行时 availability 需确认 |

---

## 7. sophia

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | sophia v0.2.1 — Symbolic Research Paradigm Engine: state machine formalism, 可组合研究范式 |
| **源文件数/代码行/测试** | 10 src / 1,445 LOC / 6 测试 (2,909 LOC) |
| **核心模块/入口** | `src/sophia/{compiler,symbols,learner,kems_runtime,cli,server/mcp_server,tui/app}.py`；入口 sopia CLI/MCP/TUI |
| **声依 vs 实依** | 声明 `core-models, rich>=13.0, fastmcp>=0.1`；实际 import `fastmcp`，未在 src 中直接 import core-models (可能运行时) |
| **测试通过/风格** | 6 测试文件, pytest asyncio_mode=auto, 测试/源码 LOC 比 ~2:1 |
| **健康标记** | 🟡存在 — Alpha, 架构清晰 (compiler/learner/symbols), 测试覆盖良好 |
| **关键债务** | core-models 可能为运行时/optional 依赖；TUI 模块测试缺失 |

---

## 8. ssot

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | ssot-kernel v1.0.0 — 领域知识单一事实源 (Domain Knowledge SSOT) |
| **源文件数/代码行/测试** | 49 src / 14,770 LOC / 10 测试 (5,264 LOC) |
| **核心模块/入口** | `src/ssot_kernel/` 含 extractor/patterns/monitoring/evolution/recovery/performance/cli；入口 `cli.py` |
| **声依 vs 实依** | 声明 `pyyaml>=6.0, pydantic>=2.0`；实际 import `yaml, psutil, sqlite3, json`；**未在 src 中找到 pydantic 导入** |
| **测试通过/风格** | 10 测试文件, pytest class-based, 覆盖 extractor/engine/evolution/patterns |
| **健康标记** | 🟢成熟 — v1.0.0, 架构完善, 七大子系统, 5 年演进基础 |
| **关键债务** | **pydantic 可能 dead dependency** (声依但 src 中未找到 import)；无 ASGI/HTTP 服务器层 |

---

## 9. symphony-protocol

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | symphony-protocol v0.1.0 — 形式化执行阶段协议：状态机 + Agent 匹配 + 触发器引擎 |
| **源文件数/代码行/测试** | 5 src / 1,014 LOC / 4 测试 (2,174 LOC) |
| **核心模块/入口** | `src/symphony_protocol/{state_machine,matcher,triggers,models}.py` |
| **声依 vs 实依** | 声明 **无 dependencies**；实际仅用 Python stdlib (dataclasses/enum/typing/collections/datetime) |
| **测试通过/风格** | 4 测试文件, pytest class-based, 测试/源码 LOC 比 ~2:1 |
| **健康标记** | 🟡存在 — Alpha, 零外部依赖小巧干净, 测试覆盖好 |
| **关键债务** | 缺少 CLI 入口/script entry point；无集成测试 (状态机通信) |

---

## 10. wksp

| 字段 | 值 |
|---|---|
| **名称/版本/职责** | wksp v0.2.0 — Workspace 统一用户入口：研究对象管理系统 |
| **源文件数/代码行/测试** | 56 src / 13,911 LOC / 39 测试 (13,211 LOC) |
| **核心模块/入口** | `src/wksp/{cli,storage,data_index,commands/*}`；入口 `wksp.cli:main` |
| **声依 vs 实依** | 声明 `click>=8.0, rich>=13.0`；实际 import `click, rich, sqlite3, yaml, pytest` |
| **测试通过/风格** | 39 测试文件, pytest class-based, 覆盖 CLI/storage/import/backup 全链路 |
| **健康标记** | 🟢成熟 — v0.2.0, 测试/源码 LOC 接近 1:1, 全命令测试 |
| **关键债务** | 未声明 yaml 依赖 (实际使用)；测试在 `src/wksp/tests/` 异于常规布局 |

---

## 汇总表

| # | 包名 | 版本 | 职责 | Src📁 | Src📄 | Test📁 | Test📄 | 声依 | 实依差异 | 🩺 | 状态 |
|---|------|------|------|------|------|------|------|------|---------|----|------|
| 1 | observability | 0.1.0 | SLO/指标/告警 | 6 | 1.6K | 1 | 0.4K | 无 | stdlib only | 🔴 | Alpha |
| 2 | ontoderive | 3.6.4 | 知识工程推导 | 129 | 6.5K | 48 | 19K | pyyaml,fastmcp,core-models | 基本匹配 + 大量std | 🟢 | Beta |
| 3 | pontus | 0.1.0 | 流水线引擎 | 5 | 0.9K | 1 | 0.7K | pyyaml | 缺 sqlite3 声 | 🟡 | Alpha |
| 4 | shared-lib | 0.1.0 | 共享工具库 | 147 | 35K | 24 | 9.5K | **无** | 🔴 click/pytest/.. 大量未声明 | 🟡 | Alpha |
| 5 | sharedbrain-bridge | 0.1.0 | SB 桥梁 | 6 | 0.2K | 1 | 0.5K | core-models | 缺 HTTP 客户端声明 | 🟡 | Alpha |
| 6 | sharedbrain-standalone | 0.1.0 | HTTP/MCP 服务 | 2 | 0.3K | 2 | 0.2K | core-models,fastapi,fastmcp,httpx | httpx 未用(dead) | 🔴 | Alpha |
| 7 | sophia | 0.2.1 | 符号研究范式 | 10 | 1.4K | 6 | 2.9K | core-models,rich,fastmcp | rich 未在 src 直接 import | 🟡 | Alpha |
| 8 | ssot | 1.0.0 | 单一事实源 | 49 | 15K | 10 | 5.3K | pyyaml,pydantic | pydantic 疑似 dead dep | 🟢 | Stable |
| 9 | symphony-protocol | 0.1.0 | 状态机协议 | 5 | 1.0K | 4 | 2.2K | 无 | stdlib only | 🟡 | Alpha |
| 10 | wksp | 0.2.0 | 用户工作台 | 56 | 14K | 39 | 13K | click,rich | 缺 yaml 声 | 🟢 | Beta |

**统计合计**: 415 src 文件 / 76K+ src LOC / 136 测试 / 53K+ 测试 LOC

### 关键发现

1. **健康包 (🟢)**: ontoderive (v3.6.4), ssot (v1.0.0), wksp (v0.2.0) — 成熟有测试
2. **存在包 (🟡)**: pontus, shared-lib, sharedbrain-bridge, sophia, symphony-protocol — 有功能但测试/声明有缺陷
3. **骨架包 (🔴)**: observability, sharedbrain-standalone — 功能太薄
4. **最大债务**: shared-lib 缺失全部依赖声明 + 147 源文件单体巨大
5. **Dead deps**: ssot 声依 pydantic 未用; sharedbrain-standalone 声依 httpx 未用
6. **测试之星**: wksp (39 测试文件, 13K 测试 LOC), ontoderive (48 测试, 19K 测试 LOC)
7. **用户数**: 用户数为 10 (非 11), 含 observability→wksp 共 10 个包
