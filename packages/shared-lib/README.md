# shared-lib

> Kairon shared library — core business logic

Kairon 包。详见 [kairon/CLAUDE.md](../CLAUDE.md)。

## 拆解记录（2026-06-06）

以下子包已从 shared-lib 独立：

| 新包 | 内容 | 测试 |
|------|------|------|
| [kairon-lib-events](../kairon-lib-events/) | 事件总线模型（BOSEvent, EventBusProtocol） | 44 |
| [kairon-utils](../kairon-utils/) | 通用工具（日志/重试/限流/错误/SQLite） | 167 |
| [kairon-plugin-sdk](../kairon-plugin-sdk/) | 插件 SDK（BosPlugin, PluginContext） | 12 |
| [kairon-observability](../kairon-observability/) | 可观测性（指标/告警/异常/SLO） | 6 |
| [kairon-pipeline](../kairon-pipeline/) | 数据管道（数据源/提取器/质量门） | 5 |

## 当前范围

shared-lib 当前保留以下核心业务模块：
- `core/` — 工作流引擎、委员会系统、安全、威胁、LLM 客户端等
- `governance/` — 审批路由、投票、用户否决、伦理治理
- `cognitive/` — 认知推理、知识图谱、RAG、思维系统
- `audit/` — 审计追踪、回顾、场景引擎

向后兼容的 facade 重导文件保留在 `kairon_lib/events.py`、`kairon_lib/errors.py` 等位置。
