"""sophia — 旧包, 已迁移到 protocols_layer.sophia.

6 个月内保留 shim 入口, 发出 DeprecationWarning.
请更新 import 路径:

    # 旧 (已弃用)
    from sophia import compile_paradigm_sync
    from sophia.compiler import compile_paradigm_sync
    # 新
    from protocols_layer.sophia import compile_paradigm_sync
    from protocols_layer.sophia.compiler import compile_paradigm_sync
"""

from __future__ import annotations

import sys as _sys
import warnings as _warnings

_warnings.warn(
    "kairon.sophia 已迁移到 protocols_layer.sophia 子模块 (P31-W1 合并)。"
    "请更新 import 路径 — 6 个月内会保留此 shim。",
    DeprecationWarning,
    stacklevel=2,
)

# 实际功能从 protocols_layer 拿
# 暴露子模块 (shim 兼容: from sophia.X import Y)
import protocols_layer.sophia.cli as _cli
import protocols_layer.sophia.compiler as _compiler
import protocols_layer.sophia.kems_runtime as _kems_runtime
import protocols_layer.sophia.learner as _learner
import protocols_layer.sophia.server.mcp_server as _mcp_server
import protocols_layer.sophia.symbols as _symbols
import protocols_layer.sophia.tui.app as _tui_app
from protocols_layer.sophia import *  # noqa: F403

_sys.modules['sophia.cli'] = _cli
_sys.modules['sophia.compiler'] = _compiler
_sys.modules['sophia.learner'] = _learner
_sys.modules['sophia.symbols'] = _symbols
_sys.modules['sophia.kems_runtime'] = _kems_runtime
_sys.modules['sophia.server'] = _sys.modules.get('protocols_layer.sophia.server', _sys.modules.get('protocols_layer.sophia'))
_sys.modules['sophia.server.mcp_server'] = _mcp_server
_sys.modules['sophia.tui'] = _sys.modules.get('protocols_layer.sophia.tui', _sys.modules.get('protocols_layer.sophia'))
_sys.modules['sophia.tui.app'] = _tui_app
