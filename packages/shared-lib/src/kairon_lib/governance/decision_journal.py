from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Decision Journal ≡ Module
# 内涵 ≝ {Decision, Journal}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, DecisionJournal)}
# 功能 ⊢ {Decision_Journal, Init_Decision, Validate_Journal}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionEntry:
    decision_id: str
    title: str
    context: str
    decision: str
    rationale: str
    alternatives: list[str]
    author: str
    timestamp: float
    tags: list[str] = field(default_factory=list)
    outcome: str | None = None


class DecisionJournal:
    metadata_path = "organs/D-Governance/organs/decision_journal.py"

    def __init__(self) -> None:
        super().__init__()
        self._entries: dict[str, DecisionEntry] = {}

    def record_decision(
        self,
        title: str,
        context: str,
        decision: str,
        rationale: str,
        alternatives: list[str],
        author: str,
        tags: list[str] | None = None,
    ) -> DecisionEntry:
        decision_id = f"DEC-{uuid.uuid4().hex[:8]}"
        entry = DecisionEntry(
            decision_id=decision_id,
            title=title,
            context=context,
            decision=decision,
            rationale=rationale,
            alternatives=list(alternatives),
            author=author,
            timestamp=time.time(),
            tags=list(tags) if tags else [],
        )
        self._entries[decision_id] = entry
        return entry

    def get_decision(self, decision_id: str) -> DecisionEntry | None:
        return self._entries.get(decision_id)

    def search(self, query: str) -> list[DecisionEntry]:
        q = query.lower()
        results: list[DecisionEntry] = []
        for entry in self._entries.values():
            if (
                q in entry.title.lower()
                or q in entry.context.lower()
                or q in entry.decision.lower()
                or any(q in tag.lower() for tag in entry.tags)
            ):
                results.append(entry)
        return results

    def record_outcome(self, decision_id: str, outcome: str) -> None:
        entry = self._entries.get(decision_id)
        if entry is None:
            raise KeyError(f"Decision not found: {decision_id}")
        entry.outcome = outcome

    def list_decisions(self, tag: str | None = None) -> list[DecisionEntry]:
        if tag is None:
            return list(self._entries.values())
        return [e for e in self._entries.values() if tag in e.tags]

    def get_timeline(self) -> list[DecisionEntry]:
        return sorted(self._entries.values(), key=lambda e: e.timestamp)

    def export_journal(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for entry in self.get_timeline():
            result.append(
                {
                    "decision_id": entry.decision_id,
                    "title": entry.title,
                    "context": entry.context,
                    "decision": entry.decision,
                    "rationale": entry.rationale,
                    "alternatives": entry.alternatives,
                    "author": entry.author,
                    "timestamp": entry.timestamp,
                    "tags": entry.tags,
                    "outcome": entry.outcome,
                }
            )
        return result
