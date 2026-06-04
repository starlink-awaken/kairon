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
# Retrospective Automation ≡ Module
# 内涵 ≝ {Retrospective, Automation}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RetrospectiveAutomation)}
# 功能 ⊢ {Retrospective_Automation, Init_Retrospective, Validate_Automation}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class RetroItem:
    item_id: str
    category: str
    description: str
    votes: int = 0
    action_item: str | None = None


@dataclass
class Retrospective:
    retro_id: str
    title: str
    items: list[RetroItem] = field(default_factory=list)
    created_at: float = 0.0
    status: str = "open"


VALID_CATEGORIES: tuple[str, ...] = (
    "what_went_well",
    "what_could_be_improved",
    "action_items",
    "appreciation",
    "start",
    "stop",
    "continue",
)


class RetrospectiveAutomation:
    def __init__(self) -> None:
        self._retros: dict[str, Retrospective] = {}

    def create_retro(self, title: str) -> Retrospective:
        rid = uuid.uuid4().hex[:12]
        retro = Retrospective(retro_id=rid, title=title, created_at=time.time())
        self._retros[rid] = retro
        return retro

    def add_item(self, retro_id: str, category: str, description: str) -> RetroItem:
        retro = self._require(retro_id)
        if category not in VALID_CATEGORIES:  # noqa: F821
            raise ValueError(f"Invalid category '{category}'; must be one of {VALID_CATEGORIES}")  # noqa: F821
        iid = uuid.uuid4().hex[:8]
        item = RetroItem(item_id=iid, category=category, description=description)
        retro.items.append(item)
        return item

    def vote(self, retro_id: str, item_id: str) -> None:
        retro = self._require(retro_id)
        for item in retro.items:
            if item.item_id == item_id:
                item.votes += 1
                return
        raise KeyError(f"Item {item_id} not found in retro {retro_id}")

    def get_top_items(self, retro_id: str, n: int = 5) -> list[RetroItem]:
        retro = self._require(retro_id)
        return sorted(retro.items, key=lambda i: i.votes, reverse=True)[:n]

    def assign_action(self, retro_id: str, item_id: str, action: str) -> None:
        retro = self._require(retro_id)
        for item in retro.items:
            if item.item_id == item_id:
                item.action_item = action
                return
        raise KeyError(f"Item {item_id} not found in retro {retro_id}")

    def close_retro(self, retro_id: str) -> dict:
        retro = self._require(retro_id)
        retro.status = "closed"
        by_cat: dict[str, int] = {}
        for item in retro.items:
            by_cat[item.category] = by_cat.get(item.category, 0) + 1
        actions = [i for i in retro.items if i.action_item]
        return {
            "retro_id": retro_id,
            "title": retro.title,
            "status": "closed",
            "total_items": len(retro.items),
            "items_by_category": by_cat,
            "action_items_count": len(actions),
        }

    def get_retro(self, retro_id: str) -> Retrospective | None:
        return self._retros.get(retro_id)

    def get_action_items(self, retro_id: str) -> list[RetroItem]:
        retro = self._require(retro_id)
        return [i for i in retro.items if i.action_item is not None]

    def list_retros(self, status: str | None = None) -> list[Retrospective]:
        if status is None:
            return list(self._retros.values())
        return [r for r in self._retros.values() if r.status == status]

    def _require(self, retro_id: str) -> Retrospective:
        retro = self._retros.get(retro_id)
        if retro is None:
            raise KeyError(f"Retrospective {retro_id} not found")
        return retro
