"""OntoDerive CLI — pip install 入口点

用法:
    ontoderive init my-project
    ontoderive derive --project .
    ontoderive check --project .
    ontoderive toolforge "分析市场" --inference-guide
"""

import sys
from pathlib import Path
from typing import Any

# 确保项目根目录可导入 engine 包
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


FORMAT_VERSION = "ontoderive-v1"
"""CLI 输出格式版本。

消费者 (pallas/agora) 应检查此版本头以检测格式不兼容。
变更此版本号 = 契约断裂, 需同步更新所有消费者。
"""


def _json_output(status: str, data: dict | None = None, error: str | None = None) -> str:
    """生成带有版本头的 JSON 输出。"""
    import json

    payload: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "status": status,
    }
    if data is not None:
        payload["data"] = data
    if error is not None:
        payload["error"] = error
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main():
    """统一 CLI 入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="OntoDerive v3.6.4 — 知识工程分析平台",
        epilog="示例: ontoderive init my-project --with-tools --derive --check",
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # init
    p_init = sub.add_parser("init", help="初始化新项目")
    p_init.add_argument("name", help="项目名称")
    p_init.add_argument(
        "--template", choices=["default", "market", "tech", "org"], default="default", help="项目模板类型"
    )

    # derive
    p_derive = sub.add_parser("derive", help="正向推导")
    p_derive.add_argument("--project", default=".", help="项目路径")
    p_derive.add_argument("--auto", action="store_true", help="自动检测LLM并增强推导")
    p_derive.add_argument("--with-tools", action="store_true", help="前置 ToolForge 匹配")
    p_derive.add_argument("--goal", help="目标描述")
    p_derive.add_argument("--tool-context", default="", help="ToolForge 上下文关键词")
    p_derive.add_argument("--pipeline-input", help="(pipeline mode) 输入文件")
    p_derive.add_argument("--pipeline-output", help="(pipeline mode) 输出文件")

    # analyze (v3.6)
    p_analyze = sub.add_parser("analyze", help="全量分析: 推导+LLM洞察(自动检测)")
    p_analyze.add_argument("--project", default=".", help="项目路径")
    p_analyze.add_argument("--auto", action="store_true", help="自动检测LLM(默认行为)")
    p_analyze.add_argument("--force", action="store_true", help="强制重新分析(跳过缓存)")

    # check
    p_check = sub.add_parser("check", help="规约检查")
    p_check.add_argument("--project", default=".", help="项目路径")

    # rounds
    p_generate = sub.add_parser("generate", help="生成推导报告")
    p_generate.add_argument("--project", default=".", help="项目路径")
    p_generate.add_argument("--export", choices=["jsonld", "turtle", "html", "json"], help="导出格式")
    p_rounds = sub.add_parser("rounds", help="多轮迭代")
    p_rounds.add_argument("--project", default=".", help="项目路径")
    p_rounds.add_argument("n", type=int, default=3, help="迭代轮数")

    # toolforge
    p_tf = sub.add_parser("toolforge", help="思维工具匹配")
    p_tf.add_argument("goal", help="目标描述")
    p_tf.add_argument("--context", default="", help="上下文关键词")
    p_tf.add_argument("--inference-guide", action="store_true", help="输出推导指导")
    p_tf.add_argument("--json", action="store_true", help="JSON输出")

    # formal (v3.2)
    p_formal = sub.add_parser("formal", help="形式化推理(Phase1-4管线)")
    p_formal.add_argument("--text", help="原始文本输入")
    p_formal.add_argument("--project", default=".", help="项目路径")
    # watch
    p_watch = sub.add_parser("watch", help="文件监听自动重推导")
    p_watch.add_argument("--project", default=".", help="项目路径")
    p_watch.add_argument("--interval", type=int, default=5, help="检测间隔(秒)")
    # extract
    p_extract = sub.add_parser("extract", help="从文本/URL提取事实")
    p_extract.add_argument("source", help="源文本或文件路径")
    p_extract.add_argument("--to", default="facts/data.md", help="输出路径")

    # mcp (v3.6)
    p_mcp = sub.add_parser("mcp", help="启动MCP server (FastMCP, 5 tools + JSON-RPC bridge)")
    p_mcp.add_argument("--port", type=int, default=0, help="监听端口(0=stdio模式)")

    # serve (v3.6)
    p_serve = sub.add_parser("serve", help="启动开发服务: MCP + 文件监听 + LLM(可选)")
    p_serve.add_argument("--project", default=".", help="项目路径")
    p_serve.add_argument("--watch", action="store_true", default=True, help="启动文件监听(默认)")
    p_serve.add_argument("--interval", type=int, default=5, help="监听间隔(秒)")
    p_serve.add_argument("--auto", action="store_true", help="自动检测LLM并增强分析")
    p_serve.add_argument("--no-mcp", action="store_true", help="不启动MCP server")
    p_serve.add_argument("--http", action="store_true", help="启动Web仪表盘(FastAPI) + MCP over HTTP")
    p_serve.add_argument("--host", default="127.0.0.1", help="Web服务绑定地址")
    p_serve.add_argument("--port", type=int, default=8080, help="Web服务端口")

    # got (v3.6)
    p_got = sub.add_parser("got", help="GoT图思维推理(需LLM, 蕴含图上游走推理)")
    p_got.add_argument("--project", default=".", help="项目路径")

    # react (v3.6)
    p_react = sub.add_parser("react", help="ReAct推理行动循环(需LLM, 7个Action原语)")
    p_react.add_argument("--project", default=".", help="项目路径")
    p_react.add_argument("--max-steps", type=int, default=5, help="最大推理步数")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 路由到对应功能（委托至 engine/core/commands/）
    from ontoderive.core.commands.derive_commands import (  # type: ignore[import-not-found]
        cmd_analyze,
        cmd_check,
        cmd_derive,
        cmd_rounds,
    )
    from ontoderive.core.commands.extract import cmd_extract  # type: ignore[import-not-found]
    from ontoderive.core.commands.mcp_serve import cmd_mcp  # type: ignore[import-not-found]
    from ontoderive.core.commands.toolforge import cmd_toolforge  # type: ignore[import-not-found]

    if args.command == "init":
        from ontoderive.foundation.templates import TEMPLATES  # type: ignore[import-not-found]

        root = Path(args.name)
        tmpl_name = getattr(args, "template", "default")
        tmpl: dict[str, Any] = TEMPLATES.get(tmpl_name, TEMPLATES["default"])

        for d in ["facts", "entities", "inferences", "protocols", "scheme", "_logs"]:
            (root / d).mkdir(parents=True, exist_ok=True)

        # 事实
        facts_lines = "| 编号 | 数据 | 数值 | 来源 |\n|------|------|------|------|\n"
        for fid, desc, val, src in tmpl["facts"]:
            facts_lines += f"| {fid} | {desc} | {val} | {src} |\n"
        (root / "facts" / "data.md").write_text(facts_lines)

        # 政策
        policy_lines = "| 编号 | 政策 | 发布主体 | 日期 |\n|------|------|---------|------|\n"
        for pid, desc, subj, date in tmpl["policy"]:
            policy_lines += f"| {pid} | {desc} | {subj} | {date} |\n"
        (root / "facts" / "policy.md").write_text(policy_lines)

        # 实体
        entity_lines = "| 实体 | 类型 | 角色 |\n|------|------|------|\n"
        for eid, etype, role in tmpl["entities"]:
            entity_lines += f"| {eid} | {etype} | {role} |\n"
        (root / "entities" / "actors.md").write_text(entity_lines)

        # 推论
        inf_lines = ""
        for inf in tmpl["inferences"]:
            df = ", ".join(inf["derives_from"])
            inf_lines += f"## {inf['id']}：{inf['title']}\n\n{inf['content']}\n\n- derives_from: [{df}]\n\n"
        (root / "inferences" / "analysis.md").write_text(inf_lines.strip())

        # 方案
        (root / "scheme" / "report.md").write_text(tmpl["scheme"])

        (root / "README.md").write_text(
            f"# {args.name}\n\n> OntoDerive v3.6.1\n\n"
            "```bash\nontoderive derive --project .\n"
            "ontoderive check --project .\n```\n"
        )
        print(f"项目 {args.name} 已初始化 (模板: {tmpl_name})")

    elif args.command in ("derive", "check", "rounds", "generate", "analyze"):
        from ontoderive.core.derive import OntoDerive  # type: ignore[import-not-found]

        od = OntoDerive(getattr(args, "project", "."))

        # ToolForge 前置
        if getattr(args, "with_tools", False):
            from ontoderive.toolforge import ToolForge  # type: ignore[import-not-found]

            tf = ToolForge()
            goal = getattr(args, "goal", "") or ""
            context = getattr(args, "tool_context", "") or ""
            print(f"\n{'━' * 50}")
            print("  🧰 ToolForge 前置匹配")
            print(f"     目标: {goal or '(未指定)'}")
            print(f"{'━' * 50}")
            guide = tf.to_inference_guide(goal, context)
            guide_path = Path(args.project) / "inferences" / "_toolforge_guide.md"
            guide_path.parent.mkdir(parents=True, exist_ok=True)
            guide_path.write_text(guide)
            top = tf.select(goal, context, top_n=3)
            if top:
                for t in top:
                    print(f"      {t['id']} {t['name']} (匹配度:{t['score']})")

        if args.command == "derive":
            cmd_derive(
                project=getattr(args, "project", "."),
                auto=getattr(args, "auto", False),
                with_tools=getattr(args, "with_tools", False),
                goal=getattr(args, "goal", ""),
                tool_context=getattr(args, "tool_context", ""),
                pipeline_input=getattr(args, "pipeline_input", None),
                pipeline_output=getattr(args, "pipeline_output", None),
            )
        elif args.command == "analyze":
            cmd_analyze(project=getattr(args, "project", "."), force=getattr(args, "force", False))
        elif args.command == "check":
            cmd_check(project=getattr(args, "project", "."))
        elif args.command == "rounds":
            cmd_rounds(project=getattr(args, "project", "."), n=getattr(args, "n", 3))
        elif args.command == "generate":
            fmt = getattr(args, "export", None)
            if fmt:
                r = od.derive()
                try:
                    if fmt in ("html", "json"):
                        from ontoderive.core.export import to_html, to_json  # type: ignore[import-not-found]

                        output = to_html(r, args.project) if fmt == "html" else to_json(r)
                        ext = fmt
                    else:
                        from ontoderive.foundation.ontology_map import OntologyMapper  # type: ignore[import-not-found]
                        from ontoderive.reasoners.formalize import Formalizer  # type: ignore[import-not-found]

                        fz = Formalizer()
                        all_text = ""
                        for d in ["facts", "entities", "inferences", "scheme"]:
                            for f in Path(args.project).glob(f"{d}/**/*.md"):
                                all_text += f.read_text() + "\n"
                        kb = fz.extract_from_text(all_text, mode="rule_only")
                        om = OntologyMapper()
                        output = om.export(kb, fmt=fmt)
                        ext = fmt if fmt != "jsonld" else "json"
                    out_path = Path(args.project) / f"export.{ext}"
                    out_path.write_text(output)
                    print(f"[export] ✅ {out_path} ({len(output)}字符)")
                except Exception as e:
                    print(f"[export] ❌ {e}")
            else:
                od.generate_report()

    elif args.command == "toolforge":
        cmd_toolforge(
            args.goal,
            getattr(args, "context", ""),
            getattr(args, "inference_guide", False),
            getattr(args, "json", False),
        )

    elif args.command == "formal":
        from ontoderive.core.derive import OntoDerive

        od = OntoDerive(args.project)
        text = getattr(args, "text", None)
        result = od.derive_formal(text=text)
        print(result.get("report", "推理完成")[:3000])

    elif args.command == "watch":
        from ontoderive.watcher import FileWatcher  # type: ignore[import-not-found]

        w = FileWatcher(args.project)
        print(f"[watch] 监听中... 间隔{args.interval}秒, Ctrl+C停止")
        w.watch(interval=args.interval, auto_run=True)

    elif args.command == "extract":
        cmd_extract(
            source=args.source, to_path=getattr(args, "to", "facts/data.md"), project=getattr(args, "project", ".")
        )

    elif args.command == "mcp":
        cmd_mcp(port=getattr(args, "port", 0))

    elif args.command == "got":
        print("[got] GoT图思维推理...")
        print("[got] 需要LLM后端支持。请运行: ontoderive analyze --project", getattr(args, "project", "."))
        print("[got] 或配置 ONTODERIVE_LLM_BACKEND=auto")

    elif args.command == "react":
        print("[react] ReAct推理行动循环...")
        print("[react] 需要LLM后端支持。请运行: ontoderive analyze --project", getattr(args, "project", "."))
        print("[react] 或配置 ONTODERIVE_LLM_BACKEND=auto")

    elif args.command == "serve":
        from ontoderive.core.commands.mcp_serve import cmd_serve

        cmd_serve(
            project=getattr(args, "project", "."),
            watch_enabled=getattr(args, "watch", True),
            interval=getattr(args, "interval", 5),
            auto=getattr(args, "auto", False),
            no_mcp=getattr(args, "no_mcp", False),
            http=getattr(args, "http", False),
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8080),
        )


if __name__ == "__main__":
    main()
