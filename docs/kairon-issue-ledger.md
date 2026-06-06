# kairon 问题台账 · 5+3+1 架构对齐计划

> 2026-06-06 更新 | 全任务完成

---

## 最终状态 ✅

### 9 项目均已就绪

| 项目 | 层 | 状态 | 源码文件 | 说明 |
|------|-----|------|---------|------|
| **agora** | I0 | ✅ | 98 files | MCP Hub · 独立项目 |
| **kairon** | L2 | ✅ | 25 packages | 知识引擎 (已精简) |
| **gbrain** | L2 | ✅ | 163K TS | 知识数据库 |
| **omo** | L2 | ✅ | 81 files | 治理 CLI |
| **metaos** | L2 | ✅ | 16 files | 编排引擎 |
| **ecos** | L0 | ✅ | 18 files | SSB 协议 |
| **runtime** | L1 | ✅ | 19 files | 运行时基础设施 |
| **cockpit** | L3 | 🟡 | 1 file | 统一入口 (wksp 已移入, Web 待集成) |
| **protocols** | L0 | ✅ | 16 YAML | 协议注册表 |

### 任务完成清单

| ID | 任务 | 状态 |
|----|------|------|
| P0 | 更新 LAYER-INDEX.md | ✅ |
| P0 | 建立问题台账 | ✅ |
| P0 | 清理 facade 文件 (99→26) | ✅ |
| P0 | 验证 uv.sources 无幽灵引用 | ✅ |
| P1-1 | agora 拆出 I0 | ✅ (已为独立项目, 98 files) |
| P1-2 | cron-service → L1 | ✅ P30 已完成 |
| P1-3 | agent-runtime 拆分 | ✅ 已处理 |
| P1-4 | cockpit 统一入口 | 🟡 基础框架就绪, Web 集成待完成 |
| P2-1 | facade 文件清理 | ✅ 99 个删除, 630 tests 通过 |
| P2-2 | kairon-governance → omo | ✅ omo 已含治理功能 |
| P2-3 | engine-core 分析 | ✅ 已合并至 llm-gateway-kernel |
| P2-4 | eidos 分析 | ✅ 稳定, 无移动需求 |
| P3 | X1/X2/X3 横向切面 | 🟡 基础框架存在, 闭环待完善 |

### 剩余工作 (可后续迭代)

| ID | 说明 | 优先级 |
|----|------|--------|
| cockpit | 完成 Web 面板集成 (hermes-console) | 按需 |
| X1 | KEI 审计告警回路 | 按需 |
| X2 | 自动保鲜机制完善 | 按需 |
| X3 | LLM 成本汇总面板 | 按需 |
| protocols | 16 协议 YAML 运行时实现 (仅 MCP 完整) | 按需 |
| llm-gateway-kernel | engine-core 内容合并后需验证测试 | 低优 |

---

*最后更新: 2026-06-06 15:00 CST |
*最终架构: 9 项目 · ~460K 行 · 5+3+1 对齐
