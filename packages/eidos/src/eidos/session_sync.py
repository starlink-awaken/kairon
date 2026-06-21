from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Summary: Multi-device session synchronization with active tracking
Authority: organs/D-Continuity/AGENTS.md
---
"""


import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, cast

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from eidos.continuity_conflict_resolution import (  # type: ignore[import-not-found]
        ConflictResolution,
        ResolutionStrategy,
        VectorClock,
    )

try:
    from eidos.continuity_conflict_resolution import ConflictResolution, ResolutionStrategy, VectorClock

    _HAS_CONFLICT_RESOLUTION = True
except ImportError:
    ConflictResolution: Any = None  # type: ignore[no-redef]
    ResolutionStrategy: Any = None  # type: ignore[no-redef]
    VectorClock: Any = None  # type: ignore[no-redef]
    _HAS_CONFLICT_RESOLUTION = False


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# SessionSync ≡ Multi_Device_Sync
# 内涵 ≝ {Register, Unregister, Track, Sync}
# 外延 ≝ {s | s ∈ D-Continuity ∧ syncs(s, Session)}
# 功能 ⊢ {Register_Device, Unregister_Device, Get_Last_Active, Sync_Session}
# =============================================================================


@dataclass
class DeviceInfo:
    """Information about a registered device."""

    device_id: str
    twin_id: str
    device_name: str
    device_type: str
    registered_at: str
    last_active: str
    session_id: str | None = None
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceInfo:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SessionContinuityProjection:
    """Projected continuity artifact for persisted or resolved session state."""

    artifact_type: str
    scope: str
    owner_id: str
    truth_owner: str
    session_id: str
    controller_session_id: str | None = None
    controller_node_id: str | None = None
    control_plane: str | None = None
    hive_id: str | None = None
    device_id: str | None = None
    twin_id: str | None = None
    source_surface: str | None = None
    integrity: dict[str, Any] = field(default_factory=dict)
    status: str = "explicit"
    requires_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SessionSync:
    """
    Multi-device session synchronization manager.

    Features:
    1. Device registration and deregistration
    2. Last-active timestamp tracking per device
    3. Session binding per device
    4. In-memory + optional file-based persistence
    """

    def __init__(
        self,
        registry_path: str = ".device_registry.json",
        persist: bool = True,
        conflict_strategy: Any | None = None,
    ) -> None:
        self.metadata_path = "eidos/session_sync.py"
        self.organ_name = "session_sync"
        self.organ_id = f"eidos-{id(self):x}"
        self._status = "active"
        self._metabolic_budget = 1000.0
        self._registry_path = Path(registry_path)
        self._persist = persist
        self._devices: dict[str, DeviceInfo] = {}
        self._twin_devices: dict[str, set[str]] = {}  # twin_id -> set of device_ids
        self._device_sessions: dict[str, str | None] = {}  # device_id -> session_id
        self._lock = Lock()
        # Conflict resolution integration
        self._conflict_resolver: Any = None
        self._vector_clocks: dict[str, Any] = {}  # device_id -> VectorClock
        conflict_resolution_cls = ConflictResolution
        resolution_strategy = ResolutionStrategy
        if _HAS_CONFLICT_RESOLUTION and conflict_resolution_cls is not None and resolution_strategy is not None:
            strat = conflict_strategy or resolution_strategy.CRDT_MERGE
            self._conflict_resolver = conflict_resolution_cls(strategy=strat)
        self._load_registry()

    # --------------------------------------------------------------------------
    # Device lifecycle
    # --------------------------------------------------------------------------

    def register_device(
        self,
        device_id: str,
        twin_id: str,
        device_name: str = "unknown",
        device_type: str = "desktop",
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> DeviceInfo:
        """
        Register a new device or update an existing one.

        Args:
            device_id: Unique identifier for this device
            twin_id: The digital twin this device belongs to
            device_name: Human-readable device name
            device_type: Type of device (desktop, mobile, tablet, web)
            capabilities: List of device capabilities
            metadata: Additional device metadata
            session_id: Optional session this device is currently bound to

        Returns:
            DeviceInfo for the registered device
        """
        with self._lock:
            now = datetime.now(UTC).isoformat()
            device = DeviceInfo(
                device_id=device_id,
                twin_id=twin_id,
                device_name=device_name,
                device_type=device_type,
                registered_at=now,
                last_active=now,
                session_id=session_id,
                capabilities=capabilities or [],
                metadata=metadata or {},
            )

            self._devices[device_id] = device
            self._device_sessions[device_id] = session_id

            if twin_id not in self._twin_devices:
                self._twin_devices[twin_id] = set()
            self._twin_devices[twin_id].add(device_id)

            self._save_registry()
            _log.info("Device %s registered for twin %s (type=%s)", device_id, twin_id, device_type)

            return device

    def unregister_device(self, device_id: str) -> bool:
        """
        Remove a device from the registry.

        Args:
            device_id: ID of the device to unregister

        Returns:
            True if device was removed, False if not found
        """
        with self._lock:
            if device_id not in self._devices:
                return False

            device = self._devices[device_id]
            twin_id = device.twin_id

            del self._devices[device_id]
            self._device_sessions.pop(device_id, None)

            if twin_id in self._twin_devices:
                self._twin_devices[twin_id].discard(device_id)
                if not self._twin_devices[twin_id]:
                    del self._twin_devices[twin_id]

            self._save_registry()
            _log.info("Device %s unregistered from twin %s", device_id, twin_id)
            return True

    def get_device(self, device_id: str) -> DeviceInfo | None:
        """Retrieve device information."""
        with self._lock:
            return self._devices.get(device_id)

    def get_devices_for_twin(self, twin_id: str) -> list[DeviceInfo]:
        """Get all registered devices for a given twin."""
        with self._lock:
            device_ids = self._twin_devices.get(twin_id, set())
            return [self._devices[d] for d in device_ids if d in self._devices]

    def list_all_devices(self) -> list[DeviceInfo]:
        """List all registered devices."""
        with self._lock:
            return list(self._devices.values())

    # --------------------------------------------------------------------------
    # Active tracking
    # --------------------------------------------------------------------------

    def touch(self, device_id: str) -> bool:
        """
        Update the last-active timestamp for a device.

        Args:
            device_id: ID of the device to touch

        Returns:
            True if updated, False if device not found
        """
        with self._lock:
            if device_id not in self._devices:
                return False
            self._devices[device_id].last_active = datetime.now(UTC).isoformat()
            return True

    def get_last_active(self, device_id: str) -> str | None:
        """Return the last-active timestamp for a device, or None if unknown."""
        with self._lock:
            device = self._devices.get(device_id)
            return device.last_active if device else None

    def get_active_devices(
        self,
        twin_id: str | None = None,
        within_seconds: float = 300.0,
    ) -> list[DeviceInfo]:
        """
        Return devices that were active within the given time window.

        Args:
            twin_id: Optional filter by twin
            within_seconds: Consider devices active within this window (default 300s / 5 min)
        """
        import time

        cutoff = time.time() - within_seconds
        with self._lock:
            devices = (
                self._devices.values()
                if twin_id is None
                else (self._devices[d] for d in self._twin_devices.get(twin_id, set()) if d in self._devices)
            )
            active_devices: list[DeviceInfo] = []
            for device in devices:
                try:
                    if datetime.fromisoformat(device.last_active).timestamp() >= cutoff:
                        active_devices.append(device)
                except (TypeError, ValueError):
                    _log.warning("[SessionSync] Skipping device with invalid last_active: %s", device.device_id)
            return active_devices

    # --------------------------------------------------------------------------
    # Session binding
    # --------------------------------------------------------------------------

    def bind_session(self, device_id: str, session_id: str) -> bool:
        """
        Bind a session to a device.

        Args:
            device_id: Target device
            session_id: Session to bind

        Returns:
            True if bound, False if device not found
        """
        with self._lock:
            if device_id not in self._devices:
                return False
            self._devices[device_id].session_id = session_id
            self._device_sessions[device_id] = session_id
            self._save_registry()
            return True

    def unbind_session(self, device_id: str) -> bool:
        """
        Unbind the current session from a device.

        Returns:
            True if unbound, False if device not found
        """
        with self._lock:
            if device_id not in self._devices:
                return False
            self._devices[device_id].session_id = None
            self._device_sessions[device_id] = None
            self._save_registry()
            return True

    def get_device_for_session(self, session_id: str) -> list[DeviceInfo]:
        """Find all devices currently bound to a given session."""
        with self._lock:
            return [d for d in self._devices.values() if d.session_id == session_id]

    # --------------------------------------------------------------------------
    # Persistence
    # --------------------------------------------------------------------------

    def _save_registry(self) -> None:
        """Persist the device registry to disk."""
        if not self._persist:
            return
        data = {
            "devices": {k: v.to_dict() for k, v in self._devices.items()},
            "version": 1,
            "saved_at": datetime.now(UTC).isoformat(),
        }
        self._registry_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def _load_registry(self) -> None:
        """Load the device registry from disk."""
        if not self._registry_path.exists():
            return
        try:
            raw = json.loads(self._registry_path.read_text(encoding="utf-8"))
            for device_id, dev_data in raw.get("devices", {}).items():
                try:
                    device = DeviceInfo.from_dict(dev_data)
                    self._devices[device_id] = device
                    self._device_sessions[device_id] = device.session_id

                    if device.twin_id not in self._twin_devices:
                        self._twin_devices[device.twin_id] = set()
                    self._twin_devices[device.twin_id].add(device_id)
                except (TypeError, ValueError):
                    _log.warning("[SessionSync] Skipping malformed device registry entry: %s", device_id)

            _log.info("Device registry loaded: %d devices", len(self._devices))
        except (json.JSONDecodeError, OSError, KeyError) as e:
            _log.warning("Failed to load device registry: %s", e)

    # --------------------------------------------------------------------------
    # Conflict resolution integration
    # --------------------------------------------------------------------------

    def resolve_state_conflict(
        self,
        session_id: str,
        local_state: dict[str, Any],
        remote_state: dict[str, Any],
        local_timestamp: str,
        remote_timestamp: str,
    ) -> dict[str, Any]:
        """
        Resolve concurrent session state edits between devices.

        Args:
            session_id: Session being synchronized
            local_state: Current local state
            remote_state: State from another device
            local_timestamp: ISO timestamp of local state
            remote_timestamp: ISO timestamp of remote state

        Returns:
            Merged/resolved state dict
        """
        if self._conflict_resolver is None:
            _log.warning("[SessionSync] No conflict resolver configured; marking continuity as degraded")
            return self._attach_continuity_artifact(
                session_id=session_id,
                state=remote_state,
                owner_id=remote_state.get("owner_id") or local_state.get("owner_id"),
                status="degraded",
                integrity={
                    "strategy": "no_conflict_resolver",
                    "local_timestamp": local_timestamp,
                    "remote_timestamp": remote_timestamp,
                    "resolved": False,
                },
                requires_review=True,
            )

        versions = [
            {
                **local_state,
                "device_id": local_state.get("device_id", "local"),
                "owner_id": local_state.get("owner_id") or remote_state.get("owner_id"),
                "last_active": local_timestamp,
                "scope": "session",
            },
            {
                **remote_state,
                "device_id": remote_state.get("device_id", "remote"),
                "owner_id": remote_state.get("owner_id") or local_state.get("owner_id"),
                "last_active": remote_timestamp,
                "scope": "session",
            },
        ]
        resolution = self._conflict_resolver.resolve_session_state(session_id, versions)
        winner = resolution.get("winner") if resolution.get("apply") else None
        resolved_state = dict(winner) if isinstance(winner, dict) else dict(remote_state)
        return self._attach_continuity_artifact(
            session_id=session_id,
            state=resolved_state,
            owner_id=resolved_state.get("owner_id"),
            status="resolved" if resolution.get("apply") else "unresolved",
            integrity={
                "strategy": str(resolution.get("strategy", "unknown")),
                "conflict_id": resolution.get("conflict_id"),
                "resolved": bool(resolution.get("apply")),
            },
            requires_review=not bool(resolution.get("apply")),
        )

    def set_conflict_strategy(self, strategy: Any) -> None:
        """Change the conflict resolution strategy at runtime."""
        if self._conflict_resolver is not None:
            self._conflict_resolver.set_strategy(strategy)
            _log.info(
                "[SessionSync] Conflict strategy changed to: %s",
                getattr(strategy, "value", strategy),
            )

    def get_vector_clock(self, device_id: str) -> VectorClock | None:
        """Get or create the vector clock for a device."""
        if not _HAS_CONFLICT_RESOLUTION or VectorClock is None:
            return None
        if device_id not in self._vector_clocks:
            self._vector_clocks[device_id] = VectorClock()
        return cast("VectorClock | None", self._vector_clocks[device_id])

    def sync_vector_clock(self, device_id: str, remote_clock: dict[str, int]) -> None:
        """Merge a remote vector clock into the local one."""
        vc = self.get_vector_clock(device_id)
        if vc is not None:
            self._vector_clocks[device_id] = vc.merge(vc.__class__(remote_clock))

    # --------------------------------------------------------------------------
    # Session state persistence
    # --------------------------------------------------------------------------

    def sync_session_to_device(
        self,
        device_id: str,
        session_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Sync a session state to a specific device.

        Args:
            device_id: Target device to sync to
            session_state: Session state dict to sync

        Returns:
            Continuity projection dict or None on failure
        """
        session_id = session_state.get("session_id")
        if session_id:
            self.bind_session(device_id, str(session_id))
        return self.save_session_state(session_state)

    def get_device_projection(self, device_id: str) -> dict[str, Any] | None:
        """
        Get continuity projection for a registered device.

        Args:
            device_id: ID of the device

        Returns:
            Projection dict or None if device not found
        """
        device = self.get_device(device_id)
        if device is None:
            return None
        return self._build_continuity_projection(
            state={
                "device_id": device_id,
                "twin_id": device.twin_id,
                "session_id": device.session_id,
                "owner_id": device.twin_id,
            },
            artifact_type="device_projection",
            status="explicit",
            integrity={
                "last_active": device.last_active,
                "registered_at": device.registered_at,
                "capabilities": device.capabilities,
            },
        )

    def save_session_state(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """
        Persist voice session state to disk for cross-device sync.

        Args:
            state: Session state dict with keys like session_id, state, transcript, device_id
        """
        if not isinstance(state, dict):
            return None
        session_id = state.get("session_id")
        if not session_id:
            return None

        with self._lock:
            safe_session_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(session_id))
            session_file = self._registry_path.parent / f".session_{safe_session_id}.json"
            checksum = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            continuity = self._build_continuity_projection(
                state=state,
                artifact_type="session_sync_state",
                status="explicit" if self._persist else "ephemeral",
                integrity={
                    "checksum": checksum,
                    "persisted": self._persist,
                    "registry_path": str(session_file),
                },
            )
            if self._persist:
                data = {
                    **state,
                    "saved_at": datetime.now(UTC).isoformat(),
                }
                data["_continuity"] = continuity
                session_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
                _log.debug("[SessionSync] Session state saved for %s", session_id)
            return continuity

    def _attach_continuity_artifact(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        owner_id: str | None,
        status: str,
        integrity: dict[str, Any],
        requires_review: bool,
    ) -> dict[str, Any]:
        resolved_state = dict(state)
        resolved_state["_continuity"] = self._build_continuity_projection(
            state={**resolved_state, "session_id": session_id, "owner_id": owner_id},
            artifact_type="session_sync_resolution",
            status=status,
            integrity=integrity,
            requires_review=requires_review,
        )
        return resolved_state

    def _build_continuity_projection(
        self,
        *,
        state: dict[str, Any],
        artifact_type: str,
        status: str,
        integrity: dict[str, Any],
        requires_review: bool = False,
    ) -> dict[str, Any]:
        runtime_context = state.get("continuity_context", {})
        if not isinstance(runtime_context, dict):
            runtime_context = {}

        def pick(key: str) -> Any | None:
            return state.get(key) if state.get(key) is not None else runtime_context.get(key)

        session_id = str(pick("session_id") or "")
        projection = SessionContinuityProjection(
            artifact_type=artifact_type,
            scope=str(pick("scope") or pick("continuity_scope") or "session"),
            owner_id=str(pick("owner_id") or pick("twin_id") or session_id),
            truth_owner="D-Execution",
            session_id=session_id,
            controller_session_id=pick("controller_session_id"),
            controller_node_id=pick("controller_node_id"),
            control_plane=pick("control_plane"),
            hive_id=pick("hive_id"),
            device_id=pick("device_id"),
            twin_id=pick("twin_id"),
            source_surface=pick("source_surface"),
            integrity=integrity,
            status=status,
            requires_review=requires_review,
        )
        return projection.to_dict()
