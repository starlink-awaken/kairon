from __future__ import annotations

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 1.0.0
Owner: '@Copilot'
Layer: L3
Summary: D-Continuity owned BOS-URI registration seam for continuity contract operations.
Authority: organs/D-Continuity/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Uri Registrar ≡ Module
# 内涵 ≝ {Uri, Registrar}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, UriRegistrar)}
# 功能 ⊢ {Uri_Registrar, Init_Uri, Validate_Registrar}
# =============================================================================


from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Protocol

from eidos.session_store import SessionState, SessionStore
from eidos.session_sync import SessionSync

_INGRESS_SURFACE = "organs/D_Continuity/organs/uri_registrar.py"


class _RouterLike(Protocol):
    def register(self, namespace: str, route: str, handler: Any) -> None: ...


@dataclass
class ContinuityOwnershipBoundary:
    truth_owner: str
    runtime_owner: str = "nucleus/Z-Microkernel/organs/uri_router.py"
    ingress_surface: str = _INGRESS_SURFACE

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def register_continuity_routes(router: _RouterLike) -> None:
    """Attach D-Continuity-owned BOS-URI handlers to a router-like object."""

    def _params_object(params: dict[str, Any] | None) -> dict[str, Any] | None:
        if params is None:
            return {}
        if not isinstance(params, dict):
            return None
        return params

    def _signature_key(params: dict[str, Any]) -> bytes | None:
        key = params.get("signature_key")
        if key is None:
            return None
        if isinstance(key, bytes):
            return key
        return str(key).encode("utf-8")

    def _store_from_params(params: dict[str, Any]) -> SessionStore:
        return SessionStore(
            storage_dir=str(params.get("storage_dir", ".sessions")),
            signature_key=_signature_key(params),
        )

    def _sync_from_params(params: dict[str, Any]) -> SessionSync:
        sync = SessionSync(
            registry_path=str(params.get("registry_path", ".device_registry.json")),
            persist=bool(params.get("persist", True)),
        )
        if params.get("use_conflict_resolver") is False:
            sync._conflict_resolver = None
        return sync

    def _ownership(truth_owner: str) -> dict[str, str]:
        return ContinuityOwnershipBoundary(truth_owner=truth_owner).to_dict()

    def _error(code: str, message: str, *, operation: str) -> dict[str, str]:
        return {
            "status": "error",
            "code": code,
            "operation": operation,
            "message": message,
        }

    def _is_iso_timestamp(value: str) -> bool:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except (TypeError, ValueError):
            return False

    async def _store_handler(_uri: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _params_object(params)
        if payload is None:
            return _error("INVALID_PAYLOAD", "request params must be an object", operation="store")
        session_payload = payload.get("session")
        if not isinstance(session_payload, dict):
            return _error("INVALID_PAYLOAD", "session payload is required", operation="store")

        try:
            store = _store_from_params(payload)
            session = SessionState.from_dict(session_payload)
        except (TypeError, ValueError) as exc:
            return _error("INVALID_PAYLOAD", f"invalid session payload: {exc}", operation="store")
        except OSError as exc:
            return _error("STORE_FAILED", f"failed to initialize store: {exc}", operation="store")

        try:
            result = store.save(session, sign=bool(payload.get("sign", True)))
        except (TypeError, ValueError) as exc:
            return _error("INVALID_PAYLOAD", f"invalid session payload: {exc}", operation="store")
        except OSError as exc:
            return _error("STORE_FAILED", f"failed to store session: {exc}", operation="store")

        return {
            "status": "success",
            "operation": "store",
            "session_id": result["session_id"],
            "continuity": result["continuity"],
            "ownership": _ownership("organs/D_Continuity/organs/session/session_store.py"),
        }

    async def _restore_handler(_uri: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _params_object(params)
        if payload is None:
            return _error("INVALID_PAYLOAD", "request params must be an object", operation="restore")
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            return _error("INVALID_PAYLOAD", "session_id is required", operation="restore")

        try:
            store = _store_from_params(payload)
            session, err = store.restore(session_id, verify=bool(payload.get("verify", True)))
        except (TypeError, ValueError) as exc:
            return _error("INVALID_PAYLOAD", f"invalid restore payload: {exc}", operation="restore")
        except OSError as exc:
            return _error("RESTORE_FAILED", f"failed to restore session: {exc}", operation="restore")
        if err or session is None:
            return _error("RESTORE_FAILED", err or "session restore failed", operation="restore")

        return {
            "status": "success",
            "operation": "restore",
            "session": session.to_dict(),
            "continuity": session.metadata.get("_continuity", {}),
            "ownership": _ownership("organs/D_Continuity/organs/session/session_store.py"),
        }

    async def _sync_handler(_uri: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _params_object(params)
        if payload is None:
            return _error("INVALID_PAYLOAD", "request params must be an object", operation="sync")
        state = payload.get("state")
        if not isinstance(state, dict):
            return _error("INVALID_PAYLOAD", "state payload is required", operation="sync")

        try:
            sync = _sync_from_params(payload)
            continuity = sync.save_session_state(state)
        except (TypeError, ValueError) as exc:
            return _error("INVALID_PAYLOAD", f"invalid sync payload: {exc}", operation="sync")
        except OSError as exc:
            return _error("SYNC_FAILED", f"failed to sync session: {exc}", operation="sync")
        if continuity is None:
            return _error("SYNC_FAILED", "session_id is required in state payload", operation="sync")

        return {
            "status": "success",
            "operation": "sync",
            "session_id": continuity.get("session_id"),
            "continuity": continuity,
            "ownership": _ownership("organs/D_Continuity/organs/session/session_sync.py"),
        }

    async def _recover_handler(_uri: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _params_object(params)
        if payload is None:
            return _error("INVALID_PAYLOAD", "request params must be an object", operation="recover")
        session_id = payload.get("session_id")
        local_state = payload.get("local_state")
        remote_state = payload.get("remote_state")
        local_timestamp = payload.get("local_timestamp")
        remote_timestamp = payload.get("remote_timestamp")

        if not isinstance(session_id, str) or not session_id.strip():
            return _error("INVALID_PAYLOAD", "session_id is required", operation="recover")
        if not isinstance(local_state, dict) or not isinstance(remote_state, dict):
            return _error(
                "INVALID_PAYLOAD",
                "local_state and remote_state must be dict payloads",
                operation="recover",
            )
        if (
            not isinstance(local_timestamp, str)
            or not local_timestamp.strip()
            or not isinstance(remote_timestamp, str)
            or not remote_timestamp.strip()
        ):
            return _error(
                "INVALID_PAYLOAD",
                "local_timestamp and remote_timestamp are required",
                operation="recover",
            )
        if not _is_iso_timestamp(local_timestamp) or not _is_iso_timestamp(remote_timestamp):
            return _error(
                "INVALID_PAYLOAD",
                "local_timestamp and remote_timestamp must be valid ISO-8601 strings",
                operation="recover",
            )

        try:
            sync = _sync_from_params(payload)
            resolved = sync.resolve_state_conflict(
                session_id=session_id,
                local_state=local_state,
                remote_state=remote_state,
                local_timestamp=local_timestamp,
                remote_timestamp=remote_timestamp,
            )
        except (TypeError, ValueError) as exc:
            return _error("INVALID_PAYLOAD", f"invalid recover payload: {exc}", operation="recover")
        except OSError as exc:
            return _error("RECOVER_FAILED", f"failed to recover session: {exc}", operation="recover")

        return {
            "status": "success",
            "operation": "recover",
            "session_id": session_id,
            "state": resolved,
            "continuity": resolved.get("_continuity", {}),
            "ownership": _ownership("organs/D_Continuity/organs/session/session_sync.py"),
        }

    router.register("continuity", "session/store", _store_handler)
    router.register("continuity", "session/restore", _restore_handler)
    router.register("continuity", "session/sync", _sync_handler)
    router.register("continuity", "session/recover", _recover_handler)
