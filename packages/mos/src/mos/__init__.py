"""Memory OS (MOS) control plane — ADR-0372."""

from mos.envelope import MemoryEnvelope, ValidationError, validate_envelope
from mos.events import CARD_UPDATED_URIS, is_card_updated_event
from mos.service import ForgetResult, KnowledgeRef, MemoryOS, RecallResult, WriteResult

__all__ = [
    "MemoryEnvelope",
    "MemoryOS",
    "RecallResult",
    "ForgetResult",
    "KnowledgeRef",
    "ValidationError",
    "WriteResult",
    "CARD_UPDATED_URIS",
    "is_card_updated_event",
    "validate_envelope",
]

__version__ = "0.4.0"
