"""End-to-end tests for Spatial Conquest CLI."""

import json
import os
import subprocess
import sys
import shutil

import pytest
from click.testing import CliRunner

from cli_anything.spatial.spatial_cli import cli


class TestCLIRunner:
    def setup_method(self):
        self.runner = CliRunner()

    def test_help(self):
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Spatial Conquest CLI" in result.output

    def test_list_counties(self):
        result = self.runner.invoke(cli, ["--json", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] >= 1
        assert any(c["county"] == "brevard" for c in data["counties"])

    def test_discover_brevard(self):
        result = self.runner.invoke(cli, ["--json", "discover", "--county", "brevard"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["county"] == "brevard"
        assert data["status"] == "known"
        assert "zoning" in data

    def test_discover_unknown(self):
        result = self.runner.invoke(cli, ["--json", "discover", "--county", "fakecounty"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "unknown"

    def test_status(self):
        result = self.runner.invoke(cli, ["--json", "status"])
        assert result.exit_code == 0

    def test_validate_no_supabase(self):
        result = self.runner.invoke(cli, ["--json", "validate", "--county", "brevard"])
        assert result.exit_code == 0

    def test_config_set(self):
        result = self.runner.invoke(cli, ["config", "set", "test_key", "test_val"])
        assert result.exit_code == 0

    def test_conquer_help(self):
        result = self.runner.invoke(cli, ["conquer", "--help"])
        assert result.exit_code == 0
        assert "--county" in result.output
        assert "--safeguard" in result.output

    def test_conquer_unknown_county(self):
        result = self.runner.invoke(cli, ["--json", "conquer", "--county", "fakecounty"])
        assert result.exit_code != 0


# ── Subprocess tests ──────────────────────────────────────────

def _resolve_cli(name):
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH.")
    return [sys.executable, "-m", "cli_anything.spatial.spatial_cli"]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-spatial")

    def _run(self, args, check=True):
        return subprocess.run(self.CLI_BASE + args, capture_output=True, text=True, check=check)

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Spatial" in result.stdout

    def test_list_json(self):
        result = self._run(["--json", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] >= 1

    def test_discover_brevard_json(self):
        result = self._run(["--json", "discover", "--county", "brevard"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["county"] == "brevard"
