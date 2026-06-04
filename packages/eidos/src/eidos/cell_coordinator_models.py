from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
# Models ≡ Module
# 内涵 ≝ {Models}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Models)}
# 功能 ⊢ {Init_Models, Execute_Models, Validate_Models}
# =============================================================================

# ---
# domain: D-Memory
# layer: organ
# status: active
# ---

import os
import time
import uuid
from enum import StrEnum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CacheLevel(StrEnum):
    """缓存层级"""

    L1_QUERY = "L1"  # 高频查询缓存 (内存, TTL=5分钟)
    L2_LESSON = "L2"  # 教训缓存 (BOS-URI, TTL=24小时)
    L3_FACT = "L3"  # 事实图谱 (持久化)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class CognitiveCell:
    """
    K-P-B认知细胞三元组

    遵循R1-ACT-COG-01-01架构定义:
    - Knowledge: 知识向量 (语义)
    - Pattern: 模式矩阵 (结构)
    - Behavior: 行为张量 (动作序列)

    CRDT支持: 实现向量时钟和合并操作用于分布式同步
    """

    knowledge: dict[str, Any]  # 语义知识
    pattern: list[list[float]]  # 模式矩阵
    behavior: list[dict[str, Any]]  # 行为序列
    cell_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: float = field(default_factory=time.time)
    access_count: int = 0

    # CRDT fields (ISC-1)
    vector_clock: dict[str, int] = field(default_factory=dict)
    node_id: str = field(default_factory=lambda: f"node_{os.getpid()}")

    def increment_clock(self) -> CognitiveCell:
        """递增本节点的向量时钟 (ISC-2)"""
        self.vector_clock[self.node_id] = self.vector_clock.get(self.node_id, 0) + 1
        return self

    @staticmethod
    def _merge_dict_cells(base: dict, update: dict) -> dict:
        """合并字典，相同key时保留value较大的（基于access_count的语义）"""
        result = base.copy()
        for key, value in update.items():
            if key not in result:
                result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                result[key] = CognitiveCell._merge_dict_cells(result[key], value)
            elif isinstance(value, (int, float)) and isinstance(result[key], (int, float)):
                # 取较大值（last-write-wins语义）
                result[key] = max(result[key], value)
            else:
                # 其他类型用后者覆盖
                result[key] = value
        return result

    @classmethod
    def merge(cls, cell_a: CognitiveCell, cell_b: CognitiveCell) -> CognitiveCell:
        """
        合并两个认知细胞 (ISC-3)

        策略:
        - 向量时钟：逐元素取max (ISC-4)
        - timestamp：较新者胜 (ISC-5)
        - access_count：较高者优先（语义感知）(ISC-6)
        - knowledge：字典合并 (ISC-7)
        - pattern：取较大值 (ISC-8)
        - behavior：去重合并 (ISC-9)
        """
        # 合并向量时钟（取max）
        merged_clock = {}
        all_keys = set(cell_a.vector_clock.keys()) | set(cell_b.vector_clock.keys())
        for key in all_keys:
            merged_clock[key] = max(cell_a.vector_clock.get(key, 0), cell_b.vector_clock.get(key, 0))

        # 判断哪个cell较新（last-write-wins + semantic awareness）
        # 先比较timestamp，相同时比较access_count
        a_is_newer = cell_a.created_at > cell_b.created_at or (
            cell_a.created_at == cell_b.created_at and cell_a.access_count > cell_b.access_count
        )

        # 选择基础细胞
        base = cell_a if a_is_newer else cell_b
        other = cell_b if a_is_newer else cell_a

        # 合并knowledge字典
        merged_knowledge = cls._merge_dict_cells(base.knowledge, other.knowledge)

        # 合并pattern矩阵（取元素级最大值）
        merged_pattern = []
        max_len = max(len(cell_a.pattern), len(cell_b.pattern))
        for i in range(max_len):
            if i >= len(cell_a.pattern):
                merged_pattern.append(cell_b.pattern[i])
            elif i >= len(cell_b.pattern):
                merged_pattern.append(cell_a.pattern[i])
            else:
                # 逐元素取最大值
                row_a = cell_a.pattern[i]
                row_b = cell_b.pattern[i]
                max_row_len = max(len(row_a), len(row_b))
                merged_row = []
                for j in range(max_row_len):
                    if j >= len(row_a):
                        merged_row.append(row_b[j])
                    elif j >= len(row_b):
                        merged_row.append(row_a[j])
                    else:
                        merged_row.append(max(row_a[j], row_b[j]))
                merged_pattern.append(merged_row)

        # 合并behavior列表（去重）
        seen_ids = set()
        merged_behavior: list[Any] = []

        # Helper to extract behavior ID
        def get_behavior_id(b: object) -> str:
            if isinstance(b, dict) and "id" in b:
                return f"id:{b['id']}"
            return str(hash(str(b)))

        for b in base.behavior + other.behavior:
            b_id = get_behavior_id(b)
            if b_id not in seen_ids:
                # 如果两个行为都有相同ID，保留较新的
                if b_id in seen_ids:
                    # 替换已有的
                    for i, existing in enumerate(merged_behavior):
                        if get_behavior_id(existing) == b_id:
                            merged_behavior[i] = b
                            break
                else:
                    merged_behavior.append(b)
                    seen_ids.add(b_id)

        # 创建合并后的细胞
        merged_cell = cls(
            knowledge=merged_knowledge,
            pattern=merged_pattern,
            behavior=merged_behavior,
            cell_id=base.cell_id,  # 保留较新细胞的ID
            created_at=base.created_at,
            access_count=max(cell_a.access_count, cell_b.access_count),
            vector_clock=merged_clock,
            node_id=base.node_id,
        )

        return merged_cell

    def merge_conflicts(self) -> dict[str, int]:
        """
        统计上次合并的冲突信息 (ISC-10)

        Returns:
            包含冲突统计的字典
        """
        # 计算向量时钟中的分歧
        clock_versions = list(self.vector_clock.values())
        if not clock_versions:
            return {"conflicts": 0, "divergent_nodes": 0}

        max_version = max(clock_versions)
        min_version = min(clock_versions)
        divergent_nodes = sum(1 for v in clock_versions if v < max_version)

        return {
            "conflicts": divergent_nodes,
            "divergent_nodes": divergent_nodes,
            "max_version": max_version,
            "min_version": min_version,
            "total_nodes": len(clock_versions),
        }

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "cell_id": self.cell_id,
            "knowledge": self.knowledge,
            "pattern": self.pattern,
            "behavior": self.behavior,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "vector_clock": self.vector_clock,
            "node_id": self.node_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CognitiveCell:
        """从字典反序列化"""
        return cls(
            knowledge=data.get("knowledge", {}),
            pattern=data.get("pattern", []),
            behavior=data.get("behavior", []),
            cell_id=data.get("cell_id", str(uuid.uuid4())[:8]),
            created_at=data.get("created_at", time.time()),
            access_count=data.get("access_count", 0),
            vector_clock=data.get("vector_clock", {}),
            node_id=data.get("node_id", f"node_{os.getpid()}"),
        )


@dataclass
class QueryResult:
    """查询结果"""

    found: bool
    data: Any | None
    level: CacheLevel | None
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheVersion:
    """缓存版本向量 - 用于L1/L2/L3一致性"""

    l1_version: int = 0  # L1缓存版本
    l2_version: int = 0  # L2缓存版本
    l3_version: int = 0  # L3缓存版本
    last_modified: float = field(default_factory=time.time)
    invalidated: bool = False

    def increment(self, level: CacheLevel) -> CacheVersion:
        """递增指定层级版本"""
        if level == CacheLevel.L1_QUERY:
            self.l1_version += 1
        elif level == CacheLevel.L2_LESSON:
            self.l2_version += 1
        elif level == CacheLevel.L3_FACT:
            self.l3_version += 1
        self.last_modified = time.time()
        return self

    def is_stale(self, other: CacheVersion) -> bool:
        """检查是否过期（版本低于其他层）"""
        return (
            self.l1_version < other.l1_version
            or self.l2_version < other.l2_version
            or self.l3_version < other.l3_version
        )

    # ISC-1: 一致性检查方法
    def is_consistent_with(self, other: CacheVersion) -> bool:
        """
        检查与另一个版本向量是否一致

        两个版本向量一致当且仅当所有层级版本号相同
        """
        return (
            self.l1_version == other.l1_version
            and self.l2_version == other.l2_version
            and self.l3_version == other.l3_version
        )

    # ISC-2: 合并版本向量
    def merge(self, other: CacheVersion) -> CacheVersion:
        """
        合并另一个版本向量（取最大值）

        用于解决冲突时合并版本信息
        """
        return CacheVersion(
            l1_version=max(self.l1_version, other.l1_version),
            l2_version=max(self.l2_version, other.l2_version),
            l3_version=max(self.l3_version, other.l3_version),
            last_modified=max(self.last_modified, other.last_modified),
            invalidated=self.invalidated or other.invalidated,
        )

    # ISC-3: 序列化方法
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "l1_version": self.l1_version,
            "l2_version": self.l2_version,
            "l3_version": self.l3_version,
            "last_modified": self.last_modified,
            "invalidated": self.invalidated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheVersion:
        """从字典反序列化"""
        return cls(
            l1_version=data.get("l1_version", 0),
            l2_version=data.get("l2_version", 0),
            l3_version=data.get("l3_version", 0),
            last_modified=data.get("last_modified", time.time()),
            invalidated=data.get("invalidated", False),
        )


@dataclass
class Lesson:
    """教训条目 - L2缓存单元"""

    lesson_id: str
    query: str
    failure_pattern: dict[str, Any]
    solution: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    effectiveness_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "lesson_id": self.lesson_id,
            "query": self.query,
            "failure_pattern": self.failure_pattern,
            "solution": self.solution,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "effectiveness_score": self.effectiveness_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Lesson:
        return cls(
            lesson_id=data.get("lesson_id", str(uuid.uuid4())),
            query=data["query"],
            failure_pattern=data["failure_pattern"],
            solution=data["solution"],
            created_at=data.get("created_at", time.time()),
            access_count=data.get("access_count", 0),
            effectiveness_score=data.get("effectiveness_score", 1.0),
        )
