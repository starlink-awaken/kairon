"""llm_gateway — Deprecated shim.

已迁移到 ``llm-gateway-kernel`` 包的子模块 ``llm_gateway_kernel.llm_gateway``。
本 shim 保留 6 个月（计划移除日期 2026-12-06），仅用于向后兼容。
新代码请直接 import from ``llm_gateway_kernel.llm_gateway``。
"""

from __future__ import annotations

import warnings
import sys
from pathlib import Path

warnings.warn(
    "kairon.llm_gateway 已迁移到 llm-gateway-kernel 子模块 'llm_gateway_kernel.llm_gateway'。"
    "请更新 import 路径（6 个月内会保留此 shim）",
    DeprecationWarning,
    stacklevel=2,
)

# 将 llm-gateway-kernel 的 src 加入 sys.path 并从新位置导入
_shim_src = str(Path(__file__).resolve().parents[3] / "llm-gateway-kernel" / "src")
if _shim_src not in sys.path:
    sys.path.insert(0, _shim_src)

try:
    from llm_gateway_kernel.llm_gateway import *  # noqa: F401,F403
except Exception:  # pragma: no cover - shim fallback
    pass
