"""LLM Provider 接口 + 后端实现 — 可插拔"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, cast


def _standard_llm_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "").strip().lower()


def _standard_llm_api_key() -> str | None:
    value = os.environ.get("LLM_API_KEY", "").strip()
    return value or None


class BaseProvider(ABC):
    """LLM provider 抽象基类"""

    def __init__(self, model: str = "", base_url: str = "") -> None:
        self.model = model
        self.base_url = base_url

    @abstractmethod
    def call(self, prompt: str, system: str = "", temperature: float = 0.3) -> str | None: ...

    @abstractmethod
    def probe(self) -> bool: ...


# 本地推理一律经 aetherforge 门面(与 kos.llm_gateway 同一解析顺序; ontoderive 不依赖 kos)。
# 旧实现: 自动探测时优先 `ollama` 子进程与 Ollama 端口 —— 绕过门面, 模型名是后端原生名,
# 不受路由/鉴权/兜底/用量统计约束; 门面上线后这条路径是唯一没被收口的本地推理入口。
_GATEWAY_DEFAULT_URL = "http://127.0.0.1:4000"
_GATEWAY_DEFAULT_MODEL = "fast"  # 门面别名(aetherforge aliases.yaml)


def _gateway_url() -> str:
    return (os.environ.get("LLM_GATEWAY_URL") or os.environ.get("OMLX_URL") or _GATEWAY_DEFAULT_URL).rstrip("/")


def _gateway_key() -> str:
    for name in ("LLM_GATEWAY_KEY", "AETHERFORGE_API_KEY", "OMLX_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", "aetherforge-gateway", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


class GatewayProvider(BaseProvider):
    """aetherforge 门面(OpenAI 兼容 /v1/chat/completions)。"""

    def call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> Any:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        body = {
            "model": self.model or _GATEWAY_DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 500,
        }
        key = _gateway_key()
        headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}
        base = (self.base_url or _gateway_url()).rstrip("/")
        url = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            return (data["choices"][0]["message"].get("content") or "").strip() or None
        except (json.JSONDecodeError, OSError, ValueError, KeyError, IndexError) as e:
            print(f"[llm] 门面调用失败: {e}", file=sys.stderr)
            return None

    def probe(self) -> bool:
        base = (self.base_url or _gateway_url()).rstrip("/").removesuffix("/v1")
        try:
            with urllib.request.urlopen(urllib.request.Request(base + "/health"), timeout=3) as r:
                return r.status == 200
        except OSError:
            return False


class OpenAIProvider(BaseProvider):
    def call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> Any:
        try:
            from openai import OpenAI

            client_kwargs = {}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            api_key = _standard_llm_api_key() or os.environ.get("OPENAI_API_KEY")
            if api_key:
                client_kwargs["api_key"] = api_key
            elif self.base_url:
                client_kwargs["api_key"] = "litellm"

            client = OpenAI(**cast("Any", client_kwargs))
            resp = client.chat.completions.create(
                model=self.model or os.environ.get("ONTODERIVE_LLM_MODEL", "gpt-4o-mini"),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=500,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"[llm] OpenAI调用失败: {e}", file=sys.stderr)
            return None

    def probe(self) -> Any:
        return bool(_standard_llm_api_key() or os.environ.get("OPENAI_API_KEY") or self.base_url)


class AnthropicProvider(BaseProvider):
    def call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> Any:
        try:
            import anthropic  # type: ignore[reportMissingImports]

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if _standard_llm_provider() == "anthropic":
                api_key = _standard_llm_api_key() or api_key
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=self.model or os.environ.get("ONTODERIVE_LLM_MODEL", "claude-sonnet-4-20250514"),
                system=system or None,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=temperature,
            )
            return resp.content[0].text if resp.content else None
        except Exception as e:
            print(f"[llm] Anthropic调用失败: {e}", file=sys.stderr)
            return None

    def probe(self) -> Any:
        return bool(
            os.environ.get("ANTHROPIC_API_KEY") or (_standard_llm_provider() == "anthropic" and _standard_llm_api_key())
        )


class NoneProvider(BaseProvider):
    """空实现 — 静默降级"""

    def call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> None:
        return None

    def probe(self) -> bool:
        return False


# 后端注册表
BACKENDS: dict[str, type[BaseProvider]] = {
    "gateway": GatewayProvider,
    # 旧名兼容: 本地推理现只经门面, LLM_PROVIDER=ollama / ONTODERIVE_LLM_BACKEND=local 也落到门面
    "ollama": GatewayProvider,
    "local": GatewayProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "none": NoneProvider,
}


def detect_backend() -> tuple[str, str]:
    """自动检测可用的LLM后端, 返回 (backend_name, model)"""
    standard_provider = _standard_llm_provider()
    standard_model = os.environ.get("LLM_MODEL", "").strip()
    if standard_provider in {"gateway", "aetherforge", "ollama", "local"}:
        return "gateway", standard_model
    if standard_provider in {"litellm", "openai", "openrouter", "deepseek", "siliconflow"}:
        return "openai", standard_model
    if standard_provider == "anthropic":
        return "anthropic", standard_model
    # 1) 本机 aetherforge 门面
    if GatewayProvider().probe():
        return "gateway", standard_model or _GATEWAY_DEFAULT_MODEL
    # 2) openai key
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", ""
    # 3) anthropic key
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", ""
    return "none", ""


# ── 向后兼容 ──────────────────────────────────────────
# 新代码优先使用 llm-gateway；若独立 CLI 环境没有安装该包，则回退到本地抽象基类。
try:
    from llm_gateway import provider  # type: ignore[reportMissingImports]
except ImportError:
    pass
