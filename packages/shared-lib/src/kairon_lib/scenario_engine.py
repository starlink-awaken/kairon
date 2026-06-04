from __future__ import annotations

from typing import Any


class _PrinciplesStub:
    """Stub implementation; replace with real Principles import."""

    def get_guidance(self, query: str) -> dict[str, Any]:
        return {"scenario": None, "principles": [], "questions": []}

    def search(self, query: str) -> list[Any]:
        return []

    def get_all_scenarios(self) -> list[Any]:
        return []

    def match_scenario(self, query: str) -> Any:
        return None

    def get_by_id(self, id_: int) -> Any:
        return None

    def get_all(self) -> list[Any]:
        return []

    def get_by_level(self, level: str) -> list[Any]:
        return []


try:
    from .principles import Principles  # type: ignore[import-not-found]
except ImportError:
    Principles = _PrinciplesStub


class ScenarioEngine:
    """Matches user input to scenarios and recommends principles."""

    def __init__(self) -> None:
        self._principles = Principles()

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data.get("query", "")
        include_questions = input_data.get("includeQuestions", True)
        guidance = self._principles.get_guidance(query)
        scenario = guidance.get("scenario")

        return {
            "matched": scenario is not None,
            "scenario": (
                {
                    "id": scenario.get("id", ""),
                    "name": scenario.get("name", ""),
                    "description": scenario.get("description", ""),
                }
                if scenario
                else None
            ),
            "principles": [
                {
                    "id": p.get("id", 0),
                    "name": p.get("name", ""),
                    "level": p.get("level", ""),
                    "rule": p.get("rule", ""),
                    "description": p.get("description", ""),
                }
                for p in guidance.get("principles", [])
            ],
            "questions": guidance.get("questions", []) if include_questions else [],
        }

    def search(self, query: str) -> list[Any]:
        return self._principles.search(query)

    def get_all_scenarios(self) -> list[Any]:
        return self._principles.get_all_scenarios()

    def match_scenario(self, query: str) -> Any:
        return self._principles.match_scenario(query)

    def get_principle(self, id_: int) -> Any:
        return self._principles.get_by_id(id_)

    def get_all_principles(self) -> list[Any]:
        return self._principles.get_all()

    def get_principles_by_level(self, level: str) -> list[Any]:
        return self._principles.get_by_level(level)


def create_scenario_engine() -> ScenarioEngine:
    return ScenarioEngine()
