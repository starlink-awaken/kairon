from __future__ import annotations

"""Local reflex system — Ollama client, grammar enforcement, prompt compression, idle processing.

Migrated from agentmesh/packages/toolkit/src/local-reflex/.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable


class OllamaClient:
    """HTTP client for local Ollama inference."""

    def __init__(self, base_url: str = "http://localhost:11434", default_model: str = "qwen2.5:7b") -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def generate(self, prompt: str, **options: Any) -> dict[str, Any]:
        import httpx
        model = options.pop("model", self.default_model)
        body = {"model": model, "prompt": prompt, "stream": False, "options": options}
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=body, timeout=120)
            resp.raise_for_status()
            return resp.json()

    async def chat(self, messages: list[dict[str, str]], **options: Any) -> dict[str, Any]:
        import httpx
        model = options.pop("model", self.default_model)
        body = {"model": model, "messages": messages, "stream": False, "options": options}
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=body, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return {"model": data["model"], "response": data.get("message", {}).get("content", ""), "done": data.get("done", True)}

    async def list_models(self) -> list[dict[str, Any]]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            return resp.json().get("models", [])

    async def is_available(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception:
            return False


def _val(value: Any, schema: dict[str, Any], path: str) -> str | None:
    """Recursive JSON schema validation (simplified)."""
    schema_type = schema.get("type")
    if schema_type and value is not None:
        actual = "array" if isinstance(value, list) else type(value).__name__
        if actual != schema_type:
            return f"{path}: Expected {schema_type!r}, got {actual!r}"
    if value is None and schema_type not in (None, "null"):
        return f"{path}: Cannot be null"
    if schema_type == "object" and isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                return f"{path}: Missing required field {req!r}"
        for k, ps in schema.get("properties", {}).items():
            if k in value:
                err = _val(value[k], ps, f"{path}.{k}")
                if err:
                    return err
    if schema_type == "array" and isinstance(value, list) and schema.get("items"):
        for i, item in enumerate(value):
            err = _val(item, schema["items"], f"{path}[{i}]")
            if err:
                return err
    return None


class GrammarEnforcer:
    """Validate structured JSON output against a schema."""

    def __init__(self, schema: dict[str, Any], strict: bool = True, max_retries: int = 3) -> None:
        self._schema = schema
        self._strict = strict

    def build_system_prompt(self) -> str:
        rule = "Do NOT include fields not in the schema" if self._strict else "Additional fields are allowed"
        return f"""You are a structured output generator. Output valid JSON matching this schema:
{json.dumps(self._schema, indent=2)}
Rules:
1. Output valid JSON only - no markdown
2. All required fields MUST be present
3. {rule}"""

    def validate(self, output: str) -> tuple[bool, Any, str | None]:
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as e:
            return False, None, f"Invalid JSON: {e}"
        err = _val(parsed, self._schema, "$")
        return (True, parsed, None) if err is None else (False, None, err)

    def fix_common_errors(self, output: str) -> str:
        output = re.sub(r"^```(?:json)?\s*", "", output)
        output = re.sub(r"```$", "", output)
        output = re.sub(r",\s*([}\]])", r"\1", output.strip())
        for ch, op, cl in (("{", "}", ","), ("[", "]", ",")):
            diff = output.count(op) - output.count(cl)
            if diff > 0:
                output += cl * diff
        return output


@dataclass
class CompressionResult:
    original: str = ""
    compressed: str = ""
    ratio: float = 1.0
    preserved_keywords: list[str] = field(default_factory=list)


class PromptCompressor:
    """Compress text using rule-based strategies."""

    def __init__(self, ratio: float = 0.4) -> None:
        self._ratio = ratio

    def compress(self, text: str) -> CompressionResult:
        compressed = re.sub(r"\s+", " ", text)
        filler = r"\b(基本上|实际上|事实上|as you know|basically|actually|obviously)\b"
        compressed = re.sub(filler, "", compressed, flags=re.IGNORECASE)
        compressed = re.sub(r"\([^)]*\)", "", compressed)
        compressed = re.sub(r"[#*_`~\[\]]", "", compressed)
        target = round(len(text) * self._ratio)
        if len(compressed) > target > 10:
            half = target // 2
            compressed = compressed[:half] + "..." + compressed[-half:]
        keywords = [m for m in re.findall(r"[a-z]+[A-Z][a-z]+|[一-鿿]{2,}|\d+(?:\.\d+)?", compressed)][:20]
        return CompressionResult(original=text, compressed=compressed.strip(), ratio=len(compressed) / max(len(text), 1), preserved_keywords=keywords)


@dataclass
class IdleTask:
    id: str = ""
    name: str = ""
    enabled: bool = True
    handler: Callable[[], Any] = lambda: None


class IdleProcessor:
    """Background task processor for idle periods."""

    def __init__(self, idle_threshold_s: float = 300.0) -> None:
        self._tasks: dict[str, IdleTask] = {}
        self._idle_threshold = idle_threshold_s
        self._last_activity = time.time()
        self._running = False

    def register(self, task: IdleTask) -> None:
        self._tasks[task.id] = task

    def remove(self, task_id: str) -> bool:
        return self._tasks.pop(task_id, None) is not None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._last_activity = time.time()

    def stop(self) -> None:
        self._running = False

    @property
    def is_idle(self) -> bool:
        return (time.time() - self._last_activity) >= self._idle_threshold

    async def execute_all(self) -> list[str]:
        completed: list[str] = []
        for task in self._tasks.values():
            if not task.enabled:
                continue
            try:
                result = task.handler()
                if hasattr(result, "__await__"):
                    await result
                completed.append(task.id)
            except Exception:
                pass
        return completed
