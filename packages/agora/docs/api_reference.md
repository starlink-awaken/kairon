# Agora API Reference

> Version: 1.2.0 — MCP 服务汇聚枢纽

## Quick Reference

| Module | Key Class | Purpose |
|--------|-----------|---------|
| `agora.mcp_proxy.registry` | `ProxyRegistry` | 工具→服务映射，连接管理 |
| `agora.mcp_proxy.manager` | `ProxyManager` | 下游 MCP 服务连接生命周期 |
| `agora.mcp_registry.repository` | `ToolCatalog` | SQLite 工具元数据仓库 |
| `agora.mcp_registry.lifecycle` | `LifecycleManager` | 动态加载/卸载 |
| `agora.mcp_registry.router` | `SmartRouter` | 智能查询路由 |
| `agora.mcp_registry.orchestrator` | `Orchestrator` | 高级工作流编排 |
| `agora.mcp_registry.embeddings` | `EmbeddingStore` | 语义搜索 |
| `agora.mcp_registry.evaluator` | `QualityScorer` | 工具质量评分 |
| `agora.mcp_registry.sources` | — | GitHub/Registry 搜索源 |
| `agora.server.mcp` | — | FastMCP 服务端点 |
| `agora.event_bus` | `EventBus` | 事件发布/订阅 |
| `agora.authorizer` | `Authorizer` | 访问控制 |

---

## 1. ProxyRegistry (`agora.mcp_proxy.registry`)

核心代理注册表，维护工具名到下游 MCP 服务的映射。

```python
class ProxyRegistry:
    def __init__(self)

    # Callback management (supports multiple callbacks)
    def add_usage_callback(callback: Callable)      # 添加使用回调
    def remove_usage_callback(callback: Callable)    # 移除使用回调
    def add_unload_callback(callback: Callable)      # 添加卸载回调
    def remove_unload_callback(callback: Callable)   # 移除卸载回调

    # Query
    def entries() -> dict[str, ProxyEntry]           # 所有条目
    def connected_services() -> list[str]            # 已连接服务列表
    def ref_counts() -> dict[str, int]               # 引用计数
    def known_services() -> list[str]                # 所有已知服务
    def get_entry(tool_name: str) -> ProxyEntry | None
    def is_connected(service_name: str) -> bool
    def get_tool_schemas() -> list[dict]             # 所有工具 schema

    # Config persistence
    def save_config(service_name: str, config: dict)
    def get_saved_config(service_name: str) -> dict | None
    def forget_config(service_name: str)
    def has_saved_config(service_name: str) -> bool

    # Connection management
    def acquire(service_name: str) -> int            # 引用计数 +1
    def release(service_name: str) -> int            # 引用计数 -1
    async def lazy_connect(service_name: str) -> bool
    async def register_service(service_name: str, client: MCPClient) -> bool
    async def unregister_service(service_name: str)
    async def unregister_and_forget(service_name: str)
    async def register_from_registry(service_registry, proxy_configs=None)
    async def dispatch(tool_name: str, arguments: dict) -> dict
    async def disconnect_all()
```

### 典型使用

```python
from agora.mcp_proxy.registry import ProxyRegistry

registry = ProxyRegistry()

# 添加使用回调（支持多个）
def on_usage(service_name, tool_name, arguments):
    print(f"{service_name}/{tool_name} called")

registry.add_usage_callback(on_usage)

# 注册服务客户端
client = create_client("my-service", ...)
await registry.register_service("my-service", client)

# 分发调用
result = await registry.dispatch("my-tool", {"arg1": "value"})
```

---

## 2. ProxyManager (`agora.mcp_proxy.manager`)

管理下游 MCP 客户端连接的生命周期，支持空闲超时和引用计数。

```python
class ProxyManager:
    def __init__(
        services: list[dict] | None = None,
        registry: ProxyRegistry | None = None,
        event_bus: EventBus | None = None
    )

    # Idle timeout
    def is_idle_timeout_enabled() -> bool
    def enable_idle_timeout(config: IdleTimeoutConfig | None = None)
    async def disable_idle_timeout()
    def get_idle_timeout_status() -> dict

    # Service lifecycle
    async def start(services: list[dict]) -> dict[str, str]
    async def add_service(svc: dict) -> str
    async def remove_service(name: str) -> str
    async def reload_service(name: str) -> str

    # Connection management
    def acquire(service_name: str) -> int
    def release(service_name: str) -> int
    async def ensure_connected(service_name: str) -> bool
    async def dispatch(tool_name: str, arguments: dict) -> dict
    def status() -> dict
    async def shutdown()
```

### Service Config 格式

```python
{
    "name": str,              # 服务名称
    "command": str,           # 启动命令
    "args": list[str],        # 命令参数
    "cwd": str,               # 工作目录
    "mcp_endpoint": str,      # MCP 端点 URL ("stdio" 表示 stdio 模式)
    "env": dict | None,       # 环境变量
    "init_timeout": float,    # 初始化超时(秒)
}
```

---

## 3. ToolCatalog (`agora.mcp_registry.repository`)

SQLite 后端工具元数据仓库。

```python
class ToolCatalog:
    def __init__(db_path: str | None = None)

    # 工具条目包含字段:
    #   id, name, description, status, source, quality,
    #   stars, version, install_path, install_error, usage_count, tags

    def add_tool(tool_info: dict) -> str               # 返回 tool_id
    def get_tool(tool_id: str) -> dict | None
    def list_tools(status: str | None = None) -> list[dict]
    def search_tools(query: str = "", status: str | None = None, limit: int = 20) -> list[dict]
    def count_by_status() -> dict[str, int]
    def update_status(tool_id: str, status: str) -> bool
    def record_usage(tool_id: str) -> bool
    def update_quality(tool_id: str, score: float) -> bool
    def update_entry(tool_id: str, entry: str, install_path: str, ...)
    def update_install(tool_id: str, install_path: str, install_error: str = "") -> bool
    def remove_tool(tool_id: str) -> bool
    def close()
```

### 工具状态机

```
discovered → installed → loaded ↔ idle
```

---

## 4. LifecycleManager (`agora.mcp_registry.lifecycle`)

动态加载/卸载 MCP 工具，支持空闲超时和健康检查。

```python
class LifecycleManager:
    def __init__(
        catalog: ToolCatalog,
        proxy: ProxyManager,
        idle_timeout: float = 300.0,
        check_interval: float = 60.0
    )

    async def load_tool(tool_id: str) -> bool
    async def unload_tool(tool_id: str) -> bool
    async def record_usage(tool_id: str)
    async def load_by_status(status: str = "idle") -> int
    async def unload_by_status(status: str = "loaded") -> int
    def get_status() -> dict
    async def start_health_watch()
    async def stop_health_watch()
    async def start_idle_watch()
    async def stop_idle_watch()
    async def close()
```

---

## 5. SmartRouter (`agora.mcp_registry.router`)

智能查询路由，支持三种模式。

```python
class SmartRouter:
    def __init__(
        catalog: ToolCatalog,
        embeddings: EmbeddingStore | None = None,
        llm_config: dict | None = None
    )

    def llm_available() -> bool
    async def route(query: str, mode: str = "auto") -> dict
    def status() -> dict
```

### 路由模式

| 模式 | 行为 |
|------|------|
| `direct` | 解析工具名，精确匹配 |
| `recommend` | 语义搜索 + 可选 LLM 推荐 |
| `auto` | 级联: direct → recommend → 外部发现 |

---

## 6. Orchestrator (`agora.mcp_registry.orchestrator`)

高级工作流编排，串联发现→安装→加载流水线。

```python
class Orchestrator:
    def __init__(catalog: ToolCatalog, lifecycle: LifecycleManager | None = None)

    async def discover_and_save(query: str, max_results: int = 10, sources=None, auto_evaluate: bool = True)
    async def discover_install_load(query: str, sources=None, auto_evaluate: bool = True, auto_load: bool = False)
    async def install_tool(name: str) -> tuple[bool, str]
    async def ensure_tool_available(name: str) -> tuple[bool, str]
    async def load_tool(name: str) -> tuple[bool, str]
    async def unload_tool(name: str) -> tuple[bool, str]
    async def reload_tool(name: str) -> tuple[bool, str]
    async def load_all_idle() -> int
    async def unload_all_loaded() -> int
    async def start_idle_watch()
    async def stop_idle_watch()
    async def start_health_watch()
    async def stop_health_watch()
    def get_status() -> dict
    async def record_usage(tool_id: str)
    async def close()
```

---

## 7. EmbeddingStore (`agora.mcp_registry.embeddings`)

语义搜索用的嵌入向量存储，基于 SQLite + sentence-transformers。

```python
class EmbeddingStore:
    def __init__(db_path: str, auto_refresh: bool = True)

    def available() -> bool
    def compute_embedding(text: str) -> list[float] | None
    def refresh_cache()
    def save_embedding(tool_id: str, embedding: list[float]) -> bool
    def save_text_embedding(tool_id: str, text: str) -> bool
    def search_similar(query: str, top_k: int = 10) -> list[tuple[str, float]]
    def rebuild_all(catalog: ToolCatalog) -> int
    def stats() -> dict
    def close()
```

---

## 8. QualityScorer (`agora.mcp_registry.evaluator`)

工具质量评分，满分 1.0。

```python
class QualityScorer:
    # 权重配置
    WEIGHTS = {
        "stars": 0.20, "freshness": 0.15, "version": 0.15,
        "local_usage": 0.25, "success_rate": 0.15, "verified": 0.10
    }

    @classmethod
    def normalize_stars(stars: int) -> float
    @classmethod
    def normalize_freshness(updated_at: str | None) -> float
    @classmethod
    def normalize_version(version: str | None) -> float
    @classmethod
    def normalize_local_usage(usage_count: int) -> float
    @classmethod
    def evaluate(tool_info: dict) -> float
    @classmethod
    def evaluate_batch(tools: list[dict]) -> list[dict]
```

---

## 9. Search Sources (`agora.mcp_registry.sources`)

外部工具的搜索发现。

```python
async def search_github(
    query: str = "mcp-server",
    min_stars: int = 0,
    max_results: int = 30
) -> list[dict]

async def search_registry(
    registry_url: str | None = None
) -> list[dict]

async def search_all(
    query: str = "mcp-server",
    sources: list[str] | None = None     # None = 全部源
) -> list[dict]
```

---

## 10. Server MCP Tools (`agora.server.mcp`)

通过 FastMCP 暴露的所有工具端点。返回格式统一为 `_ok()`/`_error()`。

### 代理工具 (6)

| Tool | 参数 | 说明 |
|------|------|------|
| `proxy_connect` | — | 连接所有已配置服务 |
| `proxy_call` | `tool_name`, `arguments` | 调用下游工具 |
| `proxy_status` | — | 代理状态 |
| `proxy_add_service` | `name`, `mcp_endpoint`, `command`, `args`, ... | 动态添加服务 |
| `proxy_remove_service` | `name` | 移除服务 |
| `proxy_list_tools` | — | 列出代理工具列表 |

### 注册工具

| Tool | 参数 | 说明 |
|------|------|------|
| `register_service` | `name`, `description`, `protocol`, ... | 注册服务 |
| `list_services` | — | 列出服务 |
| `check_health` | — | 健康检查 |
| `add_route` | `tool_name`, `service_name` | 添加路由 |
| `list_routes` | — | 列出路由 |
| `route_call` | `tool_name`, `arguments`, `caller_identity` | 路由调用 |

### A2A 异步任务

| Tool | 参数 | 说明 |
|------|------|------|
| `a2a_send_task` | `tool_name`, `arguments`, `session_id` | 提交任务 |
| `a2a_get_task` | `task_id` | 获取任务 |
| `a2a_cancel_task` | `task_id` | 取消任务 |
| `a2a_list_tasks` | `service`, `status`, `since`, `limit` | 任务列表 |

### 生命周期管理

| Tool | 参数 | 说明 |
|------|------|------|
| `repo_search` | `query`, `source`, `limit` | 搜索工具 |
| `repo_discover` | `query` | 外部发现 |
| `repo_install` | `name` | 安装工具 |
| `repo_load` | `name` | 加载工具 |
| `repo_unload` | `name` | 卸载工具 |
| `repo_pipeline` | `query`, `auto_load` | 完整流水线 |
| `lifecycle_status` | — | 生命周期状态 |
| `lifecycle_start_watch` | `idle_timeout`, `check_interval` | 启动监控 |
| `lifecycle_stop_watch` | — | 停止监控 |
| `lifecycle_load_all` | — | 加载所有 |
| `lifecycle_unload_all` | — | 卸载所有 |

### 事件 & 审计

| Tool | 参数 | 说明 |
|------|------|------|
| `publish_event` | `event_type`, `payload`, `source` | 发布事件 |
| `subscribe_event` | `pattern`, `callback_url` | 订阅事件 |
| `get_event_log` | `limit`, `since` | 事件日志 |
| `audit_query` | `actor`, `resource`, `event_type`, `since`, `limit` | 审计查询 |
| `audit_stats` | `since` | 审计统计 |

### 治理

| Tool | 参数 | 说明 |
|------|------|------|
| `create_api_key` | `name`, `scopes`, `tenant`, `expires_days` | 创建 API 密钥 |
| `list_api_keys` | `tenant` | 列出密钥 |
| `revoke_api_key` | `key_id` | 吊销密钥 |
| `get_state_transitions` | `service`, `since`, `limit` | 状态变更历史 |
| `list_agent_cards` | — | Agent Card 列表 |
| `get_agent_card` | `name` | Agent Card 详情 |

### 智能路由入口

```python
async def agora_execute(query: str, mode: str = "auto") -> dict:
    """Execute a natural-language query via SmartRouter."""
```

---

## 11. EventBus (`agora.event_bus`)

事件发布/订阅系统。

```python
class EventBus:
    def __init__()
    def subscribe(pattern: str, callback: Callable) -> str           # 返回 subscription_id
    def unsubscribe(subscription_id: str)
    def publish(event_type: str, payload: Any, source: str = "")
    def get_log(limit: int = 50, since: str = "") -> list[dict]
    def close()

# 事件类型格式
event_type: str = "{domain}:{action}"  # 例如 "registry:service.registered"
```

---

## 12. Authorizer (`agora.authorizer`)

授权和访问控制。

```python
class Authorizer:
    def __init__(store_path: str | None = None)
    def authorize(subject: str, capability: str, resource: dict | None = None) -> bool
    def grant(subject: str, capability: str, scope: str = "", constraints: str = "") -> str
    def revoke(grant_id: str)
    def list_grants(subject: str | None = None) -> list[dict]
    def check(subject: str | None = None, tool: str | None = None, cost: float | None = None) -> dict
```

---

## 响应格式

所有服务端工具函数返回统一格式的 dict：

```python
# 成功
{"status": "ok", "data": {...}, "format_version": "agora-v1"}

# 失败
{"status": "error", "error": "错误消息", "code": "ERROR_CODE", "format_version": "agora-v1"}
```

---

## CLI 命令结构

所有 CLI 命令通过 `agora.cli.parser.build_parser()` 注册，通过 `agora.cli.main()` 分发。

```bash
agora <command> [subcommand] [options]
```

完整命令列表见 `docs/retrospective.md` 附录 A。
