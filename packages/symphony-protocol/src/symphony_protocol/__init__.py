"""symphony_protocol — 旧包, 已迁移到 protocols_layer.symphony.

6 个月内保留 shim 入口, 发出 DeprecationWarning.
请更新 import 路径:

    # 旧 (已弃用)
    from symphony_protocol import SymphonyStateMachine
    from symphony_protocol.models import StageTransition
    # 新
    from protocols_layer.symphony import SymphonyStateMachine
    from protocols_layer.symphony.models import StageTransition
"""

from __future__ import annotations

import sys as _sys
import warnings as _warnings

_warnings.warn(
    "kairon.symphony_protocol 已迁移到 protocols_layer.symphony 子模块 (P31-W1 合并)。"
    "请更新 import 路径 — 6 个月内会保留此 shim。",
    DeprecationWarning,
    stacklevel=2,
)

# 实际功能从 protocols_layer 拿
# 暴露子模块 (shim 兼容: from symphony_protocol.X import Y)
import protocols_layer.symphony.matcher as _matcher
import protocols_layer.symphony.models as _models
import protocols_layer.symphony.state_machine as _state_machine
import protocols_layer.symphony.triggers as _triggers
from protocols_layer.symphony import *  # noqa: F403

_sys.modules['symphony_protocol.matcher'] = _matcher
_sys.modules['symphony_protocol.models'] = _models
_sys.modules['symphony_protocol.state_machine'] = _state_machine
_sys.modules['symphony_protocol.triggers'] = _triggers
