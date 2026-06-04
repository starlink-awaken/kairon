"""Middleware chain for request processing pipelines.

Provides a Middleware protocol, concrete implementations
(ErrorHandler, Logger, RateLimit, Security, Validation), and a
MiddlewareChain to execute them in order.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

Context = dict[str, Any]
NextFn = Callable[[Context], Context]


class Middleware:
    """Base middleware with a process(context, next) interface."""

    def process(self, context: Context, next_fn: NextFn) -> Context:
        return next_fn(context)


class ErrorHandler(Middleware):
    """Catch exceptions raised by downstream middleware."""

    def process(self, context: Context, next_fn: NextFn) -> Context:
        try:
            return next_fn(context)
        except Exception as exc:
            context["error"] = str(exc)
            context["error_handled"] = True
            return context


class Logger(Middleware):
    """Log the start and duration of the middleware chain execution."""

    def process(self, context: Context, next_fn: NextFn) -> Context:
        context.setdefault("logs", [])
        context["logs"].append(f"[Logger] start at {time.time():.3f}")
        start = time.monotonic()
        result = next_fn(context)
        elapsed = time.monotonic() - start
        context["logs"].append(f"[Logger] completed in {elapsed:.4f}s")
        return result


class RateLimit(Middleware):
    """Simple in-memory rate limiter based on a token bucket per key."""

    def __init__(self, max_requests: int = 10, window_seconds: float = 1.0) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = {}

    def process(self, context: Context, next_fn: NextFn) -> Context:
        key = context.get("client_id", "default")
        now = time.monotonic()
        timestamps = self._buckets.setdefault(key, [])
        # purge expired timestamps
        self._buckets[key] = [t for t in timestamps if now - t < self.window]
        if len(self._buckets[key]) >= self.max_requests:
            context["error"] = "rate_limit_exceeded"
            context["rate_limited"] = True
            return context
        self._buckets[key].append(now)
        return next_fn(context)


class Security(Middleware):
    """Check for forbidden patterns in context payloads."""

    def __init__(self, forbidden: list[str] | None = None) -> None:
        self.forbidden = forbidden or ["<script>", "DROP TABLE", "rm -rf"]

    def process(self, context: Context, next_fn: NextFn) -> Context:
        payload = str(context.get("payload", ""))
        for pattern in self.forbidden:
            if pattern.lower() in payload.lower():
                context["error"] = f"forbidden_pattern:{pattern}"
                context["security_blocked"] = True
                return context
        return next_fn(context)


class Validation(Middleware):
    """Validate that required keys exist in the context."""

    def __init__(self, required_keys: list[str] | None = None) -> None:
        self.required_keys = required_keys or ["payload"]

    def process(self, context: Context, next_fn: NextFn) -> Context:
        for key in self.required_keys:
            if key not in context:
                context["error"] = f"missing_required_key:{key}"
                context["validation_failed"] = True
                return context
        return next_fn(context)


class MiddlewareChain:
    """Composable middleware chain.

    Middleware are added via add() and executed in FIFO order
    when execute() is called.
    """

    def __init__(self) -> None:
        self._middleware: list[Middleware] = []

    def add(self, mw: Middleware) -> MiddlewareChain:
        self._middleware.append(mw)
        return self

    def execute(self, context: Context) -> Context:  # type: ignore[return]
        """Run all middleware in sequence, each calling the next."""

        def final(context: Context) -> Context:
            return context

        chain = final
        for mw in reversed(self._middleware):
            prev = chain
            chain = lambda ctx, m=mw, n=prev: m.process(ctx, n)  # noqa: E731  # type: ignore[misc]
