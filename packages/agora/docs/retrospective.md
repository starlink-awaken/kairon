# Agora 项目复盘报告

日期: 2026-06-02

## 1. 系统概述

Agora 是 kairon 生态中的 **MCP 服务汇聚枢纽（Service Convergence Hub）**。它将多个下游 MCP 服务（kairon 工作空间包、npm 全局工具、Docker 网关、Homebrew 工具等）聚合并对外暴露为一个统一的 FastMCP 服务器。LLM 客户端（如 Claude Code）只需连接 Agora 一个端点，即可访问全部 19 个已知服务以及动态加载的第三方工具。

Agora 以 FastMCP 为核心框架，提供三套运行模式：stdio 模式（`main()`）、HTTP 模式（`http_main()`，端口 7422）和 SSE 模式（`sse_main()`，端口 7431）。启动时自动检测工作空间、生成代理配置，并通过 `ProxyManager` 管理与下游服务的子进程生命周期。

**核心架构图**：

```
LLM Client (Claude Code / cursor / …)
        │
        ▼
  ┌─────────────────┐
  │  FastMCP Server │  40 个原生 @mcp.tool + N 个动态代理工具
  │  (stdio/HTTP/SSE)│  + AuthMiddleware (AGORA_API_KEY)
  └────────┬────────┘
           │
           ├──→ ProxyManager ──→ StdioMCPClient ──→ 下游 MCP 服务（子进程）
           │       (dispatch / idle_timeout / 引用计数)
           │
           ├──→ Router / SmartRouter ──→ EmbeddingStore ──→ 语义路由
           │       (负载均衡 / 熔断器 / 审计 / 计费)
           │
           ├──→ ServiceRegistry ──→ SQLite / JSON 双写
           │       (健康检查 / 熔断器 / 状态追踪)
           │
           └──→ EventBus / Audit / KeyManager / TenantManager
                   (事件 / 审计 / 认证 / 多租户 / 配额)
```

### 系统分层概览

| 层次 | 组件 | 职责 |
|------|------|------|
| **接入层** | FastMCP Server | 统一 MCP 协议入口，40 个原生工具 + N 个动态代理工具 |
| **路由层** | Router / SmartRouter | 工具→服务映射，负载均衡，自然语言路由 |
| **代理层** | ProxyManager / ProxyRegistry | 下游服务连接管理，工具注册，空闲超时 |
| **协议层** | StdioMCPClient / HttpMCPClient | JSON-RPC 2.0 协议实现 |
| **注册层** | ServiceRegistry | 服务元数据存储，健康检查，熔断器 |
| **治理层** | Audit / Auth / Tenancy / Quota | 审计日志，API 密钥，多租户，计费 |
| **管道层** | Pipeline / Orchestrator / Lifecycle | 数据处理，工具全生命周期管理 |

---

## 2. 用户分类

Agora 面向四类用户角色。每个角色有不同的身份背景、使用方式和核心诉求。

| 角色 | 身份 | 使用方式 | 核心诉求 |
|------|------|---------|---------|
| **最终用户** (End User) | Claude Code 等 LLM 客户端 | MCP tools/call | 快速准确地完成任务，无需关心底层服务 |
| **系统管理员** (Admin) | 运维 / 平台工程师 | CLI + MCP 治理工具 | 管理服务、监控状态、安全合规、多租户 |
| **工具开发者** (Tool Developer) | 第三方服务作者 / 发布者 | CLI + Registry 管道 | 发布和维护 MCP 工具，自动化生命周期 |
| **管道操作员** (Pipeline Operator) | 数据 / 研究工作流使用者 | CLI pipeline 命令 | 运行定制化数据处理工作流，知识工程 |

---

## 3. 用户旅程 (User Journeys)

### 旅程A：最终用户 — "我用工具完成任务"

终点用户不直接接触 Agora 的 CLI 或管理界面，而是通过 LLM 客户端（如 Claude Code）间接使用。核心体验是"我告诉 AI 我要做什么，工具自动工作"。

**路径A1：直接调用已知工具**（最常用、性能最优）

这是 LLM 客户端已知工具路径时的最优路径。LLM 会在系统提示中看到 Agora 公开的所有工具（包括原生工具和代理工具的 `ProxyForwardTool` 包装），选择匹配的工具直接调用。

```
用户: "搜索知识库关于量子计算的内容"
LLM: 调用 kos.semantic_search(query="量子计算")
     → FastMCP 匹配已注册的 ProxyForwardTool(name="kos.semantic_search")
     → ProxyManager.dispatch("kos.semantic_search", ...)
     → ProxyRegistry 查找 → StdioMCPClient.send_jsonrpc("tools/call")
     → kos 子进程处理 → JSON-RPC 响应
     → 结果逐层返回
用户: 看到基于知识库的回答
```

性能特征：约 1 次 JSON-RPC 往返，开销最小。

**路径A2：自然语言路由（SmartRouter）**

当 LLM 不确定具体用哪个工具，或者用户用自然语言描述需求时，通过 `agora_execute` 工具进行语义路由。SmartRouter 使用 EmbeddingStore 做语义搜索，支持三级策略（direct→recommend→auto）。

```
用户: "帮我查一下数据库"
LLM: 调用 agora_execute(query="帮我查一下数据库", mode="auto")
     → SmartRouter.route("帮我查一下数据库", mode="auto")
     → 模式: auto → 尝试 direct（无匹配，失败）
     → 回退 recommend → EmbeddingStore.search_similar("数据库")
     → 找到: mcp-server-sqlite (相似度 0.87)
     → 建议: 是否加载并调用 sqlite 工具？
     → 用户确认后，Orchestrator 自动完成 install→load→call
```

性能特征：需要语义嵌入计算 + 可选的 LLM 精排，延迟较高。每次调用会新建 ToolCatalog + EmbeddingStore + SmartRouter 实例（未做组件复用）。

**路径A3：通过路由层调用**

当 LLM 通过 `route_call` 明确指定工具时，经过完整的路由层处理 — 负载均衡、熔断器检查、健康检查、审计、计费和追踪。

```
用户: "运行研究任务关于气候变暖"
LLM: 调用 route_call(tool_name="minerva.research_now", ...)
     → Router.route("minerva.research_now", ...)
     → 负载均衡 → Instance(minerva)
     → 熔断器检查 → 健康检查
     → 通过 → _dispatch → StdioMCPClient
     → 计费 / 审计 / 追踪
     → 返回结果
```

---

### 旅程B：系统管理员 — "我管理系统"

系统管理员是 Agora 最深入的用户，涉及从启动初始化到日常运维的全流程。

**阶段1：启动与初始化**

```
管理员: agora init
     → 引导式设置：检测工作空间、配置代理服务
     → 生成 ~/.agora/agora-proxy-services.json
     → 配置中包含所有 KNOWN_SERVICES 的可用性检查结果

管理员: agora proxy-launch --status
     → 查看 19 个已知服务的可用性和安装状态
     → 输出表格: 服务名 | 来源 | 可用 | 已安装 | 描述

管理员: agora mcp
     → 启动 FastMCP 服务器
     → 自动执行 scan_and_launch → 连接所有 enable=true 的下游服务
     → 后台 _proxy_sync_loop 每 60 秒同步 ServiceRegistry → ProxyRegistry
```

**阶段2：服务注册与路由**

服务注册有两种方式：CLI 注册和 MCP 工具注册。

```
CLI方式:
管理员: agora register my-service --mcp http://localhost:9000/mcp
     → ServiceRegistry.add_service("my-service", ...)
     → 存储到 ~./agora/agora-services.json + ~./agora/agora.db（SQLite 双写）

管理员: agora route my-tool my-service
     → Router.add_route("my-tool", "my-service")
     → 存储到 ~./agora/agora-routes.json

MCP方式:
管理员（通过 Claude Code 等）: register_service(name="my-service", ...)
     → 同时注册到 ServiceRegistry + ProxyRegistry
     → 如果指定了 command 参数，代理也会尝试连接并注册 ProxyForwardTool
```

**阶段3：健康监控**

```
管理员: agora health
     → 检查所有已注册服务
     → psutil: CPU / 内存 / 磁盘
     → 每个服务按协议检查健康端点（HTTP 端点、gRPC 探针等）

管理员: agora health --watch --interval 10
     → 持续监控，每 10 秒刷新

管理员（通过 MCP）: check_health()
     → 返回 {total: N, healthy: N} 的摘要
```

**阶段4：审计与合规**

```
管理员: agora audit --since "2026-06-01T00:00:00Z"
     → 查询持久化的审计日志
     → 支持按 actor / resource / event_type 过滤
     → --stats 参数显示风险等级和事件类型统计

管理员（通过 MCP）: audit_query(actor="pipeline", ...)
     → 读取审计事件，支持按 actor 筛选

管理员: agora key create deploy-key --scopes "read,write"
     → KeyManager 生成新 API 密钥
     → 用于外部客户端 Bearer Token 认证
```

**阶段5：多租户与配额**

```
管理员: agora tenant add team-alpha --services "minerva,kos" --rate-limit 120
     → TenantManager 创建租户
     → 绑定服务白名单
     → 设置速率限制（每分钟请求数）

管理员: agora accounting quota --caller team-alpha --quota 50.0
     → 设置每日预算配额（USD）

管理员: agora accounting top --period day --limit 10
     → 查看调用量排名（按成本排序）
```

---

### 旅程C：工具开发者/发现者 — "我发布和安装工具"

工具开发者可以通过 Agora 的完整的生命周期管理（discover→install→load→call→unload）来发现、评估、安装和使用第三方 MCP 工具。

**阶段1：发现**

工具发现有两个来源：GitHub 搜索（`search_github`）和中央 Registry 查询（`search_registry`）。结果通过 `QualityScorer` 评估后存入本地 `ToolCatalog`（SQLite 数据库）。

```
开发者: agora repo discover "database"
     → search_all("database") → GitHub + registry.json 联合搜索
     → QualityScorer 评估: 星数 / 新鲜度 / 版本 → 排序
     → 保存到本地 ToolCatalog（~/.agora/tools.db）
     → 状态: discovered

开发者: agora repo search "database" --json
     → 查询本地目录中已发现的工具
     --status 过滤: discovered / installed / loaded / idle

开发者（通过 MCP）: repo_discover(query="database")
     → 同样的流程，在 MCP 会话中完成
```

**阶段2：安装**

```
开发者: agora repo install mcp-server-sqlite
     → LifecycleManager.install_tool("mcp-server-sqlite")
     → Market.install()
         → BUILTIN_MARKET 查找或 GitHub API 获取
         → git clone --depth 1
         → pip install -e . 或 npm install --production
     → 状态: discovered → installed
     → 记录 install_path

开发者: agora repo status
     → 查看工具状态分布: {discovered: N, installed: N, loaded: N}
```

**阶段3：加载**

加载是将已安装的工具注册到 ProxyManager 中供实际调用的过程。如果工具未安装，加载操作会自动触发安装。

```
开发者: agora repo load mcp-server-sqlite
     → LifecycleManager.load_tool("mcp-server-sqlite")
     → 如果未安装 → 自动安装
     → 构建代理配置（entry / command / args）
     → ProxyManager.add_service(config)
     → FastMCP 注册 ProxyForwardTool
     → 后台 _idle_watch_loop 开始倒计时
     → 状态: installed → loaded

开发者: agora repo list --status loaded
     → 查看所有已加载的工具
```

**阶段4：全自动管道**

```
开发者: agora repo pipeline "mcp-server"
     → Orchestrator.discover_install_load("mcp-server")
     → 发现 → 保存 → 安装 → 加载（一次完成）
     → 返回: {discovered: 5, installed: 5, loaded: 5}

开发者（通过 MCP）: repo_pipeline(query="mcp-server", auto_load=True)
     → 同样的流程，适合批量操作
```

**阶段5：发布新工具**

```
开发者: agora market publish my-tool --repo https://github.com/me/my-tool
     → Market.publish()
     → 注册到 ~/.agora/market/published.json
     → 其他用户可通过 market install my-tool 安装
     → 暂未对接中央 registry（registry.json 已创建但未推送）
```

---

### 旅程D：管道操作员 — "我运行数据处理工作流"

管道操作员使用 Agora 的 pipeline 系统运行结构化数据处理工作流，涵盖知识提取、知识工程和异步任务提交。

```
操作员: agora pipeline knowledge-base --goal "分析量子计算论文" --stream
     → Eidos Pipeline 启动
     → 执行知识卡片引擎管道
     → 流式输出每一步结果（--stream）
     → 可能调用 pallas match → ontoderive derive → check
     → 支持并行执行（--parallel）

操作员: agora pallas pipeline --goal "分析量子计算论文"
     → 完整知识工程管道: 匹配 → 派生 → 检查
     → 整合 Pallas 匹配、OntoDerive 派生和一致性检查

操作员: agora a2a send minerva.research_now --goal "量子计算"
     → A2A 异步任务提交
     → TaskManager 接收 → 提交到 minerva 执行
     → 返回 task_id
操作员: agora a2a get <task_id>
     → 获取任务状态和结果
```

---

## 4. 用户故事 (User Stories)

### 4.1 最终用户故事

| 编号 | 故事 | 对应场景 | 验证方式 |
|------|------|---------|---------|
| US-1 | 作为 Claude Code 用户，我想直接调用 `kos.semantic_search` 来搜索知识库 | 用户知道用什么 | MCP tools/call → ProxyForwardTool |
| US-2 | 作为 AI 助手，我想通过 `agora_execute("帮我研究量子计算")` 让系统自动找到并调用合适的工具 | 用户告诉需求 | SmartRouter auto 模式 |
| US-3 | 作为 AI 助手，我想通过 `agora_execute("推荐分析工具")` 获得工具推荐列表 | 用户不知道用什么 | SmartRouter recommend 模式 |
| US-4 | 作为 AI 助手，我想通过 `route_call("minerva.research_now", ...)` 获得可靠的负载均衡路由 | 用户知道用什么 | Router + 负载均衡 + 熔断器 |
| US-5 | 作为 AI 助手，我调用工具失败时，系统自动重试或切换到备用实例 | 可靠性 | 熔断器 + 负载均衡 + 降级缓存（1h TTL） |
| US-6 | 作为 AI 助手，我调用不存在的工具时，系统提示可用工具 | 容错 | Router fallback → list_services |

### 4.2 管理员故事

| 编号 | 故事 | 对应场景 | 验证方式 |
|------|------|---------|---------|
| US-7 | 作为平台管理员，我想通过 `agora mcp` 启动汇聚服务，自动连接所有下游 MCP | 启动 | mcp_bootstrap.scan_and_launch |
| US-8 | 作为平台管理员，我想通过 `register_service` 注册新服务，并让它在后台自动同步到代理 | 注册 | ServiceRegistry + _proxy_sync_loop |
| US-9 | 作为平台管理员，我想通过 `agora health` 监控系统健康状态 | 监控 | health check 工具 + psutil |
| US-10 | 作为安全管理员，我想通过 `agora audit` 查看所有操作审计日志 | 审计 | AuditLogger + SQLite 持久化 |
| US-11 | 作为安全管理员，我想通过 `create_api_key` 创建和管理 API 密钥 | 安全 | KeyManager（创建 / 列出 / 吊销 / 轮换） |
| US-12 | 作为平台管理员，我想通过 `agora tenant add` 管理多租户服务配额 | 租户 | TenantManager（租户 CRUD + Service whitelist） |
| US-13 | 作为平台管理员，我想配置空闲超时，让不用的工具自动卸载释放资源 | 资源 | LifecycleManager + IdleTimeoutManager |
| US-14 | 作为平台管理员，我想通过 `agora proxy-launch --status` 查看所有 19 个已知服务 | 查看 | KNOWN_SERVICES 状态表 |
| US-15 | 作为平台管理员，我想通过 `agora accounting top` 查看成本排名进行成本管控 | 计费 | AccountingManager（top / report / quota） |

### 4.3 工具开发者 / 发现者故事

| 编号 | 故事 | 对应场景 | 验证方式 |
|------|------|---------|---------|
| US-16 | 作为工具开发者，我想通过 `repo discover` 从 GitHub 搜索 MCP 工具 | 发现 | sources.search_all（GitHub + registry） |
| US-17 | 作为工具开发者，我想通过 `repo pipeline` 一键发现→安装→加载新工具 | 全流程 | Orchestrator（3 阶段自动化） |
| US-18 | 作为工具开发者，我想通过 `market publish` 发布自己的 MCP 工具到市场 | 发布 | Market.publish → published.json |
| US-19 | 作为工具开发者，我想通过 `agora_execute` 测试自然语言路由效果 | 测试 | SmartRouter 3 模式测试 |
| US-20 | 作为工具开发者，我想查看工具的 `quality_score` 来判断是否值得安装 | 评估 | QualityScorer（星数 / 新鲜度 / 版本） |
| US-21 | 作为工具开发者，我想将工具提交到中央 registry，让他人也能发现 | 贡献 | registry.json（已创建未推送） |

### 4.4 管道操作员故事

| 编号 | 故事 | 对应场景 | 验证方式 |
|------|------|---------|---------|
| US-22 | 作为数据研究员，我想通过 `pipeline knowledge-base` 运行知识提取管道的完整流程 | 管道 | Eidos Pipeline 命令执行 |
| US-23 | 作为知识工程师，我想通过 `pallas pipeline` 运行从匹配→推导→检查的知识工程管道 | 工程 | Pallas + OntoDerive 整合 |
| US-24 | 作为 API 用户，我想通过 `a2a_send_task` 提交异步任务并在完成后获取结果 | 异步 | A2A TaskManager（send / get / cancel / list） |
| US-25 | 作为管道设计者，我想通过 `pipeline-define` 从 JSON 定义自定义管道 | 扩展 | Pipeline Define 解析 |
| US-26 | 作为系统组件，我想通过事件总线发布和处理跨服务事件 | 集成 | EventBus（publish / subscribe / log） |

---

## 5. 用户场景 (User Scenarios)

### 场景1：用户知道用什么 — 直接调用

**触发条件**：用户明确知道需要哪个工具（通常在经过一次推荐后记住）。

**路径优先级**：
1. `ProxyForwardTool`（原生 FastMCP 工具，最快路径，零路由开销）
2. `route_call`（通过 Router 的负载均衡 + 熔断器 + 审计路径）
3. `proxy_call`（直接代理转发，需手动指定工具名和参数 JSON）

**性能特征**：
- ProxyForwardTool：~1 次 JSON-RPC 往返（直接子进程通信）
- route_call：负载均衡 + 熔断器检查 + 审计 + 追踪 + 计费
- proxy_call：直接转发，无路由开销

**典型流程**：
```
用户 → tools/call "kos.semantic_search"
     → FastMCP 匹配 ProxyForwardTool(name="kos.semantic_search")
     → ProxyForwardTool.run(arguments) → ProxyManager.dispatch()
     → ProxyRegistry 查找 kos 的 StdioMCPClient
     → StdioMCPClient.call_tool("semantic_search", ...)
     → JSON-RPC {"method":"tools/call","params":{"name":"semantic_search",...}}
     → kos 子进程处理 → JSON-RPC 响应
     → 结果逐个字段返回 ToolResult
```

**配套 CLI**：`agora route`, `agora proxy-call`

---

### 场景2：用户不知道用什么 — 推荐

**触发条件**：用户有任务但不知道哪个工具合适，需要系统根据语义推荐。

**路径**：
1. `agora_execute(query, mode="recommend")` → SmartRouter
2. 语义搜索（EmbeddingStore）→ 找到语义相似的工具
3. 可选 LLM 精排（OpenAICompatibleClient）→ 选择最佳匹配
4. 返回推荐列表（含相似度分数）

**典型流程**：
```
用户 → agora_execute("推荐一个代码分析工具", mode="recommend")
     → SmartRouter._semantic_search("代码分析")
     → 找到: codeanalyze (score: 0.92), kos (score: 0.45), ...
     → 可选: LLM 精排 → 选择 codeanalyze
     → 返回: {mode: "recommend", status: "ok", tools: [...], action: "recommend"}

CLI 等价: agora repo run "推荐一个代码分析工具" --mode recommend
```

---

### 场景3：用户直接告诉需求 — 自动发现/安装/加载

**触发条件**：用户描述需求，工具不在本地目录或尚未加载。

**路径**：`agora_execute(query, mode="auto")` → 级联策略：
1. **direct**：尝试从查询中解析工具名 → 如果已加载则调用
2. **recommend**：语义搜索本地工具 → 如果找到则推荐
3. **auto**：发现外部源 → 安装 → 加载 → 调用

**典型流程**：
```
用户 → agora_execute("帮我用 sqlite 查询数据", mode="auto")
     → SmartRouter._route_direct("帮我用 sqlite 查询数据")
       → 解析不到工具名，失败
     → SmartRouter._route_recommend("帮我用 sqlite 查询数据")
       → 语义搜索: mcp-server-sqlite (sim: 0.87)
       → 但 status=discovered，尚未安装，建议安装
     → 用户确认后:
       → Orchestrator.discover_install_load("sqlite")
       → LifecycleManager.load_tool("mcp-server-sqlite")
       → ProxyManager.add_service(config)
       → FastMCP 注册 ProxyForwardTool
       → 调用 sqlite 工具的查询方法
       → 返回结果

CLI 等价: agora repo run "帮我用 sqlite 查询数据"
```

---

### 场景4：批量管理 — 集群操作

**触发条件**：管理员需要批量操作多个工具 / 服务。

**命令链**：
```
# 批量发现
agora repo discover "mcp-server"

# 批量查看状态分布
agora repo status

# 批量加载所有闲置工具
agora repo load-all

# 批量卸载所有已加载工具
agora repo unload-all

# 持续健康监控
agora health --watch --interval 30

# CLI 等价 MCP 调用
lifecycle_load_all()    → 加载所有闲置工具
lifecycle_unload_all()  → 卸载所有已加载工具
```

---

### 场景5：故障恢复

**触发条件**：服务宕机 / 网络故障 / 代理断开 / 子进程异常退出。

**恢复路径（多层防御）**：
1. **熔断器 OPEN** → Router 跳过该服务，请求被路由到备用实例（如果有）
2. **降级模式** → Router 回退到 `service_cache.json`（1h TTL 的缓存副本）
3. **空闲超时断开** → ProxyManager 的 `lazy_connect` 在下次调用时自动重连
4. **后台同步** → `_proxy_sync_loop` 每 60 秒同步 ServiceRegistry → ProxyRegistry
5. **连接失败** → `StdioMCPClient.connect()` 的超时和重试机制

---

### 场景6：配置初始化与迁移

**触发条件**：新环境部署或数据目录迁移。

**典型流程**：
```
# 新环境: 首次安装
管理员启动 → mcp_bootstrap 模块导入
     → migrate_legacy_data() 自动执行
     → 检查旧路径（kairon 项目根目录）下的数据文件
     → 复制到 ~/.agora/（新统一目录）
     → 跳过已存在的文件（幂等）

# 手动触发
agora proxy-launch --reload
     → 删除现有配置 → 重新检测可用服务 → 生成新配置
```

---

## 5. 架构分层

Agora 的代码架构分为 7 个清晰的层次，从接入层到底层存储和管道层，每层职责明确。

| 层次 | 关键组件 | 核心类/模块 | 职责 |
|------|---------|-------------|------|
| **接入层** | FastMCP Server | `mcp.py` → `FastMCP` | 统一 MCP 协议入口：40 个原生 @mcp.tool + N 个动态 ProxyForwardTool |
| **路由层** | Router / SmartRouter | `mcp_proxy/router.py`, `mcp_registry/router.py` | 工具→服务映射、负载均衡、熔断器、自然语言语义路由 |
| **代理层** | ProxyManager / ProxyRegistry | `mcp_proxy/manager.py`, `mcp_proxy/registry.py` | 下游服务连接管理、ProxyForwardTool 注册、空闲超时、引用计数 |
| **协议层** | StdioMCPClient / HttpMCPClient | `mcp_proxy/stdio.py`, `mcp_proxy/http_client.py` | JSON-RPC 2.0 协议实现：tools/list、tools/call、初始化握手 |
| **注册层** | ServiceRegistry | `registry.py`, `service_base.py` | 服务元数据 SQLite + JSON 双写、健康检查、熔断器、状态追踪 |
| **治理层** | Audit / Auth / Tenancy / Quota | `governance.py`, `identity.py`, `audit*.py` | 审计日志（risk_level 分级）、API 密钥管理、多租户、计费配额 |
| **管道层** | Pipeline / Orchestrator / Lifecycle | `eidos_pipeline.py`, `mcp_registry/*.py` | 数据处理管道、工具 discover→install→load 全生命周期、空闲超时管理 |

---

## 6. 数据流

### 6.1 控制流（工具调用）

```
LLM Client
  → tools/call "kos.semantic_search"         # 直接调用 (ProxyForwardTool)
  → tools/call "agora_execute(...)"          # 自然语言路由 (SmartRouter)
  → tools/call "route_call(...)"             # 路由层调用 (Router)
  → tools/call "proxy_call(...)"             # 代理转发 (Direct)
  ↓
FastMCP Server
  → @mcp.tool() dispatcher                    # 参数验证
  → AuthMiddleware (AGORA_API_KEY)            # 认证检查 (permissive 模式可跳过)
  ↓
Router / ProxyManager
  → Router.get_service(tool_name)             # 路由解析
  → LoadBalancer.select(service)              # 负载均衡
  → CircuitBreaker.allow(service)             # 熔断检查
  → ProxyRegistry.dispatch(tool_name, args)   # 代理分派
  ↓
StdioMCPClient / HttpMCPClient
  → JSON-RPC 2.0: {"method":"tools/call","params":{"name":"...","arguments":{...}}}
  → stdin (stdio) / HTTP POST (http/mcp)
  ↓
下游 MCP Server (子进程 / HTTP 服务)
  → 处理请求
  → JSON-RPC 2.0 响应
  → stdout / HTTP Response
  ↓
← 结果逐层返回 →
```

### 6.2 数据流（生命周期管理）

```
discovered  ←  repo discover / search_github / search_registry / QualityScorer
    │
    ▼ [repo install / market install / LifecycleManager.install_tool]
installed (文件系统：git clone + pip/npm install)
    │
    ▼ [repo load / LifecycleManager.load_tool]
loaded (FastMCP 注册 ProxyForwardTool, ProxyManager 管理子进程)
    │          ↕
    │   [idle timeout] ──→ idle (子进程终止，释放资源)
    │   [lazy reconnect] ←── (下次调用时自动重新连接)
    │
    ▼ [repo unload / lifecycle_unload_all]
removed from proxy
```

### 6.3 存储层

```
~/.agora/                               # AGORA_DATA_DIR（可通过环境变量覆盖）
├── agora-proxy-services.json           # 代理配置（KNOWN_SERVICES 快照 + 用户自定义）
├── agora-services.json                 # 服务注册表（ServiceRegistry 持久化）
├── agora.db                            # SQLite 双写数据库（服务、路由、事件）
├── agora-routes.json                   # 工具→服务路由映射
├── service_cache.json                  # 降级缓存（1h TTL）
├── market/                             # 市场工具安装目录
│   ├── published.json                  # 本地发布的市场工具元数据
│   └── modelcontextprotocol__servers/  # git clone 的第三方工具
└── tools.db                            # ToolCatalog（MCP Registry 目录）
```

---

## 7. 已知问题与改进方向

### 7.1 架构问题

1. **三层断开（ServiceRegistry ↔ ProxyRegistry ↔ mcp_bootstrap）**：三个组件各自维护自己的服务配置状态，需要同步机制协调。
   - 已缓解：`_proxy_sync_loop` 后台每 60 秒执行一轮同步
   - 改进方向：统一配置存储（以 `~/.agora/agora-proxy-services.json` 为单一事实源），采用事件驱动同步

2. **两套空闲超时（ProxyManager 层 + LifecycleManager 层）**：
   - ProxyManager 通过 `IdleTimeoutManager` 管理引用计数（`acquire`/`release`），引用归零时关闭连接
   - LifecycleManager 通过 `_idle_watch_loop` 管理工具状态（`loaded`→`idle`）
   - 改进方向：统一空闲超时策略，向 LifecycleManager 收敛

3. **agora_execute 每次调用新建组件**：每次调用 `agora_execute` 都会创建新的 `ToolCatalog` + `EmbeddingStore` + `SmartRouter` + `Orchestrator` + `LifecycleManager` 实例。
   - 改进方向：引入单例 / 组件池，在 `_proxy_lifespan` 中初始化并复用

### 7.2 功能缺口

1. **中央 Registry 仓库未接入**：`registry.json` 文件已创建但尚未推送到 `starlink-awaken/mcp-registry`。第三方工具无法通过中央仓库发布自己的工具

2. **SmartRouter 无真实 LLM 验证**：测试时 LLM 精排均被 mock 替代（`AsyncMock`），未使用真实 Ollama / DeepSeek 端点验证推荐质量

3. **README 缺失**：agora 包的 `README.md` 只有标题，缺少用户文档、API 文档和使用指南

4. **3 个 CLI 文件未接线**：`commands_instance.py`、`commands_identity.py`、`commands_grant.py` 功能完整但尚未挂载到 `build_parser()` 的 subparsers 中

### 7.3 技术债务

1. **集成测试覆盖不足**：46 个测试文件覆盖广泛（800+ 测试），但缺少实际的子进程集成测试（全部使用 mock/stub），无法验证真实 `uv run --package` 启动场景

2. **conftest 过于简化**：`tests/conftest.py` 仅 2 个 fixture（`test_data_dir` 和 `clean_env`），与 Minerva 项目的完善 conftest 形成鲜明对比

3. **文档缺失**：缺少 API 文档（已有 `__init__.py` 的 `__all__` 导出但无 docstring 聚合）、架构决策记录、用户使用指南

4. **AuthMiddleware 未在 mcp_server.py 中激活**：`_require_agora_api_key` 函数已定义但未在 FastMCP 创建时传入 `auth_callback`，实际运行时永远为 permissive 模式

5. **代理工具重复注册问题**：`_register_proxy_tools` 和 `_unregister_proxy_tools` 在 proxy 热更新时可能重复注册

### 7.4 改进建议优先级

| 优先级 | 改进项 | 影响范围 | 预估工作量 |
|--------|--------|---------|-----------|
| P0 | 激活 AuthMiddleware | 安全基线 | 低（1 行配置） |
| P0 | 集成测试（子进程启动） | 质量保障 | 中（5-8 测试） |
| P1 | agora_execute 组件复用 | 性能 | 低（单例改造） |
| P1 | 统一空闲超时策略 | 架构 | 中（代码重构） |
| P2 | 中央 Registry 推送 | 生态 | 低（推送 + 验证） |
| P2 | 挂载 3 个未接线 CLI 文件 | 功能完整 | 低（注册 subparser） |
| P2 | 补充 README 和 API 文档 | 用户接入 | 中（文档编写） |
| P3 | 事件驱动同步取代轮询 | 实时性 | 高（架构改造） |
| P3 | 真实 LLM 验证 SmartRouter | 质量 | 中（端到端测试） |

---

## 8. 附录

### A. CLI 命令索引（37 个顶层命令）

从 `parser.py` 的 `build_parser()` 中汇总：

| 命令 | 子命令 | 用途 |
|------|--------|------|
| `register` | — | 注册新服务（支持 MCP / gRPC / REST 等协议） |
| `unregister` | — | 移除服务 |
| `list` | — | 列出所有服务 |
| `discover` | — | 自动发现工作空间中的 MCP 服务 |
| `instance` | `add` | 为服务添加负载均衡实例 |
| `tenant` | `list` / `add` / `remove` | 多租户管理 |
| `market` | `list` / `search` / `install` / `publish` | 工具市场 |
| `repo` | `list` / `search` / `status` / `info` / `discover` / `install` / `load` / `unload` / `load-all` / `unload-all` / `pipeline` / `remove` / `run` | MCP Registry 全生命周期管理 |
| `search` | — | 搜索服务 |
| `info` | — | 查看服务详情 |
| `stats` | — | 服务统计 |
| `health` | — | 健康检查（支持 --watch） |
| `route` | — | 添加工具→服务路由 |
| `routes` | — | 列出所有路由 |
| `mcp` | — | 启动 FastMCP 服务器 |
| `init` | — | 引导式初始化 |
| `sync` | — | 同步工作空间服务（--dry-run） |
| `converge` | — | 汇聚服务（委托给 sync） |
| `completion` | — | 生成 shell 补全 |
| `config` | — | 查看配置路径 |
| `proxy-launch` | — | 启动 / 查看 / 重载代理配置 |
| `web` | — | 启动 Web 仪表板（端口 7430） |
| `run` | — | 统一入口（自动路由到合适的 CLI 子命令） |
| `start-pipeline` | — | 启动 Eidos Pipeline MCP 端点 |
| `accounting` | `top` / `report` / `quota` | 资源计费和配额 |
| `pipeline` | — | 运行命名管道 |
| `key` | `create` / `list` / `revoke` / `rotate` | API 密钥管理 |
| `audit` | — | 审计日志查询 |
| `transitions` | — | 状态转换历史 |
| `a2a` | `send` / `get` / `cancel` / `list` | A2A 异步任务 |
| `agent-card` | `list` / `get` | Agent Card（A2A 元数据） |
| `proto` | `compile` | gRPC proto 编译 |
| `pipelines` | — | 列出可用管道 |
| `pipeline-define` | — | 从 JSON 定义自定义管道 |
| `event` | `publish` / `log` / `subscribe` / `unsubscribe` | 事件总线 |
| `enforce` | `list` / `set` / `clear` | 授权强制模式 |
| `pallas` | （来自 commands_pallas.py） | Pallas 工作流命令 |

---

### B. MCP 工具索引（40 个原生工具 + 动态代理工具）

从 `mcp.py` 中按功能域分类汇总的 `@mcp.tool()`：

**代理管理**（5 个）：
| 工具名 | 用途 |
|-------|------|
| `proxy_connect` | 连接所有配置的下游服务 |
| `proxy_call` | 通过代理直接调用下游工具 |
| `proxy_status` | 查看代理连接状态 |
| `proxy_add_service` | 添加新下游服务到代理 |
| `proxy_remove_service` | 从代理移除并断开服务 |

**服务注册与治理**（4 个）：
| 工具名 | 用途 |
|-------|------|
| `register_service` | 注册新服务到 ServiceRegistry + ProxyRegistry |
| `list_services` | 列出所有注册服务及健康状态 |
| `check_health` | 探活所有注册服务 |
| `register_push_notification` | 注册 Webhook 推送通知 |

**路由**（3 个）：
| 工具名 | 用途 |
|-------|------|
| `add_route` | 映射工具名→服务 |
| `list_routes` | 列出所有路由映射 |
| `route_call` | 通过路由层调用（含负载均衡 + 熔断器 + 审计 + 计费） |

**事件总线**（3 个）：
| 工具名 | 用途 |
|-------|------|
| `publish_event` | 发布事件 |
| `subscribe_event` | 订阅事件模式 |
| `get_event_log` | 查询历史事件 |

**审计**（2 个）：
| 工具名 | 用途 |
|-------|------|
| `audit_query` | 查询审计日志 |
| `audit_stats` | 审计统计（按风险等级和事件类型分组） |

**API 密钥**（3 个）：
| 工具名 | 用途 |
|-------|------|
| `create_api_key` | 创建 API 密钥 |
| `list_api_keys` | 列出 API 密钥 |
| `revoke_api_key` | 吊销 API 密钥 |

**A2A 异步任务**（4 个）：
| 工具名 | 用途 |
|-------|------|
| `a2a_send_task` | 提交异步工具调用 |
| `a2a_get_task` | 获取任务状态和结果 |
| `a2a_cancel_task` | 取消进行中的任务 |
| `a2a_list_tasks` | 列出任务（支持服务 / 状态 / 时间过滤） |

**Agent Card**（2 个）：
| 工具名 | 用途 |
|-------|------|
| `list_agent_cards` | 列出所有 Agent Card |
| `get_agent_card` | 获取特定服务的 Agent Card |

**状态追踪**（1 个）：
| 工具名 | 用途 |
|-------|------|
| `get_state_transitions` | 查询服务状态转换历史 |

**MCP Registry 工具**（8 个）：
| 工具名 | 用途 |
|-------|------|
| `repo_search` | 搜索工具目录（本地 / GitHub / 中央注册表） |
| `repo_discover` | 从外部源发现工具并保存到本地 |
| `repo_status` | 目录状态统计 |
| `repo_install` | 安装已发现的工具 |
| `repo_load` | 加载工具到代理 |
| `repo_unload` | 从代理卸载工具 |
| `repo_pipeline` | 全自动 discover→install→load 管道 |

**生命周期管理**（5 个）：
| 工具名 | 用途 |
|-------|------|
| `lifecycle_status` | 生命周期管理器状态 |
| `lifecycle_start_watch` | 启动空闲超时后台监视 |
| `lifecycle_stop_watch` | 停止空闲超时监视 |
| `lifecycle_load_all` | 加载所有闲置工具 |
| `lifecycle_unload_all` | 卸载所有已加载工具 |

**自然语言路由**（1 个）：
| 工具名 | 用途 |
|-------|------|
| `agora_execute` | 自然语言查询→自动路由（direct / recommend / auto） |

---

### C. KNOWN_SERVICES 索引（19 个已知服务）

| 名称 | 来源 | 描述 |
|------|------|------|
| kronos | kairon | 知识摄取管线 — 文档摄取、分块、向量化 |
| iris | kairon | Connector Hub — 外部数据源连接与同步 |
| eidos | kairon | 知识卡片引擎 — 卡片化知识管理与推理 |
| sophia | kairon | 智库系统 — 战略分析、决策支持、推理 |
| minerva | kairon | 深度研究系统 — 多步搜索、报告生成 |
| metaos | kairon | 编排/治理层 — 工作流编排、资源治理 |
| agent-runtime | kairon | Agent 运行时 — 多 Agent 协作执行环境 |
| codeanalyze | kairon | 代码与文档分析 — CRG 知识图谱、Tree-sitter |
| kos | kairon | 知识操作系统 — 跨域搜索、本体、协作 |
| cron-service | kairon | 定时调度引擎 — 作业管理、脚本编排 |
| mcp-server-sqlite | npm | SQLite 数据库操作 |
| mcp-server-apple-events | npm | macOS 原生集成 |
| docker-mcp-gateway | docker | Docker MCP Gateway（73 个工具） |
| gitnexus | homebrew | 代码仓库知识图谱 |
| zai-mcp-server | npm (npx) | Z.AI MCP（8 个分析工具） |
| claude-mcp-serve | agent-cli | Claude Code 跨 Agent 编排 |
| codex-mcp-server | agent-cli | Codex CLI 跨 Agent 编排 |
| chrome-devtools-mcp | npm (npx) | Chrome DevTools MCP |
| serena | npm | 开源 AI 助手 MCP |

---

### D. BUILTIN_MARKET 索引（18 个市场工具）

| 名称 | 来源 | 类型 |
|------|------|------|
| minerva | starlink-awaken/minerva | python |
| ontoderive | starlink-awaken/ontoderive | python |
| sophia | starlink-awaken/sophia | python |
| kos | starlink-awaken/kos | python |
| filesystem | modelcontextprotocol/servers | node |
| fetch | modelcontextprotocol/servers | node |
| puppeteer | modelcontextprotocol/servers | node |
| github | modelcontextprotocol/servers | node |
| sequential-thinking | modelcontextprotocol/servers | node |
| brave-search | modelcontextprotocol/servers | node |
| memory | modelcontextprotocol/servers | node |
| sqlite | modelcontextprotocol/servers | node |
| postgres | modelcontextprotocol/servers | node |
| slack | modelcontextprotocol/servers | node |
| google-drive | anthropics/superpowers | node |
| everart | modelcontextprotocol/servers | node |
| aws-kb-retrieval | modelcontextprotocol/servers | node |
| google-maps | modelcontextprotocol/servers | node |

---

### E. 测试覆盖索引（46 个测试文件）

按功能域分组：

**治理与安全**（6 个）：
- `test_governance.py` — API 密钥、审计、认证
- `test_identity.py` — 身份规范化
- `test_audit.py` — 审计日志
- `test_audit_subscriber.py` — 审计订阅者
- `test_tenant.py` — 多租户
- `test_rate_limit.py` — 速率限制

**路由与代理**（6 个）：
- `test_router.py` — 路由层
- `test_proxy.py` — 代理转发
- `test_proxy_dynamic.py` — 动态代理
- `test_discovery.py` — 服务发现
- `test_registry.py` — 服务注册
- `test_agent_registry.py` — Agent 注册

**MCP Registry**（9 个）：
- `test_repository.py` — ToolCatalog 仓库
- `test_evaluator.py` — QualityScorer 质量评分
- `test_lifecycle.py` — LifecycleManager 生命周期
- `test_orchestrator.py` — Orchestrator 编排器
- `test_commands_repo.py` — CLI repo 子命令
- `test_mcp_registry_e2e.py` — Registry 端到端
- `test_mcp_registry_e2e_full.py` — 完整端到端
- `test_github_source_e2e.py` — GitHub 搜索端到端
- `test_llm_route_e2e.py` — LLM 路由端到端

**管道与 Eidos**（7 个）：
- `test_pipeline.py` — 管道基础
- `test_eidos_pipeline.py` — Eidos 管道
- `test_eidos_pipeline_route.py` — Eidos 管道路由
- `test_eidos_service.py` — Eidos 服务
- `test_pipeline_identity.py` — 管道身份
- `test_pipeline_eventbus_integration.py` — 管道+事件总线集成
- `test_workspace_research.py` — 工作空间研究

**A2A 与事件**（4 个）：
- `test_a2a.py` — A2A 异步任务
- `test_event_bus.py` — 事件总线
- `test_mcp_server.py` — MCP 服务器端到端
- `test_accounting.py` — 计费与配额

**CLI 与市场**（3 个）：
- `test_cli.py` — CLI 命令
- `test_web_api.py` — Web API
- `test_market.py` — 市场工具

**其他基础设施**（11 个）：
- `test_integration.py` — 集成测试
- `test_degrade.py` — 降级模式
- `test_metrics.py` — 指标
- `test_tracing.py` — 追踪
- `test_otel.py` — OpenTelemetry
- `test_wizard.py` — 初始化向导
- `test_protocols.py` — 多协议支持
- `test_conftest.py` — （伴随 conftest.py）

---

### F. 存储接口索引

| 文件路径 | 用途 | 读写时机 |
|---------|------|---------|
| `~/.agora/agora-proxy-services.json` | 代理服务的持久化配置（KNOWN_SERVICES 快照 + 用户自定义） | mcp_bootstrap 读写，proxy-launch 查看/编辑 |
| `~/.agora/agora-services.json` | ServiceRegistry 的 JSON 后端 | 每次 register_service / unregister / health_check |
| `~/.agora/agora.db` | ServiceRegistry 的 SQLite 后端 | 与 JSON 双写，供查询和审计 |
| `~/.agora/agora-routes.json` | 路由映射表 | route 命令 |
| `~/.agora/service_cache.json` | 降级缓存（1h TTL） | 熔断器触发时读取 |
| `~/.agora/market/published.json` | 本地发布的市场工具 | market publish 写入 |
| `~/.agora/tools.db` | ToolCatalog 的 SQLite 数据库 | repo discover / install / load 操作 |

---

*本复盘基于 Agora 项目源代码、测试配置和架构文档综合分析，覆盖了截至 2026-06-02 的全部代码和设计。*
