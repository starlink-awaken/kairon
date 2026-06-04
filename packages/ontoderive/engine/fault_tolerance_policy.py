from __future__ import annotations

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# FaultTolerancePolicy ≡ Policy
# 内涵 ≝ {Fault, Tolerance, Policy}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, FaultTolerancePolicy)}
# 功能 ⊢ {Evaluate_Fault, Decide_Mode, Configure_Policy}
# =============================================================================

"""
from typing import Any
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Layer: L3
Constraint: "Configurable fault-tolerance via SOUL axioms"
Summary: "FaultTolerancePolicy - adaptive fault-tolerance decisions for B-OS organs"
Authority: organs/D-Logos/AGENTS.md
---
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

# Event bus integration — try shared-lib first, then legacy nucleus path
try:
    from kairon_lib.events import BOSEvent, get_global_event_bus  # type: ignore[import-not-found]
except (ModuleNotFoundError, ImportError):
    BOSEvent = None  # type: ignore[assignment]
    get_global_event_bus = None  # type: ignore[assignment]


class EventType(StrEnum):
    """Document event types published on the EventBus."""

    DOC_BEFORE_UPDATE = "doc.before_update"
    DOC_AFTER_UPDATE = "doc.after_update"


def get_event_bus() -> object:  # type: ignore[no-redef]
    """Return the global EventBus, or a dummy bus if unavailable."""
    if get_global_event_bus is None:
        return _DummyBus()
    bus = get_global_event_bus()
    if bus is None:
        return _DummyBus()
    return bus


class _DummyBus:
    """Silent no-op bus returned when the real EventBus is unavailable."""

    def subscribe(self, event_type: object, handler: object) -> None:  # type: ignore[unused-var]
        return None

    def subscribe_async(  # type: ignore[unused-var]
        self, event_type: object, handler: object
    ) -> None:
        return None


_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Data Models
# ---------------------------------------------------------------------------


class FaultMode(Enum):
    """Fault-tolerance mode governing how errors are handled."""

    FAIL_OPEN = "fail_open"
    FAIL_CLOSED = "fail_closed"
    ADAPTIVE = "adaptive"


_SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 3,
    "high": 2,
    "medium": 1,
    "low": 0,
}


@dataclass
class FaultContext:
    """Contextual information about the fault being evaluated."""

    operation: str
    severity: str  # "critical" | "high" | "medium" | "low"
    system_health: float  # 0.0 – 1.0
    retry_count: int = 0
    last_error: str | None = None


@dataclass
class FaultDecision:
    """Result of a fault-tolerance evaluation."""

    mode: FaultMode
    allow: bool
    reason: str
    fallback_action: str | None = None
    should_retry: bool = False
    retry_delay: float = 0.0


@dataclass
class PolicyConfig:
    """Tuneable knobs for the fault-tolerance policy."""

    default_mode: FaultMode = FaultMode.ADAPTIVE
    health_threshold: float = 0.5
    max_retries: int = 3
    base_retry_delay: float = 1.0
    critical_operations: list[str] = field(default_factory=list)
    soul_overrides: dict[str, FaultMode] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 2. FaultTolerancePolicy (CoreService)
# ---------------------------------------------------------------------------


class FaultTolerancePolicy:
    """
    ---
    Type: Organ
    Status: Stable
    Layer: L3-Logos
    Summary: Adaptive fault-tolerance decision engine driven by SOUL axioms
    ---

    Evaluates whether a faulting operation should be allowed to proceed
    (fail-open) or blocked (fail-closed).  Supports three modes:

    * **FAIL_OPEN** – always allow; log the incident.
    * **FAIL_CLOSED** – always deny; force an explicit fix.
    * **ADAPTIVE** – decide based on *system_health* and *severity*.
    """

    def __init__(self, config: PolicyConfig | None = None) -> None:
        super().__init__(
            metadata_path="organs/D-Logos/organs/fault_tolerance_policy.py",
        )
        self._config = config or PolicyConfig()
        self._system_health: float = 1.0
        self._stats: dict[str, int] = {
            "total": 0,
            "allowed": 0,
            "denied": 0,
            "retries": 0,
        }
        self._register_event_subscriptions()

    # -- event bus integration -----------------------------------------------

    def _register_event_subscriptions(self) -> None:
        """Subscribe to DOC_BEFORE_UPDATE and DOC_AFTER_UPDATE events from the event bus."""
        if BOSEvent is None:
            return
        bus = get_event_bus()
        if hasattr(bus, "subscribe"):
            bus.subscribe(EventType.DOC_BEFORE_UPDATE, self._on_doc_before_update)
            bus.subscribe(EventType.DOC_AFTER_UPDATE, self._on_doc_after_update)

    def _on_doc_before_update(self, event: object) -> None:
        """Handle doc-before-update: run alignment check via fault-tolerance evaluation."""
        payload = getattr(event, "payload", {}) or {}
        doc_id = payload.get("doc_id", "unknown")
        ctx = FaultContext(
            operation="doc_update",
            severity="medium",
            system_health=self._system_health,
            retry_count=0,
            last_error=None,
        )
        decision = self.evaluate(ctx)
        if not decision.allow:
            _log.warning(
                "[FaultTolerance] BLOCKED doc update for %s: %s",
                doc_id,
                decision.reason,
            )

    def _on_doc_after_update(self, event: object) -> None:
        """Handle doc-after-update: record stats and log the completion."""
        payload = getattr(event, "payload", {}) or {}
        doc_id = payload.get("doc_id", "unknown")
        _log.info("[FaultTolerance] Doc updated: %s", doc_id)

    # -- public API ----------------------------------------------------------

    def evaluate(self, context: FaultContext) -> FaultDecision:
        """Core decision engine.

        Priority order:
        1. Critical operations → always FAIL_CLOSED.
        2. SOUL overrides for the operation.
        3. Configured default mode (FAIL_OPEN / FAIL_CLOSED / ADAPTIVE).
        """
        self._stats["total"] += 1

        # 1. Critical operations – always fail-closed
        if context.operation in self._config.critical_operations:
            self._stats["denied"] += 1
            return FaultDecision(
                mode=FaultMode.FAIL_CLOSED,
                allow=False,
                reason=f"Operation '{context.operation}' is marked critical – always fail-closed",
                fallback_action="escalate",
                should_retry=context.retry_count < self._config.max_retries,
                retry_delay=self.get_retry_delay(context),
            )

        # 2. SOUL override for this operation
        effective_mode = self._config.soul_overrides.get(
            context.operation,
            self._config.default_mode,
        )

        # 3. Delegate to mode-specific evaluator
        if effective_mode == FaultMode.FAIL_OPEN:
            decision = self._evaluate_fail_open(context)
        elif effective_mode == FaultMode.FAIL_CLOSED:
            decision = self._evaluate_fail_closed(context)
        else:
            decision = self._evaluate_adaptive(context)

        # Update stats
        if decision.allow:
            self._stats["allowed"] += 1
        else:
            self._stats["denied"] += 1
        if decision.should_retry:
            self._stats["retries"] += 1

        return decision

    def load_soul_overrides(self, soul_path: str = "docs/archive/root_cleanup_20260428/SOUL.md") -> int:
        """Parse *docs/archive/root_cleanup_20260428/SOUL.md* for fault-tolerance axioms.

        Looks for lines containing ``fault_mode:``, ``tolerance:``, or
        ``resilience:`` and extracts operation→mode mappings.

        Returns the number of overrides loaded.
        """
        path = Path(soul_path)
        if not path.exists():
            _log.debug("docs/archive/root_cleanup_20260428/SOUL.md not found at %s – no overrides loaded", soul_path)
            return 0

        loaded = 0
        pattern = re.compile(
            r"(?:fault_mode|tolerance|resilience)\s*[:=]\s*(\w+)\s*(?:->|→|:)\s*(\w+)",
            re.IGNORECASE,
        )
        try:
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                operation = match.group(1).strip()
                raw_mode = match.group(2).strip().upper()
                mode_map = {
                    "FAIL_OPEN": FaultMode.FAIL_OPEN,
                    "FAIL_CLOSED": FaultMode.FAIL_CLOSED,
                    "ADAPTIVE": FaultMode.ADAPTIVE,
                    "OPEN": FaultMode.FAIL_OPEN,
                    "CLOSED": FaultMode.FAIL_CLOSED,
                }
                if raw_mode in mode_map:
                    self._config.soul_overrides[operation] = mode_map[raw_mode]
                    loaded += 1
        except OSError:
            _log.debug("Failed to read docs/archive/root_cleanup_20260428/SOUL.md at %s", soul_path)
        return loaded

    def update_system_health(self, health: float) -> None:
        """Update the current system-health metric (clamped to 0-1)."""
        self._system_health = max(0.0, min(1.0, health))

    def get_retry_delay(self, context: FaultContext) -> float:
        """Exponential back-off: ``base * 2^retry_count`` capped at 60 s."""
        delay = self._config.base_retry_delay * (2**context.retry_count)
        return min(delay, 60.0)

    def register_critical_operation(self, operation: str) -> None:
        """Mark *operation* so that it is always evaluated as fail-closed."""
        if operation not in self._config.critical_operations:
            self._config.critical_operations.append(operation)

    def get_policy_summary(self) -> dict[str, Any]:
        """Return a snapshot of current configuration, health, and stats."""
        return {
            "default_mode": self._config.default_mode.value,
            "health_threshold": self._config.health_threshold,
            "max_retries": self._config.max_retries,
            "base_retry_delay": self._config.base_retry_delay,
            "critical_operations": list(self._config.critical_operations),
            "soul_overrides": {k: v.value for k, v in self._config.soul_overrides.items()},
            "system_health": self._system_health,
            "stats": dict(self._stats),
        }

    # -- CoreService BOS-URI handler ----------------------------------------

    def call(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
        """BOS-URI handler – delegates to ``_handle_{action}``."""
        params = params or {}
        handler_name = f"_handle_{action}"
        if hasattr(self, handler_name):
            return getattr(self, handler_name)(params)
        return {"status": "error", "message": f"Unknown action: {action}"}

    def _handle_evaluate(self, params: dict[str, Any]) -> dict[str, Any]:
        ctx = FaultContext(
            operation=params.get("operation", "unknown"),
            severity=params.get("severity", "medium"),
            system_health=params.get("system_health", self._system_health),
            retry_count=params.get("retry_count", 0),
            last_error=params.get("last_error"),
        )
        decision = self.evaluate(ctx)
        return {
            "status": "ok",
            "mode": decision.mode.value,
            "allow": decision.allow,
            "reason": decision.reason,
            "should_retry": decision.should_retry,
            "retry_delay": decision.retry_delay,
        }

    def _handle_summary(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", **self.get_policy_summary()}

    def _handle_status(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._handle_summary(params)

    def _handle_stats(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "stats": dict(self._stats)}

    # -- private evaluators --------------------------------------------------

    def _evaluate_fail_open(self, context: FaultContext) -> FaultDecision:
        return FaultDecision(
            mode=FaultMode.FAIL_OPEN,
            allow=True,
            reason=f"FAIL_OPEN policy – allowing '{context.operation}'",
        )

    def _evaluate_fail_closed(self, context: FaultContext) -> FaultDecision:
        return FaultDecision(
            mode=FaultMode.FAIL_CLOSED,
            allow=False,
            reason=f"FAIL_CLOSED policy – denying '{context.operation}'",
            fallback_action="escalate",
            should_retry=context.retry_count < self._config.max_retries,
            retry_delay=self.get_retry_delay(context),
        )

    def _evaluate_adaptive(self, context: FaultContext) -> FaultDecision:
        """Adaptive formula: ``allow = system_health > (0.3 + severity_weight * 0.2)``."""
        weight = _SEVERITY_WEIGHTS.get(context.severity, 1)
        threshold = 0.3 + weight * 0.2
        health = context.system_health
        allow = health > threshold

        reason = (
            f"ADAPTIVE: health={health:.2f} vs "
            f"threshold={threshold:.2f} (severity={context.severity}) "
            f"→ {'allow' if allow else 'deny'}"
        )
        should_retry = (not allow) and context.retry_count < self._config.max_retries
        return FaultDecision(
            mode=FaultMode.ADAPTIVE,
            allow=allow,
            reason=reason,
            fallback_action=None if allow else "degrade_gracefully",
            should_retry=should_retry,
            retry_delay=self.get_retry_delay(context) if should_retry else 0.0,
        )
