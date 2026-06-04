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
# Cognitive Loop Patch ≡ Module
# 内涵 ≝ {Cognitive, Loop, Patch}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CognitiveLoopPatch)}
# 功能 ⊢ {Cognitive_Loop, Loop_Patch, Patch_Init}
# =============================================================================

# ---
# domain: D-Harvest
# layer: integration
# status: active
# ---

"""
CognitiveLoop 集成补丁

扩展 CognitiveLoop 的 THINK 阶段，使其能够查询 D-Harvest 的知识。
通过猴子补丁方式注入，避免直接修改 CognitiveLoop 源代码。

使用方式:
    from minerva.integration.cognitive_loop_patch import patch_cognitive_loop
    patch_cognitive_loop()  # 在系统启动时调用
"""

import importlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from minerva.cognitive_provider import CognitiveLoopKnowledgeProvider  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)


class KnowledgeEnhancedThinking:
    """
    知识增强的思考阶段

    包装 CognitiveLoop 的 _think_phase 方法，注入知识查询能力。
    """

    def __init__(self, provider: CognitiveLoopKnowledgeProvider | None = None) -> None:
        if provider is None:
            from minerva.cognitive_provider import CognitiveLoopKnowledgeProvider

            provider = CognitiveLoopKnowledgeProvider()
        self.provider = provider
        self._original_think = None

    def install(self, cognitive_loop_class: type) -> None:
        """
        安装补丁到 CognitiveLoop 类

        Args:
            cognitive_loop_class: CognitiveLoop 类
        """
        # 保存原始方法
        self._original_think = getattr(cognitive_loop_class, "_think_phase", None)

        # 替换为新方法
        setattr(cognitive_loop_class, "_think_phase", self._enhanced_think_phase)

        # 添加知识查询方法
        setattr(cognitive_loop_class, "query_knowledge", self._query_knowledge)

        _log.info("[CognitivePatch] Knowledge-enhanced thinking installed")

    def uninstall(self, cognitive_loop_class: type) -> None:
        """卸载补丁"""
        if self._original_think:
            setattr(cognitive_loop_class, "_think_phase", self._original_think)
            if hasattr(cognitive_loop_class, "query_knowledge"):
                delattr(cognitive_loop_class, "query_knowledge")
            _log.info("[CognitivePatch] Knowledge-enhanced thinking uninstalled")

    async def _enhanced_think_phase(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        增强的 THINK 阶段

        在原始思考逻辑之前，先查询相关知识并注入上下文。
        """
        # 准备查询上下文
        context = {
            "current_phase": "think",
            "inputs": inputs,
            "description": inputs.get("description", ""),
            "topic": inputs.get("topic", ""),
        }

        # 查询知识
        try:
            knowledge_context = await self.provider.query_for_thinking(
                context=context,
                max_results=5,
                quality_threshold=0.6,
            )

            # 将知识注入输入
            inputs["knowledge_context"] = {
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
                f"[CognitivePatch] Injected {len(knowledge_context.items)} knowledge items into thinking context"
            )

        except Exception as e:
            _log.warning(f"[CognitivePatch] Knowledge query failed: {e}")
            inputs["knowledge_context"] = {"error": str(e), "items": []}

        # 调用原始思考方法
        if self._original_think:
            return await self._original_think(self, inputs)

        # 如果没有原始方法，返回默认结果
        return {"action": "default", "reasoning": "No original think method available"}

    async def _query_knowledge(
        self,
        query: str,
        max_results: int = 10,
        min_quality: float = 0.6,
    ) -> list[dict[str, Any]]:
        """
        为 CognitiveLoop 实例提供知识查询方法

        Args:
            query: 查询关键词
            max_results: 最大结果数
            min_quality: 最低质量分数

        Returns:
            知识条目列表
        """
        context = {
            "current_phase": "query",
            "topic": query,
            "inputs": {"query": query},
        }

        result = await self.provider.query_for_thinking(
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


# 全局补丁实例
_patch_instance: KnowledgeEnhancedThinking | None = None


def patch_cognitive_loop() -> bool:
    """
    安装 CognitiveLoop 知识增强补丁

    Returns:
        是否成功安装
    """
    global _patch_instance

    try:
        # 尝试导入 CognitiveLoop (lazy import to avoid cross-organ violation)
        try:
            mod = importlib.import_module("organs.D_Governance.organs.cognitive_loop")
            CognitiveLoop = mod.CognitiveLoop
        except ImportError:
            _log.warning("[CognitivePatch] CognitiveLoop not found, skipping patch")
            return False

        # 创建并安装补丁
        _patch_instance = KnowledgeEnhancedThinking()
        _patch_instance.install(CognitiveLoop)

        _log.info("[CognitivePatch] Successfully patched CognitiveLoop")
        return True

    except Exception as e:
        _log.error(f"[CognitivePatch] Failed to patch CognitiveLoop: {e}")
        return False


def unpatch_cognitive_loop() -> bool:
    """
    卸载 CognitiveLoop 知识增强补丁

    Returns:
        是否成功卸载
    """
    global _patch_instance

    if _patch_instance is None:
        return False

    try:
        # Lazy import to avoid cross-organ violation
        mod = importlib.import_module("organs.D_Governance.organs.cognitive_loop")
        CognitiveLoop = mod.CognitiveLoop

        _patch_instance.uninstall(CognitiveLoop)
        _patch_instance = None
        return True
    except ImportError:
        return False
    except Exception as e:
        _log.error(f"[CognitivePatch] Failed to unpatch: {e}")
        return False


def is_patched() -> bool:
    """检查补丁是否已安装"""
    return _patch_instance is not None
