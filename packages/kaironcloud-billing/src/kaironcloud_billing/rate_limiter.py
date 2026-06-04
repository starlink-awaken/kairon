from __future__ import annotations

"""
---
Type: Module | Status: ACTIVE | Layer: L3 | Domain: D-Cloud
Summary: Token Bucket rate limiter for Cloud API Gateway.
Source: SharedBrain D_Cloud/organs/gateway/rate_limiter.py
---
"""
import logging
import threading
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket with fixed refill rate per second.

    Attributes:
        capacity: Max tokens the bucket can hold.
        refill_rate: Tokens added per second.
    """

    capacity: int
    refill_rate: float
    tokens: float = field(init=False)
    last_refill: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume *tokens* from the bucket."""
        with self._lock:
            self._refill()
            if self.tokens < tokens:
                return False
            self.tokens -= tokens
            return True

    def available(self) -> int:
        """Return the number of tokens currently available."""
        with self._lock:
            self._refill()
            return int(self.tokens)

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(float(self.capacity), self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


class RateLimiter:
    """Multi-key rate limiter backed by token buckets.

    Maintains one :class:`TokenBucket` per key (e.g. tenant+endpoint).
    Expired buckets are periodically cleaned up by a daemon thread.

    Attributes:
        default_capacity: Default bucket capacity (max burst).
        default_refill_rate: Default tokens added per second.
    """

    def __init__(
        self,
        default_capacity: int = 100,
        default_refill_rate: float = 1.67,
        cleanup_interval: int = 300,
        bucket_ttl: int = 3600,
    ) -> None:
        self.default_capacity = default_capacity
        self.default_refill_rate = default_refill_rate
        self.cleanup_interval = cleanup_interval
        self.bucket_ttl = bucket_ttl
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()
        self._start_cleanup_thread()

    def check(self, key: str) -> bool:
        """Check if a request identified by *key* is allowed."""
        bucket = self._get_or_create(key)
        return bucket.consume(1)

    def remaining(self, key: str) -> int:
        """Return the number of remaining tokens for *key*."""
        bucket = self._buckets.get(key)
        return bucket.available() if bucket else self.default_capacity

    def reset(self, key: str) -> None:
        """Reset (refill) the bucket for *key*."""
        bucket = self._buckets.get(key)
        if bucket is not None:
            with bucket._lock:
                bucket.tokens = float(bucket.capacity)
                bucket.last_refill = time.time()

    def clear_all(self) -> None:
        """Remove all tracked buckets."""
        with self._lock:
            self._buckets.clear()
            _log.info("Cleared all buckets")

    def _get_or_create(self, key: str) -> TokenBucket:
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(
                    capacity=self.default_capacity,
                    refill_rate=self.default_refill_rate,
                )
                self._buckets[key] = bucket
            return bucket

    def _start_cleanup_thread(self) -> None:
        def _loop() -> None:
            while True:
                time.sleep(self.cleanup_interval)
                self._cleanup()

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()

    def _cleanup(self) -> None:
        now = time.time()
        with self._lock:
            stale = [k for k, b in self._buckets.items() if now - b.last_refill > self.bucket_ttl]
            for k in stale:
                del self._buckets[k]
            if stale:
                _log.debug("Cleaned up %d stale buckets", len(stale))
