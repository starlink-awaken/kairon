"""TTS (Text-to-Speech) — provider adapters and factory.

Supported providers: ElevenLabs (API), Google Cloud TTS, Azure Speech Services.
All external dependencies are optional — adapters degrade to empty audio when
credentials or libraries are unavailable.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from .interfaces import BaseVoiceOutput, VoiceConfig, VoiceOutputProvider
from typing import Any

_log = logging.getLogger(__name__)


# ============================================================================
# Adapters
# ============================================================================


def _play_audio(audio_data: bytes, suffix: str) -> None:
    """Play audio using the system audio player (afplay on macOS, aplay on Linux)."""
    if not audio_data:
        return
    try:
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
            fh.write(audio_data)
            tmp_path = fh.name

        try:
            subprocess.run(
                ["afplay" if os.uname().sysname == "Darwin" else "aplay", tmp_path],
                capture_output=True,
                timeout=60,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as exc:
        _log.warning("Audio playback failed: %s", exc)


class ElevenLabsAdapter(BaseVoiceOutput):
    """ElevenLabs TTS adapter.

    Requires ELEVENLABS_API_KEY environment variable.
    Supports voice selection, model selection, and audio format options.
    """

    def __init__(self, config: VoiceConfig | None = None) -> None:
        super().__init__(config)
        self._api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        cfg = config
        self._voice_id = cfg.metadata.get("voice_id") if cfg else None
        self._model = cfg.metadata.get("model", "eleven_monolingual_v1") if cfg else "eleven_monolingual_v1"
        self._stability = cfg.metadata.get("stability", 0.5) if cfg else 0.5
        self._similarity_boost = cfg.metadata.get("similarity_boost", 0.75) if cfg else 0.75

    def synthesize(self, text: str) -> bytes:
        if not self._api_key:
            _log.warning("[ElevenLabsAdapter] ELEVENLABS_API_KEY not set, returning empty audio")
            return b""

        try:
            import json
            import urllib.request

            voice_id = self._voice_id or "21m00Tcm4TlvDq8ikWAM"
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

            payload = json.dumps(
                {
                    "text": text,
                    "model_id": self._model,
                    "voice_settings": {
                        "stability": self._stability,
                        "similarity_boost": self._similarity_boost,
                    },
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": self._api_key,
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self._config.timeout_seconds) as resp:
                return resp.read()

        except Exception as exc:
            _log.warning("[ElevenLabsAdapter] Synthesis failed: %s", exc)
            return b""

    def stream_audio(self, audio_data: bytes) -> None:
        """Stream audio to output device using simple playback."""
        _play_audio(audio_data, suffix=".mp3")


class GoogleTTSAdapter(BaseVoiceOutput):
    """Google Cloud Text-to-Speech adapter.

    Requires google-cloud-texttospeech package and GOOGLE_APPLICATION_CREDENTIALS
    or valid credentials configured.
    """

    def __init__(self, config: VoiceConfig | None = None) -> None:
        super().__init__(config)
        cfg = config
        self._language_code = cfg.language if cfg else "en-US"
        self._voice_name = cfg.metadata.get("voice_name") if cfg else "en-US-Neural2-J"
        self._speaking_rate = cfg.metadata.get("speaking_rate", 1.0) if cfg else 1.0
        self._sample_rate = cfg.sample_rate if cfg else 16000
        self._client = None  # type: Any | None

    def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        try:
            _gcp = __import__("google.cloud.texttospeech", fromlist=["TextToSpeechClient"])
            self._client = _gcp.TextToSpeechClient()
            return self._client
        except ImportError:
            _log.warning("[GoogleTTSAdapter] google-cloud-texttospeech not installed")
            return None
        except Exception as exc:
            _log.warning("[GoogleTTSAdapter] Failed to create client: %s", exc)
            return None

    def synthesize(self, text: str) -> bytes:
        client = self._get_client()
        if client is None:
            return b""

        try:
            _gcp = __import__(
                "google.cloud.texttospeech",
                fromlist=["SynthesisInput", "VoiceSelectionParams", "AudioConfig", "AudioEncoding"],
            )
            synthesis_input = _gcp.SynthesisInput(text=text)
            voice = _gcp.VoiceSelectionParams(
                language_code=self._language_code,
                name=self._voice_name,
            )
            audio_config = _gcp.AudioConfig(
                audio_encoding=_gcp.AudioEncoding.LINEAR16,
                speaking_rate=self._speaking_rate,
                sample_rate_hertz=self._sample_rate,
            )
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
            return response.audio_content

        except Exception as exc:
            _log.warning("[GoogleTTSAdapter] Synthesis failed: %s", exc)
            return b""

    def stream_audio(self, audio_data: bytes) -> None:
        """Stream audio to output device."""
        _play_audio(audio_data, suffix=".wav")


class AzureTTSAdapter(BaseVoiceOutput):
    """Azure Speech Services TTS adapter.

    Requires AZURE_SPEECH_KEY + AZURE_SPEECH_REGION environment variables.
    Uses the REST API (no SDK dependency).
    """

    def __init__(self, config: VoiceConfig | None = None) -> None:
        super().__init__(config)
        self._speech_key = os.environ.get("AZURE_SPEECH_KEY", "")
        self._region = os.environ.get("AZURE_SPEECH_REGION", "eastus")
        cfg = config
        self._voice_name = cfg.metadata.get("voice_name") if cfg else "en-US-JennyNeural"
        self._speaking_rate = cfg.metadata.get("speaking_rate", 0) if cfg else 0

    def synthesize(self, text: str) -> bytes:
        if not self._speech_key:
            _log.warning("[AzureTTSAdapter] AZURE_SPEECH_KEY not set, returning empty audio")
            return b""

        try:
            import urllib.request

            url = f"https://{self._region}.tts.speech.microsoft.com/cognitiveservices/v1"

            payload = f"<speak version='1.0' xml:lang='en-US'><voice name='{self._voice_name}'>{text}</voice></speak>"
            payload_bytes = payload.encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload_bytes,
                headers={
                    "Ocp-Apim-Subscription-Key": self._speech_key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self._config.timeout_seconds) as resp:
                return resp.read()

        except Exception as exc:
            _log.warning("[AzureTTSAdapter] Synthesis failed: %s", exc)
            return b""

    def stream_audio(self, audio_data: bytes) -> None:
        """Stream audio to output device."""
        _play_audio(audio_data, suffix=".mp3")


# ============================================================================
# Provider factory
# ============================================================================

_ProviderFactory = Callable[[VoiceConfig], VoiceOutputProvider]
_PROVIDER_REGISTRY: dict[str, _ProviderFactory] = {}


def _register_defaults() -> None:
    """Register built-in TTS adapter factories."""
    _PROVIDER_REGISTRY["elevenlabs"] = _ElevenLabsFactory
    _PROVIDER_REGISTRY["google"] = _GoogleFactory
    _PROVIDER_REGISTRY["azure"] = _AzureFactory


def _ElevenLabsFactory(config: VoiceConfig) -> VoiceOutputProvider:
    return ElevenLabsAdapter(config)


def _GoogleFactory(config: VoiceConfig) -> VoiceOutputProvider:
    return GoogleTTSAdapter(config)


def _AzureFactory(config: VoiceConfig) -> VoiceOutputProvider:
    return AzureTTSAdapter(config)


class TTSProviderFactory:
    """Factory for creating VoiceOutputProvider instances by provider type.

    Usage:
        factory = TTSProviderFactory()
        provider = factory.create("elevenlabs", config)
        audio_bytes = provider.synthesize("Hello world")
        provider.stream_audio(audio_bytes)
    """

    def __init__(self) -> None:
        _register_defaults()

    def register(
        self,
        provider_type: str,
        adapter_factory: _ProviderFactory,
    ) -> None:
        """Register a custom TTS adapter factory.

        Args:
            provider_type: Provider identifier (e.g. 'my-tts').
            adapter_factory: A callable returning a VoiceOutputProvider.
        """
        _PROVIDER_REGISTRY[provider_type] = adapter_factory
        _log.info(
            "Registered TTS provider: %s -> %s",
            provider_type,
            getattr(adapter_factory, "__name__", repr(adapter_factory)),
        )

    def create(
        self,
        provider_type: str,
        config: VoiceConfig | None = None,
    ) -> VoiceOutputProvider:
        """Create a VoiceOutputProvider instance.

        Args:
            provider_type: Provider name ('elevenlabs', 'google', 'azure').
            config: Optional VoiceConfig.

        Returns:
            A VoiceOutputProvider subclass instance.

        Raises:
            ValueError: If provider_type is not registered.
        """
        if not _PROVIDER_REGISTRY:
            _register_defaults()

        if provider_type not in _PROVIDER_REGISTRY:
            available = ", ".join(sorted(_PROVIDER_REGISTRY.keys()))
            raise ValueError(
                f"Unknown TTS provider '{provider_type}'. Available: {available}. Use register() to add a new provider."
            )
        factory = _PROVIDER_REGISTRY[provider_type]
        cfg = config or VoiceConfig(provider_type=provider_type)
        return factory(cfg)


__all__ = [
    "AzureTTSAdapter",
    "ElevenLabsAdapter",
    "GoogleTTSAdapter",
    "TTSProviderFactory",
]
