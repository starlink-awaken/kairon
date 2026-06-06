"""Pytest configuration for eidos tests."""

import pytest


@pytest.fixture
def sample_entity():
    """创建一个样本 Entity 用于测试。"""
    return {"id": "test-entity-1", "type": "concept", "name": "Test Entity"}
