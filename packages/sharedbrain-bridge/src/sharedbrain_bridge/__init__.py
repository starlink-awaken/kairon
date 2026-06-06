"""SharedBrain Bridge — DEPRECATED SHIM (P31-W1, ADR-0006).

sharedbrain-bridge 包已合并入 sot-bridge (sot_bridge.sharedbrain_bridge)。
本 shim 保留 6 个月（2026-06-06 ~ 2026-12-06），仅作向后兼容。

注意: SharedBrain 已于 Phase 31 退役（2026-06-06），本包内模块均为 stubify 状态。

新代码请使用:
    from sot_bridge.sharedbrain_bridge import ...
    # 或
    from sot_bridge import sharedbrain_bridge
"""

from __future__ import annotations

import warnings

_warned = False


def _warn_once() -> None:
    global _warned
    if not _warned:
        warnings.warn(
            "kairon.sharedbrain-bridge 已迁移到 sot-bridge 子模块 'sot_bridge.sharedbrain_bridge'。"
            "SharedBrain 已退役（Phase 31），本包内模块为 stub。"
            "请更新 import 路径（6 个月内会保留此 shim）。"
            "详见: .omo/_knowledge/decisions/0006-kairon-package-merge.md",
            DeprecationWarning,
            stacklevel=3,
        )
        _warned = True


_warn_once()

# 委托到新位置
from sot_bridge.sharedbrain_bridge import *  # noqa: E402, F401, F403
from sot_bridge import sharedbrain_bridge as _sot_bridge_sb  # noqa: E402

__version__ = _sot_bridge_sb.__version__
__all__ = getattr(_sot_bridge_sb, "__all__", ())
