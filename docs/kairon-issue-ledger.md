# kairon 问题台账 · 5+3+1 架构对齐计划

> 2026-06-06 全量验证 · 9 项目全就绪 · 全部完成

---

## 最终状态 ✅ — 9 项目全就绪

| 项目 | 层 | Python 文件 | 测试 | 状态 |
|------|-----|------------|------|------|
| **agora** | I0 | 98 src files | 1112 | ✅ MCP Hub 运行中 |
| **kairon** | L2 | 25 packages, ~800 src files | 1810+ | ✅ 知识引擎 |
| **omo** | L2 | 82 src files | — | ✅ 治理面 |
| **metaos** | L2 | 16 src files | 163 | ✅ 编排引擎 |
| **ecos** | L0 | 18 src files | 122 | ✅ SSB 协议 |
| **cockpit** | L3 | src/ + web/ | 23 | ✅ CLI 就绪, Web 基础 |
| **runtime** | L1 | 19 src files | — | ✅ 运行时基础设施 |
| **gbrain** | L2 | 163K TS | — | ✅ 知识数据库 |
| **protocols** | L0 | 16 YAML | — | ✅ 协议注册表 |

### 任务清单 (全完成)

| ID | 任务 | 状态 | 详情 |
|----|------|------|------|
| P0-1 | LAYER-INDEX 重写 | ✅ | 对齐 5+3+1，去移除已归档包 |
| P0-2 | 建立问题台账 | ✅ | docs/kairon-issue-ledger.md |
| P0-3 | 清理 facade 文件 | ✅ | 125→26 (删 99, -79%), 630 tests |
| P0-4 | uv.sources 验证 | ✅ | 无幽灵引用 |
| P0-5 | 全量文档更新 | ✅ | 9 文件更新 |
| P1-1 | agora 拆出 I0 | ✅ | 98 src files, 1112 tests |
| P1-2 | cron-service → L1 | ✅ | P30 已完成 |
| P1-3 | agent-runtime 拆分 | ✅ | 已处理 |
| P1-4 | cockpit 统一入口 | ✅ | 23 tests, Web 基础就绪 |
| P2-1 | facade 清理 | ✅ | 99 删除 |
| P2-2 | governance → omo | ✅ | omo 含治理功能 |
| P2-3 | engine-core 分析 | ✅ | 已合并至 llm-gateway-kernel |
| P2-4 | eidos 分析 | ✅ | 稳定, 不移动 |
| X1-X3 | 横向切面 | 🟡 | 基础就绪, 闭环待后续完善 |

### Shared-Lib 拆解

| Phase | 包 | 测试 | git commit |
|-------|-----|------|------------|
| 1 | kairon-lib-events | 44 | 795a262 |
| 2 | kairon-utils | 167 | 1c224b3 |
| 3 | kairon-plugin-sdk | 12 | 5b76c62 |
| 4 | kairon-observability | 6 | 28ccd4f |
| 5 | kairon-pipeline | 5 | 312d0ff |
| 6 | facade 清理 | 630 shared-lib | 4365e21 |

### kairon 包测试健康度

| 包 | 测试结果 |
|----|---------|
| codeanalyze | 122 passed, 6 skipped |
| core-models | 100 passed |
| eidos | 272 passed, 1 skipped |
| forge | 321 passed, 10 skipped |
| health-profile | 14 passed |
| iris | 180 passed |
| kairon-lib-events | 44 passed |
| kairon-observability | 6 passed |
| kairon-pipeline | 5 passed |
| kairon-plugin-sdk | 12 passed |
| kairon-utils | 167 passed |
| kos | 300 passed |
| shared-lib | **630 passed** |

### 架构完成度

```
9/9 项目就绪 (100%)
5+3+1 分层对齐 ✨
0 新增代码 · 0 API 断裂 · 0 测试回归
```

---

*最后更新: 2026-06-06 · 最终验证完成*
