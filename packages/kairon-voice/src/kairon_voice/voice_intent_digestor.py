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
# Voice Intent Digestor ≡ Module
# 内涵 ≝ {Voice, Intent, Digestor}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, VoiceIntentDigestor)}
# 功能 ⊢ {Voice_Intent, Intent_Digestor, Digestor_Init}
# =============================================================================

# ---
# domain: D-Voice
# layer: intent
# status: active
# version: 1.0.0
# owner: '@Prime'
# authority: P6 voice I/O architecture
# ---
"""
Voice Intent Digestor — bridges voice transcription to the D-Execution IntentDigestor.

Transforms transcribed voice text into IntentParticle instances and routes them
through the existing D-Execution intent digestion pipeline.
"""

import logging
import re
from typing import Any, Protocol

from kairon_voice.interfaces.voice_io import VoiceResult, voice_perception_surface_contract

_log = logging.getLogger(__name__)


class _IntentDigestorProtocol(Protocol):
    def ingest(self, text: str, context: dict[str, Any] | None = None) -> Any: ...


def _voice_context_snapshot(context: dict[str, Any] | None) -> dict[str, Any]:
    """Return the explicit, testable voice context passed across the boundary."""
    ctx = context or {}
    snapshot = {
        "session_id": str(ctx.get("session_id", "")),
        "controller_session_id": str(ctx.get("controller_session_id", "")),
        "controller_node_id": str(ctx.get("controller_node_id", "")),
        "control_plane": str(ctx.get("control_plane", "voice")),
        "owner_id": str(ctx.get("owner_id", "")),
        "hive_id": str(ctx.get("hive_id", "")),
        "device_id": str(ctx.get("device_id", "")),
        "twin_id": str(ctx.get("twin_id", "")),
        "source": str(ctx.get("source", "")),
        "surface_role": "voice",
        "surface_classification": "perception",
    }
    return snapshot


class VoiceIntentDigestor:
    """
    Converts voice transcription results into IntentParticles.

    Provides a lightweight layer between the voice system and the
    D-Execution IntentDigestor. Supports:
    - Direct ingestion into IntentDigestor
    - Voice-specific intent patterns (commands, queries, confirmations)
    - Context enrichment with audio metadata
    """

    # Voice command patterns for fast-path routing
    COMMAND_PATTERNS: list[tuple[str, re.Pattern, str]] = [
        ("stop", re.compile(r"^(stop|cancel|abort|never mind)[.!?]?$", re.I), "voice.cancel"),
        ("confirm", re.compile(r"^(yes|yeah|yep|sure|confirm|ok|okay|go ahead)[.!?]?$", re.I), "voice.confirm"),
        ("deny", re.compile(r"^(no|nope|nah|cancel|wait|hold on)[.!?]?$", re.I), "voice.deny"),
        ("help", re.compile(r"^(help|what can you do|assist|support)[.!?]?$", re.I), "voice.help"),
        ("repeat", re.compile(r"^(repeat|say again|what|repeat that|come again)[.!?]?$", re.I), "voice.repeat"),
        ("start_over", re.compile(r"^(start over|reset|begin again|from the top)[.!?]?$", re.I), "voice.reset"),
    ]

    def __init__(self, intent_digestor: _IntentDigestorProtocol | None = None) -> None:
        """
        Initialize VoiceIntentDigestor.

        Args:
            intent_digestor: Optional D-Execution IntentDigestor instance.
                             If None, a new instance is created lazily.
        """
        self._digestor = intent_digestor
        self._lazy_load_digestor()

    def _lazy_load_digestor(self) -> None:
        """Lazily instantiate the D-Execution IntentDigestor."""
        if self._digestor is not None:
            return
        try:
            Digestor = __import__(
                "organs.D_Execution.organs.intent_digestor",
                fromlist=["IntentDigestor"],
            ).IntentDigestor
            self._digestor = Digestor()
            _log.info("[VoiceIntentDigestor] D-Execution IntentDigestor connected")
        except ImportError as exc:
            _log.warning("[VoiceIntentDigestor] Could not load IntentDigestor: %s", exc)
            self._digestor = None

    # ─── Core conversion ──────────────────────────────────────────────────

    def digest(
        self,
        voice_result: VoiceResult,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Convert a VoiceResult into a structured intent dict.

        Pipeline:
        1. Classify voice command pattern (fast path)
        2. Route to IntentDigestor for full particle creation
        3. Enrich with voice metadata

        Args:
            voice_result: VoiceResult from STT transcription.
            context: Optional additional context (session id, device, etc.).

        Returns:
            Dict with intent classification, particle data, and routing hints.
        """
        ctx = dict(context or {})
        context_snapshot = _voice_context_snapshot(ctx)
        surface = voice_perception_surface_contract(
            session_id=context_snapshot["session_id"],
            owner_id=context_snapshot["owner_id"],
            metadata={
                key: ctx[key] for key in ("source", "device_id", "channel") if key in ctx and ctx[key] not in (None, "")
            },
        ).to_dict()
        text = voice_result.text.strip()
        if not text:
            return {
                "intent": None,
                "classification": "empty",
                "particle": None,
                "surface": surface,
                "context_snapshot": context_snapshot,
            }

        # Step 1: Fast-path voice command classification
        for cmd_name, pattern, capability in self.COMMAND_PATTERNS:
            if pattern.match(text):
                _log.info("[VoiceIntentDigestor] Fast-path command: %s", cmd_name)
                return {
                    "intent": text,
                    "classification": "voice_command",
                    "command_type": cmd_name,
                    "capability": capability,
                    "confidence": voice_result.confidence,
                    "particle": None,
                    "surface": surface,
                    "context_snapshot": context_snapshot,
                }

        # Step 2: Full ingestion through IntentDigestor
        ctx.update(
            {
                "voice_language": voice_result.language,
                "voice_duration_s": voice_result.duration_seconds,
                "voice_confidence": voice_result.confidence,
                "voice_audio_format": voice_result.audio_format,
            }
        )

        if self._digestor is not None:
            try:
                particle = self._digestor.ingest(text, context=ctx)
                _log.info("[VoiceIntentDigestor] Particle created: %s", particle.id)
                return {
                    "intent": particle.intent,
                    "classification": "full_intent",
                    "particle": particle,
                    "particle_id": particle.id,
                    "raw_text": text,
                    "metadata": {
                        "language": voice_result.language,
                        "confidence": voice_result.confidence,
                        "duration_s": voice_result.duration_seconds,
                    },
                    "surface": surface,
                    "context_snapshot": context_snapshot,
                }
            except Exception as exc:
                _log.warning("[VoiceIntentDigestor] Digestor error: %s", exc)

        # Step 3: Fallback — basic intent when digestor unavailable
        particle_id = f"VOICE-{text[:20].replace(' ', '-').upper()}"
        return {
            "intent": text,
            "classification": "basic_intent",
            "particle_id": particle_id,
            "raw_text": text,
            "metadata": {
                "language": voice_result.language,
                "confidence": voice_result.confidence,
                "duration_s": voice_result.duration_seconds,
            },
            "surface": surface,
            "context_snapshot": context_snapshot,
        }

    def ingest(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """
        Ingest plain text as voice input and return an IntentParticle.

        Convenience method that creates a VoiceResult from text and digests it.
        Returns the IntentParticle directly (for compatibility with D-Execution).

        Args:
            text: Transcribed text.
            context: Optional context dict.

        Returns:
            IntentParticle instance (or fallback object with id/intent fields).
        """
        result = VoiceResult(
            text=text,
            confidence=1.0,
            duration_seconds=0.0,
            language=context.get("language") if context else None,
        )
        parsed = self.digest(result, context)

        if parsed.get("particle") is not None:
            return parsed["particle"]

        # Fallback: create a minimal intent-like object
        import uuid

        class FallbackParticle:
            def __init__(self, text: str) -> None:
                self.id = f"VOICE-{uuid.uuid4().hex[:8].upper()}"
                self.intent = text
                self.stage = "ingested"
                self.text = text
                self.particle_type = "voice_intent"
                self.required_capabilities = ["general"]
                self.estimated_eu = 0.5
                self.dependencies: list[str] = []
                self.context_snapshot = context or {}

        return FallbackParticle(text)

    # ─── Batch processing ─────────────────────────────────────────────────

    def digest_batch(
        self,
        voice_results: list[VoiceResult],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Process multiple VoiceResults in sequence.

        Args:
            voice_results: List of VoiceResult instances.
            context: Shared context for all results.

        Returns:
            List of intent dicts, one per VoiceResult.
        """
        return [self.digest(result, context) for result in voice_results]


__all__ = ["VoiceIntentDigestor"]
