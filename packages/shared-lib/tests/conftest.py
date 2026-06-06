"""Pytest configuration for shared-lib tests."""

import pytest


@pytest.fixture
def temp_workspace(tmp_path):
    """临时工作空间目录。"""
    return tmp_path
