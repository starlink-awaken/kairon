"""Hybrid rule engine for rule + generative patterns.

Port of agentmesh/packages/toolkit/src/hybrid/ to Python.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleCondition:
    type_: str = "exact"  # exact | pattern | semantic | composite
    expression: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleAction:
    type_: str = "use_rule"  # use_rule | use_llm | use_hybrid | fallback
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridRule:
    id: str = ""
    name: str = ""
    condition: RuleCondition = field(default_factory=RuleCondition)
    action: RuleAction = field(default_factory=RuleAction)
    priority: int = 0
    enabled: bool = True


@dataclass
class ResolutionContext:
    input_: Any = ""
    session_id: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ResolutionResult:
    strategy: str = "rule"
    confidence: float = 1.0
    output: Any = None
    used_rules: list[str] = field(default_factory=list)


class RuleEngine:
    """Business rule engine supporting exact, pattern, semantic, and composite matching."""

    def __init__(self) -> None:
        self._rules: dict[str, HybridRule] = {}

    def add_rule(self, rule: HybridRule) -> None:
        self._rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def set_enabled(self, rule_id: str, enabled: bool) -> None:
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = enabled

    def evaluate(self, rule: HybridRule, context: ResolutionContext) -> bool:
        if not rule.enabled:
            return False
        input_str = self._stringify(context.input_)
        cond = rule.condition
        if cond.type_ == "exact":
            return input_str == cond.expression
        if cond.type_ == "pattern":
            try:
                return bool(re.search(cond.expression, input_str))
            except re.error:
                return False
        if cond.type_ == "semantic":
            keywords = [k.strip() for k in cond.expression.split(",") if k.strip()]
            lower_input = input_str.lower()
            return any(kw.lower() in lower_input for kw in keywords)
        if cond.type_ == "composite":
            return self._eval_composite(cond, context)
        return False

    def _eval_composite(self, condition: RuleCondition, context: ResolutionContext) -> bool:
        sub_rules = condition.parameters.get("rules", [])
        if not sub_rules:
            return False
        result = True
        for sr in sub_rules:
            sub_cond = RuleCondition(**sr.get("condition", {}))
            sub_result = self.evaluate(HybridRule(id="_sub", name="_sub", condition=sub_cond, priority=0, enabled=True), context)
            operator = sr.get("operator", "and")
            if operator == "and":
                result = result and sub_result
            else:
                result = result or sub_result
        return result

    def find_matching_rules(self, context: ResolutionContext) -> list[HybridRule]:
        matches = []
        for rule in self._rules.values():
            if self.evaluate(rule, context):
                matches.append(rule)
        matches.sort(key=lambda r: r.priority, reverse=True)
        return matches

    def get_all_rules(self) -> list[HybridRule]:
        return list(self._rules.values())

    @staticmethod
    def _stringify(input_: Any) -> str:
        if isinstance(input_, str):
            return input_
        if isinstance(input_, (dict, list)):
            return json.dumps(input_)
        return str(input_)


__all__ = [
    "RuleEngine", "HybridRule", "RuleCondition", "RuleAction",
    "ResolutionContext", "ResolutionResult",
]
