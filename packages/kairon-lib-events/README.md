# kairon-lib-events

> Shared event data model for kairon event bus systems

从 `shared-lib` 拆出的独立包（2026-06-06）。

## 公共 API

```python
from kairon_events import BOSEvent, BosEvent, make_event
from kairon_events import EventBusProtocol, EventType
from kairon_events import get_event_bus, get_global_event_bus, register_global_event_bus
```

- `BOSEvent` / `BosEvent` — 规范事件数据类
- `EventBusProtocol` — 运行时检查的事件总线协议
- `EventType` — 规范事件类型枚举
- `make_event()` — 自动填充时间戳和 event_id 的工厂函数
- `get_event_bus()` — 获取全局 EventBus（含 Null 回退）
- `get_global_event_bus()` / `register_global_event_bus()` — 全局注册表

## 依赖

- 零运行时依赖（仅 stdlib）
- Python >= 3.10

## 测试

```bash
uv run --package kairon-lib-events pytest tests/ -v
# 44 passed
```
