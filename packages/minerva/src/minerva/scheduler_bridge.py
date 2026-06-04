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
# Bridge ≡ Module
# 内涵 ≝ {Bridge}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Bridge)}
# 功能 ⊢ {Init_Bridge, Execute_Bridge, Validate_Bridge}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
HarvestScheduler集成桥接层

提供D_Harvest.HarvestTaskScheduler与现有HarvestScheduler系统的集成：
- D_Governance.organs.harvest_scheduler.HarvestScheduler
- D_Memory.organs.harvest_scheduler.MemoryHarvestScheduler

这个模块实现了统一的调度接口，支持：
1. 与现有调度器协同工作
2. 将D_Harvest的任务调度信息同步到Governance域
3. 支持跨域的知识freshness管理
"""
import logging
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from minerva.orchestrator import HarvestOrchestrator, HarvestResult

_log = logging.getLogger(__name__)
_HARVEST_BRIDGE_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    sqlite3.Error,
    TypeError,
    ValueError,
)


class HarvestSchedulerBridge:
    """
    HarvestScheduler集成桥接器

    连接D_Harvest的任务调度与现有的知识管理系统：
    - 将外部数据源的harvest任务与Governance域的ADRs/Retrospectives集成
    - 支持统一的freshness评分和知识检索
    - 提供跨域的知识同步接口
    """

    def __init__(
        self,
        d_harvest_orchestrator: HarvestOrchestrator,
        enable_governance_sync: bool = True,
        enable_memory_sync: bool = True,
    ) -> None:
        """
        初始化桥接器

        Args:
            d_harvest_orchestrator: D_Harvest域的编排器实例
            enable_governance_sync: 是否与Governance域同步
            enable_memory_sync: 是否与Memory域同步
        """
        self.orchestrator = d_harvest_orchestrator
        self.enable_governance_sync = enable_governance_sync
        self.enable_memory_sync = enable_memory_sync

        # 延迟导入现有调度器（可能不可用）
        self._gov_scheduler = None
        self._mem_scheduler = None

        if enable_governance_sync:
            self._init_governance_scheduler()

        if enable_memory_sync:
            self._init_memory_scheduler()

    def _init_governance_scheduler(self) -> None:
        """初始化Governance域的HarvestScheduler"""
        try:
            import importlib

            _gov_mod = importlib.import_module("organs.D_Governance.organs.harvest_scheduler")
            HarvestScheduler = _gov_mod.HarvestScheduler
            self._gov_scheduler = HarvestScheduler()
            _log.info("[HarvestSchedulerBridge] D_Governance.HarvestScheduler已连接")
        except (ImportError, AttributeError) as e:
            _log.warning(f"[HarvestSchedulerBridge] 无法导入D_Governance.HarvestScheduler: {e}")
            self.enable_governance_sync = False

    def _init_memory_scheduler(self) -> None:
        """初始化Memory域的MemoryHarvestScheduler"""
        try:
            import importlib

            _mem_mod = importlib.import_module("organs.D_Memory.organs.harvest_scheduler")
            MemoryHarvestScheduler = _mem_mod.MemoryHarvestScheduler
            self._mem_scheduler = MemoryHarvestScheduler()
            _log.info("[HarvestSchedulerBridge] D_Memory.MemoryHarvestScheduler已连接")
        except (ImportError, AttributeError) as e:
            _log.warning(f"[HarvestSchedulerBridge] 无法导入D_Memory.MemoryHarvestScheduler: {e}")
            self.enable_memory_sync = False

    async def sync_harvest_result(self, source_id: str, result: HarvestResult) -> bool:
        """
        将harvest结果同步到现有的知识管理系统

        Args:
            source_id: 数据源ID
            result: Harvest结果

        Returns:
            True if sync successful
        """
        if not result.success:
            _log.debug(f"[HarvestSchedulerBridge] 跳过失败harvest的同步: {source_id}")
            return False

        synced = False

        # 同步到Governance域
        if self.enable_governance_sync and self._gov_scheduler:
            try:
                await self._sync_to_governance(source_id, result)
                synced = True
            except _HARVEST_BRIDGE_ERRORS as e:
                _log.error(f"[HarvestSchedulerBridge] Governance同步失败: {e}")

        # 同步到Memory域
        if self.enable_memory_sync and self._mem_scheduler:
            try:
                await self._sync_to_memory(source_id, result)
                synced = True
            except _HARVEST_BRIDGE_ERRORS as e:
                _log.error(f"[HarvestSchedulerBridge] Memory同步失败: {e}")

        return synced

    async def _sync_to_governance(self, source_id: str, result: HarvestResult) -> None:
        """
        同步到Governance域的HarvestScheduler

        将外部数据源的harvest结果作为knowledge entry存储，
        与ADRs和Retrospectives一起管理freshness。
        """
        if not self._gov_scheduler:
            return

        # 创建一个类似ADR的entry来记录外部harvest
        content_hash = self._compute_content_hash(source_id, result)
        tags = ["external_source", "d_harvest", source_id]
        summary = f"[External Harvest] {source_id}: {result.items_count} items harvested"

        # 使用Governance的_upsert_entry方法（通过反射访问私有方法）
        # 注意：这里可能需要调整API，因为_upsert_entry是私有的
        try:
            # 检查是否已存在（避免重复）
            existing = self._gov_scheduler.search(source_id)
            if any(source_id in entry.summary for entry in existing):
                _log.debug(f"[HarvestSchedulerBridge] Governance中已存在: {source_id}")
                return

            # 创建新的knowledge entry
            import json
            import uuid

            entry_id = str(uuid.uuid4())
            now = datetime.now(UTC).isoformat()

            with self._gov_scheduler._lock, self._gov_scheduler._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO harvest_entries
                        (id, source_type, source_id, content_hash, extracted_at,
                         freshness_score, tags, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry_id,
                        "external_harvest",
                        source_id,
                        content_hash,
                        now,
                        1.0,  # 初始freshness
                        json.dumps(tags),
                        summary,
                    ),
                )
                conn.commit()

            _log.info(f"[HarvestSchedulerBridge] 已同步到Governance: {source_id}")

        except _HARVEST_BRIDGE_ERRORS as e:
            _log.error(f"[HarvestSchedulerBridge] Governance同步失败: {e}")
            raise

    async def _sync_to_memory(self, source_id: str, result: HarvestResult) -> None:
        """
        同步到Memory域的MemoryHarvestScheduler

        触发一次记忆巩固周期，将新harvest的知识整合到长期记忆。
        """
        if not self._mem_scheduler:
            return

        try:
            # 触发手动harvest周期
            harvest_result = self._mem_scheduler.trigger_harvest()
            _log.info(f"[HarvestSchedulerBridge] Memory巩固完成: {harvest_result.items_consolidated} items")
        except _HARVEST_BRIDGE_ERRORS as e:
            _log.error(f"[HarvestSchedulerBridge] Memory同步失败: {e}")
            raise

    def _compute_content_hash(self, source_id: str, result: HarvestResult) -> str:
        """计算harvest结果的content hash用于去重"""
        import hashlib

        content = f"{source_id}|{result.items_count}|{result.success}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_cross_domain_freshness(self, source_id: str) -> dict[str, Any]:
        """
        获取跨域的freshness信息

        Args:
            source_id: 数据源ID

        Returns:
            包含各域freshness信息的字典
        """
        freshness_info = {
            "source_id": source_id,
            "governance": None,
            "memory": None,
        }

        # 查询Governance域的freshness
        if self._gov_scheduler:
            try:
                entries = self._gov_scheduler.search(source_id)
                if entries:
                    freshness_info["governance"] = {
                        "freshness_score": entries[0].freshness_score,
                        "extracted_at": entries[0].extracted_at,
                        "summary": entries[0].summary,
                    }
            except _HARVEST_BRIDGE_ERRORS as e:
                _log.error(f"[HarvestSchedulerBridge] Governance freshess查询失败: {e}")

        # 查询Memory域的状态
        if self._mem_scheduler:
            try:
                status = self._mem_scheduler.get_status()
                freshness_info["memory"] = {
                    "running": status.running,
                    "total_harvests": status.total_harvests,
                    "last_harvest_at": status.last_harvest_at.isoformat() if status.last_harvest_at else None,
                }
            except _HARVEST_BRIDGE_ERRORS as e:
                _log.error(f"[HarvestSchedulerBridge] Memory状态查询失败: {e}")

        return freshness_info

    async def schedule_periodic_sync(self, interval_hours: float = 24.0) -> str:
        """
        在Governance域注册周期性同步任务

        Args:
            interval_hours: 同步间隔（小时）

        Returns:
            任务ID
        """
        if not self._gov_scheduler:
            _log.warning("[HarvestSchedulerBridge] Governance scheduler不可用，无法注册周期任务")
            return ""

        try:
            task = self._gov_scheduler.schedule(
                name="D_Harvest periodic sync",
                target="external_harvest",
                interval_hours=interval_hours,
            )
            _log.info(f"[HarvestSchedulerBridge] 已注册周期同步任务: {task['id']}")
            return task["id"]
        except _HARVEST_BRIDGE_ERRORS as e:
            _log.error(f"[HarvestSchedulerBridge] 注册周期任务失败: {e}")
            return ""

    def get_integration_status(self) -> dict[str, Any]:
        """
        获取集成状态

        Returns:
            集成状态信息字典
        """
        return {
            "governance_enabled": self.enable_governance_sync and self._gov_scheduler is not None,
            "memory_enabled": self.enable_memory_sync and self._mem_scheduler is not None,
            "governance_available": self._gov_scheduler is not None,
            "memory_available": self._mem_scheduler is not None,
        }
