"""Tests for kairon_voice — mock all external APIs."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from kairon_voice.interfaces import (
    BaseVoiceInput,
    BaseVoiceOutput,
    VoiceConfig,
    VoiceInputProvider,
    VoiceOutputProvider,
    VoiceResult,
)
from kairon_voice.stt import STTProviderFactory, WhisperAdapter
from kairon_voice.tts import (
    AzureTTSAdapter,
    ElevenLabsAdapter,
    GoogleTTSAdapter,
    TTSProviderFactory,
)

# =============================================================================
# interfaces
# =============================================================================


class TestVoiceResult:
    def test_default_values(self) -> None:
        result = VoiceResult(text="hello")
        assert result.text == "hello"
        assert result.confidence == 0.0
        assert result.duration_seconds == 0.0
        assert result.language is None
        assert result.audio_format == "pcm"
        assert result.metadata == {}

    def test_full_values(self) -> None:
        result = VoiceResult(
            text="hello world",
            confidence=0.95,
            duration_seconds=3.2,
            language="en",
            audio_format="wav",
            metadata={"source": "test"},
        )
        assert result.text == "hello world"
        assert result.confidence == 0.95
        assert result.duration_seconds == 3.2
        assert result.language == "en"
        assert result.metadata["source"] == "test"

    def test_confidence_bounds(self) -> None:
        """Confidence must be between 0.0 and 1.0."""
        with pytest.raises(Exception):
            VoiceResult(text="x", confidence=1.5)
        with pytest.raises(Exception):
            VoiceResult(text="x", confidence=-0.1)


class TestVoiceConfig:
    def test_minimal(self) -> None:
        cfg = VoiceConfig(provider_type="whisper")
        assert cfg.provider_type == "whisper"
        assert cfg.language == "en"
        assert cfg.sample_rate == 16000
        assert cfg.local_only is True
        assert cfg.timeout_seconds == 30.0

    def test_full(self) -> None:
        cfg = VoiceConfig(
            provider_type="google",
            language="zh",
            model_name="large-v3",
            metadata={"region": "eastus"},
        )
        assert cfg.language == "zh"
        assert cfg.model_name == "large-v3"
        assert cfg.metadata["region"] == "eastus"


class TestBaseVoiceInput:
    def test_transcribe_returns_empty(self) -> None:
        inp = BaseVoiceInput()
        result = inp.transcribe(b"dummy audio")
        assert result.text == ""
        assert result.confidence == 0.0

    def test_get_audio_chunks(self) -> None:
        inp = BaseVoiceInput()
        inp.add_chunk(b"chunk1")
        inp.add_chunk(b"chunk2")
        chunks = inp.get_audio_chunks()
        assert chunks == [b"chunk1", b"chunk2"]
        # Buffer cleared after get
        assert inp.get_audio_chunks() == []

    def test_close(self) -> None:
        inp = BaseVoiceInput()
        inp.close()  # no-op


class TestBaseVoiceOutput:
    def test_synthesize_returns_empty(self) -> None:
        out = BaseVoiceOutput()
        assert out.synthesize("hello") == b""

    def test_stream_audio_silently_succeeds(self) -> None:
        out = BaseVoiceOutput()
        out.stream_audio(b"fake audio")

    def test_close(self) -> None:
        out = BaseVoiceOutput()
        out.close()


# =============================================================================
# STT
# =============================================================================


class TestWhisperAdapter:
    def test_transcribe_when_unavailable(self, monkeypatch) -> None:
        """When whisper is not importable, returns empty result gracefully."""
        import kairon_voice.stt as stt_mod

        monkeypatch.setattr(stt_mod, "WhisperAvailable", False)
        adapter = WhisperAdapter(VoiceConfig(provider_type="whisper"))
        result = adapter.transcribe(b"fake audio")
        assert result.text == ""
        assert result.metadata["backend"] == "unavailable"

    def test_transcribe_chunk_buffers(self) -> None:
        import kairon_voice.stt as stt_mod

        # Ensure whisper is marked unavailable so we don't try to load models
        stt_mod.WhisperAvailable = False
        try:
            adapter = WhisperAdapter(VoiceConfig(provider_type="whisper"))
            result = adapter.transcribe_chunk(b"chunk1")
            assert result.text == ""  # chunk mode returns empty
            # Buffer should now contain the chunk
            chunks = adapter.get_audio_chunks()
            assert len(chunks) == 1
            assert chunks[0] == b"chunk1"
        finally:
            stt_mod.WhisperAvailable = True

    def test_transcribe_buffer_when_empty(self) -> None:
        import kairon_voice.stt as stt_mod

        stt_mod.WhisperAvailable = False
        try:
            adapter = WhisperAdapter(VoiceConfig(provider_type="whisper"))
            result = adapter.transcribe_buffer()
            assert result.text == ""
        finally:
            stt_mod.WhisperAvailable = True

    def test_bytes_to_np(self) -> None:
        """_bytes_to_np converts PCM16 to float32."""
        import kairon_voice.stt as stt_mod
        import numpy as np

        stt_mod.WhisperAvailable = False
        try:
            adapter = WhisperAdapter()
            # 4 bytes = 2 int16 samples
            pcm = np.array([1000, 2000], dtype=np.int16).tobytes()
            result = adapter._bytes_to_np(pcm)
            assert hasattr(result, "dtype")
        finally:
            stt_mod.WhisperAvailable = True

    def test_cleanup_releases_model(self) -> None:
        import kairon_voice.stt as stt_mod

        stt_mod.WhisperAvailable = False
        try:
            adapter = WhisperAdapter()
            adapter.cleanup()
            assert adapter._model is None
            assert adapter._model_loaded is False
        finally:
            stt_mod.WhisperAvailable = True


class TestSTTProviderFactory:
    def test_create_whisper_returns_WhisperAdapter(self) -> None:
        factory = STTProviderFactory()
        provider = factory.create("whisper")
        assert isinstance(provider, WhisperAdapter)

    def test_create_google_returns_BaseVoiceInput(self) -> None:
        factory = STTProviderFactory()
        provider = factory.create("google")
        assert isinstance(provider, BaseVoiceInput)

    def test_create_azure_returns_BaseVoiceInput(self) -> None:
        factory = STTProviderFactory()
        provider = factory.create("azure")
        assert isinstance(provider, BaseVoiceInput)

    def test_unknown_provider_raises(self) -> None:
        factory = STTProviderFactory()
        with pytest.raises(ValueError, match="Unknown STT provider"):
            factory.create("nonexistent")

    def test_register_custom_provider(self) -> None:
        factory = STTProviderFactory()

        def custom_factory(config: VoiceConfig) -> VoiceInputProvider:
            return BaseVoiceInput(config)

        factory.register("custom-stt", custom_factory)
        provider = factory.create("custom-stt")
        assert isinstance(provider, BaseVoiceInput)


# =============================================================================
# TTS
# =============================================================================


class TestElevenLabsAdapter:
    def test_synthesize_no_api_key_returns_empty(self) -> None:
        """Without ELEVENLABS_API_KEY, returns empty bytes."""
        adapter = ElevenLabsAdapter()
        # Ensure no env var leaks
        with patch.dict(os.environ, {}, clear=True):
            result = adapter.synthesize("hello")
            assert result == b""

    @patch("urllib.request.urlopen")
    def test_synthesize_with_api_key(self, mock_urlopen: MagicMock) -> None:
        """With API key set, makes HTTP request."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"fake-mp3-audio"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=True):
            adapter = ElevenLabsAdapter()
            result = adapter.synthesize("hello world")
            assert result == b"fake-mp3-audio"

    @patch("urllib.request.urlopen")
    def test_synthesize_handles_http_error(self, mock_urlopen: MagicMock) -> None:
        """HTTP errors return empty bytes."""
        mock_urlopen.side_effect = Exception("Connection refused")

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=True):
            adapter = ElevenLabsAdapter()
            result = adapter.synthesize("hello")
            assert result == b""

    @patch("subprocess.run")
    def test_stream_audio_plays(self, mock_run: MagicMock) -> None:
        adapter = ElevenLabsAdapter()
        adapter.stream_audio(b"fake audio")
        mock_run.assert_called_once()


class TestGoogleTTSAdapter:
    def test_synthesize_no_client_returns_empty(self) -> None:
        """Without google-cloud-texttospeech installed, returns empty."""
        adapter = GoogleTTSAdapter()
        result = adapter.synthesize("hello")
        assert result == b""

    def test_get_client_import_error(self) -> None:
        adapter = GoogleTTSAdapter()
        # Mock the import to fail
        with patch("builtins.__import__", side_effect=ImportError):
            client = adapter._get_client()
            assert client is None

    @patch("subprocess.run")
    def test_stream_audio_plays(self, mock_run: MagicMock) -> None:
        adapter = GoogleTTSAdapter()
        adapter.stream_audio(b"fake audio")
        mock_run.assert_called_once()


class TestAzureTTSAdapter:
    def test_synthesize_no_key_returns_empty(self) -> None:
        """Without AZURE_SPEECH_KEY, returns empty bytes."""
        adapter = AzureTTSAdapter()
        with patch.dict(os.environ, {}, clear=True):
            result = adapter.synthesize("hello")
            assert result == b""

    @patch("urllib.request.urlopen")
    def test_synthesize_with_key(self, mock_urlopen: MagicMock) -> None:
        """With key set, makes HTTP request to Azure."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"fake-mp3-audio"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.dict(
            os.environ,
            {"AZURE_SPEECH_KEY": "test-key", "AZURE_SPEECH_REGION": "eastus"},
            clear=True,
        ):
            adapter = AzureTTSAdapter()
            result = adapter.synthesize("hello world")
            assert result == b"fake-mp3-audio"

    @patch("urllib.request.urlopen")
    def test_synthesize_handles_http_error(self, mock_urlopen: MagicMock) -> None:
        """HTTP errors return empty bytes."""
        mock_urlopen.side_effect = Exception("Connection refused")

        with patch.dict(os.environ, {"AZURE_SPEECH_KEY": "test-key"}, clear=True):
            adapter = AzureTTSAdapter()
            result = adapter.synthesize("hello")
            assert result == b""

    @patch("subprocess.run")
    def test_stream_audio_plays(self, mock_run: MagicMock) -> None:
        adapter = AzureTTSAdapter()
        adapter.stream_audio(b"fake audio")
        mock_run.assert_called_once()


class TestTTSProviderFactory:
    def test_create_elevenlabs(self) -> None:
        factory = TTSProviderFactory()
        provider = factory.create("elevenlabs")
        assert isinstance(provider, ElevenLabsAdapter)

    def test_create_google(self) -> None:
        factory = TTSProviderFactory()
        provider = factory.create("google")
        assert isinstance(provider, GoogleTTSAdapter)

    def test_create_azure(self) -> None:
        factory = TTSProviderFactory()
        provider = factory.create("azure")
        assert isinstance(provider, AzureTTSAdapter)

    def test_unknown_provider_raises(self) -> None:
        factory = TTSProviderFactory()
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            factory.create("nonexistent")

    def test_register_custom_provider(self) -> None:
        factory = TTSProviderFactory()

        def custom_factory(config: VoiceConfig) -> VoiceOutputProvider:
            return BaseVoiceOutput(config)

        factory.register("custom-tts", custom_factory)
        provider = factory.create("custom-tts")
        assert isinstance(provider, BaseVoiceOutput)
