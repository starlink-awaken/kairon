"""llm-gateway-kernel — LLM 抽象 + 引擎核心基础设施。

子模块:
- llm_gateway_kernel.llm_gateway — LLM 路由 / 配额 / 抽象 (来自 llm-gateway)
- llm_gateway_kernel.engine_core — 引擎核心 (事件 / 调度 / 状态)

向后兼容:
- import llm_gateway → 6 个月 DeprecationWarning
- import engine_core → 6 个月 DeprecationWarning
"""

from __future__ import annotations

from . import llm_gateway
from . import engine_core

__all__ = ["llm_gateway", "engine_core"]
__version__ = "0.1.0"
