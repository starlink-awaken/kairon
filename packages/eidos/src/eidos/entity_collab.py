#!/usr/bin/env python3
# ruff: noqa
"""G1: 多用户实体协作 — 基于 eidos CRDT 的 entity-level 无冲突合并.

场景覆盖审计 G1 缺口实现 (多用户同时编辑知识, 实时同步, 冲突解决).
现状: eidos crdt (VectorClock/LWWRegister/ORSet) 是会话级 CRDT, 非实体级多用户协作.
本模块: 实体级 CRDT 包装 (CollaborativeEntity), label 用 LWWRegister (last-writer-wins),
        aliases/relations 用 ORSet (add/remove 合并), 支持多用户并发编辑 + 无冲突合并.
"""

from __future__ import annotations

from typing import Any

from eidos.crdt import LWWRegister, ORSet, VectorClock


class CollaborativeEntity:
    """支持多用户并发编辑的实体 (CRDT 无冲突合并).

    label: LWWRegister (last-writer-wins, 按 timestamp 决胜负).
    aliases/relations: ORSet (add/remove 可合并).
    """

    def __init__(self, entity_id: str, user_id: str = "default") -> None:
        self.entity_id = entity_id
        self.user_id = user_id
        self.clock = VectorClock(self.user_id)
        self._label = LWWRegister()
        self._aliases = ORSet()
        self._relations = ORSet()  # relation tags (predicate::target)

    def edit_label(self, label: str, timestamp: float | None = None) -> None:
        """用户编辑 label (LWW 合并)."""
        self.clock.increment()  # type: ignore[no-untyped-call]
        self._label.set(label, timestamp)

    def get_label(self) -> Any:
        return self._label.get()

    def add_alias(self, alias: str) -> None:
        self.clock.increment()  # type: ignore[no-untyped-call]
        self._aliases.add(alias, tag=f"{self.user_id}")

    def remove_alias(self, alias: str) -> None:
        self._aliases.remove(alias)

    def add_relation(self, relation: str) -> None:
        self.clock.increment()  # type: ignore[no-untyped-call]
        self._relations.add(relation, tag=f"{self.user_id}")

    def remove_relation(self, relation: str) -> None:
        self._relations.remove(relation)

    def merge(self, other: CollaborativeEntity) -> None:
        """合并另一用户的实体编辑 (CRDT 无冲突合并).

        LWW label: 取 timestamp 新的; ORSet aliases/relations: union.
        """
        self.clock.merge(other.clock)
        # LWWRegister merge: 取 timestamp 新的
        if other._label.get() is not None:
            other_ts = getattr(other._label, "timestamp", 0) or 0
            self_ts = getattr(self._label, "timestamp", 0) or 0
            if other_ts >= self_ts:
                self._label = other._label
        # ORSet merge: union (add 其他用户的)
        for item in other._aliases.items():
            self._aliases.add(item)
        for item in other._relations.items():
            self._relations.add(item)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "user_id": self.user_id,
            "clock": self.clock.to_dict(),
            "label": self.get_label(),
            "aliases": sorted(self._aliases.items()),
            "relations": sorted(self._relations.items()),
        }


def demo_multi_user_merge() -> dict[str, Any]:
    """演示: 用户 A/B 并发编辑同一实体, CRDT 合并无冲突."""
    # 用户 A 编辑 (基于基线)
    ent_a = CollaborativeEntity("P:xia", user_id="alice")
    ent_a.edit_label("夏同学", timestamp=1000)
    ent_a.add_alias("老夏")
    ent_a.add_relation("works_at::O:卫健委")

    # 用户 B 编辑 (基于同基线, 并发)
    ent_b = CollaborativeEntity("P:xia", user_id="bob")
    ent_b.edit_label("夏明兴", timestamp=2000)  # 更晚 timestamp, LWW 胜
    ent_b.add_alias("夏老师")
    ent_b.add_relation("seconded_to::O:国转中心")

    # 合并 (无冲突, CRDT)
    ent_a.merge(ent_b)
    return ent_a.to_dict()


def main() -> None:
    """CLI: eidos entity-collab — 演示多用户 CRDT 合并."""
    import json

    result = demo_multi_user_merge()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
