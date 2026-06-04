from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Voice Io ≡ Module
# 内涵 ≝ {Voice, Io}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, VoiceIo)}
# 功能 ⊢ {Voice_Io, Init_Voice, Validate_Io}
# =============================================================================

# ---
# domain: D-Voice
# layer: interfaces
# status: active
# version: 1.0.0
# owner: '@Prime'
# authority: P6 voice I/O architecture
# ---
"""
Voice I/O — abstract interfaces for voice input and output providers.

Provides VoiceInputProvider, VoiceOutputProvider ABCs and the
VoiceResult / VoiceConfig Pydantic models used throughout D-Voice.
"""


from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

try:
    from nucleus.Z_Spore.interfaces.surface_contract import SurfaceContract  # type: ignore[import-not-found]
except (ImportError, ModuleNotFoundError):
    from dataclasses import dataclass, field
    from typing import Any

    @dataclass
    class SurfaceContract:  # type: ignore[no-redef]
        """Fallback SurfaceContract — migrated module not available."""

        session_id: str = ""
        owner_id: str = ""
        metadata: dict[str, Any] = field(default_factory=dict)

        @classmethod
        def voice(
            cls,
            *,
            session_id: str = "",
            owner_id: str = "",
            metadata: dict[str, Any] | None = None,
        ) -> SurfaceContract:
            return cls(
                session_id=session_id,
                owner_id=owner_id,
                metadata=metadata or {},
            )

        def to_dict(self) -> dict[str, Any]:
            return {
                "session_id": self.session_id,
                "owner_id": self.owner_id,
                "metadata": self.metadata,
            }


class VoiceResult(BaseModel):
    """Result returned from a voice transcription operation."""

    text: str = Field(..., description="Recognized text from audio input")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Transcription confidence score")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Duration of the audio segment in seconds")
    language: str | None = Field(default=None, description="Detected or specified language code (e.g. 'en', 'zh')")
    audio_format: str = Field(default="pcm", description="Audio format of the input data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional provider-specific metadata")


class VoiceConfig(BaseModel):
    """Configuration for voice input/output providers."""

    provider_type: str = Field(..., description="Provider name: 'whisper', 'google', 'azure'")
    language: str = Field(default="en", description="Primary language code")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    audio_format: str = Field(default="pcm", description="Expected audio encoding format")
    local_only: bool = Field(default=True, description="Prefer local processing for privacy")
    model_name: str | None = Field(default=None, description="Model name or path (for Whisper)")
    timeout_seconds: float = Field(default=30.0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VoiceInputProvider(ABC):
    """
    Abstract interface for voice input (speech-to-text).

    Subclasses implement transcribe() to convert audio bytes to text.
    """

    @abstractmethod
    def transcribe(self, audio_data: bytes) -> VoiceResult:
        """
        Transcribe audio bytes to text.

        Args:
            audio_data: Raw audio bytes ( PCM 16kHz mono by default).

        Returns:
            VoiceResult with recognized text and metadata.
        """
        ...

    @abstractmethod
    def get_audio_chunks(self) -> list[bytes]:
        """
        Return buffered audio chunks accumulated since last call.

        Returns:
            List of audio byte chunks.
        """
        ...

    def close(self) -> None:
        """Release provider resources. Override in subclasses."""
        return None


class VoiceOutputProvider(ABC):
    """
    Abstract interface for voice output (text-to-speech).

    Subclasses implement synthesize() to convert text to audio bytes.
    """

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """
        Synthesize text to audio bytes.

        Args:
            text: Text to convert to speech.

        Returns:
            Audio bytes in the configured format.
        """
        ...

    @abstractmethod
    def stream_audio(self, audio_data: bytes) -> None:
        """
        Stream audio data to the output device.

        Args:
            audio_data: Raw audio bytes to stream.
        """
        ...

    def close(self) -> None:
        """Release provider resources. Override in subclasses."""
        return None


def voice_perception_surface_contract(
    *,
    session_id: str = "",
    owner_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> SurfaceContract:
    """Return the non-canonical voice perception surface binding."""
    return SurfaceContract.voice(
        session_id=session_id,
        owner_id=owner_id,
        metadata=metadata,
    )


__all__ = [
    "VoiceConfig",
    "VoiceInputProvider",
    "VoiceOutputProvider",
    "VoiceResult",
    "voice_perception_surface_contract",
]
