from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Summary: Cross-device session persistence with signature verification
Authority: organs/D-Continuity/AGENTS.md
---
"""


import hashlib
import hmac
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# SessionStore ≡ Session_Persistence
# 内涵 ≝ {Serialize, Deserialize, Sign, Verify}
# 外延 ≝ {s | s ∈ D-Continuity ∧ persists(s, Session)}
# 功能 ⊢ {Save_Session, Restore_Session, Sign_Session, Verify_Session}
# =============================================================================


@dataclass
class SessionState:
    """Session state container for cross-device persistence."""

    session_id: str
    device_id: str
    twin_id: str
    created_at: str
    last_active: str
    version: int
    context: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, Any] = field(default_factory=dict)
    emotion_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state to a plain dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Deserialize a plain dict back into SessionState."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SessionContinuityArtifact:
    """Explicit continuity contract for persisted session state."""

    artifact_type: str
    scope: str
    owner_id: str
    session_id: str
    twin_id: str
    integrity: dict[str, Any] = field(default_factory=dict)
    status: str = "explicit"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SignatureError(Exception):
    """Raised when session signature verification fails."""

    pass


class SessionStore:
    """
    Cross-device session persistence manager.

    Features:
    1. JSON-based session serialization/deserialization
    2. HMAC-SHA256 signature for integrity and authenticity
    3. Thread-safe atomic save/restore operations
    4. Configurable storage backend (file-based by default)
    """

    SIGNATURE_VERSION = 1
    SIGNATURE_ALGORITHM = "sha256"

    def __init__(
        self,
        storage_dir: str = ".sessions",
        signature_key: bytes | None = None,
    ) -> None:
        self.metadata_path = "eidos/session_store.py"
        self.organ_name = "session_store"
        self.organ_id = f"eidos-{id(self):x}"
        self._status = "active"
        self._metabolic_budget = 1000.0
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._signature_key = signature_key or b"default-dev-key-replace-in-production"
        self._lock = __import__("threading").Lock()

    # --------------------------------------------------------------------------
    # Signature helpers
    # --------------------------------------------------------------------------

    def _sign(self, payload: str) -> str:
        """Generate HMAC-SHA256 signature for a payload string."""
        return hmac.new(
            self._signature_key,
            payload.encode("utf-8"),
            digestmod=self.SIGNATURE_ALGORITHM,
        ).hexdigest()

    def _build_signable(self, state: SessionState) -> str:
        """Build deterministic string for signing (excludes signature itself)."""
        data = {
            "session_id": state.session_id,
            "device_id": state.device_id,
            "twin_id": state.twin_id,
            "created_at": state.created_at,
            "last_active": state.last_active,
            "version": state.version,
            "context": state.context,
            "memory": state.memory,
            "preferences": state.preferences,
            "emotion_state": state.emotion_state,
        }
        return json.dumps(data, sort_keys=True, default=str)

    def _compute_checksum(self, state: SessionState) -> str:
        """Compute SHA256 checksum of serialized session for integrity."""
        data = state.to_dict()
        metadata = dict(data.get("metadata") or {})
        metadata.pop("_continuity", None)
        data["metadata"] = metadata
        payload = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _build_continuity_artifact(
        self,
        state: SessionState,
        *,
        checksum: str,
        signed: bool,
        verified: bool = False,
        storage_path: str | None = None,
        status: str = "explicit",
    ) -> SessionContinuityArtifact:
        owner_id = str(state.metadata.get("owner_id") or state.twin_id)
        integrity = {
            "checksum": checksum,
            "signed": signed,
            "verified": verified,
        }
        if storage_path:
            integrity["storage_path"] = storage_path
        return SessionContinuityArtifact(
            artifact_type="session_state",
            scope="session",
            owner_id=owner_id,
            session_id=state.session_id,
            twin_id=state.twin_id,
            integrity=integrity,
            status=status,
        )

    # --------------------------------------------------------------------------
    # Core operations
    # --------------------------------------------------------------------------

    def save(
        self,
        session: SessionState,
        sign: bool = True,
    ) -> dict[str, Any]:
        """
        Persist session state to disk.

        Args:
            session: The SessionState to save
            sign: Whether to attach a signature (default True)

        Returns:
            dict with save metadata including checksum
        """
        with self._lock:
            session.last_active = datetime.now(UTC).isoformat()
            session.version += 1

            data = session.to_dict()
            checksum = self._compute_checksum(session)
            data["_checksum"] = checksum
            data["_saved_at"] = datetime.now(UTC).isoformat()

            if sign:
                signable = self._build_signable(session)
                data["_signature"] = self._sign(signable)
                data["_sig_version"] = self.SIGNATURE_VERSION

            path = self._session_path(session.session_id)
            continuity = self._build_continuity_artifact(
                session,
                checksum=checksum,
                signed=sign,
                storage_path=str(path),
            )
            data.setdefault("metadata", {})
            data["metadata"]["_continuity"] = continuity.to_dict()
            session.metadata["_continuity"] = continuity.to_dict()
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

            _log.info(
                "Session %s saved (version=%d, device=%s)", session.session_id, session.version, session.device_id
            )

            return {
                "session_id": session.session_id,
                "version": session.version,
                "checksum": data["_checksum"],
                "signed": sign,
                "path": str(path),
                "continuity": continuity.to_dict(),
            }

    def restore(
        self,
        session_id: str,
        verify: bool = True,
    ) -> tuple[SessionState | None, str | None]:
        """
        Load session state from disk and optionally verify its signature.

        Args:
            session_id: ID of the session to restore
            verify: Whether to verify the signature (default True)

        Returns:
            (SessionState, error_message) — SessionState is None on failure
        """
        with self._lock:
            path = self._session_path(session_id)

            if not path.exists():
                return None, f"Session {session_id!r} not found"

            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                return None, f"Failed to read session {session_id!r}: {e}"

            # Verify checksum
            stored_checksum = raw.pop("_checksum", None)
            data = {k: v for k, v in raw.items() if not k.startswith("_")}
            state = SessionState.from_dict(data)
            if not isinstance(state.metadata, dict):
                return None, "Invalid session payload: metadata must be an object"
            recomputed = self._compute_checksum(state)

            if stored_checksum and stored_checksum != recomputed:
                return None, "Session checksum mismatch — data may be corrupted"

            checksum_verified = True
            # Verify signature if requested
            if verify and "_signature" in raw:
                # Reconstruct signable from non-underscore fields
                signable = self._build_signable(state)
                expected_sig = self._sign(signable)

                if not hmac.compare_digest(expected_sig, raw["_signature"]):
                    return None, "Session signature verification failed"

            continuity_raw = state.metadata.get("_continuity")
            if isinstance(continuity_raw, dict):
                continuity = dict(continuity_raw)
                continuity.setdefault("artifact_type", "session_state")
                continuity.setdefault("scope", "session")
                continuity.setdefault("owner_id", str(state.metadata.get("owner_id") or state.twin_id))
                continuity.setdefault("session_id", state.session_id)
                continuity.setdefault("twin_id", state.twin_id)
                integrity = continuity.setdefault("integrity", {})
                integrity.setdefault("checksum", stored_checksum or recomputed)
                integrity["verified"] = checksum_verified
                integrity["signed"] = "_signature" in raw
                continuity.setdefault("status", "explicit")
            else:
                continuity = self._build_continuity_artifact(
                    state,
                    checksum=stored_checksum or recomputed,
                    signed="_signature" in raw,
                    verified=checksum_verified,
                    storage_path=str(path),
                    status="reconstructed",
                ).to_dict()
            state.metadata["_continuity"] = continuity
            return state, None

    def exists(self, session_id: str) -> bool:
        """Check whether a session exists on disk."""
        return self._session_path(session_id).exists()

    def delete(self, session_id: str) -> bool:
        """Remove a session file from disk."""
        with self._lock:
            path = self._session_path(session_id)
            if path.exists():
                path.unlink()
                _log.info("Session %s deleted", session_id)
                return True
            return False

    def list_sessions(self, twin_id: str | None = None) -> list[str]:
        """
        List all stored session IDs.

        Args:
            twin_id: If provided, only return sessions for this twin
        """
        sessions = []
        for path in self._storage_dir.glob("session_*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if twin_id is None or raw.get("twin_id") == twin_id:
                    sessions.append(raw.get("session_id", path.stem))
            except (json.JSONDecodeError, OSError, KeyError):
                continue
        return sessions

    # --------------------------------------------------------------------------
    # Convenience aliases
    # --------------------------------------------------------------------------

    def save_session(self, session: SessionState, sign: bool = True) -> dict[str, Any]:
        """Alias for save(). Persist session state to disk."""
        return self.save(session, sign=sign)

    def load_session(self, session_id: str, verify: bool = True) -> tuple[SessionState | None, str | None]:
        """Alias for restore(). Load session state from disk."""
        return self.restore(session_id, verify=verify)

    # --------------------------------------------------------------------------
    # Internal
    # --------------------------------------------------------------------------

    def _session_path(self, session_id: str) -> Path:
        """Return the filesystem path for a session file."""
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return self._storage_dir / f"session_{safe_name}.json"
