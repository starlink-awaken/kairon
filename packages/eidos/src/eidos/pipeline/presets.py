"""Pre-built pipeline templates.

Each preset is a Pipeline with named steps ready to run.
"""

# Determine workspace root from current file location
import os

from eidos.pipeline import Pipeline, PipelineStep

_WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KNOWLEDGE_BASE = Pipeline(
    name="知识库构建 (完整版)",
    steps=[
        PipelineStep(tool="eidos", action="meta", args={"export": True}, output_file="/tmp/pipe-meta.json"),
        PipelineStep(
            tool="kos",
            action="ingest",
            args={"path": os.path.join(_WORKSPACE, "knowledge", "ingested"), "dry_run": True, "verbose": False},
            output_file="/tmp/pipe-ingest.json",
        ),
        PipelineStep(
            tool="kos",
            action="search",
            args={"query": "", "limit": 5, "meta-type": "document"},
            output_file="/tmp/pipe-search.json",
        ),
        PipelineStep(tool="eidos", action="viz", args={"type": "graph"}),
    ],
)

REASONING = Pipeline(
    name="推理链路 (完整版)",
    steps=[
        PipelineStep(
            tool="kos", action="search", args={"query": "", "limit": 5}, output_file="/tmp/pipe-reason-search.json"
        ),
        PipelineStep(tool="ontoderive", action="derive", args={"eidos": True}, output_file="/tmp/pipe-derive.json"),
        PipelineStep(tool="eidos", action="viz", args={"type": "graph"}, output_file="/tmp/pipe-viz.json"),
    ],
)

PRESETS = {
    "knowledge-base": KNOWLEDGE_BASE,
    "reasoning": REASONING,
}
