# kairon 问题台账 · 5+3+1 架构对齐计划

> 2026-06-06 修复完成 · 21→5 剩余债务

---

## 已修复 ✅

| ID | 项目 | 问题 | 修复 |
|----|------|------|------|
| DEBT-001 | cockpit | MCP server 缺失 (38 tests fail) | ✅ 实现 15 MCP 工具, 38 passed |
| DEBT-002 | cockpit | web/ Agora 代码 | ✅ 已文档化，划归 Agora 演示面 |
| DEBT-003 | agora | agora-mcp-gateway entry point broken | ✅ 创建 mcp_gateway.py shim |
| DEBT-005 | agora | KNOW_SERVICES 引用已移包 | ✅ 更新 source 字段 |
| DEBT-006 | cockpit | click 死依赖 | ✅ 移除 |
| DEBT-007 | cockpit | 3 staleness 测试 | ✅ 更新为当前服务列表 |
| DEBT-008 | metaos | version 不一致 | ✅ 统一为 0.1.0 |
| DEBT-016 | omo | goals 标记过时 | ✅ P30.1-P30.7 done, phase 27→28 |
| DEBT-021 | agora | 旧 kairon_lib 路径 | ✅ 更新为 kairon_events/observability |

## 剩余 (5 项, 低优先)

| ID | 项目 | 问题 | 原因 |
|----|------|------|------|
| DEBT-004 | ecos | 9 tests fail (硬编码路径) | 路径依赖个人环境 |
| DEBT-009 | runtime | bus_consumer.py 硬编码 GBRAIN_DIR | 跨项目路径耦合 |
| DEBT-010 | runtime | scheduler.py 硬编码 OMO_STATE_FILE | 绝对路径硬编码 |
| DEBT-011 | ecos | type:ignore import-not-found | 导入链存在循环依赖风险 |
| DEBT-014 | omo | MCP subprocess 包装效率低 | 架构决策，非bug |

## 修复效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 严重债务 | 7 | 0 |
| 警告债务 | 9 | 4 |
| cockpit MCP 工具 | 0 | 15 |
| cockpit 测试 | 445 | 486 |
| shared-lib 测试 | 630 | 630 |

---

*最后更新: 2026-06-06 · 修复完成*
