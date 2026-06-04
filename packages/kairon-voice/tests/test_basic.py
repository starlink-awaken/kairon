"""Basic tests for kairon-voice package."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kairon_voice import (
    AzureTTSAdapter,
    BaseVoiceInput,
    BaseVoiceOutput,
    ElevenLabsAdapter,
    GoogleTTSAdapter,
    STTProviderFactory,
    TTSProviderFactory,
    VoiceConfig,
    VoiceResult,
    WhisperAdapter,
)
from kairon_voice.voice_recognition import LanguageCode, RecognitionConfig, RecognitionResult


class TestKaironVoiceBasic:
    """Core functionality and edge case tests."""

    def test_import(self):
        """All expected exports are importable."""
        assert AzureTTSAdapter is not None
        assert BaseVoiceInput is not None
        assert BaseVoiceOutput is not None
        assert ElevenLabsAdapter is not None
        assert GoogleTTSAdapter is not None
        assert STTProviderFactory is not None
        assert TTSProviderFactory is not None
        assert VoiceConfig is not None
        assert VoiceResult is not None
        assert WhisperAdapter is not None
        assert LanguageCode is not None
        assert RecognitionConfig is not None
        assert RecognitionResult is not None

    def test_voice_config_defaults(self):
        """VoiceConfig has sensible defaults."""
        cfg = VoiceConfig(provider_type="test")
        assert cfg.provider_type == "test"
        assert cfg.language == "en"
        assert cfg.sample_rate == 16000
        assert cfg.timeout_seconds == 30.0

    def test_voice_result_empty_text(self):
        """VoiceResult with empty text."""
        result = VoiceResult(text="")
        assert result.text == ""
        assert result.confidence == 0.0
        assert result.language is None

    def test_base_voice_input_add_get_chunks_empty(self):
        """BaseVoiceInput add/get chunk with no data."""
        inp = BaseVoiceInput()
        assert inp.get_audio_chunks() == []
        inp.add_chunk(b"")
        assert inp.get_audio_chunks() == [b""]

    def test_whisper_adapter_transcribe_when_unavailable(self):
        """WhisperAdapter returns empty result when unavailable."""
        import kairon_voice.stt as stt_mod

        stt_mod.WhisperAvailable = False
        try:
            adapter = WhisperAdapter(VoiceConfig(provider_type="whisper"))
            result = adapter.transcribe(b"")
            assert result.text == ""
            assert result.metadata.get("backend") == "unavailable"
        finally:
            stt_mod.WhisperAvailable = True
