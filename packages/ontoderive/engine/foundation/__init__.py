"""基础设施层 — 类型系统/数据模型/常量/工具/配置/契约"""

from engine.foundation.config import Config  # type: ignore[import-not-found]  # noqa: F401
from engine.foundation.constants import (  # type: ignore[import-not-found]  # noqa: F401
    CONFIDENCE_MAP,
    RE_ENTITY_ID,
    RE_FACT_ID,
    V2_ID_PATTERNS,
)
from engine.foundation.models import (  # type: ignore[import-not-found]  # noqa: F401
    CheckResult,
    DeriveSnapshot,
    Entity,
    Fact,
    Inference,
    Scheme,
)
from engine.foundation.ontology_map import (  # type: ignore[import-not-found]  # noqa: F401
    TYPE_MAPPINGS,
    OntologyMapper,
    RDFTriple,
)
from engine.foundation.protocols import (  # type: ignore[import-not-found]  # noqa: F401
    AnalysisResult,
    DeriveInterface,
    PipelineObservable,
    ToolForgeInterface,
)
from engine.foundation.rule_loader import RuleLoader  # type: ignore[import-not-found]  # noqa: F401
from engine.foundation.semantic import SemanticMatcher  # type: ignore[import-not-found]  # noqa: F401
from engine.foundation.typesystem import (  # type: ignore[import-not-found]  # noqa: F401
    META_TYPES,
    PREFIX_TO_META,
    TypeValidator,
)
from engine.foundation.utils import (  # type: ignore[import-not-found]  # noqa: F401
    CachedReader,
    all_md,
    detect_cycles,
    load_json,
    rf,
    save_json,
    wf,
)
