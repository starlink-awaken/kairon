import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "engine"))

# 测试环境禁用LLM，避免ollama冷启动导致测试超时
os.environ.setdefault("ONTODERIVE_LLM_BACKEND", "none")


@pytest.fixture(scope="session")
def project_root():
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def z_park_path(project_root):
    return project_root / "examples" / "z-park"


@pytest.fixture
def tmp_project(tmp_path):
    """创建临时 OntoDerive 项目"""
    for d in ["facts", "entities", "inferences", "protocols", "scheme", "_logs"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "facts" / "data.md").write_text(
        "| 编号 | 数据 | 数值 | 来源 |\n|------|------|------|------|\n| D-F1 | 测试事实 | 100 | 测试 |\n"
    )
    (tmp_path / "facts" / "policy.md").write_text(
        "| 编号 | 政策 | 发布主体 | 日期 |\n|------|------|---------|------|\n| P-F1 | 测试政策 | 测试 | 2024 |\n"
    )
    return tmp_path


@pytest.fixture
def mock_facts():
    """返回标准测试用事实字典"""
    return {
        "D-F1": {"desc": "测试事实A", "value": "100"},
        "D-F2": {"desc": "测试事实B", "value": "200"},
    }


@pytest.fixture
def mock_inferences():
    """返回标准测试用推论字典"""
    return {
        "INF-L1": {
            "text": "## 推论测试\nconfidence: high\n结论: 这是一个测试推论\n",
            "derives_from": ["D-F1", "D-F2"],
        },
    }


class _MockEnhancer:
    """模拟LLMEnhancer，返回固定结果，无需LLM连接"""

    available = True
    backend = "mock"
    model = "mock-model"

    def _call(self, prompt, system="", temperature=0.3):
        """模拟LLM调用，返回固定响应"""
        return "模拟分析结论：建议增加事实引用"

    def enhance_derivation_hints(self, facts_summary, inferences_text, existing_hints):
        return existing_hints + ["mock hint: 增加事实引用以提升追溯率"]

    def detect_contradictions(self, inference_a, inference_b, shared_facts):
        return False

    def smart_match_tools(self, goal, context, tools_descriptions):
        return [t["id"] for t in tools_descriptions[:3]] if tools_descriptions else []

    def derive_insights(self, project_root, facts_summary, inferences_text):
        return []


@pytest.fixture
def mock_enhancer():
    """返回模拟的LLM增强器，用于测试LLM依赖路径"""
    return _MockEnhancer()
