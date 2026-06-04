"""Eidos CoreService — 最小化膜层基类，替代 nucleus.Z_Microkernel.organs.core_service。

提供 SharedBrain 模块所需的基础方法桩，确保迁移后的 eidos 模块可独立运行。
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


class CoreService:
    """Eidos 膜层基类，提供 SharedBrain CoreService 兼容 API。"""

    def __init__(self, metadata_path: str = "eidos/unknown") -> None:
        self.metadata_path = metadata_path
        self.organ_name = metadata_path.split("/")[-1].replace(".py", "")
        self.organ_id = f"eidos-{id(self):x}"
        self._status = "active"
        self._metabolic_budget = 1000.0

    def initialize(self) -> None:
        self._status = "active"

    def shutdown(self) -> None:
        self._status = "inactive"

    @property
    def status(self) -> str:
        return getattr(self, "_status", "inactive")

    def _deduct_metabolic_tax(self, amount: float = 0.0) -> None:
        """代谢税扣除（桩实现）。"""
        self._metabolic_budget = max(0.0, self._metabolic_budget - amount)

    def _audit_log(self, action: str, target: str, details: dict[str, Any]) -> None:
        """审计日志（桩实现）。"""
        _log.debug("[Eidos:CoreService] audit: action=%s target=%s", action, target)

    def ping(self) -> bool:
        return True

    def validate_access(self, operation: str, context: dict[str, Any]) -> bool:
        return True

    def get_metadata(self) -> dict[str, Any]:
        return {
            "organ": self.organ_name,
            "organ_id": self.organ_id,
            "status": self.status,
            "metadata_path": self.metadata_path,
        }

    def get_registry_info(self) -> dict[str, Any]:
        return {
            "name": self.organ_name,
            "type": "organ",
            "domain": "eidos",
            "status": self.status,
        }

    def validate_internal_state(self) -> bool:
        return True


__all__ = ["CoreService"]
