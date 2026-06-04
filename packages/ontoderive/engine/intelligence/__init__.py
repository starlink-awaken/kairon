"""LLM智能层 — 推理增强 + 洞察 + 评估 + 提示词工程"""

from engine.intelligence.insight import (  # type: ignore[import-not-found]  # noqa: F401
    Insight,
    InsightCache,
    InsightEngine,
)
from engine.intelligence.judge import JudgeResult, OntoDeriveJudge  # type: ignore[import-not-found]  # noqa: F401
from engine.intelligence.llm import LLMEnhancer, get_enhancer  # type: ignore[import-not-found]  # noqa: F401
from engine.intelligence.prompts import (  # type: ignore[import-not-found]  # noqa: F401
    DOMAIN_PRESETS,
    PromptTemplate,
    auto_detect_domain,
    get_template,
)
