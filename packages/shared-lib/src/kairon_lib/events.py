"""Backward-compat module alias."""

import sys

from kairon_lib.core import events as _impl

sys.modules[__name__] = _impl
