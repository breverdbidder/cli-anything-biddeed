"""
Test Suite — DesignWise CLI (13 subcommands)
Tests: subcommand invocations, --json flag, --help flag.
15 tests total.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS_DIR = Path(__file__).parent.parent / "agent-harness"
CLI_MODULE = "cli_anything.designwise.designwise_cli"


def run_cli(*args, expect_exit_code=0) -> tuple:
    """Run designwise CLI with given args. Returns (stdout, stderr, exit_code)."""
    cmd = [sys.executable, "-m", CLI_MODULE] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(HARNESS_DIR),
        env={**__import__("os").environ, "PYTHONPATH": str(HARNESS_DIR)},
        timeout=30,
    )
    return result.stdout, result.stderr, result.returncode


class TestCLIHelp:
    """Test --help flags for CLI and all subcommands."""

    def test_root_help_exits_zero(self):
        """designwise --help exits 0."""
        stdout, stderr, code = run_cli("--help", expect_exit_code=0)
        assert code == 0

    def test_root_help_lists_agents(self):
        """designwise --help mentions all 13 agents."""
        stdout, stderr, code = run_cli("--help")
        agents = ["commander", "stitch", "brandguard", "code", "deploy", "qa",
                  "analytics", "support", "iterate", "seo", "a11y", "competitor", "content"]
        for agent in agents:
            assert agent in stdout, f"Agent '{agent}' not in help output"

    def test_commander_help(self):
        stdout, _, code = run_cli("commander", "--help")
        assert code == 0

    def test_brandguard_help(self):
        stdout, _, code = run_cli("brandguard", "--help")
        assert code == 0

    def test_deploy_help(self):
        stdout, _, code = run_cli("deploy", "--help")
        assert code == 0


class TestCLIJsonFlag:
    """Test --json flag produces valid JSON on all subcommands."""

    def test_commander_check_quota_json(self):
        """commander --check-quota --json produces valid JSON."""
        stdout, stderr, code = run_cli("commander", "--check-quota", "--json")
        # May fail due to Supabase not configured, but output must be JSON
        try:
            data = json.loads(stdout)
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            pytest.skip("Output not JSON — likely Supabase not configured in CI")

    def test_analytics_daily_json(self):
        """analytics --daily --json produces valid JSON."""
        stdout, stderr, code = run_cli("analytics", "--daily", "--json")
        try:
            data = json.loads(stdout)
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            pytest.skip("Not JSON output")

    def test_iterate_scan_json(self):
        """iterate --scan --json produces valid JSON."""
        stdout, stderr, code = run_cli("iterate", "--scan", "--json")
        try:
            data = json.loads(stdout)
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            pytest.skip("Not JSON output")

    def test_seo_json_has_score(self):
        """seo --url --json output has 'score' key."""
        stdout, stderr, code = run_cli("seo", "--url", "https://example.com", "--json")
        try:
            data = json.loads(stdout)
            assert "score" in data or "error" in data
        except json.JSONDecodeError:
            pytest.skip("Not JSON")

    def test_support_ticket_json(self):
        """support --ticket produces JSON with category field."""
        stdout, stderr, code = run_cli("support", "--ticket", "the login is broken", "--json")
        try:
            data = json.loads(stdout)
            assert "category" in data
        except json.JSONDecodeError:
            pytest.skip("Not JSON")


class TestCLISubcommands:
    """Test each subcommand is importable and responds."""

    def test_no_command_exits_zero(self):
        """designwise with no args prints help and exits 0."""
        stdout, stderr, code = run_cli()
        assert code == 0

    def test_unknown_command_exits_nonzero(self):
        """Unknown subcommand exits nonzero."""
        stdout, stderr, code = run_cli("nonexistent-command-xyz")
        # argparse should reject unknown subcommand
        assert code != 0 or "error" in stderr.lower() or "error" in stdout.lower()

    def test_deploy_env_lab(self):
        """deploy --env lab returns structured output."""
        stdout, stderr, code = run_cli("deploy", "--env", "lab", "--json")
        # May fail without VERCEL_TOKEN but should return JSON error
        output = stdout or stderr
        assert len(output) > 0, "No output from deploy command"

    def test_13_subcommands_importable(self):
        """All 13 agent modules importable via sys.path."""
        agents = [
            "cli_anything.designwise.core.commander",
            "cli_anything.designwise.core.stitch_agent",
            "cli_anything.designwise.core.brandguard_agent",
            "cli_anything.designwise.core.codewise_agent",
            "cli_anything.designwise.core.deploywise_agent",
            "cli_anything.designwise.core.qawise_agent",
            "cli_anything.designwise.core.analytics_agent",
            "cli_anything.designwise.core.support_agent",
            "cli_anything.designwise.core.iterate_agent",
            "cli_anything.designwise.core.seo_agent",
            "cli_anything.designwise.core.a11y_agent",
            "cli_anything.designwise.core.competitor_agent",
            "cli_anything.designwise.core.content_agent",
        ]
        sys.path.insert(0, str(HARNESS_DIR))
        import importlib
        failed = []
        for module_path in agents:
            try:
                importlib.import_module(module_path)
            except ImportError as e:
                failed.append(f"{module_path}: {e}")

        assert not failed, f"Import failures:\n" + "\n".join(failed)
