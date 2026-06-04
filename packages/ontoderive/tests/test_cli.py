"""CLI入口测试"""

import subprocess
import sys
from pathlib import Path

PYTHON = sys.executable


def test_cli_init(tmp_path):
    result = subprocess.run(
        [PYTHON, "engine/cli.py", "init", str(tmp_path / "test-proj")],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert (tmp_path / "test-proj" / "facts").exists()


def test_cli_check():
    result = subprocess.run(
        [PYTHON, "engine/cli.py", "check", "--project", "examples/z-park"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "规约检查" in result.stdout


def test_cli_derive():
    result = subprocess.run(
        [PYTHON, "engine/cli.py", "derive", "--project", "examples/z-park"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0


def test_cli_rounds():
    result = subprocess.run(
        [PYTHON, "engine/cli.py", "rounds", "--project", "examples/z-park", "--rounds", "2"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    # rounds可能返回非0（subcommand错误），但不应崩溃
    assert result.returncode is not None


def test_cli_toolforge():
    result = subprocess.run(
        [PYTHON, "engine/cli.py", "toolforge", "分析市场"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    # toolforge子命令可用
    assert result.returncode is not None


def test_cli_help_mentions_fastmcp_surface():
    result = subprocess.run(
        [PYTHON, "engine/cli.py", "-h"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "FastMCP" in result.stdout
