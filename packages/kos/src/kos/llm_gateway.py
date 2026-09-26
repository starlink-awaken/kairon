"""KOS → aetherforge 网关的唯一连接点(地址 + 密钥)。

此前各模块各写一份: 地址写死为 tailnet IP(机器换 IP 后全部失联), 密钥写死为
"123456" / "sk-omlx-admin" / "local"(网关一律 401), 连接失败又被静默吞掉并降级,
结果语义索引从未建成、实体抽取从未跑通, 而表面上"没报错"。

解析顺序:
  地址  LLM_GATEWAY_URL → OMLX_URL → http://127.0.0.1:4000 (KOS 与门面同机, 走 loopback)
  密钥  LLM_GATEWAY_KEY → AETHERFORGE_API_KEY → OMLX_API_KEY → macOS Keychain(aetherforge-gateway)
"""

from __future__ import annotations

import functools
import os
import subprocess

DEFAULT_URL = "http://127.0.0.1:4000"
_KEYCHAIN_SERVICE = "aetherforge-gateway"


def gateway_url() -> str:
    return (os.environ.get("LLM_GATEWAY_URL") or os.environ.get("OMLX_URL") or DEFAULT_URL).rstrip("/")


@functools.lru_cache(maxsize=1)
def _keychain_key() -> str:
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", _KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def gateway_key() -> str:
    for name in ("LLM_GATEWAY_KEY", "AETHERFORGE_API_KEY", "OMLX_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    return _keychain_key()


def auth_headers() -> dict[str, str]:
    key = gateway_key()
    return {"Authorization": f"Bearer {key}"} if key else {}
