"""Basic tests for Forge tool registry and discovery."""

import shutil
import subprocess

import pytest

FORGE = shutil.which("forge") or shutil.which("forge-bridge")


def _run_cli(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [FORGE, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout or proc.stderr


class TestForgeBasic:
    @pytest.mark.skipif(not FORGE, reason="forge CLI not found on PATH")
    def test_forge_help(self):
        rc, out = _run_cli("--help")
        assert rc == 0

    @pytest.mark.skipif(not FORGE, reason="forge CLI not found on PATH")
    def test_forge_status(self):
        rc, out = _run_cli("status")
        assert rc in (0, 1)  # 1 if no backend available

    @pytest.mark.skipif(not FORGE, reason="forge CLI not found on PATH")
    def test_forge_list(self):
        rc, out = _run_cli("list")
        assert rc == 0
