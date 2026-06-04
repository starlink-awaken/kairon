# Kairon 治理规划（V1）

> **制定日期**: 2026-06-02
> **版本**: v1.0
> **状态**: Draft
> **关联文档**: `architecture_audit.md` · `WORKSPACE/.omo/GOVERNANCE_PLAN.md`

---

## 1. 治理背景

### 1.1 架构审计结论

2026-06-02 完成的 Kairon 架构审计（`docs/architecture_audit.md`）覆盖了 `projects/kairon/packages/` 下的 **26 个 Python 包**，发现以下核心问题：

| 严重度 | 问题 | 数量 |
|--------|------|------|
| 🔴 严重 | LLM 抽象层重复 | 4 路独立实现（ontoderive `BaseProvider`、minerva `OpenAICompatibleClient`、ssot `LLMBackend`、llm-gateway `ABC`） |
| 🔴 严重 | Ruff 配置不一致 | target-version 跨包 py310~py314，line-length 跨包 100~240 |
| 🔴 严重 | 测试覆盖严重不足 | 26 包中多数仅 1 个测试文件，仅 agora 有 ~20 个、ontoderive 有 50 个 |
| 🟡 中等 | 迁移过渡文件 | engine-core `workers/` 与顶层重复、`result_bus.py` 为空文件 |
| 🟡 中等 | 缺失文件 | kairon-assistant 引用不存在的 `governance_integration.py` |
| 🟡 中等 | 版本内外不一致 | metaos pyproject:0.1.0 vs `__version__`:"v7.1.0"；kronos pyproject:0.4.0 vs 0.5.0 |
| 🟡 中等 | 外部依赖混淆 | 导入 `hermes_ops` 但 hermes 是独立 TS 项目 |
| ⚪ 待确认 | 5 个包未深入分析 | ecos, eu-pricing, forge, shared-lib, wksp |

审计建议概括为 **S-1~S-6**，按 P0~P2 优先级排列。

### 1.2 当前状态

| 指标 | 值 |
|------|-----|
| 系统健康分 | **29.1**（加权后，严重低于 .omo HEALTH_DASHBOARD 的 66.80 目标） |
| 债务项 | **9 项**，全部 unresolved |
| 任务进度 | 124/131 已完成，**5 个活跃** |
| Phase 状态 | Phase 16 completed，Phase 17 已制定计划但未执行 |
| 包数量 | 26 个（全部已 git tracked） |
| 测试文件 | 仅 agora (49) + ontoderive (50) 较充分，其余严重不足 |

### 1.3 为什么需要治理规划

Kairon 项目处于"快速原型 → 工程化"的转折点。当前 **29.1 的健康分** 反映以下根本矛盾：

- **架构债累积速度快于清理速度**：4 路 LLM 抽象是典型的"先复制再抽象"反模式，每新增一个包都可能再增加第 5 路
- **缺乏质量底线**：无统一 lint、无测试基线、无版本一致性检查，导致合入门禁形同虚设
- **.omo 治理能力未下沉**：工作区级 `.omo` 已建立完整的治理体系（Phase 1~16），但 kairon 项目层面没有对应的治理目录和执行分册

本规划旨在将 **架构审计结论** 转化为 **可执行的治理计划**，分阶段将 kairon 从"原型"推进到"工程化"。

---

## 2. 治理目标

### 2.1 总体目标

1. **代码质量基线化** — 统一 Ruff 配置、补齐测试覆盖、建立版本一致性检测
2. **架构债务存量清理** — LLM 统一、迁移残留清理、缺失文件修复、版本不一致修复
3. **治理体系落地** — 将 `.omo` 工作区治理能力下沉到 kairon 项目层面，建立门禁和持续改进机制

### 2.2 量化指标

| 指标 | 当前值 | Phase 1 目标 | Phase 2 目标 | Phase 3 目标 |
|------|--------|-------------|-------------|-------------|
| Ruff 错误数 | 分散配置 | 统一配置 + 0 错误 | 维持 0 | CI gate 自动阻止 |
| 核心包覆盖率 | <10% | >=50%（4 包） | >=60%（+5 包） | 全包 >=30% |
| 版本一致性 | 2 包不一致 | 0 包不一致 | 自动化检测 | CI gate |
| 包治理注册 | 无 | 无 | 建立 | 可自动评估 |
| 健康分 | 29.1 | >=45 | >=60 | >=75 |

---

## 3. 分阶段规划

### Phase 1: 基础治理（P0-P1 优先，2 周）

**目标**: 建立代码质量和架构底线，消除最高优先级架构债。

#### 核心任务

##### 1.1 Ruff 标准化（S-2）

**根级统一配置** — 删除各包独立 `[tool.ruff]` 段，在根级 `pyproject.toml` 集中配置：

```toml
[tool.ruff]
target-version = "py313"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "PLE", "RUF100"]

[tool.ruff.format]
quote-style = "double"
indent-width = 4
```

**执行步骤**:

1. 在 `projects/kairon/pyproject.toml` 添加统一 `[tool.ruff]` 配置
2. 移除各包 `pyproject.toml` 中的 `[tool.ruff]` 段（如仅覆盖 `target-version` 或 `line-length` 的，删除；如有特殊规则需要保留，加注释说明理由）
3. 全量执行 `ruff check --fix` 和 `ruff format`
4. 验证 `ruff check` 零错误通过

**验收条件**: `ruff check packages/` 返回 0 错误，`ruff format --check packages/` 无差异。

##### 1.2 LLM Provider 统一（S-1）

**架构方案**: 以 `llm-gateway`（已存在但未提交）承载统一 ABC，现有 3 路实现适配为 Provider。

```python
# llm-gateway 提供的统一抽象
class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str: ...
    @abstractmethod
    async def chat_stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]: ...

class OpenAIProvider(LLMProvider): ...
class AnthropicProvider(LLMProvider): ...
class OllamaProvider(LLMProvider): ...
```

**迁移步骤**:

1. 确认 `llm-gateway` 的 ABC 定义，补充缺失方法签名
2. 将 `ontoderive BaseProvider` 适配为 `llm-gateway.OntoderiveProvider`（包装器模式）
3. 将 `minerva OpenAICompatibleClient` 适配为 `llm-gateway.MinervaProvider`
4. 将 `ssot LLMBackend` 适配为 `llm-gateway.SSOTProvider`
5. 原包保留向后兼容别名（`BaseProvider = OntoderiveProvider`），推荐新代码直接使用 llm-gateway
6. 更新各包文档和导入路径

**风险控制**:

- 每个 Provider 适配需单独的测试覆盖
- 适配器优先使用委托模式而非重写，最小化功能变更风险
- 适配完成后运行各包现有测试套件验证无回归

**验收条件**: `llm-gateway` 提供完整 ABC，3 个适配器通过各自测试，现有包代码正常运行。

##### 1.3 关键包测试基线（S-3 Phase 1）

目标 **4 个核心包** 覆盖率达 **>=50%**：

| 包 | 当前测试文件 | 目标 | 策略 |
|----|------------|------|------|
| `agora` | 49 | >=50% | 已有良好基础，补充集成和场景测试 |
| `minerva` | 34 | >=50% | 核心研究管线各步骤独立测试 |
| `kos` | 22 | >=50% | 知识图 CRUD + MCP 工具测试 |
| `ssot` | 11 | >=50% | SSOT 核心逻辑 + 版本追踪测试 |

每个包至少包含：
- **单元测试**: 核心类和函数
- **集成测试**: 跨模块调用链路
- **CLI 测试**: 命令行入口

##### 1.4 修复已知 Bug

| Bug | 修复方案 |
|-----|---------|
| kairon-assistant 缺失 `governance_integration.py` | 创建空桩文件或修复 import 引用 |
| metaos 版本不一致（pyproject:0.1.0, `__version__`:"v7.1.0"） | 统一为 `__version__ = "0.1.0"`，pyproject 引用 `__version__` |
| kronos 版本不一致（pyproject:0.4.0 vs 内部 0.5.0） | 统一为 0.4.0，pyproject 与代码一致 |

##### 1.5 提交 6 个未跟踪包

| 包 | 版本 | 职责 | 注意事项 |
|---|------|------|---------|
| `engine-core` | 0.1.0 | 核心引擎 — EventBus、CRDT、Worker 抽象 | 含重复文件和空 `result_bus.py`，需先清理 |
| `kairon-assistant` | 1.0.0 | 智能助手 | 需先修复 `governance_integration.py` 引用 |
| `kairon-voice` | 1.0.0 | 语音子系统 | 策略模式 + 抽象工厂 |
| `kaironcloud-billing` | 0.1.0 | 计费系统 | 已有 4 个测试文件 |
| `llm-gateway` | 0.1.0 | LLM 抽象层 | P0 任务的核心载体，确保 ABC 完整 |
| `symphony-protocol` | 0.1.0 | 阶段门控协议 | 状态门控模式 |

**注意**: 6 个包可能已落后于主线，需做兼容性检查再提交。

#### 交付物

- [ ] 根级 `ruff.toml` + 全量 lint fix 通过
- [ ] `llm-gateway` LLMProvider ABC + 3 个适配器
- [ ] 4 个核心包测试文件 >=50% 覆盖率
- [ ] `pyproject.toml` 版本修复（metaos, kronos）
- [ ] kairon-assistant 缺失文件修复
- [ ] 6 包 git add + PR

---

### Phase 2: 架构清理（P1-P2 优先，2 周）

**目标**: 清理迁移残留，补齐剩余测试，启动器官迁移。

#### 核心任务

##### 2.1 补齐全量包测试（S-3 Phase 2）

目标 **5 个稳定包** 覆盖率达 **>=60%**：

| 包 | 当前测试文件 | 目标 | 策略 |
|----|------------|------|------|
| `ontoderive` | 50 | >=60% | 已有最佳基础，补充边缘场景 |
| `cron-service` | 1 | >=60% | 定时任务核心逻辑 + MCP 工具 |
| `kairon-assistant` | 2 | >=60% | 对话流程 + 知识检索链路 |
| `kairon-voice` | 1 | >=60% | 语音引擎策略 + 工厂测试 |
| `kaironcloud-billing` | 5 | >=60% | 用量计量 + 计费逻辑 |

##### 2.2 清理 engine-core（S-4）

**问题**: engine-core 的 `workers/` 目录与顶层存在重复代码，`result_bus.py` 为空文件。

**执行步骤**:

1. 梳理 `workers/` 与顶层的职责划分 — 明确哪些是通用 Worker 抽象，哪些是具体实现
2. 删除顶层重复代码，统一到 `workers/` 目录
3. 决定 `result_bus.py` 的去留：
   - 如有对应功能需求：补全实现
   - 如无对应功能需求：删除文件 + 清理所有 import 引用
4. 重构后确保 EventBus、CRDT、WorkerAbstract 三组核心能力可独立导入和测试

**交付**: engine-core 职责清晰，无重复文件、无空文件。

##### 2.3 提取共享库（S-6）

识别已有 **2+ 使用者** 的通用能力，提取到 `shared-lib`：

| 能力 | 当前所在包 | 使用者 | 提取目标 |
|------|-----------|--------|---------|
| EventBus | engine-core | engine-core, agora | `shared-lib/eventbus/` |
| CRDT | engine-core, eidos | eidos, engine-core | `shared-lib/crdt/` |
| WorkerAbstract | engine-core | engine-core 内部 | `shared-lib/worker/` |

**原则**: 仅提取已有 2+ 使用者的功能，避免过早抽象。

**交付**: `shared-lib` 新增 eventbus/crdt/worker 模块 + 独立测试套件。

##### 2.4 Phase 17 器官迁移 — Wave 1

根据 Phase 17 计划执行 Wave 1：

| 迁移 | 源 | 目标 | 说明 |
|------|-----|------|------|
| D_Economy | .omo 器官 | `eu-pricing` 包 | 经济模型能力注入 |
| D_KnowledgeIntegration | .omo 器官 | `kos` 包 | 知识集成能力注入 |

**每个迁移包括**:
1. 能力注册 — 将器官功能注册到目标包的接口
2. 测试验证 — 功能可运行
3. 废弃标记 — 源器官标记为 `@deprecated`

#### 交付物

- [ ] 5 个稳定包测试 >=60%
- [ ] engine-core 重构完成（无重复代码、无空文件）
- [ ] `shared-lib` 新增 eventbus/crdt/worker 模块
- [ ] Phase 17 W1 器官迁移完成

---

### Phase 3: 治理体系落地（P2 优先，2 周）

**目标**: 将 `.omo` 治理能力下沉到 kairon 项目层面，建立持续治理机制。

#### 核心任务

##### 3.1 kairon 专属治理目录

在 `projects/kairon/.omo/` 建立轻量治理层，链接到根级 `.omo/`：

```
.omo/
  ├── INDEX.md              # kairon 治理导航
  ├── registry/             # 包治理注册表
  │   └── packages.yaml     # 26 包治理状态
  ├── state/                # kairon 状态快照
  │   └── status.yaml       # 健康分、债务、测试覆盖率
  ├── standards/            # kairon 专属标准
  │   ├── ruff.toml         # 引用根级配置（或本地覆盖）
  │   └── import-rules.md   # 跨包依赖边界
  └── tests/                # kairon 质量门禁结果
      └── gate-results/     # CI gate 运行历史
```

##### 3.2 包治理注册表

创建 `projects/kairon/.omo/registry/packages.yaml`，记录每个包的核心治理属性：

```yaml
packages:
  agora:
    maturity: stable
    version: 2.0.0
    owner: null
    test_files: 49
    test_coverage_target: 50%
    ruff_status: pending
    llm_unified: n/a
    known_debts:
      - "SSRF 防护需补充安全测试"
    dependencies: []
```

##### 3.3 全量包测试覆盖（S-3 Phase 3）

目标 **所有 26 包** 测试覆盖 >=**30%**。

优先级顺序：Phase 1+2 处理过的 9 个包 → 剩余 17 个 Alpha/Beta 包。

| 未处理包 | 当前测试文件 | 覆盖缺口 |
|---------|------------|---------|
| core-models | 2 | 核心模型定义需 100% |
| ecos | 12 | 新增功能测试 |
| eidos | 19 | 已接近目标 |
| forge | 11 | 补充功能测试 |
| iris | 10 | 补充连接器测试 |
| metaos | 11 | 补充治理层测试 |
| shared-lib | 7 | 补充共享组件测试 |
| sharedbrain-bridge | 2 | 轻量 HTTP 桥接测试 |
| sophia | 6 | 补充符号推理测试 |
| symphony-protocol | 1 | 补充门控协议测试 |
| wksp | 40 | 已有较好基础 |
| agent-runtime | 6 | 补充运行时测试 |

##### 3.4 深度分析 5 个未分析包

对架构审计中标记为"未深入分析"的 5 个包进行深度分析：

| 包 | 审计标记 | 分析大纲 |
|----|---------|---------|
| `ecos` (v0.6.0) | 待补全 | 认知 OS 生态层 — 外化认知服务注册与发现 |
| `eu-pricing` (v0.1.0) | 待补全 | 定价引擎 — 欧盟定价模型与策略 |
| `forge` (v1.3.0) | 待补全 | 锻造引擎 — 工具注册与内部工具集 |
| `shared-lib` (v0.1.0) | 待补全 | 共享库 — 通用工具函数与类型 |
| `wksp` (v0.2.0) | 待补全 | 工作台 — CLI 交互式工作台 |

每个分析报告包含：
- 包定位与职责
- 代码质量评估（lint、测试、文档）
- 依赖分析（内部 + 外部）
- 架构建议

##### 3.5 CI 集成

建立 **Kairon CI Gate**，集成以下检查：

1. **Ruff lint** — `ruff check packages/` 零错误
2. **pytest** — `pytest packages/` 通过率 100%
3. **版本一致性** — AST 扫描各包 `__version__` vs `pyproject.toml`
4. **格式检查** — `ruff format --check`

配置在 `projects/kairon/.github/workflows/` 或根级 CI。

#### 交付物

- [ ] `projects/kairon/.omo/` 建立
- [ ] 包治理注册表 YAML 文件（26 包）
- [ ] 5 个包深度分析报告（ecos, eu-pricing, forge, shared-lib, wksp）
- [ ] CI gate 配置（ruff + pytest + version check）

---

### Phase 4: 持续演进（ongoing）

**目标**: 建立持续改进机制，将治理融入日常开发流程。

#### 核心任务

##### 4.1 季度架构审计

每季度运行一次全量审计，审计范围：

1. 新包合规检查 — Ruff、测试、版本一致性
2. 架构债扫描 — LLM 抽象层是否又有新的重复
3. 依赖性分析 — 是否有隐式依赖或循环依赖
4. 测试覆盖评估 — 是否达到目标阈值

审计结果写入 `docs/architecture_audit.md`（追加新章节）。

##### 4.2 债务看板

基于 `.omo/debt/` 运行，维护一个 **Kairon 专属债务看板**：

```yaml
# .omo/debt/kairon-debt.yaml
debts:
  - id: K-001
    title: "LLM 抽象层 4 路重复"
    status: resolved (Phase 1)
    resolved_at: 2026-06-16
  - id: K-002
    title: "engine-core 重复文件"
    status: resolved (Phase 2)
    resolved_at: 2026-06-30
```

##### 4.3 架构决策记录（ADR）

建立 `docs/adr/` 目录，重大架构变更必须记录 ADR：

```
docs/adr/
  ├── README.md          # ADR 索引
  ├── 0001-llm-unification.md
  ├── 0002-ruff-standardization.md
  └── TEMPLATE.md        # ADR 模板
```

**ADR 触发条件**:
- 新增 MCP 服务器
- 新增 LLM Provider
- 修改跨包依赖边界
- 新增共享库模块
- 废弃包或合并包

##### 4.4 跨包协同规则

定义"什么可以跨包 import"的边界规则：

```
允许的跨包 import:
  ✓ core-models → 任何包（依赖根）
  ✓ shared-lib → 任何包（共享工具）
  ✓ llm-gateway → 需要 LLM 能力的包
  ✗ eidos ← kos（反向依赖禁止）
  ✗ 业务层 → 外部集成层（层级倒挂）
```

##### 4.5 成熟度自动评估

基于以下维度自动评分：

| 维度 | 权重 | 评分依据 |
|------|------|---------|
| 测试覆盖率 | 30% | pytest --cov 结果 |
| Lint 通过率 | 20% | ruff 错误数 |
| 文档完备度 | 20% | README、docstring、ADR |
| 版本一致性 | 15% | 代码 vs pyproject |
| 依赖健康度 | 15% | 是否引入循环依赖 |

自动评分集成到 CI 门禁中，**成熟度 < 2★ 的包不能晋升到下一阶段**。

#### 交付物

- [ ] 季度审计 SOP
- [ ] ADR 模板 + 目录（`docs/adr/`）
- [ ] 跨包依赖边界文档（`.omo/standards/import-rules.md`）
- [ ] 成熟度自动评估脚本

---

## 4. 治理规则

### 4.1 硬性门禁（Hard Gate）

以下规则为 **必须遵守** 的硬性门禁，CI 门禁不通过则不允许合入：

| 规则 | 适用范围 | 检测方式 |
|------|---------|---------|
| Ruff 零错误 | 所有 Python 文件 | `ruff check packages/` |
| 测试全部通过 | 所有测试文件 | `pytest packages/` |
| 版本一致性 | 每个包 | AST 扫描 `__version__` vs `pyproject.toml` |
| 格式一致性 | 所有 Python 文件 | `ruff format --check` |

### 4.2 强烈建议（Soft Gate）

以下规则为 **强烈建议**，合入时需在 PR 描述中说明理由：

| 规则 | 适用范围 | 说明 |
|------|---------|------|
| 新包 >=3 个测试文件 | 新创建的包 | 单元 + 集成 + CLI |
| 跨包 import 需 ADR | 所有跨包依赖 | 记录理由和边界 |
| 包成熟度登记 | 每个包 | 首次合入时注册到 registry |
| 重大变更需 ADR | 架构级变更 | MCP 服务器、LLM Provider、共享库 |

### 4.3 最佳实践（Guidance）

以下为推荐实践，鼓励但不强制：

- 每个包使用 `src/` 布局
- CLI 入口统一为 `__main__.py` + `pyproject.toml` scripts
- LLM 调用优先使用 `llm-gateway` 统一接口
- 通用能力优先提取到 `shared-lib`
- 新功能优先基于已有模式（策略模式、事件驱动、Pipeline）

---

## 5. 责任人矩阵

| 领域 | 所有者 | 说明 |
|------|--------|------|
| **架构治理** | TBD | 全局架构决策、ADR 审批、跨包边界定义 |
| **代码质量** | TBD | Ruff 标准维护、lint gate 管理、代码审查规范 |
| **测试治理** | TBD | 测试基线制定、覆盖率门禁、测试框架选型 |
| **包治理** | 各包维护者 | 每个包有明确 owner，维护成熟度注册表 |
| **债务追踪** | TBD | 跟踪 `.omo/debt/kairon-debt.yaml` 更新，定期 review |
| **CI 门禁** | TBD | CI gate 配置维护、版本一致性检测脚本 |
| **LLM 统一专项** | TBD | S-1 执行负责人，确保 3 个适配器完成迁移 |
| **Phase 17 器官迁移** | TBD | D_Economy、D_KnowledgeIntegration 迁移执行 |

**初始设定建议**: 在当前单作者开发模式下，上述角色可由同一人承担。建议随着团队扩展逐步分配。

---

## 6. 与 .omo 治理体系的关系

### 6.1 层次关系

```
工作区级 .omo（根级）
  └── 覆盖所有项目（kairon, SharedBrain, agentmesh, gbrain）
      └── 四平面体系（控制面 · 事实面 · 知识面 · 交付面）
          └── Phase 1~16 已完成

Kairon 项目层（projects/kairon/）
  └── 本治理规划（kairon-governance-plan）
      └── projects/kairon/.omo/（轻量治理目录，Phase 3 目标）
          └── 链接到根级 .omo 的相关目录
```

### 6.2 具体关系

| 维度 | 根级 `.omo` | `kairon` 治理 | 关系 |
|------|-----------|--------------|------|
| 健康分 | `state/system.yaml` → health_score: 29.1 | 健康分子集 | kairon 治理进展直接影响根级健康分 |
| 债务追踪 | `.omo/debt/`（9 项 unresolved） | `.omo/debt/kairon-debt.yaml` | kairon 专项债务看板，同步到根级 |
| 治理标准 | `.omo/standards/` | `.omo/standards/` | kairon 可引用或扩展根级标准 |
| 阶段规划 | `.omo/plans/`（Phase 1~17） | 本规划 Phase 1~4 | kairon 治理是 .omo Phase 17 的"项目执行分册" |
| 包治理 | 无包级注册 | `.omo/registry/packages.yaml` | 首次建立包级治理维度 |

### 6.3 关键桥梁

- **健康分关联**: 根级健康分中的 `debt_weight` 直接关联 kairon 债务项的解决进度。当前 29.1 的健康分有 9 项 unresolved 债务，其中大部分来自 kairon
- **Phase 17 载体**: `kairon` 项目是 `.omo` Phase 17 的核心载体。器官迁移（D_Economy→eu-pricing, D_KnowledgeIntegration→kos）的目标就是 kairon 包
- **门禁联动**: kairon CI gate 结果应上报到根级 `.omo/state/`，形成统一的"治理仪表盘"

---

## 7. 风险与缓解

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|---------|
| **LLM 统一破坏已有功能** | 高 — 4 个包涉及 LLM 调用 | 中 | 每个适配器独立测试 + 回归套件 + 功能冻结期 |
| **Phase 17 器官迁移引入新耦合** | 中 — 迁移可能产生隐式依赖 | 中 | 代码审查严格把关 + 依赖拓扑分析 + 迁移后审计 |
| **治理体系过度治理拖慢开发** | 中 — 门禁过多影响开发效率 | 低 | 软硬门禁分层（Hard Gate / Soft Gate / Guidance），先硬后软 |
| **6 个未提交包已落后主线** | 中 — 兼容性问题或功能冲突 | 高 | 提交前做 git diff 分析 + 功能兼容性检查 + 渐进式合入 |
| **测试基线推高维护成本** | 低 — 测试本身需要维护 | 中 | 测试策略按包成熟度分级，Alpha 包可适当降低要求 |
| **单作者瓶颈** | 中 — 所有角色由同一人承担 | 高 | 保持治理过程文档化，降低交接成本；角色矩阵预留扩展位 |
| **健康分 29.1 短期内难以显著提升** | 低 — 影响团队信心 | 高 | 聚焦 Phase 1 快速见效项（Ruff 统一、版本修复），建立早期动量 |

### 7.1 应急路线（如果 Phase 1 延期）

1. **优先交付**: Ruff 统一 + 版本修复（1-2 天）→ 快速提升代码一致性
2. **必须交付**: LLM 统一至少完成 1 个适配器 + 回归测试
3. **可延期**: 测试基线 → 延至 Phase 2 或与 LLM 统一并行

---

## 8. 附录：状态追踪

### 8.1 包状态追踪表

| 包名 | 版本 | 成熟度 | 测试文件数 | 测试目标 | Ruff 状态 | LLM 统一状态 | 责任人 | 备注 |
|------|------|--------|-----------|---------|----------|-------------|--------|------|
| agora | 2.0.0 | Stable | 49 | 50%+ | ❌ 待统一 | N/A（不含 LLM） | TBD | 核心包，测试基础好 |
| minerva | 0.11.0 | Beta | 34 | 50%+ | ❌ 待统一 | 🔄 需适配（OpenAICompatibleClient） | TBD | 最大包之一 |
| kos | 2.0.0 | Stable | 22 | 50%+ | ❌ 待统一 | N/A | TBD | 知识 OS，Phase 17 W1 目标 |
| ssot | 1.0.0 | Stable | 11 | 50%+ | ❌ 待统一 | 🔄 需适配（LLMBackend） | TBD | SSOT 知识引擎 |
| ontoderive | 3.6.4 | Stable | 50 | 60%+ | ❌ 待统一 | 🔄 需适配（BaseProvider） | TBD | 测试覆盖最佳 |
| cron-service | 1.0.0 | Stable | 1 | 60%+ | ❌ 待统一 | N/A | TBD | 定时任务调度 |
| kairon-assistant | 1.0.0 | Stable | 2 | 60%+ | ❌ 待统一 | N/A | TBD | 需修复缺失文件 |
| kairon-voice | 1.0.0 | Stable | 1 | 60%+ | ❌ 待统一 | N/A | TBD | 语音子系统 |
| kaironcloud-billing | 0.1.0 | Alpha | 5 | 60%+ | ❌ 待统一 | N/A | TBD | 计费系统 |
| sophia | 0.2.1 | Beta | 6 | 30%+ | ❌ 待统一 | N/A | TBD | 符号范式引擎 |
| kronos | 0.4.0 | Beta | 9 | 30%+ | ❌ 待统一 | N/A | TBD | 版本不一致需修复 |
| codeanalyze | 0.3.0 | Beta | 9 | 30%+ | ❌ 待统一 | N/A | TBD | 代码分析工具 |
| forge | 1.3.0 | Beta | 11 | 30%+ | ❌ 待统一 | N/A | TBD | ⚪ 需深度分析 |
| eidos | 0.1.0 | Alpha | 19 | 30%+ | ❌ 待统一 | N/A | TBD | 记忆与知识管理 |
| metaos | 0.1.0 | Alpha | 11 | 30%+ | ❌ 待统一 | N/A | TBD | ⚠️ 版本严重不一致 |
| ecos | 0.6.0 | Alpha | 12 | 30%+ | ❌ 待统一 | N/A | TBD | ⚪ 需深度分析 |
| iris | 0.1.0 | Alpha | 10 | 30%+ | ❌ 待统一 | N/A | TBD | 连接器中心 |
| agent-runtime | 0.1.0 | Alpha | 6 | 30%+ | ❌ 待统一 | N/A | TBD | Agent 运行时 |
| core-models | 0.1.0 | Alpha | 2 | 30%+ | ❌ 待统一 | N/A | TBD | 依赖根 |
| engine-core | 0.1.0 | Alpha | 2 | 30%+ | ❌ 待统一 | N/A | TBD | 需重构，含重复文件 |
| llm-gateway | 0.1.0 | Alpha | 1 | 30%+ | ❌ 待统一 | 🟢 统一载体（ABC） | TBD | LLM 统一的核心 |
| shared-lib | 0.1.0 | Alpha | 7 | 30%+ | ❌ 待统一 | N/A | TBD | ⚪ 需深度分析 |
| sharedbrain-bridge | 0.1.0 | Alpha | 2 | 30%+ | ❌ 待统一 | N/A | TBD | HTTP 桥接 |
| eu-pricing | 0.1.0 | Alpha | 3 | 30%+ | ❌ 待统一 | N/A | TBD | ⚪ 需深度分析 |
| symphony-protocol | 0.1.0 | Alpha | 1 | 30%+ | ❌ 待统一 | N/A | TBD | 阶段门控协议 |
| wksp | 0.2.0 | Alpha | 40 | 30%+ | ❌ 待统一 | N/A | TBD | ⚪ 需深度分析 |

**状态标记**: ❌ 未完成 · 🟢 已完成 · 🔄 进行中 · ⚪ 待分析 · ⚠️ 需关注

### 8.2 阶段进度追踪

| Phase | 状态 | 计划开始 | 计划完成 | 实际完成 | 交付物数 | 笔记 |
|-------|------|---------|---------|---------|---------|------|
| Phase 1 | 📋 Planned | - | - | - | - | 基础治理 |
| Phase 2 | 📋 Planned | - | - | - | - | 架构清理 |
| Phase 3 | 📋 Planned | - | - | - | - | 治理体系落地 |
| Phase 4 | 📋 Planned | - | - | - | - | 持续演进 |

**状态标记**: 📋 Planned · 🔄 In Progress · ✅ Completed · ❌ Delayed

### 8.3 债务追踪表

| ID | 债务 | Phase | 状态 | 风险等级 | 说明 |
|----|------|-------|------|---------|------|
| K-001 | LLM 抽象层 4 路重复 | Phase 1 | 🔴 Unresolved | P0 | S-1 |
| K-002 | Ruff 配置不一致 | Phase 1 | 🔴 Unresolved | P1 | S-2 |
| K-003 | 测试覆盖严重不足 | Phase 1~3 | 🔴 Unresolved | P1 | S-3 |
| K-004 | engine-core 重复/空文件 | Phase 2 | 🟡 Unresolved | P2 | S-4 |
| K-005 | 版本内外不一致（metaos, kronos） | Phase 1 | 🟡 Unresolved | P2 | S-5 |
| K-006 | 共享能力未提取 | Phase 2 | 🟡 Unresolved | P2 | S-6 |
| K-007 | kairon-assistant 缺失文件 | Phase 1 | 🟡 Unresolved | P2 | 引用 governance_integration.py |
| K-008 | 5 包未深度分析 | Phase 3 | ⚪ Unresolved | P2 | ecos/eu-pricing/forge/shared-lib/wksp |
| K-009 | 外部依赖混淆（hermes_ops） | Phase 3 | 🟡 Unresolved | P2 | 独立 TS 项目 |

---

> **维护者**: TBD | **更新频率**: 每 Phase 结束时
> **下一版本预计**: Phase 1 完成后发布 V2
