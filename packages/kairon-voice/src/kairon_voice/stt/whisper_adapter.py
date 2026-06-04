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
# Whisper Adapter ≡ Module
# 内涵 ≝ {Whisper, Adapter}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, WhisperAdapter)}
# 功能 ⊢ {Whisper_Adapter, Init_Whisper, Validate_Adapter}
# =============================================================================

# ---
# domain: D-Voice
# layer: stt
# status: active
# version: 1.0.0
# owner: '@Prime'
# authority: P6 voice I/O architecture
# ---
"""
Whisper STT adapter — local-first speech-to-text using OpenAI Whisper.

Supports streaming chunked audio input.  Processes audio locally on-device
to preserve privacy.  Falls back gracefully if whisper is unavailable.
"""


import importlib
import logging
from collections.abc import Iterable
from typing import Any, Literal, Protocol, TypedDict, cast

from ..interfaces.base_voice import BaseVoiceInput  # type: ignore[import-not-found]
from ..interfaces.voice_io import VoiceConfig, VoiceResult

_log = logging.getLogger(__name__)

WhisperAvailable = True
_whisper_module: Any | None = None
_fwhisper_module: Any | None = None


class _OpenAIWhisperResult(TypedDict, total=False):
    text: str
    confidence: float
    duration: float
    language: str


class _FasterWhisperSegment(Protocol):
    text: str


class _FasterWhisperInfo(Protocol):
    language_probability: float
    duration: float | None
    language: str | None


class _OpenAIWhisperModel(Protocol):
    def transcribe(
        self,
        audio: Any,
        *,
        language: str,
    ) -> _OpenAIWhisperResult: ...


class _FasterWhisperModel(Protocol):
    def transcribe(
        self,
        audio: Any,
        *,
        language: str,
        beam_size: int,
    ) -> tuple[Iterable[_FasterWhisperSegment], _FasterWhisperInfo]: ...


try:
    _whisper_module = importlib.import_module("whisper")
except ImportError:
    try:
        _fwhisper_module = importlib.import_module("faster_whisper")
    except ImportError:
        _log.warning(
            "Neither 'openai-whisper' nor 'faster-whisper' is installed. WhisperAdapter will return empty results."
        )
        WhisperAvailable = False


class WhisperAdapter(BaseVoiceInput):
    """
    Whisper-based STT adapter with streaming chunk support.

    Uses faster-whisper if available (faster), falls back to openai-whisper,
    and degrades gracefully to empty results if neither is installed.
    """

    def __init__(self, config: VoiceConfig | None = None) -> None:
        super().__init__(config or VoiceConfig(provider_type="whisper"))
        self._model: _OpenAIWhisperModel | _FasterWhisperModel | None = None
        self._backend: Literal["faster_whisper", "openai_whisper", "unavailable"] = "unavailable"
        self._model_loaded = False
        self._load_model()

    def _load_model(self) -> None:
        """Lazily load the Whisper model on first use."""
        if not WhisperAvailable:
            _log.info("Whisper libraries unavailable — running in dummy mode")
            return

        model_name = self._config.model_name or "base.en"
        try:
            if _fwhisper_module is not None:
                _log.info("Loading faster-whisper model: %s", model_name)
                whisper_model = getattr(_fwhisper_module, "WhisperModel", None)
                if whisper_model is None:
                    _log.error("faster_whisper.WhisperModel is unavailable")
                    return
                self._model = cast(
                    _FasterWhisperModel,
                    whisper_model(
                        model_name,
                        device="auto",
                        compute_type="int8",
                    ),
                )
                self._backend = "faster_whisper"
            else:
                _log.info("Loading openai-whisper model: %s", model_name)
                if _whisper_module is None:
                    _log.error("OpenAI Whisper module is unavailable")
                    return
                load_model = getattr(_whisper_module, "load_model", None)
                if not callable(load_model):
                    _log.error("whisper.load_model is unavailable")
                    return
                self._model = cast(_OpenAIWhisperModel, load_model(model_name))
                self._backend = "openai_whisper"
            self._model_loaded = True
        except Exception as exc:
            _log.error("Failed to load Whisper model '%s': %s", model_name, exc)
            self._model_loaded = False
            self._backend = "unavailable"

    def transcribe(self, audio_data: bytes) -> VoiceResult:
        """
        Transcribe a full audio segment to text.

        Args:
            audio_data: Raw PCM audio bytes.

        Returns:
            VoiceResult with recognized text.
        """
        model = self._model
        if not self._model_loaded or model is None:
            return VoiceResult(
                text="",
                confidence=0.0,
                language=self._config.language,
                audio_format=self._config.audio_format,
                metadata={"provider": "whisper", "backend": self._backend},
            )

        try:
            if self._backend == "faster_whisper":
                audio_np = self._bytes_to_np(audio_data)
                segments, info = cast(_FasterWhisperModel, model).transcribe(
                    audio_np,
                    language=self._config.language,
                    beam_size=5,
                )
                text_parts = [seg.text for seg in segments]
                return VoiceResult(
                    text="".join(text_parts).strip(),
                    confidence=float(info.language_probability),
                    duration_seconds=float(info.duration or 0.0),
                    language=info.language or self._config.language,
                    audio_format=self._config.audio_format,
                    metadata={"provider": "whisper", "backend": self._backend},
                )
            else:
                audio_np = self._bytes_to_np(audio_data)
                result = cast(_OpenAIWhisperModel, model).transcribe(
                    audio_np,
                    language=self._config.language,
                )
                return VoiceResult(
                    text=result.get("text", "").strip(),
                    confidence=float(result.get("confidence", 0.0)),
                    duration_seconds=float(result.get("duration", 0.0)),
                    language=result.get("language", self._config.language),
                    audio_format=self._config.audio_format,
                    metadata={"provider": "whisper", "backend": self._backend},
                )
        except Exception as exc:
            _log.exception("Whisper transcription failed: %s", exc)
            return VoiceResult(
                text="",
                confidence=0.0,
                language=self._config.language,
                audio_format=self._config.audio_format,
                metadata={"provider": "whisper", "backend": self._backend},
            )

    def transcribe_chunk(self, audio_chunk: bytes) -> VoiceResult:
        """
        Process a streaming audio chunk.

        Buffers chunks internally. Call transcribe_buffer() to flush.

        Args:
            audio_chunk: Audio bytes from a stream.

        Returns:
            VoiceResult (may be empty if buffering mode is active).
        """
        self.add_chunk(audio_chunk)
        return VoiceResult(
            text="",
            confidence=0.0,
            language=self._config.language,
            audio_format=self._config.audio_format,
            metadata={"provider": "whisper", "backend": self._backend},
        )

    def transcribe_buffer(self) -> VoiceResult:
        """
        Transcribe all buffered audio chunks.

        Clears the buffer after transcription.

        Returns:
            VoiceResult from combined buffered audio.
        """
        audio_chunks = self.get_audio_chunks()
        if not audio_chunks:
            return VoiceResult(
                text="",
                confidence=0.0,
                language=self._config.language,
                audio_format=self._config.audio_format,
                metadata={"provider": "whisper", "backend": self._backend},
            )
        combined = b"".join(audio_chunks)
        return self.transcribe(combined)

    def cleanup(self) -> None:
        """Release the Whisper model from memory."""
        if self._model is not None:
            del self._model
            self._model = None
            self._model_loaded = False
            self._backend = "unavailable"
            _log.info("Whisper model unloaded")

    def close(self) -> None:
        """Release provider resources."""
        self.cleanup()

    @staticmethod
    def _bytes_to_np(audio_bytes: bytes) -> Any:
        """Convert PCM 16-bit audio bytes to a float32 numpy array."""
        import numpy as np

        int16_data = np.frombuffer(audio_bytes, dtype=np.int16)
        float32_data = int16_data.astype(np.float32) / 32768.0
        return float32_data


__all__ = ["WhisperAdapter"]
