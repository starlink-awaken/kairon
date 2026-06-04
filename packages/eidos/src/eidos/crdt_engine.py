from __future__ import annotations

"""
---
Type: Core
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Layer: L3
Summary: Advanced CRDT (Observed-Remove Set) for FactGraph synchronization.
Extracted from: SharedBrain D_Memory/organs/core/crdt_engine.py → eidos/crdt_engine.py
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Crdt Engine ≡ Engine
# 内涵 ≝ {Crdt, Engine}
# 外延 ≝ {e | e ∈ Eidos ∧ implements(e, CrdtEngine)}
# 功能 ⊢ {Crdt_Engine, Init_Crdt, Validate_Engine}
# =============================================================================


import uuid
from typing import Any


class ORSet:
    """Observed-Remove Set (CRDT).
    支持分布式环境下的最终一致性集合操作。
    """

    def __init__(self) -> None:
        # 存储格式: { element: set(tags) }
        self.add_set: dict[Any, set[str]] = {}
        self.remove_set: dict[Any, set[str]] = {}

    def add(self, sub: str, pred: str, obj: str, tag: str | None = None) -> None:
        """添加一个三元组。"""
        element = (sub, pred, obj)
        t = tag or str(uuid.uuid4())
        if element not in self.add_set:
            self.add_set[element] = set()
        self.add_set[element].add(t)

    def remove(self, sub: str, pred: str, obj: str) -> None:
        """移除一个三元组（移除当前观察到的所有标签）。"""
        element = (sub, pred, obj)
        if element in self.add_set:
            if element not in self.remove_set:
                self.remove_set[element] = set()
            # 将当前 add_set 中的所有标签加入 remove_set
            self.remove_set[element].update(self.add_set[element])

    def lookup(self, sub: str, pred: str, obj: str) -> bool:
        """检查三元组是否存在。"""
        element = (sub, pred, obj)
        if element not in self.add_set:
            return False

        # 只要 add_set 中存在不在 remove_set 中的标签，即为存在
        if element not in self.remove_set:
            return True

        remaining_tags = self.add_set[element] - self.remove_set[element]
        return len(remaining_tags) > 0

    def merge(self, other: ORSet) -> None:
        """合并另一个 OR-Set。"""
        # 合并 add_sets
        for element, tags in other.add_set.items():
            if element not in self.add_set:
                self.add_set[element] = set()
            self.add_set[element].update(tags)

        # 合并 remove_sets
        for element, tags in other.remove_set.items():
            if element not in self.remove_set:
                self.remove_set[element] = set()
            self.remove_set[element].update(tags)

    def get_active_triples(self) -> set[tuple[str, str, str]]:
        """获取当前有效的全部三元组。"""
        active = set()
        for element in self.add_set:
            if self.lookup(*element):
                active.add(element)
        return active
