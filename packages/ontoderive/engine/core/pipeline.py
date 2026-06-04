"""
OntoDerive Pipeline — 推导管道
===============================
串联 toolforge → load → derive → check → resolve → report 六个阶段。
结果可序列化为 JSON，供 Minerva/Sophia 程序化调用。
"""

from pathlib import Path

try:
    from .config import Config
    from .protocols import AnalysisResult, PipelineStage
except ImportError:
    from engine.foundation.config import Config  # noqa
    from engine.foundation.protocols import PipelineStage, AnalysisResult


class ToolForgeStage(PipelineStage):
    name = "toolforge"

    def run(self, ctx):
        try:
            from .toolforge import ToolForge
        except ImportError:
            from engine.toolforge import ToolForge
        tf = ToolForge()
        cfg = ctx.get("config", {})
        goal = ctx.get("goal", "")
        context = ctx.get("context", "")
        mode = cfg.get("toolforge_mode", "tfidf") if isinstance(cfg, dict) else "tfidf"
        return {
            "matches": tf.select(
                goal, context, top_n=cfg.get("toolforge_top_n", 5) if isinstance(cfg, dict) else 5, mode=mode
            ),
            "guide": tf.to_inference_guide(goal, context, mode=mode),
        }


class LoadStage(PipelineStage):
    name = "load"

    def run(self, ctx):
        try:
            from .derive import OntoDerive as _OD  # noqa: N814
        except ImportError:
            from engine.core.derive import OntoDerive as _OD  # noqa: N814
        od = _OD(ctx["project_root"])
        summary = od.derive()
        return {"derive_summary": summary}


class DeriveStage(PipelineStage):
    name = "derive"

    def run(self, ctx):
        # 复用LoadStage结果，避免重复扫描+Bayesian
        cached = ctx.get("_derive_result")
        if cached:
            return cached
        try:
            from .derive import OntoDerive as _OD  # noqa: N814
        except ImportError:
            from engine.core.derive import OntoDerive as _OD  # noqa: N814
        od = _OD(ctx["project_root"])
        result = od.derive()
        ctx["_derive_result"] = result
        return result


class CheckStage(PipelineStage):
    name = "check"

    def run(self, ctx):
        try:
            from .derive import OntoDerive as _OD  # noqa: N814
        except ImportError:
            from engine.core.derive import OntoDerive as _OD  # noqa: N814
        od = _OD(ctx["project_root"])
        return od.check()


class ResolveStage(PipelineStage):
    name = "resolve"

    def run(self, ctx):
        try:
            from .derive import OntoDerive as _OD  # noqa: N814
        except ImportError:
            from engine.core.derive import OntoDerive as _OD  # noqa: N814
        od = _OD(ctx["project_root"])
        return {"fixed": od.resolve()}


class ReportStage(PipelineStage):
    name = "report"

    def run(self, ctx):
        try:
            from .derive import OntoDerive as _OD  # noqa: N814
        except ImportError:
            from engine.core.derive import OntoDerive as _OD  # noqa: N814
        od = _OD(ctx["project_root"])
        return {"report": od.generate_report()}


PIPELINE_STAGES = [
    ToolForgeStage,
    LoadStage,
    DeriveStage,
    CheckStage,
    ResolveStage,
    ReportStage,
]


class DerivePipeline:
    """六阶段推导管道，可序列化结果"""

    def __init__(self, project_root, config=None, observers=None):
        self.project_root = Path(project_root)
        self.config = config or Config(project_root).to_dict()
        self.observers = observers or []
        self.stages = [s() for s in PIPELINE_STAGES]
        self.ctx = {"project_root": str(project_root), "config": self.config}
        self.results = {}

    def set_goal(self, goal, context=""):
        self.ctx["goal"] = goal
        self.ctx["context"] = context

    def run(self, stages=None):
        """执行指定阶段或全部阶段"""
        names = stages or [s.name for s in self.stages]
        for stage in self.stages:
            if stage.name not in names:
                continue
            self._notify("stage_start", stage.name)
            try:
                stage.before(self.ctx)
                result = stage.run(self.ctx)
                stage.after(self.ctx, result)
                self.results[stage.name] = result
                self._notify("stage_end", stage.name, result)
            except Exception as e:
                stage.on_error(self.ctx, e)
                self._notify("stage_error", stage.name, error=e)
                raise

    def _notify(self, event, stage_name, result=None, error=None):
        for obs in self.observers:
            try:
                if event == "stage_start":
                    obs.on_stage_start(stage_name, self.ctx)
                elif event == "stage_end":
                    obs.on_stage_end(stage_name, result or {})
                elif event == "stage_error":
                    obs.on_error(stage_name, error or Exception("unknown"))
            except Exception:
                pass

    def to_analysis_result(self) -> AnalysisResult:
        derive_r = self.results.get("derive", {})
        check_r = self.results.get("check", [])
        toolforge_r = self.results.get("toolforge", {}).get("matches", [])
        return AnalysisResult(summary=derive_r, checks=check_r, toolforge_matches=toolforge_r)

    def to_dict(self):
        return {
            "project_root": str(self.project_root),
            "config": self.config,
            "results": self.results,
        }
