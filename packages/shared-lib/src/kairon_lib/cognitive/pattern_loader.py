"""Pattern loader and executor -- migrated from agentmesh toolkit/patterns/PatternLoader.ts."""

from __future__ import annotations

from typing import Any

from .pattern_fabric import (
    ALL_PATTERNS,
    PatternDefinition,
    get_pattern_by_id,
    get_patterns_by_category,
    search_patterns,
)


class PatternLoader:
    """Loads, registers, and manages Fabric patterns."""

    def __init__(
        self,
        patterns_dir: str = "./patterns",
        allow_custom: bool = True,
        timeout: int = 30000,
    ) -> None:
        self._patterns_dir = patterns_dir
        self._allow_custom = allow_custom
        self._timeout = timeout
        self._custom: dict[str, PatternDefinition] = {}

    def load(self, pattern_id: str) -> PatternExecutor:
        pattern = self.get_pattern(pattern_id)
        if pattern is None:
            raise ValueError(f"Pattern not found: {pattern_id}")
        return PatternExecutor(pattern)

    def get_pattern(self, pattern_id: str) -> PatternDefinition | None:
        builtin = get_pattern_by_id(pattern_id)
        if builtin is not None:
            return builtin
        return self._custom.get(pattern_id)

    def get_by_category(self, category: str) -> list[PatternDefinition]:
        return get_patterns_by_category(category)

    def search(self, keyword: str) -> list[PatternDefinition]:
        return search_patterns(keyword)

    def list(self) -> list[PatternDefinition]:
        return list(ALL_PATTERNS)

    def register(self, pattern: PatternDefinition) -> None:
        if not self._allow_custom:
            raise RuntimeError("Custom patterns not allowed")
        if not pattern.id or not pattern.name or not pattern.template:
            raise ValueError("Pattern definition missing required fields")
        self._custom[pattern.id] = pattern

    def get_pattern_tree(self) -> dict[str, list[PatternDefinition]]:  # type: ignore[valid-type]
        return {
            "analyze": self.get_by_category("analyze"),
            "extract": self.get_by_category("extract"),
            "summarize": self.get_by_category("summarize"),
            "transform": self.get_by_category("transform"),
        }


class PatternExecutor:
    """Executes a pattern template with variable substitution."""

    def __init__(self, pattern: PatternDefinition) -> None:
        self._pattern = pattern

    async def execute(
        self,
        variables: dict[str, str],
        llm: Any = None,
    ) -> dict[str, Any]:
        try:
            self._validate_variables(variables)
            prompt = self._generate_prompt(variables)
            if llm is not None:
                output = await llm(prompt)
            else:
                output = prompt
            return {
                "success": True,
                "output": output,
                "metadata": {
                    "patternId": self._pattern.id,
                    "patternName": self._pattern.name,
                    "variables": variables,
                },
            }
        except Exception as exc:
            return {
                "success": False,
                "output": "",
                "metadata": {
                    "patternId": self._pattern.id,
                    "error": str(exc),
                },
            }

    def _validate_variables(self, variables: dict[str, str]) -> None:
        for var in self._pattern.variables:
            if var not in variables:
                raise ValueError(f"Missing required variable: {var}")

    def _generate_prompt(self, variables: dict[str, str]) -> str:
        prompt = self._pattern.template
        for key, value in variables.items():
            prompt = prompt.replace("{{" + key + "}}", value)
        return prompt

    def get_info(self) -> dict[str, Any]:
        return self._pattern.to_dict()
