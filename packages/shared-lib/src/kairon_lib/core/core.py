from __future__ import annotations

"""Core execution engine — AlgorithmEngine, ISCGenerator, CapabilityRouter.

Migrated from agentmesh/packages/toolkit/src/core/.
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AlgorithmPhase(Enum):
    OBSERVE = "OBSERVE"
    THINK = "THINK"
    PLAN = "PLAN"
    BUILD = "BUILD"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    LEARN = "LEARN"


class PhaseStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CapabilityType(Enum):
    ANALYZE = "analyze"
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    TRANSFORM = "transform"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SEARCH = "search"
    TEST = "test"
    SECURITY = "security"
    DEFAULT = "default"


@dataclass
class ISCCriterion:
    id: str = ""
    description: str = ""
    status: PhaseStatus = PhaseStatus.PENDING
    evidence: str | None = None


@dataclass
class AlgorithmContext:
    task: str
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


DEFAULT_PHASES: list[AlgorithmPhase] = list(AlgorithmPhase)
PhaseHandler = Callable[[AlgorithmContext, dict[str, Any]], Any]  # type: ignore[misc, valid-type]


class ISCGenerator:
    """Generate Ideal State Criteria from a task description."""

    def __init__(self, max_criteria: int = 10, include_negative: bool = True) -> None:
        self._max = max_criteria
        self._include_negative = include_negative

    def generate_from_task(self, task: str) -> list[ISCCriterion]:
        lower = task.lower()
        criteria: list[ISCCriterion] = []
        if "登录" in lower or "auth" in lower:
            criteria += [self._make("用户可以成功登录系统"), self._make("登录失败时显示错误提示")]
        if "创建" in lower or "添加" in lower:
            criteria.append(self._make("可以成功创建新记录"))
        if "删除" in lower:
            criteria.append(self._make("可以成功删除数据"))
        if "api" in lower or "接口" in lower:
            criteria.append(self._make("API 返回正确格式"))
        if "性能" in lower or "performance" in lower:
            criteria.append(self._make("响应时间在可接受范围内"))
        if "安全" in lower or "security" in lower:
            criteria.append(self._make("未授权访问被拒绝"))
        if "代码" in lower or "实现" in lower:
            criteria.append(self._make("代码符合规范"))
        if self._include_negative:
            import re
            for match in re.findall(r"不(.+?)[的。]|不要(.+)", task):
                text = next((m for m in match if m), "")
                if text:
                    criteria.append(self._make(f"确保不: {text}"))
        seen: set[str] = set()
        return [c for c in criteria if not (c.description in seen or seen.add(c.description))][:self._max]  # type: ignore[func-returns-value]

    @staticmethod
    def _make(desc: str) -> ISCCriterion:
        return ISCCriterion(id=f"isc-{uuid.uuid4().hex[:8]}", description=desc)

    @classmethod
    def generate(cls, task: str, max_criteria: int = 10) -> list[ISCCriterion]:
        return cls(max_criteria).generate_from_task(task)


class AlgorithmEngine:
    """7-phase execution engine (OBSERVE -> LEARN)."""

    def __init__(self, auto_generate_isc: bool = True, debug: bool = False) -> None:
        self._auto_isc = auto_generate_isc
        self._debug = debug
        self._handlers: dict[AlgorithmPhase, PhaseHandler] = {}  # type: ignore[valid-type]

    def log(self, msg: str, *args: Any) -> None:
        if self._debug:
            print(f"[AlgorithmEngine] {msg}", *args)

    def register(self, phase: AlgorithmPhase, handler: PhaseHandler) -> None:  # type: ignore[valid-type]
        self._handlers[phase] = handler

    async def execute(self, context: AlgorithmContext) -> dict[str, Any]:
        result: dict[str, Any] = {
            "success": False,
            "phases": {p: {"status": PhaseStatus.PENDING.value} for p in DEFAULT_PHASES},
            "criteria": [], "errors": [],
        }
        if self._auto_isc:
            result["criteria"] = ISCGenerator.generate(context.task)
        try:
            for phase in DEFAULT_PHASES:
                start = time.time()
                result["phases"][phase] = {"status": PhaseStatus.RUNNING.value}
                handler = self._handlers.get(phase)
                output = await handler(context, result) if handler else None
                result["phases"][phase] = {"status": PhaseStatus.COMPLETED.value, "output": output, "duration": time.time() - start}
                self.log(f"  {phase.value} done ({result['phases'][phase]['duration']:.2f}s)")
            result["success"] = True
        except Exception as exc:
            result["errors"].append(str(exc))
            self.log(f"  FAILED: {exc}")
        return result


CAPABILITY_PATTERNS: dict[CapabilityType, list[str]] = {
    CapabilityType.ANALYZE: ["分析", "analyze", "评估", "review", "diagnose"],
    CapabilityType.EXTRACT: ["提取", "extract", "获取", "fetch", "parse"],
    CapabilityType.SUMMARIZE: ["总结", "summarize", "概括", "摘要", "归纳"],
    CapabilityType.TRANSFORM: ["转换", "convert", "翻译", "格式化"],
    CapabilityType.CREATE: ["创建", "create", "生成", "build", "设计"],
    CapabilityType.UPDATE: ["更新", "update", "修改", "modify", "优化"],
    CapabilityType.DELETE: ["删除", "delete", "移除", "remove", "清除"],
    CapabilityType.SEARCH: ["搜索", "search", "查找", "find", "查询"],
    CapabilityType.TEST: ["测试", "test", "verify", "验证", "确认"],
    CapabilityType.SECURITY: ["安全", "security", "漏洞", "audit"],
    CapabilityType.DEFAULT: ["处理", "process", "执行", "run"],
}


class CapabilityRouter:
    """Route tasks to appropriate capabilities by pattern matching."""

    def __init__(self, min_confidence: float = 0.1) -> None:
        self._min_confidence = min_confidence

    def route(self, task: str) -> tuple[CapabilityType, float]:
        lower = task.lower()
        best_type, best_score = CapabilityType.DEFAULT, 0.0
        for ctype, patterns in CAPABILITY_PATTERNS.items():
            score = sum(1 for p in patterns if p.lower() in lower) / max(len(patterns), 1)
            if score > best_score:
                best_type, best_score = ctype, score
        if best_score < self._min_confidence:
            best_type = CapabilityType.DEFAULT
        return best_type, best_score
