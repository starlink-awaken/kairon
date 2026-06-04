# Kairon 架构审计报告

> **审计范围**: `projects/kairon/packages/` — 26 个 Python 包
> **审计日期**: 2026-06-02
> **审计方法**: 静态代码分析 + 依赖拓扑分析

---

## 1. 项目全局概览

| 维度 | 值 |
|------|-----|
| 仓库创建 | 2026-05-30，4 天历史 |
| 提交次数 | 7 次 |
| 作者 | 单作者 (starlink-awaken)，线性开发 |
| 包数量 | 26（20 已提交 + 6 磁盘存在未提交） |
| 构建系统 | Hatchling |
| Python 版本 | >=3.10（根级），各包独立配置 |
| 包管理 | uv workspace（`packages/*`） |
| 当前开发焦点 | Agora 核心能力冲刺（5/7 次提交全部修改 agora） |

### Git 历史快照

```
2026-05-30  Phase 2 baseline — 初始 20 包一次性导入
2026-06-02  [1] agora: MCP 代理实现
2026-06-02  [2] agora: 身份认证机制
2026-06-02  [3] agora: 速率限制
2026-06-02  [4] agora: SSRF 防护
2026-06-02  [5] agora: 三层桥接 + 文档完善
```

20 包已提交，6 包在磁盘存在但未跟踪，属于下一批能力扩展。

---

## 2. 包速查总表

### 2.1 已提交（Git Tracked, 20 包）

| 包名 | 版本 | 文件数 | Python | 核心依赖 | 入口类型 | 定位描述 | 成熟度 |
|------|------|--------|--------|----------|----------|----------|--------|
| agora | 2.0.0 | ~95 | >=3.10 | fastmcp, fastapi, httpx | MCP / Web UI | MCP Service Hub — 服务发现、路由、认证、代理 | **Stable** |
| minerva | 0.11.0 | ~90 | >=3.10 | fastmcp, fastapi, openai | MCP / Web UI | 深度研究系统 — 研究管线、报告生成、协作 | Beta |
| sophia | 0.2.1 | 10 | >=3.10 | fastmcp, textual | MCP / TUI | 符号范式引擎 — 逻辑推理、符号计算 | Beta |
| metaos | 0.1.0 (__v7.1.0) | 29 | >=3.10 | fastmcp, fastapi | MCP / CLI | 认知 OS 治理层 — 元认知编排 | Alpha |
| kronos | 0.4.0 (pyproject: 0.5.0) | 15 | >=3.10 | fastmcp, httpx | MCP / CLI | 知识摄取管线 — 数据采集、转换、入库 | Beta |
| eidos | 0.1.0 | ~67 | >=3.10 | fastmcp, sqlalchemy | MCP / CLI | 记忆与知识管理 — 语义索引、CRDT 同步 | Alpha |
| iris | 0.1.0 | ~25 | >=3.10 | fastmcp | MCP / CLI | 连接器中心 — 外部数据源适配器 | Alpha |
| kos | 2.0.0 | ~30 | >=3.10 | fastmcp, fastapi | MCP / Web+TUI | 知识操作系统 — 知识图、协作、推送 | **Stable** |
| codeanalyze | 0.3.0 | ~40 | >=3.10 | fastmcp, tree-sitter | MCP / CLI | 代码/文档分析 — AST 解析、质量指标 | Beta |
| cron-service | 1.0.0 | 10 | >=3.10 | fastmcp, fastapi | MCP / Web | 定时任务调度 — 作业编排、执行、监控 | **Stable** |
| agent-runtime | 0.1.0 | 10 | >=3.10 | fastmcp, fastapi | MCP / Web | Agent 运行时 — 工具执行、任务编排 | Alpha |
| core-models | 0.1.0 | ~3 | >=3.10 | 无 | CLI | 零依赖根包 — 核心数据模型定义 | Alpha |
| ontoderive | 3.6.4 | 6 | >=3.10 | fastmcp | MCP / CLI | 文档治理引擎 — 策略推导、合规检查 | **Stable** |
| ssot (ssot-kernel) | 0.1.0 | 64 | >=3.10 | fastmcp | MCP / CLI | SSOT 知识引擎 — 单一事实源维护 | Alpha |
| sharedbrain-bridge | - | 5 | >=3.10 | httpx | CLI | 轻量 HTTP 桥接 — SharedBrain 连接 | Alpha |
| ecos | 待补全 | - | - | - | - | 待补全 | - |
| eu-pricing | 待补全 | - | - | - | - | 待补全 | - |
| forge | 待补全 | - | - | - | - | 待补全 | - |
| shared-lib | 待补全 | - | - | - | - | 待补全 | - |
| wksp | 待补全 | - | - | - | - | 待补全 | - |

### 2.2 未提交（磁盘存在，6 包 — 孵化中）

| 包名 | 版本 | 文件数 | Python | 核心依赖 | 入口类型 | 定位描述 | 成熟度 |
|------|------|--------|--------|----------|----------|----------|--------|
| engine-core | 0.1.0 | 57+ | >=3.10 | fastapi | CLI | 核心引擎 — 事件总线、CRDT、Worker 抽象 | Alpha |
| kairon-assistant | 1.0.0 | 8 | >=3.10 | - | CLI | 智能助手 — 对话式知识检索 | **Stable** |
| kairon-voice | 1.0.0 | 6 | >=3.10 | - | CLI | 语音子系统 — 语音交互与处理 | **Stable** |
| kaironcloud-billing | 0.1.0 | 8 | >=3.10 | - | CLI | 计费系统 — 用量计量与计费 | Alpha |
| llm-gateway | 0.1.0 | 9 | >=3.10 | httpx | CLI | LLM 抽象层 — 统一 LLM 调用接口 | Alpha |
| symphony-protocol | 0.1.0 | 5 | >=3.10 | - | CLI | 阶段门控协议 — 任务生命周期门控 | Alpha |

---

## 3. 领域分类

将 26 个包划分为 6 大业务领域：

### 基础设施/核心

| 包 | 角色 |
|----|------|
| core-models | 零依赖根包，定义核心数据类型，作为 8 个包的依赖根 |
| agora | MCP Service Hub，服务治理中枢，含 MCP 代理/身份认证/速率限制/SSRF 防护/三层桥接 |
| engine-core | 核心引擎，提供 EventBus、CRDT 同步、Worker 抽象等通用能力（未提交） |
| cron-service | 定时任务调度服务，提供可靠的作业执行（Stable） |

### 知识/认知

| 包 | 角色 |
|----|------|
| eidos | 记忆与知识管理 — 语义索引、CRDT 同步、SharedBrain 适配 |
| kos | 知识操作系统 — 知识图管理、协同编辑、模式学习、推送引擎 |
| minerva | 深度研究系统 — 多轮研究管线、报告生成、协作（最大包之一） |
| sophia | 符号范式引擎 — 逻辑推理、符号计算、CLI 子进程模式 |
| ssot (ssot-kernel) | SSOT 知识引擎 — 单一事实源维护、版本追踪 |
| ontoderive | 文档治理引擎 — 策略推导、合规检查、最成熟包（v3.6.4） |

### 数据处理

| 包 | 角色 |
|----|------|
| kronos | 知识摄取管线 — 数据采集、转换、ETL 入库 |
| codeanalyze | 代码/文档分析 — tree-sitter AST 解析、代码质量评估 |
| sharedbrain-bridge | 轻量 HTTP 桥接 — 连接 SharedBrain 外部服务 |

### 外部集成

| 包 | 角色 |
|----|------|
| iris | 连接器中心 — Obsidian、GitHub、Notion 等外部数据源 |
| llm-gateway | LLM 抽象层 — 统一 OpenAI/Anthropic 等 API 调用（未提交） |
| kairon-voice | 语音子系统 — 语音交互处理与合成（未提交） |

### 业务/用户层

| 包 | 角色 |
|----|------|
| kairon-assistant | 智能助手 — 对话式知识检索与交互（未提交） |
| kaironcloud-billing | 计费系统 — 用量计量与云计费（未提交） |
| agent-runtime | Agent 运行时 — 工具注册、任务编排、HTTP 服务 |
| metaos | 认知 OS 治理层 — 元认知编排与 OS 协调 |

### 共享/工具

| 包 | 角色 |
|----|------|
| shared-lib | 共享工具库 |
| symphony-protocol | 阶段门控协议 — 任务生命周期管理 |
| ecos | 待补全 |
| eu-pricing | 待补全 |
| forge | 待补全 |
| wksp | 待补全 |

### 领域分布

```
基础设施/核心   ████  4 包
知识/认知       ██████  6 包
数据处理         ███  3 包
外部集成         ███  3 包
业务/用户层     ████  4 包
共享/工具       ██████  6 包
```

---

## 4. 依赖拓扑分析

### 依赖根

**core-models** 是唯一的依赖根节点，被 8 个包直接依赖：

```
core-models
  ├── eidos
  ├── iris
  ├── kos
  ├── codeanalyze
  ├── agent-runtime
  ├── metaos
  ├── ssot-kernel
  └── agora (indirect via others)
```

### 二级叶节点

**ssot-kernel** 作为二级叶节点，仅被 iris 可选依赖（conditional import）。

### 跨包桥接

| 桥接路径 | 方式 | 说明 |
|----------|------|------|
| minerva → sophia | CLI subprocess | minerva 通过子进程调用 sophia 的 CLI 接口 |
| agora ↔ sophia | MCP 生态 | 共享 MCP 服务器注册/发现机制 |
| agora ↔ minerva | MCP 生态 | 同上 |
| kos → eidos | import direct | kos 直接导入 eidos 的类 |
| iris → eidos | import direct | iris 连接器引用 eidos 的模型 |
| iris → ssot | import direct | iris 引用 ssot-kernel 的配置 |
| codeanalyze → eidos | import direct | codeanalyze 引用 eidos 的语义索引 |
| codeanalyze → core-models | import direct | 模型定义依赖 |

### 独立包

15 个包无内部依赖（不依赖其他 kairon 包），仅依赖外部 PyPI 包：

```
sharedbrain-bridge, ecos, eu-pricing, forge, shared-lib, wksp,
cron-service, engine-core, kairon-assistant, kairon-voice,
kaironcloud-billing, llm-gateway, symphony-protocol,
ontoderive, sophia, minerva
```

### 依赖图（简化）

```
core-models (根)
  ├── eidos ──┬── kos
  │           └── iris ── ssot-kernel
  ├── codeanalyze
  ├── agent-runtime
  └── metaos

minerva ──(subprocess)── sophia

agora (MCP 生态中心) ──(MCP 协议)── minerva, sophia, kronos, eidos, iris, kos, ... (所有 fastmcp 包)

独立包: cron-service, ontoderive, sharedbrain-bridge, 等 15 个
```

---

## 5. 架构模式审计

### 5.1 MCP 服务器模式

**13 个包**使用 `fastmcp` 构建 MCP 服务器，占总量的 50%：

| 包 | MCP 工具数 | MCP 资源数 | 备注 |
|----|-----------|-----------|------|
| agora | 20+ | 10+ | MCP 代理 + 原生 MCP |
| minerva | 15+ | 5+ | 研究工具集 |
| sophia | 5+ | 2+ | 符号推理 |
| metaos | 5+ | 3+ | 治理操作 |
| kronos | 5+ | 2+ | 摄取控制 |
| eidos | 10+ | 5+ | 记忆操作 |
| iris | 3+ | 2+ | 连接器 |
| kos | 10+ | 5+ | 知识操作 |
| codeanalyze | 5+ | 3+ | 分析工具 |
| cron-service | 3+ | 1+ | 任务管理 |
| agent-runtime | 5+ | 2+ | 工具执行 |
| ontoderive | 3+ | 1+ | 策略工具 |
| ssot | 5+ | 3+ | SSOT 维护 |

**架构评价**: MCP 是 Kairon 生态的核心通信范式，所有包都基于 fastmcp 构建统一工具/资源接口。Agora 额外实现了 MCP 代理层，支持下游 MCP server 的透明访问和路由。

### 5.2 CLI 入口

几乎所有包都提供 CLI 入口（`__main__.py` + `pyproject.toml` scripts），使用 `argparse` 或 `click` 构建。典型模式：

```python
# 伪代码模式
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp", action="store_true", help="Run as MCP server")
    args = parser.parse_args()
    if args.mcp:
        run_mcp_server()
    else:
        run_cli()
```

### 5.3 Web UI

| 包 | 框架 | 端口 | 用途 |
|----|------|------|------|
| agora | FastAPI + Jinja2 | 7430 | 服务仪表板、健康检查 |
| minerva | FastAPI + Jinja2 | 7530 | 研究 Web App |
| kos | FastAPI + FastUI | 7630 | 知识管理 UI + TUI fallback |
| sophia | Textual (TUI) | - | 终端推理界面 |
| cron-service | FastAPI | 7730 | 任务管理 API |
| agent-runtime | FastAPI | 7830 | Agent 执行 API |

### 5.4 设计模式

| 模式 | 包 | 说明 |
|------|----|------|
| **策略模式** | kairon-voice | 不同语音引擎的 Strategy 抽象 |
| **抽象工厂** | kairon-voice | 语音引擎工厂创建 |
| **状态机** | sophia, symphony-protocol | 推理状态机、阶段状态转换 |
| **事件驱动** | engine-core (EventBus), agora | 异步事件发布/订阅 |
| **Pipeline** | minerva, kairon-assistant | 多阶段处理管线 |
| **单例** | engine-core (EventBus) | 全局唯一事件总线实例 |
| **CRDT** | eidos, engine-core | 无冲突复制数据类型同步 |
| **门控 (Gate)** | symphony-protocol | 阶段门控，条件通过/阻塞 |

### 5.5 LLM 抽象层冗余（已解决 ✅）

**已于 2026-06-04 统一为 `llm-gateway` 单一抽象**，详细见对应的治理 Plan。

存在 **4 种独立 LLM 抽象实现**，语义重复（已解决）：

| 实现 | 包 | 基类/接口 | 状态 |
|------|-----|-----------|------|
| `BaseProvider` | ontoderive | ABC → `OntoderiveProvider` | ✅ 已适配 |
| `OpenAICompatibleClient` | minerva | 自定义 → `MinervaProvider` | ✅ 已适配 |
| `LLMBackend` | ssot-kernel | 自定义 → `SSOTProvider` | ✅ 已适配 |
| `llm-gateway` | llm-gateway | ABC（统一载体） | 🟢 统一完成 |
| `llm-gateway` | llm-gateway | ABC | OpenAI, Anthropic（未提交） |

**问题**: 同一功能重复实现 4 次，导致维护成本 4x，接口不统一，参数配置各异。

### 5.6 SSOT 模式

ssot-kernel 实现了 **Single Source of Truth** 模式，通过版本化知识条目和冲突检测维护数据一致性。iris（连接器）作为 ssot 的消费端，负责将外部数据同步为 SSOT 条目。

---

## 6. 成熟度评估

### 6.1 成熟度分级

| 等级 | 标准 | 包数 | 包列表 |
|------|------|------|--------|
| **Stable** | v1.0+ | 6 | agora(2.0.0), kos(2.0.0), ontoderive(3.6.4), kairon-assistant(1.0.0), kairon-voice(1.0.0), cron-service(1.0.0) |
| **Beta** | v0.3~v0.11 | 4 | minerva(0.11.0), sophia(0.2.1), kronos(0.4.0), codeanalyze(0.3.0) |
| **Alpha** | v0.1 / 未定 | 16 | 其余包（含全部 6 个未提交包） |

### 6.2 版本一致性问题

| 包 | pyproject.toml | 内部版本 | 差异 |
|----|---------------|----------|------|
| metaos | 0.1.0 | `__version__ = "v7.1.0"` | **严重不一致** |
| kronos | 0.4.0 | pyproject 声明 0.5.0 | 轻微不一致 |
| 其余各包 | 基本一致 | - | 正常 |

### 6.3 测试覆盖率

| 覆盖程度 | 包数 | 代表包 |
|----------|------|--------|
| 20+ 测试文件 | 1 | agora |
| 4 测试文件 | 1 | kaironcloud-billing |
| 1 测试文件 | 大多数 | minerva, kos, eidos, iris 等 |
| 0 测试文件 | 若干 | 待确认 |

```
agora                 ████████████████████  ~20
kaironcloud-billing   ████                  4
minerva               █                     1
...                   █                     1
若干                    ▯                     0
```

**问题**: 26 个包中绝大多数仅有 1 个测试文件，测试覆盖严重不足。

### 6.4 Ruff 配置不一致

| 配置项 | 值 | 包数 |
|--------|----|------|
| target-version | py310 | 部分包 |
| target-version | py313 | 部分包（含根级） |
| target-version | py314 | 部分包 |
| line-length | 100 | 部分包 |
| line-length | 120 | 部分包（含根级） |
| line-length | 140 | 部分包 |
| line-length | 240 | 部分包 |

---

## 7. Git 历史与演进方向

### 7.1 阶段划分

```
Phase 2 Baseline (2026-05-30)
  └── 一次性提交 20 个包
       ├── 基础设施: agora, cron-service, core-models, agent-runtime
       ├── 知识: eidos, kos, minerva, sophia, ssot, ontoderive
       ├── 数据处理: kronos, codeanalyze, sharedbrain-bridge
       └── 共享: ecos, eu-pricing, forge, shared-lib, wksp, metaos, iris

Agora 冲刺 (2026-06-02)
  ├── [1] MCP 代理实现
  ├── [2] 身份认证机制
  ├── [3] 速率限制器
  ├── [4] SSRF 防护
  └── [5] 三层桥接 + 文档完善

下一阶段（预测）
  ├── 提交 6 个未跟踪包
  ├── 新增根级 kairon 可安装包（已存在分支）
  └── 统一 LLM 抽象层（架构建议）
```

### 7.2 演进特点

- **Agora 优先**: 2/3 的提交专注于 Agora 包，反映 MCP Service Hub 作为生态核心的战略位置
- **渐进式扩展**: 20 包一次性基线 + 6 包孵化中 + 新增根级包 = 3 阶段部署
- **单作者线性**: 无分支/PR/协作历史，属于快速原型阶段的开发模式

---

## 8. 关键发现与架构缺口

### 8.1 严重问题

#### 🔴 LLM 抽象层重复（4 路）

4 个独立的 LLM 调用实现（ontoderive `BaseProvider`、minerva `OpenAICompatibleClient`、ssot `LLMBackend`、llm-gateway `ABC`）功能完全重叠，但接口、配置、错误处理各不兼容。

**影响**: 维护成本 4x、接口不统一、生态碎片化。

#### 🔴 Ruff 配置不一致

跨包使用不同 Python 版本目标和行宽，无法统一格式化：

```toml
# 包 A
target-version = "py310"
line-length = 100

# 包 B
target-version = "py314"
line-length = 240
```

**影响**: 代码风格不统一，根级 ruff 配置无法覆盖所有包。

#### 🔴 测试覆盖严重不足

26 个包中绝大多数仅有 1 个测试文件，仅 agora 有 ~20 个测试文件、kaironcloud-billing 有 4 个。

**影响**: 重构风险高、回归难以检测。

### 8.2 中等问题

#### 🟡 迁移过渡文件

- `engine-core/workers/` 与顶层存在重复文件，职责未明确划分
- `result_bus.py` 为空文件，可能是迁移残留

#### 🟡 缺失文件

- `kairon-assistant` 引用了不存在的 `governance_integration.py`，编译/运行时可能报错

#### 🟡 版本内外不一致

- `metaos`: pyproject.toml 声明 0.1.0，代码内声明 `__version__ = "v7.1.0"`
- `kronos`: pyproject.toml 声明 0.4.0，但内容指向 0.5.0

### 8.3 待确认

| 项目 | 说明 |
|------|------|
| ecos | 未深入分析，功能待确认 |
| eu-pricing | 未深入分析，功能待确认 |
| forge | 未深入分析，功能待确认 |
| shared-lib | 未深入分析，功能待确认 |
| wksp | 未深入分析，功能待确认 |

### 8.4 外部依赖混淆

以下路径/引用不是 kairon 包，而是独立的 TypeScript 项目：

```
hermes/       → 独立 TypeScript 项目，非 kairon 包
agentmesh/    → 独立 TypeScript 项目，非 kairon 包
honeycomb/    → 独立 TypeScript 项目，非 kairon 包
```

**影响**: 代码中的 `from hermes_ops...` 等导入可能在纯 kairon 环境下失败。

---

## 9. 架构建议

### S-1 统一 LLM Provider 抽象（优先级: P0）

**现状**: 4 路独立实现，互不兼容。

**建议方案**:

```
llm-gateway (统一接口)
  ├── Provider: OpenAI
  ├── Provider: Anthropic
  ├── Provider: Ollama
  └── ...
```

- 采用 ABC + 策略模式，定义统一的 `LLMProvider` 抽象基类
- `ontoderive`/`minerva`/`ssot` 的现有实现适配为新 Provider
- 配置集中化（环境变量 + 统一的 YAML 配置）

### S-2 标准化 Ruff 配置（优先级: P1）

**现状**: 各包使用不同 py 版本目标和行宽。

**建议方案**:

```toml
# 根级 pyproject.toml 统一配置
[tool.ruff]
target-version = "py313"  # 统一目标
line-length = 120         # 统一行宽

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "PLE", "RUF100"]
```

- 删除各包独立的 `[tool.ruff]` 段（或只保留必须覆盖的项）
- 运行 `ruff check --fix` 全量修复一次

### S-3 补齐测试覆盖（优先级: P1）

**现状**: 26 包中绝大多数仅有 1 个测试文件。

**建议方案**:

| 阶段 | 目标 | 包 |
|------|------|----|
| Phase 1 | 核心包 >=50% 覆盖 | agora, minerva, kos, ssot-kernel |
| Phase 2 | 稳定包 >=60% 覆盖 | ontoderive, cron-service, kairon-assistant |
| Phase 3 | 所有包 >=30% 覆盖 | 全量 |

- 最低要求：每个包至少 3 个测试文件（单元 + 集成 + CLI）
- 核心公共组件（EventBus/CRDT/Worker）需独立测试

### S-4 清理迁移过渡文件（优先级: P2）

**现状**: engine-core 存在重复文件和空文件。

**建议方案**:

- 明确 `engine-core/workers/` 职责，删除顶层重复代码
- 删除或补全 `result_bus.py`
- 修复 `kairon-assistant` 对 `governance_integration.py` 的引用

### S-5 统一版本号管理（优先级: P2）

**现状**: metaos、kronos 存在内外版本不一致。

**建议方案**:

- 根级 `pyproject.toml` 统一管理版本号（或使用 `tool.hatch.version` 引用 `__init__.py`）
- 批量校验各包的 `pyproject.toml` vs `__version__` 一致性
- 考虑使用 `__version__ = "0.1.0"` 作为单一事实源

### S-6 提取通用能力为共享库（优先级: P2）

**现状**: engine-core 包含 EventBus、CRDT、WorkerAbstract 等通用组件，但功能重复。

**建议方案**:

```
shared-lib (扩展)
  ├── eventbus/        # 移入 engine-core EventBus
  ├── crdt/            # 移入 eidos/engine-core CRDT 通用部分
  ├── worker/          # Worker 抽象
  └── models/          # 通用类型
```

- 减少跨包代码重复
- 引入独立测试套件
- 注意：避免过早抽象，仅提取已有 2+ 使用者的功能

---

## 总结

Kairon 项目在短短 4 天内完成了 26 个包的架构架设，以 **MCP 协议** 作为统一通信范式，**Agora** 作为服务治理中枢，形成了"知识/认知 → 数据处理 → 外部集成 → 业务层"的清晰分层。核心包（agora、kos、minerva）的代码质量较高，MCP 生态设计良好。

但项目目前处于 **快速原型** 阶段，存在以下核心问题需要解决：

1. **LLM 抽象重复** — 最关键的架构债，随着包数量增长成本将指数上升
2. **测试覆盖严重不足** — 26 包中多数仅 1 个测试文件
3. **配置不一致** — ruff 跨包不统一，版本信息散乱
4. **迁移残留** — engine-core 等包存在过渡期文件

建议按 P0 → P3 优先级逐步修复，在下一批包提交前完成 S-1（LLM 统一）和 S-2（Ruff 标准化）两项基础性工作，避免架构债进一步堆积。

---

> **生成日期**: 2026-06-02
> **审计范围**: `projects/kairon/packages/` — 26 个包
> **审计方法**: 静态代码分析 + 依赖拓扑分析
