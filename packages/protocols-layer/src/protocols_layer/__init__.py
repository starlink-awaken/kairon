"""protocols-layer — 规则/协议层.

子模块:
- protocols_layer.sophia — 范式编译 (来自原 sophia 包)
- protocols_layer.symphony — 协议实现 (来自原 symphony-protocol 包)

向后兼容:
- import sophia / from sophia import X  → 6 个月 DeprecationWarning (shim)
- import symphony_protocol / from symphony_protocol import X  → 6 个月 DeprecationWarning (shim)
"""

from __future__ import annotations

__version__ = "0.1.0"

# 自动 import 子包
from . import sophia, symphony

__all__ = ["sophia", "symphony", "__version__"]
