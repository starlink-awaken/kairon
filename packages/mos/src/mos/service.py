"""MemoryOS control plane: write / recall / status."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mos.backends import InMemoryRawBackend, InMemorySearchBackend, InMemoryThetaBackend, SearchBackend
from mos.dual_track import DualTrackResult, DualTrackWriter
from mos.envelope import MemoryEnvelope, validate_envelope
from mos.routing import backends_for_intent, classify_intent, rrf_fuse


@dataclass
class WriteResult:
    ok: bool
    envelope_id: str
    dual_track: DualTrackResult
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        dt = self.dual_track
        return {
            "ok": self.ok,
            "envelope_id": self.envelope_id,
            "content_hash": self.content_hash,
            "raw_id": dt.raw_id,
            "raw_ok": dt.raw_ok,
            "theta_ok": dt.theta_ok,
            "theta_id": dt.theta_id,
            "degraded": dt.degraded,
            "skipped_theta": dt.skipped_theta,
            "theta_error": dt.theta_error,
            "reason": dt.reason,
        }


@dataclass
class RecallResult:
    query: str
    intent: str
    hits: list[dict[str, Any]]
    backend_status: dict[str, str] = field(default_factory=dict)
    empty: bool = False

    @property
    def count(self) -> int:
        return len(self.hits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "intent": self.intent,
            "hits": self.hits,
            "backend_status": self.backend_status,
            "empty": self.empty or len(self.hits) == 0,
            "count": self.count,
        }


class MemoryOS:
    """Unified memory control surface."""

    def __init__(
        self,
        *,
        dual_track: DualTrackWriter | None = None,
        search_backends: dict[str, SearchBackend] | None = None,
        raw: InMemoryRawBackend | None = None,
        theta: InMemoryThetaBackend | None = None,
        confidence_threshold: float = 0.6,
    ) -> None:
        self._raw = raw or InMemoryRawBackend()
        self._theta = theta or InMemoryThetaBackend()
        self._dual = dual_track or DualTrackWriter(
            self._raw, self._theta, confidence_threshold=confidence_threshold
        )
        # Default offline-friendly backends; tests inject corpora
        self._search: dict[str, SearchBackend] = search_backends or {}
        # Theta store is also searchable under gbrain_facts when no override
        if "gbrain_facts" not in self._search:
            self._search["gbrain_facts"] = _ThetaAsSearch(self._theta, name="gbrain_facts")
        if "gbrain" not in self._search:
            self._search["gbrain"] = _ThetaAsSearch(self._theta, name="gbrain")

    @property
    def raw_backend(self) -> InMemoryRawBackend:
        return self._raw  # type: ignore[return-value]

    @property
    def theta_backend(self) -> InMemoryThetaBackend:
        return self._theta  # type: ignore[return-value]

    def write(self, envelope: MemoryEnvelope | dict[str, Any]) -> WriteResult:
        env = validate_envelope(envelope)
        dt = self._dual.write(env)
        return WriteResult(
            ok=dt.raw_ok,
            envelope_id=env.id or "",
            dual_track=dt,
            content_hash=env.content_hash or "",
        )

    def recall(
        self,
        query: str,
        *,
        intent: str | None = None,
        scope: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> RecallResult:
        resolved = classify_intent(query, intent)
        names = backends_for_intent(resolved)
        ranked: list[list[dict[str, Any]]] = []
        status: dict[str, str] = {}
        for name in names:
            backend = self._search.get(name)
            if backend is None:
                status[name] = "missing"
                continue
            try:
                hits = backend.search(query, limit=limit, scope=scope)
                for h in hits:
                    h.setdefault("backend", name)
                ranked.append(hits)
                status[name] = "ok"
            except Exception as exc:  # noqa: BLE001
                status[name] = f"degraded:{exc}"
        fused = rrf_fuse(ranked, limit=limit)
        return RecallResult(
            query=query,
            intent=resolved,
            hits=fused,
            backend_status=status,
            empty=len(fused) == 0,
        )

    def status(self) -> dict[str, Any]:
        raw_n = len(getattr(self._raw, "events", []) or [])
        theta_n = len(getattr(self._theta, "docs", []) or [])
        return {
            "ok": True,
            "version": "0.1.0",
            "raw_events": raw_n,
            "theta_docs": theta_n,
            "search_backends": sorted(self._search.keys()),
            "control_plane": "bos://memory/mos/*",
        }

    def register_search_backend(self, name: str, backend: SearchBackend) -> None:
        self._search[name] = backend


class _ThetaAsSearch:
    """Adapt InMemoryThetaBackend to SearchBackend protocol."""

    def __init__(self, theta: InMemoryThetaBackend, name: str = "gbrain") -> None:
        self.name = name
        self._theta = theta

    def search(self, query: str, *, limit: int = 10, scope: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        hits = self._theta.search(query, limit=limit, scope=scope)
        for h in hits:
            h["backend"] = self.name
        return hits


def default_memory_os_with_fixtures() -> MemoryOS:
    """Factory used by CLI smoke and demos with empty corpora."""
    kos = InMemorySearchBackend(
        name="kos",
        docs=[
            {
                "id": "kos-adr-0372",
                "title": "ADR-0372 Memory OS",
                "snippet": "Memory OS control plane unified write recall",
                "path": ".omo/_knowledge/decisions/0372-memory-os-control-plane.md",
            }
        ],
    )
    mos = MemoryOS()
    mos.register_search_backend("kos", kos)
    mos.register_search_backend("cards", InMemorySearchBackend(name="cards", docs=[]))
    mos.register_search_backend("codebase_memory", InMemorySearchBackend(name="codebase_memory", docs=[]))
    mos.register_search_backend("governance_omo", InMemorySearchBackend(name="governance_omo", docs=[]))
    return mos
