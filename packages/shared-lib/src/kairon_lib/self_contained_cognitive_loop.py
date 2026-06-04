from __future__ import annotations

"""
---
Type: Organ
Status: Active
Layer: D-Governance
Owner: '@Sage'
Constraint: '[!!] ZERO_DEPENDENCY'
Summary: SelfContainedCognitiveLoop — 零外部依赖的认知循环，内置所有思维路径
Tags:
- cognitive
- loop
- self-contained
- zero-dependency
---
Extracted from SharedBrain D_Governance → kairon_lib.
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Self Contained Cognitive Loop ≡ Module
# 内涵 ≝ {Self, Contained, Cognitive, Loop}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, SelfContainedCognitiveLoop)}
# 功能 ⊢ {Self_Contained, Contained_Cognitive, Cognitive_Init}
# =============================================================================


import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

_log = logging.getLogger(__name__)


class ThinkingMode(Enum):
    """思维模式"""

    COUNCIL = "council"
    FIRST_PRINCIPLES = "first_principles"
    RED_TEAM = "red_team"
    CREATIVE = "creative"
    SCIENCE = "science"


@dataclass
class ThinkingStep:
    """思维步骤"""

    name: str
    prompt: str
    expected_output: str


@dataclass
class ThinkingPath:
    """思维路径"""

    mode: ThinkingMode
    steps: list[ThinkingStep]
    confidence: float = 0.8


# ---------------------------------------------------------------------------
# Built-in Thinking Paths (Zero External Dependency)
# ---------------------------------------------------------------------------

BUILTIN_PATHS: dict[str, ThinkingPath] = {
    "architecture": ThinkingPath(
        mode=ThinkingMode.COUNCIL,
        steps=[
            ThinkingStep("observe", "观察当前系统状态", "状态描述"),
            ThinkingStep("analyze", "分析架构约束", "约束列表"),
            ThinkingStep("evaluate", "评估方案选项", "选项对比"),
            ThinkingStep("decide", "做出架构决策", "决策结果"),
        ],
        confidence=0.85,
    ),
    "performance": ThinkingPath(
        mode=ThinkingMode.FIRST_PRINCIPLES,
        steps=[
            ThinkingStep("deconstruct", "分解性能问题到根本因素", "因素列表"),
            ThinkingStep("measure", "测量关键指标", "测量数据"),
            ThinkingStep("identify", "识别瓶颈", "瓶颈定位"),
            ThinkingStep("optimize", "优化关键路径", "优化方案"),
        ],
        confidence=0.9,
    ),
    "security": ThinkingPath(
        mode=ThinkingMode.RED_TEAM,
        steps=[
            ThinkingStep("threat_model", "威胁建模", "威胁列表"),
            ThinkingStep("attack", "模拟攻击路径", "攻击向量"),
            ThinkingStep("assess", "评估影响", "风险评估"),
            ThinkingStep("mitigate", "制定缓解措施", "缓解方案"),
        ],
        confidence=0.88,
    ),
    "feature": ThinkingPath(
        mode=ThinkingMode.CREATIVE,
        steps=[
            ThinkingStep("explore", "探索用户需求", "需求列表"),
            ThinkingStep("brainstorm", "头脑风暴方案", "创意方案"),
            ThinkingStep("prototype", "快速原型", "原型描述"),
            ThinkingStep("validate", "验证方案可行性", "验证结果"),
        ],
        confidence=0.75,
    ),
    "incident": ThinkingPath(
        mode=ThinkingMode.SCIENCE,
        steps=[
            ThinkingStep("observe", "观察现象", "现象描述"),
            ThinkingStep("hypothesis", "提出假设", "假设列表"),
            ThinkingStep("experiment", "设计验证实验", "实验方案"),
            ThinkingStep("conclude", "得出结论", "根因分析"),
        ],
        confidence=0.92,
    ),
    "default": ThinkingPath(
        mode=ThinkingMode.COUNCIL,
        steps=[
            ThinkingStep("gather", "收集信息", "信息汇总"),
            ThinkingStep("analyze", "分析问题", "分析结果"),
            ThinkingStep("decide", "做出决策", "决策建议"),
        ],
        confidence=0.8,
    ),
}


@dataclass
class LoopIteration:
    """循环迭代记录"""

    id: str
    phase: str
    inputs: dict
    outputs: dict
    started_at: float
    completed_at: float | None = None


class SelfContainedCognitiveLoop:
    """自包含认知循环 (零外部依赖)

    内置6种思维路径，无需外部导入:
    - architecture: 架构决策 (Council)
    - performance: 性能优化 (First Principles)
    - security: 安全分析 (Red Team)
    - feature: 功能设计 (Creative)
    - incident: 事件响应 (Science)
    - default: 通用决策 (Council)
    """

    def __init__(self) -> None:
        self._history: list[LoopIteration] = []
        self._current_phase = "observe"

        # 验证所有路径可用
        self._validate_paths()

    def _validate_paths(self) -> None:
        """验证内置路径完整性"""
        required_paths = [
            "architecture",
            "performance",
            "security",
            "feature",
            "incident",
            "default",
        ]
        for path_name in required_paths:
            if path_name not in BUILTIN_PATHS:
                raise RuntimeError(f"Missing required thinking path: {path_name}")
        _log.info(f"Validated {len(BUILTIN_PATHS)} built-in thinking paths")

    def run_iteration(self, context: dict[str, Any]) -> LoopIteration:
        """执行一次认知循环"""
        iteration_id = str(uuid.uuid4())
        started_at = time.time()

        # OBSERVE
        self._current_phase = "observe"
        observe_out = self._run_observe(context)

        # THINK
        self._current_phase = "think"
        think_out = self._run_think(observe_out)

        # ACT
        self._current_phase = "act"
        act_out = self._run_act(think_out)

        # LEARN
        self._current_phase = "learn"
        learn_out = self._run_learn(iteration_id, act_out)

        self._current_phase = "observe"

        iteration = LoopIteration(
            id=iteration_id,
            phase="learn",
            inputs=context,
            outputs={
                "observe": observe_out,
                "think": think_out,
                "act": act_out,
                "learn": learn_out,
            },
            started_at=started_at,
            completed_at=time.time(),
        )

        self._history.append(iteration)
        return iteration

    def _run_observe(self, context: dict) -> dict:
        """观察阶段"""
        return {
            "context_keys": list(context.keys()),
            "problem_type": context.get("problem_type", "default"),
            "timestamp": time.time(),
        }

    def _run_think(self, observe_out: dict) -> dict:
        """思考阶段 (使用内置路径)"""
        problem_type = observe_out.get("problem_type", "default")

        # 使用内置路径，永不失败
        path = BUILTIN_PATHS.get(problem_type, BUILTIN_PATHS["default"])

        return {
            "mode": path.mode.value,
            "steps": [s.name for s in path.steps],
            "step_count": len(path.steps),
            "confidence": path.confidence,
            "source": "builtin",
        }

    def _run_act(self, think_out: dict) -> dict:
        """行动阶段"""
        return {
            "action": f"execute_{think_out.get('mode', 'default')}",
            "step_count": think_out.get("step_count", 0),
            "confidence": think_out.get("confidence", 0.8),
        }

    def _run_learn(self, iteration_id: str, act_out: dict) -> dict:
        """学习阶段"""
        # 记录到内部历史，无需外部RetrospectiveEngine
        return {
            "iteration_recorded": True,
            "action": act_out.get("action"),
            "lesson": f"Executed {act_out.get('action')} with confidence {act_out.get('confidence')}",
        }

    def get_path(self, problem_type: str) -> ThinkingPath:
        """获取思维路径"""
        return BUILTIN_PATHS.get(problem_type, BUILTIN_PATHS["default"])

    def get_history(self, limit: int = 10) -> list[LoopIteration]:
        """获取历史记录"""
        return self._history[-limit:]

    def get_statistics(self) -> dict:
        """获取统计"""
        return {
            "iterations_completed": len(self._history),
            "builtin_paths": len(BUILTIN_PATHS),
            "current_phase": self._current_phase,
            "zero_dependency": True,
        }
