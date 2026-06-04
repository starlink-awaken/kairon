"""Voice I/O interfaces — abstract base classes and data models.

Provides VoiceInputProvider, VoiceOutputProvider ABCs and the VoiceResult /
VoiceConfig Pydantic models used throughout the voice subsystem.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

_log = logging.getLogger(__name__)


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
    """Abstract interface for voice input (speech-to-text).

    Subclasses implement transcribe() to convert audio bytes to text.
    """

    @abstractmethod
    def transcribe(self, audio_data: bytes) -> VoiceResult:
        """Transcribe audio bytes to text.

        Args:
            audio_data: Raw audio bytes (PCM 16kHz mono by default).

        Returns:
            VoiceResult with recognized text and metadata.
        """
        ...

    @abstractmethod
    def get_audio_chunks(self) -> list[bytes]:
        """Return buffered audio chunks accumulated since last call.

        Returns:
            List of audio byte chunks.
        """
        ...

    def close(self) -> None:
        """Release provider resources. Override in subclasses."""
        return None


class VoiceOutputProvider(ABC):
    """Abstract interface for voice output (text-to-speech).

    Subclasses implement synthesize() to convert text to audio bytes.
    """

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio bytes.

        Args:
            text: Text to convert to speech.

        Returns:
            Audio bytes in the configured format.
        """
        ...

    @abstractmethod
    def stream_audio(self, audio_data: bytes) -> None:
        """Stream audio data to the output device.

        Args:
            audio_data: Raw audio bytes to stream.
        """
        ...

    def close(self) -> None:
        """Release provider resources. Override in subclasses."""
        return None


class BaseVoiceInput(VoiceInputProvider):
    """Instantiable base for voice input providers.

    Default transcribe() returns a VoiceResult with empty text.
    Subclass and override transcribe() for real STT behavior.
    """

    def __init__(self, config: VoiceConfig | None = None) -> None:
        self._config = config or VoiceConfig(provider_type="base")
        self._chunks: list[bytes] = []

    def transcribe(self, audio_data: bytes) -> VoiceResult:
        _ = audio_data
        return VoiceResult(
            text="",
            confidence=0.0,
            duration_seconds=0.0,
            language=self._config.language,
        )

    def get_audio_chunks(self) -> list[bytes]:
        chunks = list(self._chunks)
        self._chunks.clear()
        return chunks

    def add_chunk(self, audio_data: bytes) -> None:
        """Buffer an audio chunk for later transcription.

        Args:
            audio_data: Raw audio bytes.
        """
        self._chunks.append(audio_data)


class BaseVoiceOutput(VoiceOutputProvider):
    """Instantiable base for voice output providers.

    Default synthesize() returns empty bytes.
    Subclass and override synthesize() for real TTS behavior.
    """

    def __init__(self, config: VoiceConfig | None = None) -> None:
        self._config = config or VoiceConfig(provider_type="base")

    def synthesize(self, text: str) -> bytes:
        _ = text
        return b""

    def stream_audio(self, audio_data: bytes) -> None:
        _ = audio_data


__all__ = [
    "BaseVoiceInput",
    "BaseVoiceOutput",
    "VoiceConfig",
    "VoiceInputProvider",
    "VoiceOutputProvider",
    "VoiceResult",
]
