"""Model Scheduler — dynamic model selection with load awareness."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from .policies import score_models
from .registry import ModelRegistry
from .types import (
    DEFAULT_SCHEDULER_CONFIG,
    LoadInfo,
    ModelRequest,
    ModelRoutePolicy,
    ModelSelection,
    SchedulerConfig,
)

_log = logging.getLogger(__name__)


class ModelScheduler:
    """Dynamic model scheduler with load-aware, policy-driven selection.

    Selects the optimal model for a :class:`ModelRequest` using scoring
    strategies from the policies module.  Tracks active-request load and
    optionally auto-refreshes the registry's model list.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: SchedulerConfig | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or DEFAULT_SCHEDULER_CONFIG
        self._load_map: dict[str, LoadInfo] = {}
        self._refresh_task: asyncio.Task[None] | None = None

    async def select_model(
        self,
        request: ModelRequest,
        policy: ModelRoutePolicy | None = None,
    ) -> ModelSelection | None:
        """Select the best model for *request* using optional *policy*.

        Algorithm:
            1. Filter by availability + required capabilities
            2. Priority sort if *policy.priority* is set
            3. Score by strategy (delegated to ``policies.score_models``)
            4. Apply load penalty
            5. Return highest-scoring model
        """
        all_models = self._registry.get_all()
        merged_policy = policy or ModelRoutePolicy(strategy=self._config.default_policy)

        candidates = [
            m
            for m in all_models
            if m.is_available
            and all(c in m.capabilities for c in request.required_capabilities)
        ]
        if not candidates:
            return None

        # Priority-based short-circuit
        if merged_policy.priority:
            priority_map = {mid: i for i, mid in enumerate(merged_policy.priority)}
            candidates.sort(key=lambda m: priority_map.get(m.id, 999))
            best = candidates[0]
            return ModelSelection(
                model=best,
                provider_name=best.provider,
                confidence=1.0,
                reasoning=f"Matched priority order: {best.id}",
            )

        scored = score_models(candidates, request, merged_policy, self._load_map)
        if not scored:
            return None

        best = scored[0]  # type: ignore[assignment]
        self._record_load(best.model.id)  # type: ignore[attr-defined]

        return ModelSelection(
            model=best.model,  # type: ignore[attr-defined]
            provider_name=best.model.provider,  # type: ignore[attr-defined]
            confidence=max(0.0, min(1.0, best.score - best.load_penalty)),  # type: ignore[attr-defined]
            reasoning=(
                f"Scored {best.score:.2f} (penalty: {best.load_penalty:.2f}): "  # type: ignore[attr-defined]
                f"{merged_policy.strategy}"
            ),
        )

    def _record_load(self, model_id: str) -> None:
        existing = self._load_map.get(model_id)
        self._load_map[model_id] = LoadInfo(
            model_id=model_id,
            active_requests=(existing.active_requests if existing else 0) + 1,
            avg_latency_ms=existing.avg_latency_ms if existing else 0.0,
            last_checked=time.time() * 1000,
        )

    def release_load(self, model_id: str) -> None:
        """Decrement the active-request count for *model_id*."""
        load = self._load_map.get(model_id)
        if load:
            load.active_requests = max(0, load.active_requests - 1)

    def start_auto_refresh(self, interval_ms: int = 30_000) -> Callable[[], None]:
        """Start periodic model discovery refresh.

        Returns a ``dispose`` callable to stop the refresh loop.
        """
        self.stop_auto_refresh()

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval_ms / 1000)
                try:
                    await self._registry.refresh()
                except Exception as exc:
                    _log.warning("[ModelScheduler] auto-refresh failed: %s", exc)

        self._refresh_task = asyncio.create_task(_loop())

        def dispose() -> None:
            self.stop_auto_refresh()

        return dispose

    def stop_auto_refresh(self) -> None:
        """Cancel the auto-refresh task if running."""
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None

    def get_all_loads(self) -> list[LoadInfo]:
        """Return load info for all tracked models."""
        return list(self._load_map.values())
