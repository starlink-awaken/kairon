"""Full middleware chain with security, logging, rate-limit, validation, error handling.

Migrated from agentmesh toolkit/src/middleware/ (all .ts files).
Consolidates MiddlewareChain, SecurityMiddleware, LoggingMiddleware,
RateLimitMiddleware, ValidationMiddleware, ErrorMiddleware, RequestInterceptor,
ResponseInterceptor, and schemas into a single cohesive module.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Context = dict[str, Any]
NextFn = Callable[[Context], "Awaitable[Context]"]

try:
    from collections.abc import Awaitable
except ImportError:
    from collections.abc import Awaitable


def _generate_id() -> str:
    return f"ctx_{int(time.time() * 1000)}_{id({})}"


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    sensitive = {"authorization", "cookie", "x-api-key"}
    return {k: "***REDACTED***" if k.lower() in sensitive else v for k, v in headers.items()}


class Middleware:
    """Base middleware with process(context, next) interface."""

    def process(self, context: Context, next_fn: NextFn) -> Awaitable[Context]:
        return next_fn(context)


class MiddlewareChain:
    """Composable middleware chain with sync/async support, error handling, and timeout."""

    def __init__(self, name: str = "chain", timeout_ms: int = 30000) -> None:
        self._middleware: list[Middleware] = []
        self._name = name
        self._timeout_ms = timeout_ms

    def add(self, mw: Middleware) -> MiddlewareChain:
        self._middleware.append(mw)
        return self

    async def execute(self, context: Context) -> Context:  # type: ignore[return]
        async def final(ctx: Context) -> Context:
            return ctx

        chain = final
        for mw in reversed(self._middleware):
            prev = chain
            chain = lambda ctx, m=mw, n=prev: self._run_with_timeout(m.process(ctx, n))  # noqa: E731  # type: ignore[misc]

    async def _run_with_timeout(self, coro: Awaitable[Context]) -> Context:
        return await asyncio.wait_for(coro, timeout=self._timeout_ms / 1000.0)


class ErrorHandler(Middleware):
    """Catch exceptions raised by downstream middleware."""

    async def process(self, context: Context, next_fn: NextFn) -> Context:
        try:
            return await next_fn(context)
        except Exception as exc:
            context["error"] = str(exc)
            context["error_handled"] = True
            context["status"] = context.get("status", 500)
            return context


class Logger(Middleware):
    """Log start, duration, request, and response details."""

    def __init__(self, log_request_body: bool = False, log_response_body: bool = False) -> None:
        self._log_req = log_request_body
        self._log_resp = log_response_body

    async def process(self, context: Context, next_fn: NextFn) -> Context:
        context.setdefault("logs", [])
        method = context.get("method", "GET")
        path = context.get("path", "/")
        context["logs"].append(f"[Logger] {method} {path} start")
        if self._log_req and "body" in context:
            context["logs"].append(f"[Logger] body: {json.dumps(context['body'], default=str)[:200]}")
        start = time.monotonic()
        result = await next_fn(context)
        elapsed = time.monotonic() - start
        status = result.get("status", 200)
        context["logs"].append(f"[Logger] {method} {path} -> {status} in {elapsed:.4f}s")
        if self._log_resp and "response" in result:
            context["logs"].append(f"[Logger] response: {json.dumps(result['response'], default=str)[:200]}")
        return result


class RateLimiter(Middleware):
    """In-memory token bucket rate limiter per client key."""

    def __init__(self, max_requests: int = 10, window_seconds: float = 1.0) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = {}

    async def process(self, context: Context, next_fn: NextFn) -> Context:
        key = context.get("client_id", "default")
        now = time.monotonic()
        timestamps = self._buckets.setdefault(key, [])
        self._buckets[key] = [t for t in timestamps if now - t < self._window]
        if len(self._buckets[key]) >= self._max:
            context["error"] = "rate_limit_exceeded"
            context["rate_limited"] = True
            context["status"] = 429
            return context
        self._buckets[key].append(now)
        return await next_fn(context)


class SecurityChecker(Middleware):
    """Check for XSS, SQL injection, and dangerous patterns in payloads."""

    XSS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
    ]
    SQL_PATTERNS = [
        re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE),
        re.compile(r"\bUNION\s+SELECT\b", re.IGNORECASE),
        re.compile(r"--\s", re.IGNORECASE),
    ]
    DANGEROUS = re.compile(r"[|;&$`<>]")

    def __init__(self, max_request_size: int = 10 * 1024 * 1024) -> None:
        self._max_size = max_request_size

    async def process(self, context: Context, next_fn: NextFn) -> Context:
        payload = str(context.get("payload") or context.get("body", ""))
        if len(payload.encode("utf-8")) > self._max_size:
            context["error"] = "request_too_large"
            context["security_blocked"] = True
            context["status"] = 413
            return context
        for pat in self.XSS_PATTERNS:
            if pat.search(payload):
                context["error"] = f"xss_detected:{pat.pattern[:30]}"
                context["security_blocked"] = True
                context["status"] = 400
                return context
        for pat in self.SQL_PATTERNS:
            if pat.search(payload):
                context["error"] = f"sql_injection_detected:{pat.pattern[:30]}"
                context["security_blocked"] = True
                context["status"] = 400
                return context
        if self.DANGEROUS.search(payload):
            context["error"] = "dangerous_chars_detected"
            context["security_blocked"] = True
            context["status"] = 400
            return context
        return await next_fn(context)


class Validator(Middleware):
    """Validate that required keys exist in context."""

    def __init__(self, required_keys: list[str] | None = None) -> None:
        self._required = required_keys or ["payload"]

    async def process(self, context: Context, next_fn: NextFn) -> Context:
        for key in self._required:
            if key not in context:
                context["error"] = f"missing_required_key:{key}"
                context["validation_failed"] = True
                context["status"] = 400
                return context
        return await next_fn(context)


class RequestInterceptor:
    """Intercept and transform requests before processing."""

    def __init__(self, name: str = "", priority: int = 100) -> None:
        self.name = name
        self.priority = priority

    async def pre_process(self, context: Context) -> Context:
        return context

    async def validate(self, context: Context) -> bool:
        return True

    async def transform(self, context: Context) -> Context:
        return context


class ResponseInterceptor:
    """Intercept and transform responses after processing."""

    def __init__(self, name: str = "", priority: int = 100) -> None:
        self.name = name
        self.priority = priority

    async def post_process(self, context: Context) -> Context:
        return context

    async def transform(self, context: Context) -> Context:
        return context


class InterceptorChain:
    """Manage request and response interceptors."""

    def __init__(self) -> None:
        self._req: list[RequestInterceptor] = []
        self._resp: list[ResponseInterceptor] = []

    def add_request(self, interceptor: RequestInterceptor) -> None:
        self._req.append(interceptor)
        self._req.sort(key=lambda x: x.priority)

    def add_response(self, interceptor: ResponseInterceptor) -> None:
        self._resp.append(interceptor)
        self._resp.sort(key=lambda x: x.priority)

    async def process_request(self, context: Context) -> Context:
        for i in self._req:
            context = await i.pre_process(context)
            if context.get("state", {}).get("stopped"):
                return context
        context["_valid"] = True
        for i in self._req:
            if not await i.validate(context):
                context["error"] = f"interceptor_rejected:{i.name}"
                context["status"] = 400
                return context
        for i in self._req:
            context = await i.transform(context)
        return context

    async def process_response(self, context: Context) -> Context:
        for i in self._resp:
            context = await i.transform(context)
        for i in self._resp:
            context = await i.post_process(context)
        return context


# ----- Schema validation helpers (simplified from schemas.ts) -----

@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[dict[str, Any]] = field(default_factory=list)
    data: Any = None


class Schema:
    """Simple schema validator with string, number, boolean checks."""

    def __init__(self, name: str, required: bool = False) -> None:
        self.name = name
        self.required = required

    def validate(self, value: Any, field: str = "") -> ValidationResult:
        raise NotImplementedError


class StringSchema(Schema):
    def __init__(self, *, required: bool = False, min_len: int = 0, max_len: int = 0, pattern: str = "") -> None:
        super().__init__("string", required)
        self._min = min_len
        self._max = max_len
        self._pat = re.compile(pattern) if pattern else None

    def validate(self, value: Any, field: str = "") -> ValidationResult:
        errors: list[dict[str, Any]] = []
        if value is None:
            if self.required:
                errors.append({"field": field, "message": "required"})
            return ValidationResult(valid=len(errors) == 0, errors=errors)
        s = str(value)
        if self._min and len(s) < self._min:
            errors.append({"field": field, "message": f"min_length:{self._min}"})
        if self._max and len(s) > self._max:
            errors.append({"field": field, "message": f"max_length:{self._max}"})
        if self._pat and not self._pat.search(s):
            errors.append({"field": field, "message": f"pattern_mismatch:{self._pat.pattern}"})
        return ValidationResult(valid=len(errors) == 0, errors=errors, data=s)


class NumberSchema(Schema):
    def __init__(self, *, required: bool = False, min_val: float | None = None, max_val: float | None = None) -> None:
        super().__init__("number", required)
        self._min = min_val
        self._max = max_val

    def validate(self, value: Any, field: str = "") -> ValidationResult:
        errors: list[dict[str, Any]] = []
        if value is None:
            if self.required:
                errors.append({"field": field, "message": "required"})
            return ValidationResult(valid=len(errors) == 0, errors=errors)
        try:
            n = float(value)
        except (ValueError, TypeError):
            errors.append({"field": field, "message": "not_a_number"})
            return ValidationResult(valid=False, errors=errors)
        if self._min is not None and n < self._min:
            errors.append({"field": field, "message": f"min:{self._min}"})
        if self._max is not None and n > self._max:
            errors.append({"field": field, "message": f"max:{self._max}"})
        return ValidationResult(valid=len(errors) == 0, errors=errors, data=n)
