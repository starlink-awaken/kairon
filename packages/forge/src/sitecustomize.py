"""Test-time compatibility shims for Forge."""

from __future__ import annotations

import shlex
import subprocess

_orig_getstatusoutput = subprocess.getstatusoutput


def _compat_getstatusoutput(cmd):
    if isinstance(cmd, (list, tuple)):
        cmd = " ".join(shlex.quote(str(part)) for part in cmd)
    return _orig_getstatusoutput(cmd)


subprocess.getstatusoutput = _compat_getstatusoutput
