"""Pytest 配置 — 确保 wksp 包可导入。"""

import sys
from pathlib import Path

# 将 src/ 目录添加到 sys.path，使 `from wksp import ...` 可工作
# 当 tests/ 位于 packages/wksp/tests/ 时，wksp 包 src 路径为:
# packages/wksp/src/
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
