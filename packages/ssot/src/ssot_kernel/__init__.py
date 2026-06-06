"""SSOT Kernel — DEPRECATED SHIM (P31-W1, ADR-0006).

ssot 包已合并入 sot-bridge (sot_bridge.ssot_kernel)。
本 shim 保留 6 个月（2026-06-06 ~ 2026-12-06），仅作向后兼容。

新代码请使用:
    from sot_bridge.ssot_kernel import ...
    # 或
    from sot_bridge import ssot_kernel
"""

from __future__ import annotations

import sys
import warnings

_warned = False


def _warn_once() -> None:
    global _warned
    if not _warned:
        warnings.warn(
            "kairon.ssot 已迁移到 sot-bridge 子模块 'sot_bridge.ssot_kernel'。"
            "请更新 import 路径（6 个月内会保留此 shim）。"
            "详见: .omo/_knowledge/decisions/0006-kairon-package-merge.md",
            DeprecationWarning,
            stacklevel=3,
        )
        _warned = True


_warn_once()

# 委托到新位置
from sot_bridge.ssot_kernel import *  # noqa: E402, F401, F403
from sot_bridge import ssot_kernel as _sot_bridge_ssot_kernel  # noqa: E402

__version__ = _sot_bridge_ssot_kernel.__version__
__all__ = getattr(_sot_bridge_ssot_kernel, "__all__", ())
