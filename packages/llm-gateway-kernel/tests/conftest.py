"""Pytest configuration for llm-gateway-kernel tests."""

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    """清理环境变量以确保测试隔离。"""
    for var in ("BOS_ROOT", "BOS_SKIP_COGNITION", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
