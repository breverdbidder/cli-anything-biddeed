"""
Unit tests for evolution/evolver_jsonpath.py.

All LLM HTTP calls are mocked — no real API traffic, no real cost.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from evolution.evolver_jsonpath import JsonPathEvolver
from evolution.jsonpath_schema import JsonPathEntry, WhitelistConfig
from evolution.schema import EntryAction, EvolutionSignal, SignalType


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def signals() -> list[EvolutionSignal]:
    return [
        EvolutionSignal(
            signal_type=SignalType.SCORE_REGRESSION,
            skill_name="sentinel-thresholds",
            excerpt="Alert volume dropped 80% after threshold change; missing real failures.",
            source="eval_runner",
        )
    ]


@pytest.fixture
def whitelist() -> WhitelistConfig:
    return WhitelistConfig(
        target="sentinel-thresholds",
        allowed_paths={
            r"^thresholds\.alert_threshold$": dict(type="int", min=10, max=10000),
            r"^thresholds\.retry_max$":       dict(type="int", min=1, max=10),
        },
    )


@pytest.fixture
def config() -> dict:
    return {"thresholds": {"alert_threshold": 100, "retry_max": 3}}


# ── _parse_entries ────────────────────────────────────────────────────────────

class TestParseEntries:
    def test_well_formed_response(self, signals):
        evo = JsonPathEvolver(skill_name="sentinel-thresholds")
        llm_output = json.dumps({
            "entries": [
                {"field": "thresholds.alert_threshold", "new_value": 50,
                 "action": "update", "reason": "alerts too quiet"}
            ]
        })
        result = evo._parse_entries(
            llm_output, signals=signals, model="deepseek-chat", token_cost=0.001,
        )
        assert len(result) == 1
        assert result[0].field == "thresholds.alert_threshold"
        assert result[0].new_value == 50
        assert result[0].action == EntryAction.UPDATE
        assert result[0].llm_model_used == "deepseek-chat"
        assert result[0].source_signal_id == signals[0].id

    def test_json_in_markdown_fence(self, signals):
        evo = JsonPathEvolver(skill_name="x")
        llm_output = '```json\n{"entries": [{"field": "a.b", "new_value": 1}]}\n```'
        result = evo._parse_entries(llm_output, signals=signals,
                                    model="m", token_cost=0)
        assert len(result) == 1
        assert result[0].field == "a.b"

    def test_garbage_returns_empty(self, signals):
        evo = JsonPathEvolver(skill_name="x")
        assert evo._parse_entries("nonsense output", signals=signals,
                                  model="m", token_cost=0) == []

    def test_drops_missing_field(self, signals):
        evo = JsonPathEvolver(skill_name="x")
        llm_output = json.dumps({"entries": [{"new_value": 1}, {"field": "ok.path", "new_value": 2}]})
        result = evo._parse_entries(llm_output, signals=signals,
                                    model="m", token_cost=0)
        assert len(result) == 1
        assert result[0].field == "ok.path"

    def test_drops_missing_new_value(self, signals):
        evo = JsonPathEvolver(skill_name="x")
        llm_output = json.dumps({"entries": [{"field": "a.b"}, {"field": "c.d", "new_value": 5}]})
        result = evo._parse_entries(llm_output, signals=signals,
                                    model="m", token_cost=0)
        assert len(result) == 1
        assert result[0].field == "c.d"

    def test_invalid_action_defaults_to_update(self, signals):
        evo = JsonPathEvolver(skill_name="x")
        llm_output = json.dumps({"entries": [{"field": "a.b", "new_value": 1, "action": "bogus"}]})
        result = evo._parse_entries(llm_output, signals=signals,
                                    model="m", token_cost=0)
        assert len(result) == 1
        assert result[0].action == EntryAction.UPDATE

    def test_respects_max_entries(self, signals):
        evo = JsonPathEvolver(skill_name="x", max_entries=1)
        llm_output = json.dumps({"entries": [
            {"field": "a.b", "new_value": 1},
            {"field": "c.d", "new_value": 2},
        ]})
        result = evo._parse_entries(llm_output, signals=signals,
                                    model="m", token_cost=0)
        assert len(result) == 1


# ── _build_prompt ─────────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_prompt_includes_critical_sections(self, signals, whitelist, config):
        evo = JsonPathEvolver(skill_name="sentinel-thresholds")
        prompt = evo._build_prompt(signals, config, whitelist, score_context="No score data.")
        # Sanity: prompt mentions key elements
        assert "sentinel-thresholds" in prompt
        # The whitelist regex has escaped dots, so check for the unique substrings.
        assert "alert_threshold" in prompt              # whitelist key + config value
        assert "retry_max" in prompt                    # whitelist key + config value
        assert '"min": 10' in prompt                    # constraint
        assert "score_regression" in prompt              # signal type
        assert "WHITELIST" in prompt
        assert "MUST match a whitelist pattern" in prompt

    def test_prompt_caps_long_config(self, signals, whitelist):
        evo = JsonPathEvolver(skill_name="x")
        big_config = {"data": "x" * 10000}
        prompt = evo._build_prompt(signals, big_config, whitelist, score_context="")
        # 3000 char cap on config dump; prompt overall is bigger because of template,
        # but the config dump section is bounded.
        assert len(prompt) < 6000


# ── _format_score_context ─────────────────────────────────────────────────────

class TestScoreContext:
    def test_no_scores(self):
        evo = JsonPathEvolver(skill_name="x")
        assert evo._format_score_context(None, None) == "No score data available."

    def test_drop(self):
        evo = JsonPathEvolver(skill_name="x")
        msg = evo._format_score_context(0.8, 0.6)
        assert "dropped" in msg
        assert "80.0%" in msg and "60.0%" in msg

    def test_improvement(self):
        evo = JsonPathEvolver(skill_name="x")
        msg = evo._format_score_context(0.5, 0.7)
        assert "improved" in msg


# ── generate() full path with mocked LLMs ─────────────────────────────────────

class TestGenerateFullPath:
    def _mock_httpx_response(self, json_body: dict, status: int = 200):
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.json.return_value = json_body
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    @patch("httpx.post")
    def test_deepseek_primary_returns_patches(self, mock_post, signals, whitelist, config):
        # DeepSeek returns a valid patch
        mock_post.return_value = self._mock_httpx_response({
            "choices": [{"message": {"content": json.dumps({
                "entries": [{"field": "thresholds.alert_threshold",
                             "new_value": 50, "action": "update",
                             "reason": "too quiet"}]
            })}}],
            "usage": {"total_tokens": 100},
        })
        evo = JsonPathEvolver(
            skill_name="sentinel-thresholds",
            gemini_api_key="",       # skip RCA (returns all signals)
            deepseek_api_key="ds",
        )
        entries = evo.generate(signals, config=config, whitelist=whitelist)
        assert len(entries) == 1
        assert entries[0].field == "thresholds.alert_threshold"
        assert entries[0].new_value == 50
        assert evo._total_token_cost > 0

    @patch("httpx.post")
    def test_deepseek_empty_falls_back_to_claude(self, mock_post, signals, whitelist, config):
        # First call (DeepSeek) returns garbage; second call (Claude) returns good
        deepseek_resp = self._mock_httpx_response({
            "choices": [{"message": {"content": "no valid json"}}],
            "usage": {"total_tokens": 50},
        })
        claude_resp = self._mock_httpx_response({
            "content": [{"text": json.dumps({
                "entries": [{"field": "thresholds.retry_max",
                             "new_value": 5, "action": "update",
                             "reason": "retry too aggressive"}]
            })}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })
        mock_post.side_effect = [deepseek_resp, claude_resp]

        evo = JsonPathEvolver(
            skill_name="sentinel-thresholds",
            gemini_api_key="",            # skip RCA
            deepseek_api_key="ds",
            anthropic_api_key="ant",
        )
        entries = evo.generate(signals, config=config, whitelist=whitelist)
        assert len(entries) == 1
        assert entries[0].field == "thresholds.retry_max"
        assert entries[0].new_value == 5
        assert entries[0].llm_model_used == "claude-sonnet-4-6"
        assert mock_post.call_count == 2

    @patch("httpx.post")
    def test_no_signals_short_circuits(self, mock_post, whitelist, config):
        evo = JsonPathEvolver(skill_name="x", deepseek_api_key="ds")
        assert evo.generate([], config=config, whitelist=whitelist) == []
        assert mock_post.call_count == 0

    @patch("httpx.post")
    def test_no_keys_returns_empty_silently(self, mock_post, signals, whitelist, config):
        evo = JsonPathEvolver(
            skill_name="x",
            gemini_api_key="",
            deepseek_api_key="",
            anthropic_api_key="",
        )
        result = evo.generate(signals, config=config, whitelist=whitelist)
        assert result == []
        assert mock_post.call_count == 0


# ── Integration: generate() + JsonPathPatcher.apply() round-trip ──────────────

class TestEvolveAndApplyRoundTrip:
    """The real value: end-to-end LLM-emit → patcher-apply, no manual schema knowledge."""

    @patch("httpx.post")
    def test_evolve_then_apply_lands_change(self, mock_post, signals, whitelist, config):
        from evolution.jsonpath_patcher import JsonPathPatcher

        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "choices": [{"message": {"content": json.dumps({
                    "entries": [{"field": "thresholds.alert_threshold",
                                 "new_value": 50, "action": "update",
                                 "reason": "too quiet"}]
                })}}],
                "usage": {"total_tokens": 100},
            }),
            raise_for_status=MagicMock(return_value=None),
        )
        evo = JsonPathEvolver(
            skill_name="sentinel-thresholds",
            gemini_api_key="",  # skip RCA
            deepseek_api_key="ds",
        )
        entries = evo.generate(signals, config=config, whitelist=whitelist)
        patcher = JsonPathPatcher(whitelist=whitelist)
        result = patcher.apply(config, entries)
        # The config dict was mutated in place by the patcher.
        assert config["thresholds"]["alert_threshold"] == 50
        assert config["thresholds"]["retry_max"] == 3  # untouched
        assert result.total_applied == 1
        assert result.total_skipped == 0
