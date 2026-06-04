"""Adapter exports."""

from iris.adapters.eidos import EidosAdapter  # type: ignore[import-not-found]
from iris.adapters.ssot import SSOTDomainAdapter  # type: ignore[import-not-found]

__all__ = ["SSOTDomainAdapter", "EidosAdapter"]
