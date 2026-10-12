"""嵌入请求瞬时断连必须重试而不是击穿构建。

2026-10-10 实证: EG2 服务长跑中静默死亡, RemoteDisconnected 不在
URLError 体系内, 旧实现一次断连就返回空列表 → build 整体崩。
重试 + 指数退避后单次抖动不再致命。
"""

from __future__ import annotations

import http.client
import json
import urllib.request
from unittest.mock import patch

from kos import semantic


def _resp(vector):
    payload = json.dumps({"data": [{"index": 0, "embedding": vector}]}).encode()
    return type("Resp", (), {"read": lambda self: payload, "__enter__": lambda self: self, "__exit__": lambda self, *a: False})()


def test_remote_disconnected_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(semantic, "_get_embed_backend", lambda: "omlx")

    calls = []

    def flaky(req, timeout=None):
        calls.append(1)
        if len(calls) < 3:
            raise http.client.RemoteDisconnected("peer closed")
        return _resp([0.1, 0.2])

    sleeps = []
    monkeypatch.setattr(semantic.time, "sleep", sleeps.append)
    # 注意: semantic 里 urllib.request 是函数内 import, 模块命名空间没有该属性;
    # 必须 patch 全局 urllib.request(同一模块对象), patch semantic.urllib 会 AttributeError
    with patch.object(urllib.request, "urlopen", flaky):
        result = semantic._embed_texts_omlx(["x"])
    assert result == [[0.1, 0.2]]
    assert len(calls) == 3
    assert sleeps == [1, 2]  # 2^0, 2^1 退避


def test_persistent_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(semantic, "_get_embed_backend", lambda: "omlx")

    def always_dead(req, timeout=None):
        raise http.client.RemoteDisconnected("peer closed")

    monkeypatch.setattr(semantic.time, "sleep", lambda _s: None)
    with patch.object(urllib.request, "urlopen", always_dead):
        assert semantic._embed_texts_omlx(["x"]) == []


def test_task_payload_only_for_query(monkeypatch):
    """document(默认)不发送 task 字段, 保持对现有 Qwen3 后端字节级兼容。"""
    monkeypatch.setattr(semantic, "_get_embed_backend", lambda: "omlx")
    import urllib.request as _ur

    seen = []

    def capture(req, timeout=None):
        seen.append(json.loads(req.data.decode()))
        return _resp([0.0])

    with patch.object(_ur, "urlopen", capture):
        semantic._embed_texts_omlx(["doc text"])
        semantic._embed_texts_omlx(["query text"], task="query")
    assert "task" not in seen[0]
    assert seen[1]["task"] == "query"
