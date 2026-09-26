"""kos.llm_gateway: 地址/密钥解析顺序, 以及不再有写死的 tailnet IP 或假 key。"""

from __future__ import annotations

import pathlib

import pytest
from kos import llm_gateway


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_GATEWAY_URL", "OMLX_URL", "LLM_GATEWAY_KEY", "AETHERFORGE_API_KEY", "OMLX_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    llm_gateway._keychain_key.cache_clear()


def test_url_defaults_to_loopback() -> None:
    assert llm_gateway.gateway_url() == "http://127.0.0.1:4000"


def test_url_env_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMLX_URL", "http://b:4000/")
    assert llm_gateway.gateway_url() == "http://b:4000"
    monkeypatch.setenv("LLM_GATEWAY_URL", "http://a:4000")
    assert llm_gateway.gateway_url() == "http://a:4000"


def test_key_env_beats_keychain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_gateway, "_keychain_key", lambda: "from-keychain")
    monkeypatch.setenv("OMLX_API_KEY", "k3")
    monkeypatch.setenv("LLM_GATEWAY_KEY", "k1")
    assert llm_gateway.auth_headers() == {"Authorization": "Bearer k1"}


def test_key_falls_back_to_keychain_and_omits_header_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_gateway, "_keychain_key", lambda: "from-keychain")
    assert llm_gateway.auth_headers() == {"Authorization": "Bearer from-keychain"}
    monkeypatch.setattr(llm_gateway, "_keychain_key", lambda: "")
    assert llm_gateway.auth_headers() == {}


def test_no_hardcoded_gateway_ip_or_fake_keys_left() -> None:
    src = pathlib.Path(llm_gateway.__file__).resolve().parent
    offenders = [
        str(p.relative_to(src))
        for p in src.rglob("*.py")
        if p.name != "llm_gateway.py"  # 它的文档字符串记录了这些旧值
        and any(bad in p.read_text(encoding="utf-8") for bad in ("100.96.126.35", "sk-omlx-admin", '"123456"'))
    ]
    assert offenders == []
