"""End-to-end tests for ZoneWise CLI.

Tests the CLI interface via Click's CliRunner and subprocess.
"""

import json
import os
import subprocess
import sys
import shutil

import pytest
from click.testing import CliRunner

from cli_anything.zonewise.zonewise_cli import cli


# ── CLI Runner tests ──────────────────────────────────────────────────

class TestCLIRunner:
    def setup_method(self):
        self.runner = CliRunner()

    def test_help(self):
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ZoneWise CLI" in result.output

    def test_county_list(self):
        result = self.runner.invoke(cli, ["county", "list"])
        assert result.exit_code == 0
        assert "brevard" in result.output

    def test_county_list_json(self):
        result = self.runner.invoke(cli, ["--json", "county", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 46
        assert data["state"] == "FL"

    def test_county_scrape_tier4(self):
        result = self.runner.invoke(cli, ["--json", "county", "scrape", "--county", "brevard", "--tier", "4"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "manual_flag"
        assert data["county"] == "brevard"

    def test_county_scrape_invalid(self):
        result = self.runner.invoke(cli, ["--json", "county", "scrape", "--county", "fake"])
        assert result.exit_code != 0

    def test_county_status(self):
        result = self.runner.invoke(cli, ["--json", "county", "status", "--county", "brevard"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["county"] == "brevard"

    def test_parcel_lookup_no_args(self):
        result = self.runner.invoke(cli, ["--json", "parcel", "lookup"])
        assert result.exit_code != 0

    def test_parcel_lookup_address(self):
        result = self.runner.invoke(cli, ["--json", "parcel", "lookup", "--address", "123 Main St"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query_type"] == "address"

    def test_export_json(self, tmp_path):
        out = str(tmp_path / "test.json")
        result = self.runner.invoke(cli, ["--json", "export", "json", "--county", "brevard", "-o", out])
        assert result.exit_code == 0
        assert os.path.exists(out)

    def test_export_csv(self, tmp_path):
        out = str(tmp_path / "test.csv")
        result = self.runner.invoke(cli, ["--json", "export", "csv", "--county", "brevard", "-o", out])
        assert result.exit_code == 0

    def test_session_status(self):
        result = self.runner.invoke(cli, ["--json", "session", "status"])
        assert result.exit_code == 0

    def test_config_set_get(self):
        result = self.runner.invoke(cli, ["config", "set", "test_key", "test_value"])
        assert result.exit_code == 0

    def test_county_help(self):
        result = self.runner.invoke(cli, ["county", "--help"])
        assert result.exit_code == 0
        assert "scrape" in result.output
        assert "list" in result.output


# ── Subprocess tests (installed CLI) ──────────────────────────────────

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.zonewise.zonewise_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-zonewise")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True, check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "ZoneWise" in result.stdout

    def test_county_list_json(self):
        result = self._run(["--json", "county", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] == 46

    def test_county_scrape_tier4_json(self):
        result = self._run(["--json", "county", "scrape", "--county", "orange", "--tier", "4"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "manual_flag"
