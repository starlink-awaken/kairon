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
# Voice Recognition ≡ Module
# 内涵 ≝ {Voice, Recognition}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, VoiceRecognition)}
# 功能 ⊢ {Voice_Recognition, Init_Voice, Validate_Recognition}
# =============================================================================

# ---
# domain: D-Voice
# layer: organ
# status: active
# version: 1.0.0
# ---
"""Voice Recognition Module — Whisper-based speech-to-text with multilingual support."""

import logging
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


class LanguageCode(StrEnum):
    """Supported language codes."""

    EN = "en"  # English
    ZH = "zh"  # Chinese
    JP = "ja"  # Japanese
    DE = "de"  # German
    FR = "fr"  # French
    ES = "es"  # Spanish
    AUTO = "auto"  # Auto-detect


@dataclass
class RecognitionResult:
    """Result of voice recognition."""

    text: str
    language: str
    confidence: float
    duration: float
    segments: list[dict]
    is_final: bool = True


@dataclass
class RecognitionConfig:
    """Configuration for voice recognition."""

    language: LanguageCode = LanguageCode.AUTO
    model_size: Literal["tiny", "base", "small", "medium", "large"] = "base"
    device: Literal["cpu", "cuda"] = "cpu"
    enable_timestamps: bool = True
    enable_punctuation: bool = True


class WhisperVoiceRecognizer:
    """Whisper-based voice recognizer with multilingual support.

    Features:
    1. Real-time speech-to-text
    2. Multi-language support (EN/ZH/JP/DE/FR/ES)
    3. Confidence scoring
    4. Timestamp alignment
    5. Streaming support (chunked processing)
    """

    SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}

    def __init__(self, config: RecognitionConfig | None = None) -> None:
        self.config = config or RecognitionConfig()
        self._model: Any = None
        self._is_initialized = False

    def initialize(self) -> bool:
        """Initialize the Whisper model."""
        try:
            import whisper

            logger.info("Loading Whisper model: %s (device=%s)", self.config.model_size, self.config.device)

            self._model = whisper.load_model(self.config.model_size, device=self.config.device)
            self._is_initialized = True
            logger.info("Whisper model loaded successfully")
            return True

        except ImportError:
            logger.error("Whisper not installed. Run: pip install openai-whisper")
            return False
        except (RuntimeError, OSError, ValueError) as e:
            logger.error("Failed to load Whisper model: %s", str(e))
            return False

    def recognize_file(self, audio_path: str | Path) -> RecognitionResult | None:
        """Recognize speech from an audio file."""
        if not self._is_initialized:
            if not self.initialize():
                return None

        audio_path = Path(audio_path)
        if audio_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            logger.error("Unsupported audio format: %s", audio_path.suffix)
            return None

        try:
            import time

            start_time = time.time()

            # Transcribe
            language = None if self.config.language == LanguageCode.AUTO else self.config.language.value

            result = self._model.transcribe(
                str(audio_path),
                language=language,
                task="transcribe",
                verbose=False,
            )

            duration = time.time() - start_time

            # Calculate confidence (average of segment probabilities)
            segments = result.get("segments", [])
            if segments:
                avg_confidence = sum(seg.get("avg_logprob", -1.0) for seg in segments) / len(segments)
                # Convert logprob to 0-1 scale
                confidence = max(0.0, min(1.0, 1.0 + avg_confidence))
            else:
                confidence = 0.0

            detected_language = result.get("language", "unknown")

            logger.info(
                "Recognition complete: lang=%s, confidence=%.2f, duration=%.2fs, text_len=%d",
                detected_language,
                confidence,
                duration,
                len(result["text"]),
            )

            return RecognitionResult(
                text=result["text"].strip(),
                language=detected_language,
                confidence=confidence,
                duration=duration,
                segments=[
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"],
                    }
                    for seg in segments
                ]
                if self.config.enable_timestamps
                else [],
            )

        except (RuntimeError, OSError, ValueError) as e:
            logger.error("Recognition failed: %s", str(e))
            return None

    def recognize_bytes(self, audio_bytes: bytes, format: str = "wav") -> RecognitionResult | None:
        """Recognize speech from audio bytes."""
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            result = self.recognize_file(temp_path)
            return result
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes."""
        return [lang.value for lang in LanguageCode if lang != LanguageCode.AUTO]


class VoiceIntentParser:
    """Parse voice text into structured intents."""

    def __init__(self) -> None:
        self._patterns = {
            "create_task": ["create", "add", "new", "启动", "创建"],
            "query_status": ["status", "check", "查询", "状态"],
            "execute_command": ["run", "execute", "执行", "运行"],
            "get_recommendation": ["recommend", "suggest", "建议", "推荐"],
        }

    def parse_intent(self, text: str) -> tuple[str, float]:
        """Parse intent from recognized text."""
        text_lower = text.lower()
        scores: dict[str, float] = {}

        for intent, keywords in self._patterns.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[intent] = score / len(keywords)

        if not scores:
            return "unknown", 0.0

        best_intent = max(scores, key=lambda k: scores[k])
        return best_intent, scores[best_intent]
