from __future__ import annotations

"""
---
Type: DataModel
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Summary: Role memory data model — MemoryType, MemoryItem, and RoleMemoryContext.
Extracted from: SharedBrain D_Memory/organs/role_memory_model.py → eidos/role_memory_model.py
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Memory_Model ≡ Memory_System
# 内涵 ≝ {Store, Retrieve, Index, Compact}
# 外延 ≝ {m | m ∈ Eidos ∧ persists(m, Knowledge)}
# 功能 ⊢ {StoreMemories, RetrieveMemories, MaintainIndex}
# =============================================================================

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

_log = logging.getLogger(__name__)


class MemoryType(Enum):
    """Memory Types based on cognitive science"""

    WORKING = "working"  # Short-term, active context
    EPISODIC = "episodic"  # Events, history, logs
    SEMANTIC = "semantic"  # Facts, knowledge, world model
    PROCEDURAL = "procedural"  # Skills, how-to, functions


@dataclass
class MemoryItem:
    """Base class for a memory item"""

    memory_id: str
    role_id: str
    type: MemoryType
    content: Any
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "role_id": self.role_id,
            "type": self.type.value,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryItem:
        return cls(
            memory_id=data["memory_id"],
            role_id=data["role_id"],
            type=MemoryType(data["type"]),
            content=data["content"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RoleMemoryContext:
    """
    Runtime memory context for a role.
    Holds loaded memories.
    """

    role_id: str
    working_memory: list[MemoryItem] = field(default_factory=list)
    recent_episodic: list[MemoryItem] = field(default_factory=list)
    relevant_semantic: list[MemoryItem] = field(default_factory=list)
    active_procedural: list[MemoryItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "working_memory": [m.to_dict() for m in self.working_memory],
            "recent_episodic": [m.to_dict() for m in self.recent_episodic],
            "relevant_semantic": [m.to_dict() for m in self.relevant_semantic],
            "active_procedural": [m.to_dict() for m in self.active_procedural],
        }
