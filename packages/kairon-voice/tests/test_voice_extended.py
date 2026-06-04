"""Extended tests: voice_recognition, voice_intent_digestor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Voice Recognition ───────────────────────────────────────

from kairon_voice.voice_recognition import (
    LanguageCode,
    RecognitionConfig,
    RecognitionResult,
    VoiceIntentParser,
    WhisperVoiceRecognizer,
)


class TestLanguageCode:
    def test_values(self):
        assert LanguageCode.EN == "en"
        assert LanguageCode.ZH == "zh"
        assert LanguageCode.JP == "ja"
        assert LanguageCode.AUTO == "auto"

    def test_is_str_enum(self):
        assert isinstance(LanguageCode.EN, str)


class TestRecognitionConfig:
    def test_defaults(self):
        cfg = RecognitionConfig()
        assert cfg.language == LanguageCode.AUTO
        assert cfg.model_size == "base"
        assert cfg.device == "cpu"
        assert cfg.enable_timestamps is True

    def test_custom(self):
        cfg = RecognitionConfig(language=LanguageCode.ZH, model_size="large", device="cuda")
        assert cfg.language == LanguageCode.ZH
        assert cfg.model_size == "large"
        assert cfg.device == "cuda"


class TestRecognitionResult:
    def test_fields(self):
        r = RecognitionResult(text="hello world", language="en", confidence=0.95,
                              duration=3.2, segments=[], is_final=True)
        assert r.text == "hello world"
        assert r.confidence == 0.95


class TestWhisperVoiceRecognizer:
    def test_init_defaults(self):
        r = WhisperVoiceRecognizer()
        assert r.config.model_size == "base"
        assert r._is_initialized is False

    def test_initialize_import_error(self):
        r = WhisperVoiceRecognizer()
        with patch("builtins.__import__", side_effect=ImportError("no whisper")):
            result = r.initialize()
            assert result is False
            assert r._is_initialized is False

    def test_recognize_file_not_initialized(self):
        r = WhisperVoiceRecognizer()
        with patch.object(r, "initialize", return_value=False):
            result = r.recognize_file("test.wav")
            assert result is None

    def test_recognize_file_unsupported_format(self):
        r = WhisperVoiceRecognizer()
        r._is_initialized = True
        result = r.recognize_file("test.txt")
        assert result is None

    def test_get_supported_languages(self):
        r = WhisperVoiceRecognizer()
        langs = r.get_supported_languages()
        assert "en" in langs
        assert "zh" in langs
        assert "auto" not in langs


class TestVoiceIntentParser:
    def test_parse_create_task(self):
        parser = VoiceIntentParser()
        intent, score = parser.parse_intent("create a new task")
        assert intent == "create_task"
        assert score > 0

    def test_parse_query_status(self):
        parser = VoiceIntentParser()
        intent, score = parser.parse_intent("status check")
        assert intent == "query_status"
        assert score > 0

    def test_parse_unknown(self):
        parser = VoiceIntentParser()
        intent, score = parser.parse_intent("something completely different")
        assert intent == "unknown"
        assert score == 0.0


# ── Voice Intent Digestor ──────────────────────────────────

from kairon_voice.voice_intent_digestor import VoiceIntentDigestor, _voice_context_snapshot
from kairon_voice.interfaces.voice_io import VoiceResult


class TestVoiceContextSnapshot:
    def test_empty_context(self):
        snap = _voice_context_snapshot(None)
        assert snap["session_id"] == ""
        assert snap["surface_role"] == "voice"

    def test_with_context(self):
        snap = _voice_context_snapshot({"session_id": "sess-1", "owner_id": "owner-1"})
        assert snap["session_id"] == "sess-1"
        assert snap["owner_id"] == "owner-1"


class TestVoiceIntentDigestor:
    def test_init_no_digestor(self):
        v = VoiceIntentDigestor(intent_digestor=None)
        assert v._digestor is None

    def test_init_with_mock_digestor(self):
        mock_d = MagicMock()
        v = VoiceIntentDigestor(intent_digestor=mock_d)
        assert v._digestor is mock_d

    def test_digest_empty_text(self):
        v = VoiceIntentDigestor(intent_digestor=MagicMock())
        result = v.digest(VoiceResult(text=""))
        assert result["classification"] == "empty"
        assert result["intent"] is None

    def test_digest_fast_path_stop(self):
        v = VoiceIntentDigestor(intent_digestor=MagicMock())
        result = v.digest(VoiceResult(text="stop"))
        assert result["classification"] == "voice_command"
        assert result["command_type"] == "stop"

    def test_digest_fast_path_confirm(self):
        v = VoiceIntentDigestor(intent_digestor=MagicMock())
        result = v.digest(VoiceResult(text="yes"))
        assert result["classification"] == "voice_command"
        assert result["command_type"] == "confirm"

    def test_digest_fast_path_deny(self):
        v = VoiceIntentDigestor(intent_digestor=MagicMock())
        result = v.digest(VoiceResult(text="no"))
        assert result["classification"] == "voice_command"

    def test_digest_fast_path_help(self):
        v = VoiceIntentDigestor(intent_digestor=MagicMock())
        result = v.digest(VoiceResult(text="help"))
        assert result["classification"] == "voice_command"
        assert result["command_type"] == "help"

    def test_digest_full_intent_with_digestor(self):
        mock_d = MagicMock()
        mock_particle = MagicMock()
        mock_particle.intent = "test intent"
        mock_particle.id = "PARTICLE-001"
        mock_d.ingest.return_value = mock_particle
        v = VoiceIntentDigestor(intent_digestor=mock_d)
        result = v.digest(VoiceResult(text="create a task", confidence=0.9))
        assert result["classification"] == "full_intent"
        assert result["particle_id"] == "PARTICLE-001"

    def test_digest_fallback_basic_intent(self):
        v = VoiceIntentDigestor(intent_digestor=None)
        result = v.digest(VoiceResult(text="hello world", confidence=0.8))
        assert result["classification"] == "basic_intent"
        assert result["particle_id"].startswith("VOICE-")

    def test_ingest_returns_fallback_particle(self):
        v = VoiceIntentDigestor(intent_digestor=None)
        particle = v.ingest("test voice input")
        assert hasattr(particle, "id")
        assert hasattr(particle, "intent")
        assert particle.intent == "test voice input"

    def test_ingest_with_mock_digestor(self):
        mock_d = MagicMock()
        mock_particle = MagicMock()
        mock_particle.intent = "processed"
        mock_particle.id = "P-001"
        mock_d.ingest.return_value = mock_particle
        v = VoiceIntentDigestor(intent_digestor=mock_d)
        particle = v.ingest("hello", {"language": "en"})
        assert particle.intent == "processed"

    def test_digest_batch(self):
        mock_d = MagicMock()
        v = VoiceIntentDigestor(intent_digestor=mock_d)
        results = v.digest_batch([
            VoiceResult(text="stop"),
            VoiceResult(text="hello", confidence=0.5),
        ])
        assert len(results) == 2
        assert results[0]["classification"] == "voice_command"
