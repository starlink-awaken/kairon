"""Basic tests for Forge tool registry and discovery."""

import shutil
import subprocess

import pytest

FORGE = shutil.which("forge") or shutil.which("forge-bridge")


class TestForgeBasic:
    @pytest.mark.skipif(not FORGE, reason="forge CLI not found on PATH")
    def test_forge_help(self):
        rc, out = subprocess.getstatusoutput([FORGE, "--help"])
        assert rc == 0

    @pytest.mark.skipif(not FORGE, reason="forge CLI not found on PATH")
    def test_forge_status(self):
        rc, out = subprocess.getstatusoutput([FORGE, "status"])
        assert rc in (0, 1)  # 1 if no backend available

    @pytest.mark.skipif(not FORGE, reason="forge CLI not found on PATH")
    def test_forge_list(self):
        rc, out = subprocess.getstatusoutput([FORGE, "list"])
        assert rc == 0
