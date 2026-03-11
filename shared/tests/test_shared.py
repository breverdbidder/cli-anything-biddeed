"""Unit tests for cli_anything_shared utilities.

No external dependencies required — all Supabase calls are mocked.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Config tests ──────────────────────────────────────────────────────

from cli_anything_shared.config import (
    load_config, save_config, get_config, delete_config, _config_path
)


class TestConfig:
    def test_config_path(self):
        path = _config_path("test-cli")
        assert "cli-anything" in str(path)
        assert "test-cli" in str(path)
        assert str(path).endswith("config.json")

    def test_load_missing_config(self):
        assert load_config("nonexistent-cli-xyz") == {}

    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli_anything_shared.config.CONFIG_DIR", tmp_path)
        save_config("test", "api_key", "sk-123")
        assert get_config("test", "api_key") == "sk-123"

    def test_env_var_priority(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli_anything_shared.config.CONFIG_DIR", tmp_path)
        save_config("test", "api_key", "from-file")
        monkeypatch.setenv("TEST_API_KEY", "from-env")
        val = get_config("test", "api_key", env_var="TEST_API_KEY")
        assert val == "from-env"

    def test_default_value(self):
        val = get_config("nonexistent", "missing_key", default="fallback")
        assert val == "fallback"

    def test_delete_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli_anything_shared.config.CONFIG_DIR", tmp_path)
        save_config("test", "key1", "val1")
        assert delete_config("test", "key1") is True
        assert get_config("test", "key1") is None

    def test_delete_missing_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli_anything_shared.config.CONFIG_DIR", tmp_path)
        assert delete_config("test", "nope") is False


# ── Cost tracking tests ───────────────────────────────────────────────

from cli_anything_shared.cost import CostTracker, BudgetExceeded, PRICING


class TestCostTracker:
    def test_log_single_call(self):
        tracker = CostTracker(budget=1.00, cli="test", command="analyze")
        cost = tracker.log("claude-sonnet-4.5", tokens_in=1000, tokens_out=500)
        assert cost > 0
        assert tracker.total_tokens_in == 1000
        assert tracker.total_tokens_out == 500
        assert len(tracker.entries) == 1

    def test_free_model_zero_cost(self):
        tracker = CostTracker()
        cost = tracker.log("gemini-2.5-flash", tokens_in=10000, tokens_out=5000)
        assert cost == 0.0
        assert tracker.total_cost == 0.0

    def test_budget_enforcement(self):
        tracker = CostTracker(budget=0.001)
        tracker.log("claude-opus-4.6", tokens_in=100000, tokens_out=50000)
        with pytest.raises(BudgetExceeded):
            tracker.enforce_budget()

    def test_budget_ok(self):
        tracker = CostTracker(budget=10.00)
        tracker.log("deepseek-v3.2", tokens_in=1000, tokens_out=500)
        tracker.enforce_budget()  # Should not raise

    def test_summary(self):
        tracker = CostTracker(budget=5.00, cli="auction", command="batch")
        tracker.log("claude-sonnet-4.5", tokens_in=2000, tokens_out=1000)
        tracker.log("deepseek-v3.2", tokens_in=500, tokens_out=200)
        summary = tracker.summary()
        assert summary["cli"] == "auction"
        assert summary["command"] == "batch"
        assert summary["calls"] == 2
        assert summary["total_tokens_in"] == 2500
        assert summary["total_tokens_out"] == 1200
        assert summary["budget_usd"] == 5.00

    def test_context_manager(self):
        with CostTracker(budget=1.00) as tracker:
            tracker.log("deepseek-v3.2", tokens_in=100, tokens_out=50)
        assert tracker.total_cost >= 0

    def test_unknown_model_uses_default_pricing(self):
        tracker = CostTracker()
        cost = tracker.log("unknown-model", tokens_in=1_000_000, tokens_out=0)
        # Default pricing: $3/M input
        assert cost == 3.00

    def test_multiple_entries_accumulate(self):
        tracker = CostTracker()
        tracker.log("deepseek-v3.2", tokens_in=1000, tokens_out=500)
        tracker.log("deepseek-v3.2", tokens_in=2000, tokens_out=1000)
        assert tracker.total_tokens_in == 3000
        assert tracker.total_tokens_out == 1500
        assert len(tracker.entries) == 2


# ── Audit logging tests ──────────────────────────────────────────────

from cli_anything_shared.audit import _hash_args, log_audit, audit_logged


class TestAudit:
    def test_hash_args_deterministic(self):
        h1 = _hash_args(("case1",), {"persist": True})
        h2 = _hash_args(("case1",), {"persist": True})
        assert h1 == h2
        assert len(h1) == 12

    def test_hash_args_different(self):
        h1 = _hash_args(("case1",), {})
        h2 = _hash_args(("case2",), {})
        assert h1 != h2

    @patch("cli_anything_shared.supabase.persist_result")
    def test_log_audit_success(self, mock_persist):
        mock_persist.return_value = {"id": 1}
        result = log_audit(
            cli="cli-anything-test",
            command="analyze",
            duration_ms=1000,
            result_summary="BID",
        )
        assert result == {"id": 1}
        mock_persist.assert_called_once()

    @patch("cli_anything_shared.supabase.persist_result", side_effect=Exception("DB down"))
    def test_log_audit_graceful_failure(self, mock_persist):
        result = log_audit(cli="test", command="fail", duration_ms=0)
        assert result is None  # Should not raise

    def test_audit_decorator(self):
        @audit_logged("cli-anything-test")
        def my_command(x):
            return x * 2

        with patch("cli_anything_shared.audit.log_audit") as mock_log:
            result = my_command(5)
            assert result == 10
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[1]["cli"] == "cli-anything-test"
            assert call_kwargs[1]["command"] == "my_command"
            assert call_kwargs[1]["result_summary"] == "success"

    def test_audit_decorator_on_exception(self):
        @audit_logged("cli-anything-test")
        def failing_command():
            raise ValueError("bad input")

        with patch("cli_anything_shared.audit.log_audit") as mock_log:
            with pytest.raises(ValueError):
                failing_command()
            call_kwargs = mock_log.call_args
            assert "error" in call_kwargs[1]["result_summary"]


# ── Supabase client tests (mocked) ───────────────────────────────────

from cli_anything_shared.supabase import reset_client


class TestSupabase:
    def setup_method(self):
        reset_client()

    def test_get_client_raises_without_config(self):
        from cli_anything_shared.supabase import get_client
        # Clear any env vars
        os.environ.pop("SUPABASE_URL", None)
        os.environ.pop("SUPABASE_KEY", None)
        with pytest.raises(RuntimeError, match="Supabase not configured"):
            get_client("nonexistent-cli")

    @patch("cli_anything_shared.supabase.get_config")
    def test_persist_result(self, mock_config):
        mock_config.return_value = None
        # Can't test actual Supabase without keys, but verify the interface
        from cli_anything_shared.supabase import persist_result
        with pytest.raises(RuntimeError):
            persist_result("test_table", {"key": "value"}, "no-cli")

    def test_reset_client(self):
        reset_client()  # Should not raise
