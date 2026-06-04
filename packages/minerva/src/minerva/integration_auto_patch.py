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
# Auto Patch ≡ Module
# 内涵 ≝ {Auto, Patch}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, AutoPatch)}
# 功能 ⊢ {Auto_Patch, Init_Auto, Validate_Patch}
# =============================================================================

# ---
# domain: D-Harvest
# layer: integration
# status: active
# ---

"""
CognitiveLoop 自动补丁机制

功能：
- 系统启动时自动检测并安装补丁
- 支持手动触发补丁安装
- 补丁版本管理（避免重复安装）
- 补丁状态查询
- 支持补丁卸载

使用方式:
    # 手动触发
    from organs.D_Harvest import auto_patch_cognitive_loop
    auto_patch_cognitive_loop()

    # 检查状态
    from minerva.integration.auto_patch import is_cognitive_loop_patched
    assert is_cognitive_loop_patched() == True

    # 卸载补丁
    from minerva.integration.auto_patch import unpatch_cognitive_loop
    unpatch_cognitive_loop()

自动触发：
    在 D_Harvest 模块导入时，如果环境变量 BOS_AUTO_PATCH_COGNITIVE=1，
    会自动尝试安装补丁。
"""

import logging
import os
import weakref
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from minerva.cognitive_provider import CognitiveLoopKnowledgeProvider

_log = logging.getLogger(__name__)

_AUTO_PATCH_OPERATIONAL_ERRORS = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_AUTO_PATCH_SUPPORTED_ERROR_MODULE_PREFIXES = (
    "builtins",
    "organs.D_Harvest",
)


def _is_supported_auto_patch_error(exc: BaseException) -> bool:
    return type(exc).__module__.startswith(_AUTO_PATCH_SUPPORTED_ERROR_MODULE_PREFIXES)


# 补丁版本号，用于管理补丁更新
PATCH_VERSION = "1.0.0"

# 自动补丁环境变量开关
AUTO_PATCH_ENV_VAR = "BOS_AUTO_PATCH_COGNITIVE"


@dataclass
class PatchStatus:
    """补丁状态记录"""

    version: str = ""
    installed_at: str = ""
    installed_by: str = ""  # 'auto' | 'manual'
    cognitive_loop_class: Any = field(default=None, repr=False)
    provider: Any = field(default=None, repr=False)
    error_message: str = ""


class AutoPatcher:
    """
    CognitiveLoop 自动补丁管理器

    负责：
    1. 检测 CognitiveLoop 是否可用
    2. 安装/卸载补丁
    3. 记录补丁状态
    4. 避免重复安装

    使用 weakref 避免循环引用。
    """

    _instance: ClassVar[AutoPatcher | None] = None
    _lock: ClassVar[bool] = False
    _initialized: bool = False

    def __new__(cls) -> AutoPatcher:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._status = PatchStatus()
        self._original_think: Any = None
        self._provider: CognitiveLoopKnowledgeProvider | None = None
        self._cognitive_loop_ref: weakref.ref | None = None
        self._initialized = True

    @property
    def status(self) -> PatchStatus:
        """获取当前补丁状态"""
        return self._status

    def is_patched(self) -> bool:
        """检查补丁是否已安装"""
        if self._cognitive_loop_ref is None:
            return False

        cognitive_loop_class = self._cognitive_loop_ref()
        if cognitive_loop_class is None:
            # 原始类已被垃圾回收
            self._reset_state()
            return False

        # 检查是否有我们的补丁标记
        return getattr(cognitive_loop_class, "_harvest_patch_version", None) == PATCH_VERSION

    def patch(self, force: bool = False) -> bool:
        """
        安装 CognitiveLoop 补丁

        Args:
            force: 是否强制重新安装（即使已安装）

        Returns:
            是否成功安装
        """
        if not force and self.is_patched():
            _log.info("[AutoPatch] CognitiveLoop already patched (version=%s)", PATCH_VERSION)
            return True

        try:
            # 尝试导入 CognitiveLoop
            cognitive_loop_class = self._import_cognitive_loop()
            if cognitive_loop_class is None:
                self._status.error_message = "CognitiveLoop not found"
                _log.warning("[AutoPatch] %s", self._status.error_message)
                return False

            # 如果已安装且不是强制模式，跳过
            if not force and hasattr(cognitive_loop_class, "_harvest_patch_version"):
                existing_version = getattr(cognitive_loop_class, "_harvest_patch_version", None)
                if existing_version == PATCH_VERSION:
                    _log.info("[AutoPatch] Patch already installed (version=%s)", PATCH_VERSION)
                    return True
                _log.info(
                    "[AutoPatch] Upgrading patch from %s to %s",
                    existing_version,
                    PATCH_VERSION,
                )
                self._uninstall_internal(cognitive_loop_class)

            # 创建知识提供者
            from minerva.cognitive_provider import CognitiveLoopKnowledgeProvider

            self._provider = CognitiveLoopKnowledgeProvider()

            # 保存原始方法
            self._original_think = cognitive_loop_class._run_think

            # 使用 weakref 引用类，避免循环引用
            self._cognitive_loop_ref = weakref.ref(cognitive_loop_class)

            # 安装增强方法
            cognitive_loop_class._run_think = self._create_enhanced_think()

            # 添加知识查询方法
            cognitive_loop_class.query_knowledge = self._create_query_knowledge()

            # 添加补丁标记
            cognitive_loop_class._harvest_patch_version = PATCH_VERSION
            cognitive_loop_class._harvest_patch_installed_at = datetime.now(UTC).isoformat()

            # 更新状态
            self._status = PatchStatus(
                version=PATCH_VERSION,
                installed_at=datetime.now(UTC).isoformat(),
                installed_by="manual",
                cognitive_loop_class=cognitive_loop_class,
                provider=self._provider,
            )

            _log.info(
                "[AutoPatch] Successfully patched CognitiveLoop (version=%s)",
                PATCH_VERSION,
            )
            return True

        except _AUTO_PATCH_OPERATIONAL_ERRORS as e:
            if not _is_supported_auto_patch_error(e):
                raise
            self._status.error_message = str(e)
            _log.error("[AutoPatch] Failed to patch CognitiveLoop: %s", e)
            return False

    def unpatch(self) -> bool:
        """
        卸载 CognitiveLoop 补丁

        Returns:
            是否成功卸载
        """
        if self._cognitive_loop_ref is None:
            _log.warning("[AutoPatch] No patch to uninstall")
            return False

        cognitive_loop_class = self._cognitive_loop_ref()
        if cognitive_loop_class is None:
            _log.warning("[AutoPatch] CognitiveLoop reference lost, cleaning up state")
            self._reset_state()
            return True

        return self._uninstall_internal(cognitive_loop_class)

    def _uninstall_internal(self, cognitive_loop_class: type) -> bool:
        """内部卸载逻辑"""
        try:
            # 恢复原始方法
            if self._original_think is not None:
                cognitive_loop_class._run_think = self._original_think

            # 移除添加的方法
            for attr in [
                "query_knowledge",
                "_harvest_patch_version",
                "_harvest_patch_installed_at",
            ]:
                if hasattr(cognitive_loop_class, attr):
                    delattr(cognitive_loop_class, attr)

            # 清理状态
            self._reset_state()

            _log.info("[AutoPatch] Successfully unpatched CognitiveLoop")
            return True

        except _AUTO_PATCH_OPERATIONAL_ERRORS as e:
            if not _is_supported_auto_patch_error(e):
                raise
            _log.error("[AutoPatch] Failed to unpatch CognitiveLoop: %s", e)
            return False

    def _reset_state(self) -> None:
        """重置内部状态"""
        self._status = PatchStatus()
        self._original_think = None
        self._provider = None
        self._cognitive_loop_ref = None

    def _import_cognitive_loop(self) -> type | None:
        """
        尝试导入 CognitiveLoop 类

        Returns:
            CognitiveLoop 类，如果未找到则返回 None
        """
        import importlib

        # 尝试多个可能的路径
        paths = [
            "organs.D_Governance.organs.cognitive_loop",
            "organs.D_Governance.organs.cognitive_loop",
        ]

        for path in paths:
            try:
                mod = importlib.import_module(path)
                cognitive_loop_class = getattr(mod, "CognitiveLoop", None)
                if cognitive_loop_class is not None:
                    return cognitive_loop_class
            except ImportError:
                continue

        return None

    def _create_enhanced_think(self) -> Callable[[Any, dict[str, Any]], dict[str, Any]]:
        """
        创建增强的 _run_think 方法

        在原始思考逻辑之前，先查询相关知识并注入上下文。
        """
        original_think = self._original_think
        provider = self._provider

        def _enhanced_run_think(self: Any, observe_outputs: dict[str, Any]) -> dict[str, Any]:
            """增强的 THINK 阶段"""
            # 准备查询上下文
            context = {
                "current_phase": "think",
                "inputs": observe_outputs,
                "description": observe_outputs.get("description", ""),
                "topic": observe_outputs.get("topic", ""),
                "problem_type": observe_outputs.get("problem_type", ""),
            }

            # 查询知识（同步方式）
            knowledge_context = None
            if provider is not None:
                try:
                    import asyncio

                    # 尝试异步查询，如果失败则同步查询
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # 在运行中的事件循环中，暂时不注入知识
                            # 避免复杂的异步处理
                            knowledge_context = None
                        else:
                            knowledge_context = loop.run_until_complete(
                                provider.query_for_thinking(
                                    context=context,
                                    max_results=5,
                                    quality_threshold=0.6,
                                )
                            )
                    except RuntimeError as e:
                        if not _is_supported_auto_patch_error(e):
                            raise
                        # 没有事件循环，创建新的
                        knowledge_context = asyncio.run(
                            provider.query_for_thinking(
                                context=context,
                                max_results=5,
                                quality_threshold=0.6,
                            )
                        )

                except _AUTO_PATCH_OPERATIONAL_ERRORS as e:
                    if not _is_supported_auto_patch_error(e):
                        raise
                    _log.warning("[AutoPatch] Knowledge query failed: %s", e)

            # 调用原始思考方法
            result = original_think(self, observe_outputs) if original_think else {}

            # 注入知识上下文
            if knowledge_context is not None:
                result["knowledge_context"] = {
                    "query": knowledge_context.query,
                    "summary": knowledge_context.context_summary,
                    "items": [
                        {
                            "id": item.id,
                            "title": item.title,
                            "uri": item.uri,
                            "quality_score": item.quality_score,
                            "freshness_score": item.freshness_score,
                            "relevance_score": item.relevance_score,
                        }
                        for item in knowledge_context.items
                    ],
                }
                _log.debug(
                    "[AutoPatch] Injected %d knowledge items into thinking context",
                    len(knowledge_context.items),
                )
            else:
                result["knowledge_context"] = {
                    "error": "Async mode - knowledge not injected",
                    "items": [],
                }

            return result

        return _enhanced_run_think

    def _create_query_knowledge(
        self,
    ) -> Callable[[Any, str, int, float], Awaitable[list[dict[str, Any]]]]:
        """
        创建 query_knowledge 方法

        为 CognitiveLoop 实例提供知识查询接口。
        """
        provider = self._provider

        async def query_knowledge(
            self: Any,
            query: str,
            max_results: int = 10,
            min_quality: float = 0.6,
        ) -> list[dict[str, Any]]:
            """
            查询知识库

            Args:
                query: 查询关键词
                max_results: 最大结果数
                min_quality: 最低质量分数

            Returns:
                知识条目列表
            """
            if provider is None:
                return []

            context = {
                "current_phase": "query",
                "topic": query,
                "inputs": {"query": query},
            }

            try:
                result = await provider.query_for_thinking(
                    context=context,
                    max_results=max_results,
                    quality_threshold=min_quality,
                )

                return [
                    {
                        "id": item.id,
                        "title": item.title,
                        "body": item.body[:500],  # 截断正文
                        "uri": item.uri,
                        "quality_score": item.quality_score,
                        "freshness_score": item.freshness_score,
                        "harvested_at": item.harvested_at,
                    }
                    for item in result.items
                ]
            except _AUTO_PATCH_OPERATIONAL_ERRORS as e:
                if not _is_supported_auto_patch_error(e):
                    raise
                _log.warning("[AutoPatch] Knowledge query failed: %s", e)
                return []

        return query_knowledge


def auto_patch_cognitive_loop() -> bool:
    """
    手动触发 CognitiveLoop 补丁安装

    Returns:
        是否成功安装

    Example:
        >>> from organs.D_Harvest import auto_patch_cognitive_loop
        >>> auto_patch_cognitive_loop()
        True
    """
    patcher = AutoPatcher()
    return patcher.patch(force=False)


def unpatch_cognitive_loop() -> bool:
    """
    卸载 CognitiveLoop 补丁

    Returns:
        是否成功卸载

    Example:
        >>> from minerva.integration.auto_patch import unpatch_cognitive_loop
        >>> unpatch_cognitive_loop()
        True
    """
    patcher = AutoPatcher()
    return patcher.unpatch()


def is_cognitive_loop_patched() -> bool:
    """
    检查 CognitiveLoop 补丁是否已安装

    Returns:
        如果已安装则返回 True

    Example:
        >>> from minerva.integration.auto_patch import is_cognitive_loop_patched
        >>> is_cognitive_loop_patched()
        True
    """
    patcher = AutoPatcher()
    return patcher.is_patched()


def get_patch_status() -> PatchStatus:
    """
    获取补丁状态

    Returns:
        PatchStatus 对象，包含版本、安装时间等信息

    Example:
        >>> from minerva.integration.auto_patch import get_patch_status
        >>> status = get_patch_status()
        >>> print(status.version)
        '1.0.0'
    """
    patcher = AutoPatcher()
    return patcher.status


def _try_auto_patch() -> bool:
    """
    尝试自动安装补丁（内部使用）

    检查环境变量 BOS_AUTO_PATCH_COGNITIVE=1 时自动安装。

    Returns:
        是否成功安装或已安装
    """
    auto_patch_enabled = os.environ.get(AUTO_PATCH_ENV_VAR, "0") == "1"

    if not auto_patch_enabled:
        _log.debug("[AutoPatch] Auto-patch disabled (set %s=1 to enable)", AUTO_PATCH_ENV_VAR)
        return False

    _log.info("[AutoPatch] Auto-patching enabled, attempting to patch CognitiveLoop")
    patcher = AutoPatcher()
    result = patcher.patch(force=False)

    if result:
        patcher.status.installed_by = "auto"

    return result


# 模块导入时尝试自动补丁（仅在环境变量启用时）
_patch_result = _try_auto_patch()
