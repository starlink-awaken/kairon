"""sot-bridge — 单源真相 (SSOT) + 跨系统桥接 (SharedBrain Bridge).

子模块:
- sot_bridge.ssot_kernel — 单一事实源系统（来自 ssot 包，~17.6k 行）
- sot_bridge.sharedbrain_bridge — 跨系统桥接（来自 sharedbrain-bridge 包，~1k 行；Phase 31 已 stubify）

合并来源: ADR-0006 (P31-W1)

向后兼容（6 个月 shim，DeprecationWarning）:
- import ssot_kernel / from ssot_kernel import X  → 见 packages/ssot/src/ssot_kernel/__init__.py
- import sharedbrain_bridge / from sharedbrain_bridge import X  → 见 packages/sharedbrain-bridge/src/sharedbrain_bridge/__init__.py
"""

from __future__ import annotations

from . import sharedbrain_bridge, ssot_kernel

__all__ = ["ssot_kernel", "sharedbrain_bridge"]
__version__ = "0.1.0"


def main() -> None:
    """sot-bridge 顶层 CLI 入口（占位）。"""
    import sys

    print("sot-bridge v0.1.0")
    print("子命令:")
    print("  ssot-kernel    — SSOT 内核 CLI（原 ssot-kernel）")
    print("  sb-bridge      — SharedBrain 桥接 CLI（已 stubify，Phase 31）")
    print("已合并自 ssot + sharedbrain-bridge (P31-W1, ADR-0006)。")
    sys.exit(0)
