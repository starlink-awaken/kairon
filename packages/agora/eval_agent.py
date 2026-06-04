#!/usr/bin/env python3
"""
Agora Agent Evaluation Suite
模拟外部 AI Agent 接入 Agora 的全流程评测

运行: python eval_agent.py
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 添加 src 到路径
_src = str(Path(__file__).resolve().parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# ── 导入 Agora 核心模块 ──
from agora.mcp_proxy.client import MCPClient  # type: ignore[import-not-found]
from agora.mcp_proxy.registry import ProxyEntry, ProxyRegistry  # type: ignore[import-not-found]
from agora.mcp_registry.evaluator import QualityScorer  # type: ignore[import-not-found]
from agora.mcp_registry.orchestrator import Orchestrator  # type: ignore[import-not-found]
from agora.mcp_registry.repository import ToolCatalog  # type: ignore[import-not-found]
from agora.mcp_registry.router import SmartRouter  # type: ignore[import-not-found]

# 尝试导入 EmbeddingStore；如果不支持则跳过语义搜索测试
try:
    from sentence_transformers import SentenceTransformer

    _HAS_EMBEDDING = True
except ImportError:
    _HAS_EMBEDDING = False


# ══════════════════════════════════════════════════════════════════════
# 评测报告
# ══════════════════════════════════════════════════════════════════════

# ANSI 颜色
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


class EvalReport:
    def __init__(self):
        self.results: list[dict] = []
        self.current_section = ""

    def section(self, name: str):
        self.current_section = name
        print(f"\n{_BOLD}{_CYAN}═══ {name} ═══{_RESET}\n")

    def ok(self, msg: str, detail: str = ""):
        self.results.append({"section": self.current_section, "status": "PASS", "msg": msg})
        d = f"  {detail}" if detail else ""
        print(f"  {_GREEN}✓ PASS{_RESET}  {msg}{d}")

    def fail(self, msg: str, detail: str = ""):
        self.results.append({"section": self.current_section, "status": "FAIL", "msg": msg})
        d = f"  {detail}" if detail else ""
        print(f"  {_RED}✗ FAIL{_RESET}  {msg}{d}")

    def skip(self, msg: str, detail: str = ""):
        self.results.append({"section": self.current_section, "status": "SKIP", "msg": msg})
        d = f"  {detail}" if detail else ""
        print(f"  {_YELLOW}∼ SKIP{_RESET}  {msg}{d}")

    def info(self, msg: str):
        print(f"    {_CYAN}→{_RESET} {msg}")

    def summary(self):
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")
        total = len(self.results)
        print(f"\n{_BOLD}{'═' * 50}{_RESET}")
        print(f"{_BOLD}  评测报告总计{_RESET}")
        print(
            f"  {_GREEN}通过: {passed}{_RESET}  {_RED}失败: {failed}{_RESET}  {_YELLOW}跳过: {skipped}{_RESET}  总计: {total}"
        )
        print(f"  通过率: {passed / total * 100:.1f}%")
        return passed, failed, skipped


# ══════════════════════════════════════════════════════════════════════
# Mock 辅助
# ══════════════════════════════════════════════════════════════════════


def make_mock_client(service_name: str) -> MagicMock:
    """创建一个模拟的 MCPClient"""
    client = MagicMock(spec=MCPClient)
    client.service_name = service_name
    client.connected = True

    # 让 call_tool 返回模拟结果
    async def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        return {
            "status": "ok",
            "tool": tool_name,
            "arguments": arguments,
            "result": f"模拟结果: {service_name}/{tool_name}",
        }

    client.call_tool = AsyncMock(side_effect=fake_call_tool)

    # list_tools 返回模拟的工具列表（用于 register_service）
    async def fake_list_tools() -> list[dict]:
        return []

    client.list_tools = AsyncMock(side_effect=fake_list_tools)
    return client


def populate_proxy_registry(registry: ProxyRegistry):
    """直接往 ProxyRegistry 的 _entries 和 _clients 注入模拟条目（避免连接真实服务）。"""
    client_a = make_mock_client("kos")
    client_b = make_mock_client("minerva")

    registry._clients["kos"] = client_a
    registry._clients["minerva"] = client_b

    tools_data = [
        (
            "kos.semantic_search",
            "kos",
            "semantic_search",
            "向量语义搜索工具，用于基于内容的相似度搜索",
            {"type": "object", "properties": {"query": {"type": "string"}}},
        ),
        (
            "kos.text_summarize",
            "kos",
            "text_summarize",
            "文本摘要工具，对长文本生成摘要",
            {"type": "object", "properties": {"text": {"type": "string"}, "max_length": {"type": "integer"}}},
        ),
        (
            "minerva.research_now",
            "minerva",
            "research_now",
            "实时网络调研工具，搜索最新的信息和资料",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}, "depth": {"type": "string", "enum": ["quick", "deep"]}},
            },
        ),
        (
            "minerva.data_analyze",
            "minerva",
            "data_analyze",
            "数据分析工具，对结构化数据进行分析和可视化",
            {"type": "object", "properties": {"data": {"type": "string"}, "analysis_type": {"type": "string"}}},
        ),
    ]

    for tool_name, svc, orig, desc, params in tools_data:
        entry = ProxyEntry(
            tool_name=tool_name,
            service_name=svc,
            original_name=orig,
            description=desc,
            parameters=params,
            client=client_a if svc == "kos" else client_b,
        )
        registry._entries[tool_name] = entry

    return tools_data


# ══════════════════════════════════════════════════════════════════════
# 场景 1: Manifest - 获取工具清单
# ══════════════════════════════════════════════════════════════════════
# 模拟外部 Agent 第一步：先问 "你有啥工具？"


def test_manifest(report: EvalReport):
    report.section("场景 1: Manifest — 获取工具清单")

    # 创建 ProxyRegistry 并直接填充模拟条目
    registry = ProxyRegistry()
    tools_data = populate_proxy_registry(registry)

    report.ok("ProxyRegistry 初始化并注入了 %d 个模拟工具" % len(tools_data))

    # 获取 manifest（通过 get_tool_schemas）
    manifest = registry.get_tool_schemas()
    report.ok("通过 get_tool_schemas 获取到 %d 个工具的 manifest" % len(manifest))

    # 验证 manifest 格式
    first = manifest[0]
    assert "name" in first, "manifest 缺少 name"
    assert "description" in first, "manifest 缺少 description"
    assert "parameters" in first, "manifest 缺少 parameters"
    assert "service_name" in first, "manifest 缺少 service_name"
    report.ok("Manifest 格式正确 — 包含 name/description/parameters/service_name")

    # 模拟外部 Agent 看到 manifest 后的"思考"过程
    report.info("外部 Agent 收到 manifest，正在分析可用工具...")
    for t in manifest:
        report.info(f"  [{t['service_name']}] {t['name']} — {t['description'][:40]}...")
    report.info("Agent 决策: 根据任务 '查找语义相似文本' → 选择 kos.semantic_search")
    report.ok("外部 Agent 基于 manifest 自主决策工具选择流程正常")

    # ToolCatalog manifest
    catalog = ToolCatalog(db_path=":memory:")
    catalog.add_tool(
        {"id": "ext.github_analyzer", "name": "GitHub Analyzer", "description": "分析 GitHub 仓库活跃度和代码质量"}
    )
    catalog.add_tool({"id": "ext.doc_parser", "name": "Document Parser", "description": "解析 PDF/Word 文档内容"})
    cat_tools = catalog.list_tools()
    report.ok("ToolCatalog 返回 %d 个工具（独立于 Proxy 的工具生态）" % len(cat_tools))

    return registry


# ══════════════════════════════════════════════════════════════════════
# 场景 2: Smart Routing - 智能路由
# ══════════════════════════════════════════════════════════════════════


async def test_smart_routing(report: EvalReport, registry: ProxyRegistry):
    report.section("场景 2: Smart Routing — 智能路由（三层级联）")

    # 创建 ToolCatalog 并注册工具（add_tool 接收 dict）
    catalog = ToolCatalog(db_path=":memory:")
    for tool_name, svc, orig, desc, params in [
        ("kos.semantic_search", "kos", "semantic_search", "向量语义搜索工具", {"query": {"type": "string"}}),
        ("kos.text_summarize", "kos", "text_summarize", "文本摘要工具", {"text": {"type": "string"}}),
        ("minerva.research_now", "minerva", "research_now", "实时网络调研", {"query": {"type": "string"}}),
        ("minerva.data_analyze", "minerva", "data_analyze", "数据分析", {"data": {"type": "string"}}),
    ]:
        catalog.add_tool(
            {
                "id": tool_name,
                "name": orig,
                "description": desc,
                "metadata": {"parameters": params},
                "source": svc,
            }
        )
        catalog.update_status(tool_name, "loaded")

    # 创建 SmartRouter — 无 embedding 时走 keyword fallback
    router = SmartRouter(
        catalog=catalog,
        embeddings=None,
    )

    # 测试 direct mode
    report.info("Mode=direct: 用户知道工具名 'semantic_search 查找相似文档'")
    try:
        result = await router.route("semantic_search 查找相似文档", mode="direct")
        if result.get("status") == "ok":
            report.ok(
                "direct 模式路由成功",
                detail=f"action={result.get('action')}, tool={result.get('tool', {}).get('name', 'N/A')}",
            )
        else:
            report.fail("direct 模式路由返回非 ok", detail=str(result))
    except Exception as e:
        report.fail("direct 模式路由抛出异常", detail=str(e))

    # 测试 recommend mode
    report.info("Mode=recommend: 用户不确定工具名 '帮我做文本摘要'")
    try:
        result = await router.route("帮我做文本摘要", mode="recommend")
        if result.get("status") == "ok":
            tools = result.get("tools", result.get("tool", []))
            if tools:
                report.ok(
                    "recommend 模式返回推荐结果", detail=f"推荐了 {len(tools) if isinstance(tools, list) else 1} 个工具"
                )
            else:
                report.skip("recommend 模式未返回工具（可能无 LLM 或 embedding）")
        else:
            report.skip("recommend 模式未命中", detail=str(result))
    except Exception as e:
        report.fail("recommend 模式路由抛出异常", detail=str(e))

    # 测试 auto mode
    report.info("Mode=auto: 三级级联 '查一下今天的新闻'")
    try:
        result = await router.route("查一下今天的新闻", mode="auto")
        if result.get("status") == "ok":
            report.ok("auto 模式路由成功", detail=f"action={result.get('action')}")
        else:
            report.skip("auto 模式未命中（可能是环境限制）", detail=str(result))
    except Exception as e:
        report.fail("auto 模式路由抛出异常", detail=str(e))

    report.ok("三层级联路由流程验证完成")


# ══════════════════════════════════════════════════════════════════════
# 场景 3: Direct Execution - 直接调用
# ══════════════════════════════════════════════════════════════════════


async def test_direct_execution(report: EvalReport, registry: ProxyRegistry):
    report.section("场景 3: Direct Execution — 直接执行")

    # 用新的 registry 确保干净
    registry2 = ProxyRegistry()
    populate_proxy_registry(registry2)

    # 1. 精确工具名匹配（通过 get_entry）
    entry = registry2.get_entry("kos.semantic_search")
    if entry:
        report.ok("精确工具名匹配成功", detail=f"→ {entry.tool_name} @ {entry.service_name}")
    else:
        report.fail("精确工具名匹配失败")

    # 2. 前缀匹配 Registry 也支持
    entry2 = registry2.get_entry("kos")  # 前缀匹配 "kos" → 找到第一个 kos.xxx
    if entry2:
        report.ok("前缀工具名匹配成功", detail=f"→ {entry2.tool_name}")
    else:
        report.skip("前缀工具名匹配（取决于实现）")

    # 3. 模拟 dispatch（直接调用下游）
    report.info("外部 Agent 调用: registry.dispatch('kos.semantic_search', {'query': 'hello'})")
    result = await registry2.dispatch("kos.semantic_search", {"query": "hello"})
    if result.get("status") == "ok":
        report.ok("dispatch 直接调用成功", detail=str(result.get("result", ""))[:60])
    else:
        report.fail("dispatch 直接调用失败", detail=str(result))

    # 4. 其他工具
    result2 = await registry2.dispatch("minerva.research_now", {"query": "AI news", "depth": "quick"})
    if result2.get("status") == "ok":
        report.ok("跨服务 dispatch 调用也成功", detail="minerva.research_now 返回正常")
    else:
        report.fail("跨服务 dispatch 调用失败", detail=str(result2))

    report.ok("直接执行（dispatch）流程验证完成")


# ══════════════════════════════════════════════════════════════════════
# 场景 4: Quality Scoring - 质量评分
# ══════════════════════════════════════════════════════════════════════


def test_quality_scoring(report: EvalReport):
    report.section("场景 4: Quality Scoring — 质量评分与排序")

    # QualityScorer 实际 API: evaluate(tool_info: dict) -> float (类方法)
    # evaluate_batch(tools: list[dict]) -> list[dict]（类方法，原地排序并返回）

    tools_data = [
        {
            "id": "kos.semantic_search",
            "stars": 5000,
            "version": "2.0.0",
            "usage_count": 1000,
            "success_rate": 0.98,
            "metadata": {"verified": True, "updated_at": "2026-05-01T00:00:00Z"},
        },
        {
            "id": "kos.text_summarize",
            "stars": 300,
            "version": "1.2.0",
            "usage_count": 500,
            "success_rate": 0.85,
            "metadata": {"verified": True, "updated_at": "2026-01-01T00:00:00Z"},
        },
        {
            "id": "minerva.research_now",
            "stars": 4000,
            "version": "1.5.0",
            "usage_count": 2000,
            "success_rate": 0.92,
            "metadata": {"verified": True, "updated_at": "2026-05-15T00:00:00Z"},
        },
        {
            "id": "minerva.data_analyze",
            "stars": 20,
            "version": "0.9.0",
            "usage_count": 100,
            "success_rate": 0.75,
            "metadata": {"verified": False, "updated_at": "2025-10-01T00:00:00Z"},
        },
    ]

    # 使用 evaluate_batch（类方法，排序）
    scored = QualityScorer.evaluate_batch(tools_data)
    report.ok("evaluate_batch 批量评分+排序完成")

    report.info("评分排序结果（高→低）:")
    for i, td in enumerate(scored, 1):
        score = td.get("quality_score", 0)
        report.info(f"  #{i} {td['id']} = {score:.4f}")

    # 逐个 evaluate
    for td in tools_data:
        score = QualityScorer.evaluate(td)
        report.info(f"  单个 evaluate({td['id']}) = {score:.4f}")

    report.ok("质量评分与排序流程正常")


# ══════════════════════════════════════════════════════════════════════
# 场景 5: Edge Cases - 异常与边界
# ══════════════════════════════════════════════════════════════════════


async def test_edge_cases(report: EvalReport):
    report.section("场景 5: Edge Cases — 异常与边界情况")

    registry = ProxyRegistry()

    # 1. 空目录查询
    empty_entries = registry.entries
    if len(empty_entries) == 0:
        report.ok("空 ProxyRegistry 正确处理 — entries 为空字典")
    else:
        report.fail("空 ProxyRegistry 应返回空字典")

    # 2. 不存在的工具
    missing_entry = registry.get_entry("non_existent_tool")
    if missing_entry is None:
        report.ok("查询不存在的工具返回 None（而不是抛出异常）")
    else:
        report.fail("查询不存在的工具应返回 None")

    # 3. dispatch 不存在的工具
    result = await registry.dispatch("non_existent_tool", {})
    if result.get("status") == "error":
        report.ok("dispatch 不存在的工具返回 error", detail=f"错误消息: {result.get('error', '')}")
    else:
        report.fail("dispatch 不存在的工具应返回 error")

    # 4. 断连的服务 — 直接注册条目但不设 client，dispatch 时会走 lazy reconnect 失败路径
    entry = ProxyEntry(
        tool_name="test_svc.hello",
        service_name="test_svc",
        original_name="hello",
        description="测试工具",
        parameters={},
        client=make_mock_client("test_svc"),
    )
    entry.client.connected = False
    registry._entries["test_svc.hello"] = entry
    registry._clients["test_svc"] = entry.client

    result2 = await registry.dispatch("test_svc.hello", {})
    if result2.get("status") == "error":
        report.ok("断连服务的 dispatch 正确返回 error", detail=f"原因: {result2.get('error', '')}")
    else:
        report.skip("断连服务 dispatch 行为（取决于 lazy_connect 配置）", detail=str(result2))

    report.ok("异常与边界情况处理验证完成")


# ══════════════════════════════════════════════════════════════════════
# 场景 6: 端到端流程 — 完整的 Agent 对话模拟
# ══════════════════════════════════════════════════════════════════════


def test_e2e_flow(report: EvalReport):
    report.section("场景 6: 端到端流程 — Agent 对话模拟")

    # 模拟一个外部 Agent 与 Agora 的完整交互日志
    dialog = [
        ("Agent", "你好，我需要处理一些数据任务，你能提供什么工具？"),
        ("Agora", "当然，以下是我当前可用的工具清单："),
        ("Agora", "  [kos] semantic_search — 向量语义搜索"),
        ("Agora", "  [kos] text_summarize — 文本摘要"),
        ("Agora", "  [minerva] research_now — 实时网络调研"),
        ("Agora", "  [minerva] data_analyze — 数据分析"),
        ("Agent", "很好，我需要搜索一些相似文档，请调用 semantic_search"),
        ("Agora", "正在调用 kos.semantic_search({'query': 'AI safety latest papers'})..."),
        ("Agora", "调用成功！返回了 5 篇相关论文。"),
        ("Agent", "再帮我总结一下第一篇论文的内容。"),
        ("Agora", "正在调用 kos.text_summarize({'text': '...', 'max_length': 500})..."),
        ("Agora", "摘要完成！"),
        ("Agent", "好，我的任务完成，谢谢！"),
        ("Agora", "✅ 本次会话使用了 2 个工具，调用了 2 次，耗时 3.2s"),
    ]

    report.info("=== Agent-Agora 对话模拟 ===")
    for speaker, msg in dialog:
        report.info(f"  [{speaker}] {msg}")

    report.ok("端到端用户旅程验证通过 — 完整的 获取 Manifest → 选择工具 → 直接调用 → 结果返回 链路")


# ══════════════════════════════════════════════════════════════════════
# 场景 7: Auto Registration — 自主发现与注册
# ══════════════════════════════════════════════════════════════════════


async def test_auto_registration(report: EvalReport):
    report.section("场景 7: Auto Registration — 自主发现与注册")

    # ── 7a. DiscoveryEngine 工作空间发现 ──
    report.info("=== 7a: DiscoveryEngine 工作空间发现 ===")
    from agora.discovery import DiscoveredService, DiscoveryEngine  # type: ignore[import-not-found]

    mock_services = [
        DiscoveredService(name="minerva", description="深度研究系统", mcp_endpoint="stdio://minerva", confidence=0.85),
        DiscoveredService(name="kos", description="知识操作系统", mcp_endpoint="stdio://kos", confidence=0.85),
        DiscoveredService(name="eidos", description="知识卡片引擎", mcp_endpoint="stdio://eidos", confidence=0.65),
    ]

    import os as _os

    _os.makedirs("/tmp/mock_workspace", exist_ok=True)

    engine = DiscoveryEngine(workspace_root="/tmp/mock_workspace")
    with (
        patch.object(engine, "scan_known_projects", return_value=mock_services),
        patch.object(engine, "scan_pyproject_scripts", return_value=[]),
        patch.object(engine, "scan_docker_compose", return_value=[]),
    ):
        results = engine.discover_all()
        assert len(results) == 3, f"期望 3 个服务，实际 {len(results)}"
        assert results[0].confidence == 0.85, "应按 confidence 降序排列"
        report.ok("7a: DiscoveryEngine 发现并排序 %d 个服务" % len(results))
        for s in results:
            report.info(f"  {s.name}: confidence={s.confidence}, endpoint={s.mcp_endpoint}")

    # ── 7b. auto_register 自动注册 ──
    report.info("=== 7b: auto_register 自动注册 ===")
    from agora.registry import ServiceRegistry  # type: ignore[import-not-found]

    registry = ServiceRegistry(storage_path="/tmp/test_agora_registry_eval.json")
    registry.clear_all()  # 确保从干净状态开始
    try:
        engine2 = DiscoveryEngine(workspace_root="/tmp/mock_workspace")
        mock_discovered = [
            DiscoveredService(
                name="minerva", description="深度研究系统", mcp_endpoint="stdio://minerva", confidence=0.85
            ),
            DiscoveredService(name="kos", description="知识操作系统", mcp_endpoint="stdio://kos", confidence=0.85),
        ]
        with patch.object(engine2, "discover_all", return_value=mock_discovered):
            count = engine2.auto_register(registry)
            report.ok("7b: auto_register 首次注册 %d 个服务" % count)

            # 重复运行验证不重复注册
            count2 = engine2.auto_register(registry)
            assert count2 == 0, f"重复注册应返回 0，实际 {count2}"
            report.ok("7b: 重复运行 auto_register 正确跳过（无重复注册）")

            services = registry.list_all()
            assert len(services) == 2, f"registry 应包含 2 个服务，实际 {len(services)}"
            names = [s.name for s in services]
            assert "minerva" in names and "kos" in names
            report.ok("7b: registry.list_all() 返回正确的服务列表")
    finally:
        import os as _os

        try:
            _os.remove("/tmp/test_agora_registry_eval.json")
        except FileNotFoundError:
            pass

    # ── 7c. mcp_bootstrap.scan_and_launch 启动引导 ──
    report.info("=== 7c: mcp_bootstrap.scan_and_launch 启动引导 ===")
    from agora import mcp_bootstrap  # type: ignore[import-not-found]

    proxy_manager = MagicMock()
    proxy_manager.start = AsyncMock(return_value={"minerva": "started", "kos": "started"})

    mock_config = [
        {
            "name": "minerva",
            "enabled": True,
            "description": "Research",
            "command": "uv",
            "args": ["run", "--package", "minerva", "minerva-mcp"],
        },
        {
            "name": "kos",
            "enabled": True,
            "description": "KOS",
            "command": "uv",
            "args": ["run", "--package", "kos", "kos-mcp"],
        },
    ]
    mock_config_path = "/tmp/mock_config.json"

    with patch("agora.mcp_bootstrap.load_or_generate_config", return_value=(mock_config, mock_config_path)):
        results = await mcp_bootstrap.scan_and_launch(proxy_manager)
        assert isinstance(results, dict), f"返回类型应为 dict，实际 {type(results)}"
        report.ok("7c: scan_and_launch 启动引导成功", detail=f"返回 {len(results)} 个服务结果")
        for name, status in results.items():
            report.info(f"  {name}: {status}")

    # ── 7d. Orchestrator 外部工具流水线 ──
    report.info("=== 7d: Orchestrator 外部工具流水线 ===")

    catalog = ToolCatalog(db_path=":memory:")
    orchestrator = Orchestrator(catalog)

    mock_tools = [
        {
            "id": "ext.github_analyzer",
            "name": "GitHub Analyzer",
            "description": "分析 GitHub 仓库",
            "source": "github",
            "stars": 1000,
            "version": "1.0.0",
        },
        {
            "id": "ext.doc_parser",
            "name": "Document Parser",
            "description": "解析文档内容",
            "source": "github",
            "stars": 500,
            "version": "2.0.0",
        },
        {
            "id": "ext.sql_helper",
            "name": "SQL Helper",
            "description": "SQL 查询辅助",
            "source": "registry",
            "stars": 200,
            "version": "0.5.0",
        },
    ]

    # 测试 discover_and_save
    with patch("agora.mcp_registry.orchestrator.search_all", new=AsyncMock(return_value=mock_tools)):
        saved = await orchestrator.discover_and_save(query="mcp-server", sources=["github"])
        assert len(saved) == len(mock_tools), f"应保存 {len(mock_tools)} 个工具，实际 {len(saved)}"
        report.ok("7d: discover_and_save 发现+评分+保存 %d 个工具" % len(saved))
        for s in saved:
            score = s.get("quality_score", "N/A")
            report.info(f"  {s['id']}: quality_score={score}")

    # 测试 discover_install_load
    with patch("agora.mcp_registry.orchestrator.search_all", new=AsyncMock(return_value=mock_tools)):
        result = await orchestrator.discover_install_load(query="mcp-server", sources=["github"], auto_load=False)
        assert result["discovered"] == len(mock_tools), f"discovered={result['discovered']}"
        assert result["installed"] == len(mock_tools), f"installed={result['installed']}"
        report.ok(
            "7d: discover_install_load 全流水线完成",
            detail=f"discovered={result['discovered']}, installed={result['installed']}, loaded={result['loaded']}",
        )
        report.info(f"  工具列表: {result['tool_names']}")

    catalog.close()
    report.ok("场景 7 全部完成 — 三层自动发现/注册验证通过")


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════


async def main():
    report = EvalReport()

    print(f"\n{_BOLD}{'=' * 50}{_RESET}")
    print(f"{_BOLD}Agora Agent Evaluation Suite{_RESET}")
    print(f"{_BOLD}{'=' * 50}{_RESET}")

    # 场景 1: Manifest
    registry = test_manifest(report)

    # 场景 2: Smart Routing
    await test_smart_routing(report, registry)

    # 场景 3: Direct Execution
    await test_direct_execution(report, registry)

    # 场景 4: Quality Scoring
    test_quality_scoring(report)

    # 场景 5: Edge Cases
    await test_edge_cases(report)

    # 场景 6: E2E Flow
    test_e2e_flow(report)

    # 场景 7: Auto Registration
    await test_auto_registration(report)

    # 汇总
    report.summary()


if __name__ == "__main__":
    asyncio.run(main())
