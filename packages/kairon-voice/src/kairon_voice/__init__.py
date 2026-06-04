"""kairon_voice — Voice subsystem extracted from SharedBrain D_Voice.

Provides speech-to-text and text-to-speech interfaces with multiple provider
adapters (Whisper, ElevenLabs, Google Cloud, Azure).  All external dependencies
are optional — adapters degrade gracefully when their underlying libraries are
not installed.
"""

from __future__ import annotations

from .interfaces import (
    BaseVoiceInput,
    BaseVoiceOutput,
    VoiceConfig,
    VoiceInputProvider,
    VoiceOutputProvider,
    VoiceResult,
)
from .stt import STTProviderFactory, WhisperAdapter
from .tts import (
    AzureTTSAdapter,
    ElevenLabsAdapter,
    GoogleTTSAdapter,
    TTSProviderFactory,
)

__all__ = [
    "AzureTTSAdapter",
    "BaseVoiceInput",
    "BaseVoiceOutput",
    "ElevenLabsAdapter",
    "GoogleTTSAdapter",
    "STTProviderFactory",
    "TTSProviderFactory",
    "VoiceConfig",
    "VoiceInputProvider",
    "VoiceOutputProvider",
    "VoiceResult",
    "WhisperAdapter",
]

__version__ = "1.0.0"
