"""Tests for voice models — extracted from SharedBrain D_Voice."""

from agent_runtime.voice_models import LanguageCode, RecognitionConfig, RecognitionResult


def test_language_codes():
    assert LanguageCode.EN == "en"
    assert LanguageCode.ZH == "zh"
    assert LanguageCode.AUTO == "auto"


def test_recognition_result():
    r = RecognitionResult(text="hello", language="en", confidence=0.95, duration=1.5, segments=[])
    assert r.text == "hello"
    assert r.confidence == 0.95


def test_recognition_config_defaults():
    c = RecognitionConfig()
    assert c.language == LanguageCode.AUTO
    assert c.model_size == "base"
    assert c.device == "cpu"
