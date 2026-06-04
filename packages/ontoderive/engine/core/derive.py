#!/usr/bin/env python3
"""
OntoDerive 分析引擎 v3.6.4
========================
知识工程质量分析引擎。双模式运行:
- 规则引擎模式: 结构分析(文件扫描/计数/格式检查), 始终可用
- LLM增强模式: 洞察推导/质量评估/语义矛盾检测, 需要LLM后端

用法:
    python3 derive.py --init my-project     # 初始化
    python3 derive.py --analyze             # 分析(结构+[LLM洞察])
    python3 derive.py --check               # 规约检查
    python3 derive.py --rounds 5            # 多轮迭代
"""

import datetime
import re
import sys
from pathlib import Path

try:
    from .utils import all_md, load_json, rf, save_json, wf
except ImportError:
    from engine.foundation.utils import rf, wf, all_md, load_json, save_json  # noqa

VERSION = "3.6.4"

try:
    from .protocols import DeriveInterface
except ImportError:
    from engine.foundation.protocols import DeriveInterface


class OntoDerive(DeriveInterface):
    def __init__(self, project_root):
        self.root = Path(project_root)
        self.facts_dir = self.root / "facts"
        self.entities_dir = self.root / "entities"
        self.inferences_dir = self.root / "inferences"
        self.scheme_dir = self.root / "scheme"
        self.protocols_dir = self.root / "protocols"
        self.log_dir = self.root / "_derivation_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._facts: dict = {"data": {}, "policy": {}}
        self._loaded_rules = self._init_rules()  # v3.4: 加载YAML规则

    def _init_rules(self):
        """加载声明式YAML规则 (v3.4)"""
        try:
            from engine.foundation.rule_loader import RuleLoader

            rl = RuleLoader()
            rules_dir = Path(__file__).parent.parent / "foundation" / "rules"
            if rules_dir.exists():
                for yf in rules_dir.glob("*.yaml"):
                    rl.load_yaml(str(yf))
            return rl.rules
        except Exception:
            return []

    def derive(self):
        """正向推导 — 事实扫描 + 多引擎推理"""
        summary = self._derive_baseline()
        self._derive_bayesian(summary)
        self._derive_entailment(summary)
        self._derive_hints(summary)
        self._derive_unified(summary)
        print(
            f"[derive] 📊 事实={summary.get('facts', 0)}, "
            f"推论={summary.get('inferences', 0)}, "
            f"推导结论={len(summary.get('derived_conclusions', []))}条, "
            f"结构提示={len(summary.get('derivation_hints', []))} "
            + ("(LLM洞察需运行 analyze())" if not self._try_llm() else "")
        )
        return summary

    def _derive_baseline(self):
        """扫描事实/实体/推论基线"""
        print("[derive] 事实基座扫描...")
        from engine.foundation.utils import scan_facts_from_md

        self._facts = {"data": {}, "policy": {}}
        for f in all_md(self.facts_dir):
            result = scan_facts_from_md(rf(f))
            self._facts["data"].update(result["data"])
            self._facts["policy"].update(result["policy"])

        entities = {}
        for f in all_md(self.entities_dir):
            for m in re.finditer(r"\*\*(ORG-[\w-]+|ROL-[\w-]+|PRJ-[\w-]+|DOC-[\w-]+|STD-[\w-]+)\*\*", rf(f)):
                entities[m.group(1)] = True

        infer_count = 0
        for f in all_md(self.inferences_dir):
            infer_count += len(re.findall(r"^##\s+INF-", rf(f), re.MULTILINE))

        summary = {
            "derived_at": datetime.datetime.now().isoformat(),
            "facts": len(self._facts["data"]) + len(self._facts["policy"]),
            "entities": len(entities),
            "inferences": infer_count,
            "scheme_files": len(all_md(self.scheme_dir)),
        }
        return summary

    def _derive_bayesian(self, summary):
        """贝叶斯置信度传播"""
        # v2.1: 集成贝叶斯置信度分布+逻辑链深度
        try:
            from engine.theories.bayesian import BayesianLayer

            bl = BayesianLayer(self.root)
            _, bayes_infs = bl.propagate_all()
            confs = [i.get("propagated_confidence", i.get("base_confidence", 0.85)) for i in bayes_infs.values()]
            if confs:
                summary["confidence_distribution"] = {
                    "mean": round(sum(confs) / len(confs), 4),
                    "min": round(min(confs), 4),
                    "max": round(max(confs), 4),
                    "count": len(confs),
                }
        except Exception as e:
            import sys

            print(f"[derive] Bayesian skip: {e}", file=sys.stderr)

    def _derive_entailment(self, summary):
        """逻辑依赖图分析"""
        try:
            from engine.theories.logic import build_from_project

            g = build_from_project(self.root).stats()
            summary["entailment_graph"] = {
                "nodes": g["nodes"],
                "edges": g["edges"],
                "max_depth": g["max_depth"],
                "cycles": g["cycles"],
            }
        except Exception as e:
            import sys

            print(f"[derive] Logic skip: {e}", file=sys.stderr)

    def _derive_hints(self, summary):
        """内容推导 + DAG矛盾检测"""
        # v2.3: 内容推导 — 规则引擎 + DAG分析
        derivation_hints = []
        for f in all_md(self.inferences_dir):
            text = rf(f)
            if "derives_from" not in text:
                derivation_hints.append(f"{f.name}: 缺少 derives_from 声明")
            if "理论支撑" not in text and "理论" not in text:
                derivation_hints.append(f"{f.name}: 建议添加理论支撑")
        for f in all_md(self.scheme_dir):
            text = rf(f)
            if len(re.findall(r"D-F\d+|P-F\d+", text)) == 0:
                derivation_hints.append(f"{f.name}: 未引用任何事实编号")

        # DAG分析：弱推论、矛盾检测
        try:
            from engine.theories.logic import build_from_project

            g = build_from_project(self.root)
            st = g.stats()
            if st["contradictions"]:
                for c in st["contradictions"]:
                    derivation_hints.append(
                        f"⚠️ 矛盾: {c['inference_a']} vs {c['inference_b']} "
                        f"(共享事实{c['shared_facts']}, 对立词{c['opposing_terms']})"
                    )
            if st["max_depth"] < 2 and st["inferences"] >= 3:
                derivation_hints.append(f"推导链深度仅{st['max_depth']}，推论间缺少递进关系")
            if st["has_cycles"]:
                derivation_hints.append(f"检测到{st['cycles']}个循环引用，请检查 derives_from 链")
        except Exception:
            pass

        # v3.1: 规则引擎提示（始终可用，标注为结构分析）
        summary["analysis_mode"] = "structural"
        if derivation_hints:
            summary["derivation_hints"] = derivation_hints[:15]

    def _derive_unified(self, summary):
        """统一推理引擎"""
        # v3.4: 统一推理引擎 (RuleReasoner + FormalReasoner + AnalyticsEngine)
        try:
            from engine.reasoners.unified_reasoner import UnifiedReasoner

            # 重建推论dict
            inferences_dict = {}
            for f in all_md(self.inferences_dir):
                text = rf(f)
                for block in re.split(r"^##\s+", text, flags=re.MULTILINE)[1:]:
                    title = block.strip().split("\n")[0].strip()
                    df_line = re.search(r"derives_from:\s*\[([^\]]+)\]", block)
                    df = re.findall(r"(D-F\d+|P-F\d+|INF-[\w\d]+)", df_line.group(1)) if df_line else []
                    inferences_dict[title] = {"derives_from": list(set(df)), "text": block[:300]}
            # 解析关系声明
            relations = []
            for sf in all_md(self.scheme_dir):
                text = rf(sf)
                for m in re.finditer(
                    r"[-*]\s+((?:ORG|ROL|PRJ|RES|DOC|STD)-[\w一-鿿-]+)"
                    r"\s+(\w+)\s+"
                    r"((?:ORG|ROL|PRJ|RES|DOC|STD)-[\w一-鿿-]+)",
                    text,
                ):
                    relations.append(
                        {
                            "subject": m.group(1),
                            "relation_type": m.group(2),
                            "object": m.group(3),
                        }
                    )
            ur = UnifiedReasoner(loaded_rules=self._loaded_rules)
            uc_list = ur.reason(
                self._facts["data"],
                inferences_dict,
                relations=relations if relations else None,
                enhancer=self._try_llm(),
            )
            summary["derived_conclusions"] = [uc.to_dict() for uc in uc_list[:25]]
        except Exception:
            pass

        save_json(self.log_dir / "derive-summary.json", summary)

    def derive_formal(self, text=None):
        """
        v3.2: 形式化推理 — 四阶段管线。
        Phase1: LLM提取(降级规则) → Phase2: 符号化 → Phase3: 形式推理 → Phase4: 解读
        """
        from engine.reasoners.pipeline_v4 import FormalPipeline

        enhancer = self._try_llm()
        pipeline = FormalPipeline(enhancer=enhancer)
        if text:
            return pipeline.run(text)
        all_text = "\n".join(rf(f) for f in all_md(self.root) if "_derivation_logs" not in str(f))
        return pipeline.run(all_text)

    def analyze(self):
        """
        v3.1: 完整分析 — 结构分析 + LLM洞察推导。
        这是OntoDerive的"真实推导"入口。需要LLM后端。
        """
        summary = self.derive()  # 结构分析
        if not self._try_llm():
            summary["llm_status"] = "unavailable"
            summary["llm_message"] = (
                "结构分析已完成。深度洞察推导需要接入LLM后端。配置方式: export ONTODERIVE_LLM_BACKEND=local"
            )
            print("[analyze] ⚠️ LLM不可用 — 仅完成结构分析。洞察推导需要LLM。")
            print("[analyze]    配置: ONTODERIVE_LLM_BACKEND=local ONTODERIVE_LLM_MODEL=qwopus3.6-35b-a3b-v1")
            return summary

        print("[analyze] 🤖 启动LLM洞察推导...")
        try:
            from engine.intelligence.insight import InsightEngine

            engine = InsightEngine(enhancer=self._try_llm())
            facts_summary = f"事实数={summary['facts']}, 推论数={summary['inferences']}"
            infs_text = "\n".join(rf(f) for f in all_md(self.inferences_dir))
            insights = engine.derive_insights(self.root, facts_summary, infs_text)
            if insights:
                summary["llm_insights"] = [i.to_dict() for i in insights]
                summary["llm_status"] = "enhanced"
                summary["llm_model"] = insights[0].model if insights else ""
                print(f"[analyze] ✅ +{len(insights)}条LLM洞察")
                summary["analysis_mode"] = "llm_enhanced"
            engine.save_insights(self.log_dir)
        except Exception as e:
            summary["llm_status"] = f"error: {e}"
            print(f"[analyze] ⚠️ LLM调用失败: {e}")
        return summary

    def _try_llm(self):
        try:
            from engine.intelligence.llm import get_enhancer

            e = get_enhancer()
            return e if e.available else None
        except Exception:
            return None

    def check(self):
        print("[check] 执行规约检查...")
        try:
            from .check import run_check
        except ImportError:
            from engine.core.check import run_check
        return run_check(
            self.root, self.facts_dir, self.entities_dir, self.inferences_dir, self.scheme_dir, self.log_dir
        )[0]

    def run_rounds(self, rounds=3):
        for rnd in range(1, rounds + 1):
            print(f"\n Round {rnd}/{rounds}")
            self.derive()
            self.check()
        print(f"[rounds] ✅ {rounds}轮迭代完成")

    def generate_report(self):
        summary = load_json(self.log_dir / "derive-summary.json") or {}
        checks = load_json(self.log_dir / "check-result.json") or {"details": []}
        report = f"""---
title: OntoDerive 推导报告
version: {VERSION}
generated: {datetime.datetime.now().isoformat()}
---

## 执行摘要
| 指标 | 数值 |
|------|------|
| 事实数 | {summary.get("facts", 0)} |
| 推偶数 | {summary.get("inferences", 0)} |
| 规约通过 | {checks.get("passed", 0)}/{checks.get("total", 0)} |
"""
        for d in checks.get("details", []):
            report += f"\n{'✅' if d.get('passed') else '🟠'} {d['protocol_id']}: {d['detail']}"
        wf(self.log_dir / "report.md", report)
        print(f"[report] 报告: {self.log_dir / 'report.md'}")
        return report

    def resolve(self):
        checks = load_json(self.log_dir / "check-result.json") or {}
        fixed = 0
        for d in checks.get("details", []):
            if d.get("passed"):
                continue
            for fix in d.get("fixes", []):
                if "创建" in fix:
                    m = re.search(r"创建\s+(facts|entities|inferences|scheme|protocols)", fix)
                    if m:
                        (self.root / m.group(1)).mkdir(parents=True, exist_ok=True)
                        fixed += 1
        print(f"[resolve] 修复 {fixed} 项")
        return fixed


# CLI入口 (v2.2: 委托给cli.py)
def main():
    try:
        from .cli import main as _main
    except ImportError:
        from cli import main as _main
    _main()


if __name__ == "__main__":
    import sys

    sys.exit(main())
