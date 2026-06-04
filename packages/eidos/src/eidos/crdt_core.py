from __future__ import annotations

"""
---
Type: Core
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Layer: L3
Summary: CRDT (Conflict-free Replicated Data Type) implementation for FactGraph synchronization.
Extracted from: SharedBrain D_Memory/organs/core/crdt.py → eidos/crdt_core.py
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Crdt ≡ Module
# 内涵 ≝ {Crdt}
# 外延 ≝ {e | e ∈ Eidos ∧ implements(e, Crdt)}
# 功能 ⊢ {Init_Crdt, Execute_Crdt, Validate_Crdt}
# =============================================================================


import time


class LWWElementSet:
    """Last-Write-Wins Element Set (CRDT).
    支持事实三元组的跨节点一致性合并。
    """

    def __init__(self) -> None:
        # 存储格式: { (sub, pred, obj): (timestamp, is_removed) }
        self.add_set: dict[tuple[str, str, str], float] = {}
        self.remove_set: dict[tuple[str, str, str], float] = {}

    def add(self, sub: str, pred: str, obj: str, timestamp: float | None = None) -> None:
        ts = timestamp or time.time()
        key = (sub, pred, obj)
        if key not in self.add_set or ts > self.add_set[key]:
            self.add_set[key] = ts

    def remove(self, sub: str, pred: str, obj: str, timestamp: float | None = None) -> None:
        ts = timestamp or time.time()
        key = (sub, pred, obj)
        if key not in self.remove_set or ts > self.remove_set[key]:
            self.remove_set[key] = ts

    def lookup(self, sub: str, pred: str, obj: str) -> bool:
        key = (sub, pred, obj)
        if key not in self.add_set:
            return False
        if key not in self.remove_set:
            return True
        return self.add_set[key] > self.remove_set[key]

    def merge(self, other: LWWElementSet) -> None:
        """合并另一个 LWW 集。"""
        for key, ts in other.add_set.items():
            if key not in self.add_set or ts > self.add_set[key]:
                self.add_set[key] = ts
        for key, ts in other.remove_set.items():
            if key not in self.remove_set or ts > self.remove_set[key]:
                self.remove_set[key] = ts

    def get_active_triples(self) -> set[tuple[str, str, str]]:
        """获取当前有效的全部三元组。"""
        active = set()
        for key in self.add_set:
            if key not in self.remove_set or self.add_set[key] > self.remove_set[key]:
                active.add(key)
        return active
