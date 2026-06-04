"""Runnable composition: sequences, parallel, lambda, binding.

Migrated from agentmesh toolkit/src/langchain/ (Runnable, RunnableLambda,
RunnableParallel, RunnableSequence, SkillRunnable, types).
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass
class RunnableConfig:
    timeout: float = 0.0
    max_retries: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RunnableInterface(ABC):
    """Minimal interface for all Runnable components."""

    name: str = ""

    @abstractmethod
    async def invoke(self, input_val: Any, config: RunnableConfig | None = None) -> Any:
        ...

    async def batch(self, inputs: list[Any], config: RunnableConfig | None = None) -> list[Any]:
        return [await self.invoke(inp, config) for inp in inputs]

    async def stream(self, input_val: Any, config: RunnableConfig | None = None) -> AsyncGenerator[Any]:
        yield await self.invoke(input_val, config)

    def pipe(self, next_runnable: RunnableInterface) -> RunnableSequence:
        return RunnableSequence(first=self, last=next_runnable)


class Runnable(RunnableInterface):
    """Abstract base class for all Runnable components."""

    def __init__(self, name: str = "", description: str = "") -> None:
        self.name = name or self.__class__.__name__
        self._description = description

    async def _before(self, input_val: Any, config: RunnableConfig | None) -> None:
        pass

    async def _after(self, output_val: Any, config: RunnableConfig | None) -> None:
        pass

    async def invoke(self, input_val: Any, config: RunnableConfig | None = None) -> Any:
        cfg = config or RunnableConfig()
        await self._before(input_val, cfg)
        last_error: Exception | None = None
        for attempt in range(cfg.max_retries + 1):
            try:
                result = await self._invoke(input_val, cfg)
                await self._after(result, cfg)
                return result
            except Exception as e:
                last_error = e
                if attempt < cfg.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise last_error  # type: ignore[misc]

    @abstractmethod
    async def _invoke(self, input_val: Any, config: RunnableConfig) -> Any:
        ...


class RunnableLambda(Runnable):
    """Wrap a Python function as a Runnable."""

    def __init__(self, func: Callable[[Any], Any], name: str = "", description: str = "") -> None:
        super().__init__(name or getattr(func, "__name__", "lambda"), description)
        self._func = func

    async def _invoke(self, input_val: Any, config: RunnableConfig) -> Any:
        result = self._func(input_val)
        if asyncio.iscoroutine(result):
            return await result
        return result

    def pipe_func(self, next_func: Callable[[Any], Any]) -> RunnableLambda:
        orig = self._func
        def composed(inp: Any) -> Any:
            mid = orig(inp)
            if asyncio.iscoroutine(mid):
                return next_func(mid)
            return next_func(mid)
        return RunnableLambda(composed, name=f"{self.name}->pipe")


class RunnableSequence(Runnable):
    """Execute runnables in sequence, piping output to input."""

    def __init__(self, first: RunnableInterface, last: RunnableInterface, middle: list[RunnableInterface] | None = None) -> None:
        super().__init__("RunnableSequence")
        self._first = first
        self._middle = middle or []
        self._last = last

    async def _invoke(self, input_val: Any, config: RunnableConfig) -> Any:
        cur: Any = await self._first.invoke(input_val, config)
        for m in self._middle:
            cur = await m.invoke(cur, config)
        return await self._last.invoke(cur, config)

    async def stream(self, input_val: Any, config: RunnableConfig | None = None) -> AsyncGenerator[Any]:
        async for chunk in self._first.stream(input_val, config):
            cur: Any = chunk
        for m in self._middle:
            async for chunk in m.stream(cur, config):
                cur = chunk
        async for chunk in self._last.stream(cur, config):
            yield chunk

    @classmethod
    def from_runnables(cls, *runnables: RunnableInterface) -> RunnableSequence:
        if len(runnables) == 0:
            raise ValueError("At least one Runnable required")
        if len(runnables) == 1:
            return cls(first=runnables[0], last=runnables[0])
        return cls(first=runnables[0], last=runnables[-1], middle=list(runnables[1:-1]))


class RunnableParallel(Runnable):
    """Execute multiple runnables in parallel over the same input."""

    def __init__(self, **runnables: RunnableInterface) -> None:
        super().__init__("RunnableParallel")
        self._runnables: dict[str, RunnableInterface] = runnables

    async def _invoke(self, input_val: Any, config: RunnableConfig) -> dict[str, Any]:
        async def run(key: str, r: RunnableInterface) -> tuple[str, Any]:
            try:
                return key, await r.invoke(input_val, config)
            except Exception as e:
                return key, {"error": str(e)}
        results = await asyncio.gather(*(run(k, r) for k, r in self._runnables.items()))
        return dict(results)

    def add(self, name: str, runnable: RunnableInterface) -> RunnableParallel:
        self._runnables[name] = runnable
        return self

    def remove(self, name: str) -> RunnableParallel:
        self._runnables.pop(name, None)
        return self

    @property
    def count(self) -> int:
        return len(self._runnables)

    def get_keys(self) -> list[str]:
        return list(self._runnables.keys())

    @classmethod
    def empty(cls) -> RunnableParallel:
        return cls()


class RunnablePick(Runnable):
    """Pick specific keys from a dict input."""

    def __init__(self, keys: list[str], name: str = "") -> None:
        super().__init__(name or "pick")
        self._keys = keys

    async def _invoke(self, input_val: Any, config: RunnableConfig) -> Any:
        d = input_val if isinstance(input_val, dict) else {}
        return {k: d.get(k) for k in self._keys}


class RunnableCoalesce(Runnable):
    """Try each runnable in order until one succeeds."""

    def __init__(self, *runnables: RunnableInterface, name: str = "") -> None:
        super().__init__(name or "coalesce")
        self._runnables = list(runnables)

    async def _invoke(self, input_val: Any, config: RunnableConfig) -> Any:
        last_error: Exception | None = None
        for r in self._runnables:
            try:
                return await r.invoke(input_val, config)
            except Exception as e:
                last_error = e
        raise last_error  # type: ignore[misc]


__all__ = [
    "Runnable",
    "RunnableInterface",
    "RunnableConfig",
    "RunnableLambda",
    "RunnableSequence",
    "RunnableParallel",
    "RunnablePick",
    "RunnableCoalesce",
]
