"""sot-bridge 测试 conftest — 保证 sot_bridge 在 sys.path。

P31-W1 合并后, 测试位于 tests/ssot_kernel/ 和 tests/sharedbrain_bridge/ 子目录,
子目录名与原包名同名, 避免 pytest 把它当 package 解析。
此 conftest 在 collection 前把 src/ 加到 sys.path 顶端, 保证 sot_bridge 可导入。
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
