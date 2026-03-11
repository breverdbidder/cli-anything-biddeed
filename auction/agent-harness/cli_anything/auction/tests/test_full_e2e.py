"""End-to-end tests for Auction CLI."""

import json
import os
import subprocess
import sys
import shutil

import pytest
from click.testing import CliRunner

from cli_anything.auction.auction_cli import cli


class TestCLIRunner:
    def setup_method(self):
        self.runner = CliRunner()

    def test_help(self):
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Auction CLI" in result.output

    def test_discover_upcoming(self):
        result = self.runner.invoke(cli, ["--json", "discover", "upcoming"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["county"] == "brevard"
        assert data["count"] > 0

    def test_discover_scrape(self):
        result = self.runner.invoke(cli, ["--json", "discover", "scrape", "--date", "sample"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["cases_found"] > 0

    def test_analyze_case(self):
        result = self.runner.invoke(cli, ["--json", "analyze", "case", "--case", "2024-CA-001234"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["case_number"] == "2024-CA-001234"
        assert data["recommendation"] in ("BID", "REVIEW", "SKIP")
        assert data["max_bid"] > 0

    def test_analyze_case_not_found(self):
        result = self.runner.invoke(cli, ["--json", "analyze", "case", "--case", "FAKE-999"])
        assert result.exit_code != 0

    def test_analyze_case_with_overrides(self):
        result = self.runner.invoke(cli, ["--json", "analyze", "case", "--case", "2024-CA-001234",
                                          "--arv", "300000", "--repairs", "40000"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["arv"] == 300000
        assert data["repairs"] == 40000

    def test_analyze_batch(self):
        result = self.runner.invoke(cli, ["--json", "analyze", "batch", "--date", "sample"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] > 0
        assert data["bid"] + data["review"] + data["skip"] == data["analyzed"]

    def test_analyze_liens(self):
        result = self.runner.invoke(cli, ["--json", "analyze", "liens", "--case", "2024-CA-001234"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "liens" in data

    def test_recommend_bid(self):
        result = self.runner.invoke(cli, ["--json", "recommend", "bid", "--date", "sample"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "count" in data

    def test_recommend_summary(self):
        result = self.runner.invoke(cli, ["--json", "recommend", "summary", "--date", "sample"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total" in data

    def test_report_generate_text(self, tmp_path):
        out = str(tmp_path / "report.txt")
        result = self.runner.invoke(cli, ["report", "generate", "--case", "2024-CA-001234",
                                          "--format", "text", "-o", out])
        assert result.exit_code == 0
        assert os.path.exists(out)
        content = open(out).read()
        assert "2024-CA-001234" in content

    def test_report_batch(self, tmp_path):
        out_dir = str(tmp_path / "reports")
        result = self.runner.invoke(cli, ["--json", "report", "batch", "--date", "sample",
                                          "-o", out_dir, "--format", "text"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["generated"] > 0

    def test_export_csv(self, tmp_path):
        out = str(tmp_path / "export.csv")
        result = self.runner.invoke(cli, ["--json", "export", "csv", "--date", "sample", "-o", out])
        assert result.exit_code == 0
        assert os.path.exists(out)

    def test_session_status(self):
        result = self.runner.invoke(cli, ["--json", "session", "status"])
        assert result.exit_code == 0

    def test_discover_help(self):
        result = self.runner.invoke(cli, ["discover", "--help"])
        assert result.exit_code == 0
        assert "upcoming" in result.output

    def test_analyze_help(self):
        result = self.runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "case" in result.output


# ── Subprocess tests ──────────────────────────────────────────────────

def _resolve_cli(name):
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.auction.auction_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-auction")

    def _run(self, args, check=True):
        return subprocess.run(self.CLI_BASE + args, capture_output=True, text=True, check=check)

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Auction" in result.stdout

    def test_analyze_case_json(self):
        result = self._run(["--json", "analyze", "case", "--case", "2024-CA-001234"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["recommendation"] in ("BID", "REVIEW", "SKIP")

    def test_analyze_batch_json(self):
        result = self._run(["--json", "analyze", "batch", "--date", "sample"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["total"] > 0

    def test_discover_upcoming_json(self):
        result = self._run(["--json", "discover", "upcoming"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["county"] == "brevard"


# ── Supabase persistence tests (skip when no credentials) ────────────

SUPABASE_AVAILABLE = os.environ.get("SUPABASE_URL") is not None


@pytest.mark.skipif(not SUPABASE_AVAILABLE, reason="SUPABASE_URL not set")
class TestSupabasePersistence:
    def test_persist_flag_accepted(self):
        """Verify --persist flag is accepted by CLI."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "--persist", "analyze", "case", "--case", "2024-CA-001234"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "recommendation" in data

    def test_audit_log_query(self):
        """Verify audit_log table is queryable."""
        from cli_anything_shared.supabase import query_table
        rows = query_table("audit_log", {"cli": "cli-anything-auction"}, limit=1, cli_name="auction")
        assert isinstance(rows, list)
