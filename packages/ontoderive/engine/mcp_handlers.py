"""
OntoDerive MCP Handlers
=======================
All 17 tool handlers, tool definitions, dispatch table, and JSON-RPC request handler.
Split from mcp_server.py for cleanliness.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # 项目根
sys.path.insert(0, str(Path(__file__).parent))  # engine/
from toolforge.matcher import ToolForge

from engine.core.derive import OntoDerive

tf = ToolForge()


def respond(req_id, result):
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}, ensure_ascii=False)


def err(req_id, code, message):
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}, ensure_ascii=False)


TOOL_DEFS = [
    # ── 推导工具 (5) ──
    {
        "name": "ontoderive_init",
        "description": "初始化新OntoDerive项目骨架",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "项目名称"}},
            "required": ["name"],
        },
    },
    {
        "name": "ontoderive_derive",
        "description": "正向推导：含分析模式(A1-A9)+关系推理(R19)+推导链路trail",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string", "description": "项目路径", "default": "."}},
        },
    },
    {
        "name": "ontoderive_check",
        "description": "规约检查：13条规约(C-01~C-13)含贝叶斯/KQI/PID",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string", "description": "项目路径", "default": "."}},
        },
    },
    {
        "name": "ontoderive_rounds",
        "description": "多轮迭代：derive→check循环至收敛",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目路径", "default": "."},
                "rounds": {"type": "number", "description": "迭代轮数", "default": 3},
            },
        },
    },
    {
        "name": "ontoderive_generate",
        "description": "生成推导报告(markdown)",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string", "description": "项目路径", "default": "."}},
        },
    },
    # ── 分析工具 (1+2新) ──
    {
        "name": "ontoderive_analyze",
        "description": "全量分析：Pipeline全流程(ToolForge+derive+check)，含匹配推荐+置信度+KQI+收敛",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目路径"},
                "goal": {"type": "string", "description": "分析目标"},
                "context": {"type": "string", "description": "上下文关键词"},
            },
        },
    },
    {
        "name": "ontoderive_config",
        "description": "获取当前配置项(匹配模式/阈值等)",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string", "description": "项目路径", "default": "."}},
        },
    },
    {
        "name": "ontoderive_delta",
        "description": "对比最近两次推导的状态差异",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string", "description": "项目路径", "default": "."}},
        },
    },
    # ── 分析模式 (v3.5 NEW) ──
    {
        "name": "ontoderive_analytics",
        "description": (
            "运行分析模式(A1-A9): 供给弹性/风险传导/代理问题/激励相容/补救规划/市场结构/博弈均衡/策略空间/信息生态"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目路径", "default": "."},
                "max_depth": {"type": "number", "description": "最大推理深度(0=纯规则,5=LLM)", "default": 1},
            },
        },
    },
    {
        "name": "ontoderive_relations",
        "description": "关系推理(R19): 传递性+逆关系+域约束, 输入项目路径",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string", "description": "项目路径", "default": "."}},
        },
    },
    {
        "name": "ontoderive_export",
        "description": "导出分析结果(html/json/jsonld/turtle)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目路径", "default": "."},
                "format": {"type": "string", "description": "导出格式: html|json|jsonld|turtle", "default": "html"},
            },
        },
    },
    # ── 工具匹配 (3) ──
    {
        "name": "toolforge_match",
        "description": "按目标匹配思维工具并按类别分组",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "目标描述"},
                "context": {"type": "string", "description": "上下文"},
                "mode": {"type": "string", "description": "匹配模式: tfidf|keyword|hybrid", "default": "keyword"},
            },
            "required": ["goal"],
        },
    },
    {
        "name": "toolforge_select",
        "description": "跨类别Top-N工具选择",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "目标描述"},
                "context": {"type": "string"},
                "top_n": {"type": "number", "default": 5},
                "mode": {"type": "string", "default": "keyword"},
            },
            "required": ["goal"],
        },
    },
    {
        "name": "toolforge_guide",
        "description": "生成推导指导(markdown)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "目标描述"},
                "context": {"type": "string"},
                "mode": {"type": "string", "default": "keyword"},
            },
            "required": ["goal"],
        },
    },
    # ── 写入工具 (v3.6 NEW) ──
    {
        "name": "ontoderive_write_fact",
        "description": "写入/更新事实记录到 facts/data.md",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目路径"},
                "fid": {"type": "string", "description": "事实编号(D-Fx或P-Fx)"},
                "description": {"type": "string", "description": "事实描述"},
                "value": {"type": "string", "description": "事实值"},
                "source": {"type": "string", "description": "来源", "default": "MCP"},
            },
            "required": ["project", "fid", "description", "value"],
        },
    },
    {
        "name": "ontoderive_write_inference",
        "description": "写入/更新推论到 inferences/ 文件",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目路径"},
                "inf_id": {"type": "string", "description": "推论编号(INF-Lx)"},
                "title": {"type": "string", "description": "推论标题"},
                "content": {"type": "string", "description": "推论内容"},
                "derives_from": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "引用的事实/推论编号列表",
                },
            },
            "required": ["project", "inf_id", "title", "content"],
        },
    },
    {
        "name": "ontoderive_write_scheme",
        "description": "写入/更新方案到 scheme/ 文件",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目路径"},
                "title": {"type": "string", "description": "方案标题"},
                "content": {"type": "string", "description": "方案内容(markdown)"},
            },
            "required": ["project", "title", "content"],
        },
    },
]


# ── 工具处理器 ──


def _handle_init(args, req_id):
    name = args.get("name", "demo")
    od = OntoDerive(name)
    od.derive()
    return respond(req_id, {"output": f"项目'{name}'已初始化，目录: facts/entities/inferences/scheme/"})


def _handle_derive(args, req_id):
    project = args.get("project", ".")
    od = OntoDerive(project)
    result = od.derive()
    return respond(req_id, {"output": str(result)[:1000]})


def _handle_check(args, req_id):
    project = args.get("project", ".")
    od = OntoDerive(project)
    result = od.check()
    return respond(req_id, {"output": str(result)[:1000]})


def _handle_generate(args, req_id):
    project = args.get("project", ".")
    od = OntoDerive(project)
    result = od.generate_report()
    return respond(req_id, {"output": str(result)[:1000]})


def _handle_rounds(args, req_id):
    project = args.get("project", ".")
    rounds = args.get("rounds", 3)
    od = OntoDerive(project)
    od.run_rounds(int(rounds))
    return respond(req_id, {"output": f"{rounds}轮迭代完成，日志在 _derivation_logs/"})


def _handle_analyze(args, req_id):
    project = args.get("project", ".")
    goal = args.get("goal", "")
    context = args.get("context", "")
    od = OntoDerive(project)
    if goal:
        matches = tf.select(goal, context, top_n=5)
        guide = tf.to_inference_guide(goal, context)
    else:
        matches, guide = [], ""
    derive_r = od.derive()
    check_r = od.check()
    return respond(
        req_id,
        {
            "derive_summary": derive_r,
            "checks_passed": sum(1 for r in check_r if r.get("passed")),
            "checks_total": len(check_r),
            "toolforge_matches": [{"id": m["id"], "name": m["name"], "score": m["score"]} for m in matches],
            "guide": guide[:500],
        },
    )


def _handle_config(args, req_id):
    project = args.get("project", ".")
    from engine.foundation.config import Config

    cfg = Config(project).to_dict()
    return respond(req_id, cfg)


def _handle_delta(args, req_id):
    project = args.get("project", ".")
    from engine.theories.turing_k import KnowledgeTM

    ktm = KnowledgeTM(project)
    d = ktm.delta()
    return respond(req_id, d)


def _handle_analytics(args, req_id):
    project = args.get("project", ".")
    od = OntoDerive(project)
    r = od.derive()
    ae_conclusions = [c for c in r.get("derived_conclusions", []) if c.get("source") == "analytics"]
    return respond(req_id, {"analytics_count": len(ae_conclusions), "conclusions": ae_conclusions[:10]})


def _handle_relations(args, req_id):
    project = args.get("project", ".")
    od = OntoDerive(project)
    r = od.derive()
    rel_conclusions = [c for c in r.get("derived_conclusions", []) if c.get("type", "").startswith("relation_")]
    return respond(req_id, {"relations_count": len(rel_conclusions), "conclusions": rel_conclusions[:10]})


def _handle_export(args, req_id):
    project = args.get("project", ".")
    fmt = args.get("format", "html")
    od = OntoDerive(project)
    r = od.derive()
    if fmt in ("html", "json"):
        from engine.core.export import to_html, to_json

        output = to_html(r, project) if fmt == "html" else to_json(r)
    else:
        from engine.foundation.ontology_map import OntologyMapper
        from engine.reasoners.formalize import Formalizer

        fz = Formalizer()
        kb = fz.extract_from_text("\n".join(str(r.get(k, "")) for k in r), mode="rule_only")
        om = OntologyMapper()
        output = om.export(kb, fmt=fmt)
    return respond(req_id, {"format": fmt, "output": output[:3000], "length": len(output)})


def _handle_toolforge_match(args, req_id):
    goal = args.get("goal", "")
    context = args.get("context", "")
    mode = args.get("mode", "keyword")
    result = tf.match(goal, context, mode=mode)
    return respond(req_id, result)


def _handle_toolforge_select(args, req_id):
    goal = args.get("goal", "")
    context = args.get("context", "")
    top_n = args.get("top_n", 5)
    mode = args.get("mode", "keyword")
    result = tf.select(goal, context, top_n=int(top_n), mode=mode)
    return respond(req_id, result)


def _handle_toolforge_guide(args, req_id):
    goal = args.get("goal", "")
    context = args.get("context", "")
    mode = args.get("mode", "keyword")
    guide = tf.to_inference_guide(goal, context, mode=mode)
    return respond(req_id, {"guide": guide[:2000]})


# ── 写入工具处理器 (v3.6 NEW) ──


def _handle_write_fact(args, req_id):
    project = Path(args.get("project", "."))
    fid = args.get("fid", "")
    desc = args.get("description", "")
    value = args.get("value", "")
    source = args.get("source", "MCP")
    facts_dir = project / "facts"
    facts_dir.mkdir(parents=True, exist_ok=True)

    prefix = "D" if fid.startswith("D-F") else "P"
    file_path = facts_dir / f"{prefix}.md"
    if not file_path.exists():
        file_path.write_text("| 编号 | 数据 | 数值 | 来源 |\n|------|------|------|------|\n")
    old = file_path.read_text()
    if fid in old:
        # 替换已有行
        lines = old.split("\n")
        for i, line in enumerate(lines):
            if line.startswith(f"| {fid} "):
                lines[i] = f"| {fid} | {desc} | {value} | {source} |"
                break
        file_path.write_text("\n".join(lines))
    else:
        file_path.write_text(old.rstrip() + f"\n| {fid} | {desc} | {value} | {source} |\n")
    return respond(req_id, {"output": f"事实{fid}已写入 {file_path.name}"})


def _handle_write_inference(args, req_id):
    project = Path(args.get("project", "."))
    inf_id = args.get("inf_id", "")
    title = args.get("title", "")
    content = args.get("content", "")
    derives_from = args.get("derives_from", [])

    inf_dir = project / "inferences"
    inf_dir.mkdir(parents=True, exist_ok=True)
    file_path = inf_dir / "analysis.md"

    df_line = f"derives_from: [{', '.join(derives_from)}]" if derives_from else ""
    block = f"\n## {inf_id}：{title}\n\n{content}\n\n{df_line}\n"
    if not file_path.exists():
        file_path.write_text(f"# 推论分析\n\n{block.strip()}\n")
    else:
        file_path.write_text(file_path.read_text().rstrip() + "\n" + block)
    return respond(req_id, {"output": f"推论{inf_id}已写入 {file_path.name}"})


def _handle_write_scheme(args, req_id):
    project = Path(args.get("project", "."))
    title = args.get("title", "")
    content = args.get("content", "")

    scheme_dir = project / "scheme"
    scheme_dir.mkdir(parents=True, exist_ok=True)
    file_path = scheme_dir / "report.md"

    block = f"\n## {title}\n\n{content}\n"
    if not file_path.exists():
        file_path.write_text(f"# 方案分析\n\n{block.strip()}\n")
    else:
        file_path.write_text(file_path.read_text().rstrip() + "\n" + block)
    return respond(req_id, {"output": f"方案'{title}'已写入 {file_path.name}"})


# ── 调度表 ──

TOOL_HANDLERS = {
    "ontoderive_init": _handle_init,
    "ontoderive_derive": _handle_derive,
    "ontoderive_check": _handle_check,
    "ontoderive_generate": _handle_generate,
    "ontoderive_rounds": _handle_rounds,
    "ontoderive_analyze": _handle_analyze,
    "ontoderive_config": _handle_config,
    "ontoderive_delta": _handle_delta,
    "ontoderive_analytics": _handle_analytics,
    "ontoderive_relations": _handle_relations,
    "ontoderive_export": _handle_export,
    "toolforge_match": _handle_toolforge_match,
    "toolforge_select": _handle_toolforge_select,
    "toolforge_guide": _handle_toolforge_guide,
    "ontoderive_write_fact": _handle_write_fact,
    "ontoderive_write_inference": _handle_write_inference,
    "ontoderive_write_scheme": _handle_write_scheme,
}


def handle_request(req):
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "tools/list":
        return respond(req_id, {"tools": TOOL_DEFS})

    if method == "initialize":
        return respond(
            req_id,
            {
                "protocolVersion": "0.1.0",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ontoderive-unified-mcp", "version": "3.6.0"},
            },
        )

    if method == "tools/call":
        tool = params.get("name", "")
        args = params.get("arguments", {})

        try:
            handler = TOOL_HANDLERS.get(tool)
            if handler:
                return handler(args, req_id)
            return err(req_id, -32601, f"未知工具: {tool}")
        except Exception as e:
            return err(req_id, -32000, f"{tool}失败: {str(e)[:200]}")

    return err(req_id, -32601, f"未知方法: {method}")
