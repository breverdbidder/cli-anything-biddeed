"""
Unit tests for evolution/jsonpath_patcher.py.

No external dependencies — all tests run with pure stdlib + pytest.

Coverage:
1. parse_path edge cases (valid, invalid, indexed, multi-index)
2. path_exists for dict + list + missing + non-container
3. set_path mutations including list-append
4. coerce type discriminations
5. Whitelist enforcement (regex match, type, range, enum)
6. AUTO_CREATE_ROOTS materialization
7. Full apply() flow with PatchResult shape
8. Drop-in patch-plan.cjs compat (CI fixture from agentic-video-maker)
9. Scene regen tracking (video-maker back-compat)
"""

from __future__ import annotations

import json

import pytest

from evolution.jsonpath_patcher import (
    parse_path, path_exists, set_path, coerce, ensure_path_parent,
    JsonPathPatcher, PatchResult,
)
from evolution.jsonpath_schema import JsonPathEntry, WhitelistConfig
from evolution.schema import EntryAction


# ── parse_path ────────────────────────────────────────────────────────────────

class TestParsePath:
    def test_simple_dotted(self):
        assert parse_path("audio_mix.music_volume") == ["audio_mix", "music_volume"]

    def test_indexed(self):
        assert parse_path("scenes[3].text_position") == ["scenes", 3, "text_position"]

    def test_multi_index(self):
        assert parse_path("tags[0][2]") == ["tags", 0, 2]

    def test_single_key(self):
        assert parse_path("title") == ["title"]

    def test_empty(self):
        assert parse_path("") is None

    def test_none(self):
        assert parse_path(None) is None  # type: ignore[arg-type]

    def test_invalid_chars(self):
        assert parse_path("scenes[3].text-position") is None  # hyphen not allowed
        assert parse_path("123abc") is None  # can't start with digit


# ── path_exists ───────────────────────────────────────────────────────────────

class TestPathExists:
    def test_dict_parent_exists(self):
        obj = {"a": {"b": 1}}
        assert path_exists(obj, ["a", "b"]) is True

    def test_dict_parent_missing(self):
        obj = {"a": {}}
        assert path_exists(obj, ["a", "b", "c"]) is False

    def test_list_index_in_range(self):
        obj = {"xs": [10, 20, 30]}
        assert path_exists(obj, ["xs", 1]) is True

    def test_list_index_out_of_range(self):
        obj = {"xs": [10]}
        assert path_exists(obj, ["xs", 5, "_"]) is False

    def test_non_container_parent(self):
        obj = {"x": "string"}
        assert path_exists(obj, ["x", "y"]) is False


# ── set_path ──────────────────────────────────────────────────────────────────

class TestSetPath:
    def test_set_dict_leaf(self):
        obj = {"a": {"b": 1}}
        set_path(obj, ["a", "b"], 99)
        assert obj["a"]["b"] == 99

    def test_set_list_index(self):
        obj = {"xs": [1, 2, 3]}
        set_path(obj, ["xs", 1], 99)
        assert obj["xs"] == [1, 99, 3]

    def test_set_list_append_at_end(self):
        obj = {"xs": [1, 2]}
        set_path(obj, ["xs", 2], 99)
        assert obj["xs"] == [1, 2, 99]

    def test_set_list_with_non_int_key_raises(self):
        obj = {"xs": [1]}
        with pytest.raises(TypeError):
            set_path(obj, ["xs", "bad"], 99)


# ── coerce ────────────────────────────────────────────────────────────────────

class TestCoerce:
    def test_true_false(self):
        assert coerce("true") is True
        assert coerce("false") is False

    def test_int(self):
        assert coerce("42") == 42
        assert coerce("-7") == -7

    def test_float(self):
        assert coerce("3.14") == 3.14
        assert coerce("-0.5") == -0.5

    def test_passthrough_string(self):
        assert coerce("hello") == "hello"

    def test_passthrough_non_string(self):
        assert coerce(42) == 42
        assert coerce(True) is True
        assert coerce(None) is None


# ── WhitelistConfig ───────────────────────────────────────────────────────────

class TestWhitelist:
    def test_match_simple(self):
        wl = WhitelistConfig(
            target="t",
            allowed_paths={r"^audio_mix\.music_volume$": dict(type="number", min=0, max=1)},
        )
        assert wl.match("audio_mix.music_volume") is not None
        assert wl.match("audio_mix.something_else") is None

    def test_validate_type_number(self):
        wl = WhitelistConfig(target="t", allowed_paths={r"^x$": dict(type="number")})
        ok, _ = wl.validate_value("x", 1.5)
        assert ok is True
        ok, reason = wl.validate_value("x", "string")
        assert ok is False and "number" in reason

    def test_validate_range(self):
        wl = WhitelistConfig(target="t", allowed_paths={r"^x$": dict(type="number", min=0, max=10)})
        assert wl.validate_value("x", 5)[0] is True
        assert wl.validate_value("x", -1)[0] is False
        assert wl.validate_value("x", 11)[0] is False

    def test_validate_enum(self):
        wl = WhitelistConfig(target="t", allowed_paths={r"^pos$": dict(type="enum", values=["a", "b"])})
        assert wl.validate_value("pos", "a")[0] is True
        assert wl.validate_value("pos", "c")[0] is False

    def test_path_not_whitelisted(self):
        wl = WhitelistConfig(target="t", allowed_paths={r"^x$": dict(type="number")})
        ok, reason = wl.validate_value("y", 1)
        assert ok is False and reason == "path not whitelisted"


# ── ensure_path_parent (AUTO_CREATE_ROOTS) ────────────────────────────────────

class TestAutoCreateRoots:
    def test_materializes_whitelisted_root(self):
        obj: dict = {}
        ok = ensure_path_parent(obj, ["audio_mix", "music_volume"], auto_create_roots={"audio_mix"})
        assert ok is True
        assert obj == {"audio_mix": {}}

    def test_skips_non_whitelisted_root(self):
        obj: dict = {}
        ok = ensure_path_parent(obj, ["arbitrary", "field"], auto_create_roots={"audio_mix"})
        assert ok is False


# ── Full apply() flow ─────────────────────────────────────────────────────────

class TestPatcherApply:
    """Mirrors agentic-video-maker CI smoke test fixture verbatim."""

    @pytest.fixture
    def video_plan(self) -> dict:
        return {
            "title": "Test",
            "scenes": [
                {"i": 1, "duration_sec": 3, "text_on_screen": "hello", "status": "ready"},
                {"i": 2, "duration_sec": 4, "text_on_screen": "world", "status": "ready"},
            ],
        }

    @pytest.fixture
    def video_whitelist(self) -> WhitelistConfig:
        return WhitelistConfig(
            target="video-plan",
            allowed_paths={
                r"^scenes\[\d+\]\.duration_sec$":       dict(type="number"),
                r"^audio_mix\.music_volume$":           dict(type="number", min=0, max=1),
            },
            auto_create_roots={"audio_mix"},
        )

    def test_drop_in_patch_plan_cjs_compat(self, video_plan, video_whitelist):
        """Replicates the exact patch-plan.cjs CI test cases from
        breverdbidder/agentic-video-maker/.github/workflows/ci-smoke.yml"""
        entries = [
            # Patches the duration (string→int coerced, whitelisted)
            JsonPathEntry(skill_name="vm", target="video-plan",
                          field="scenes[0].duration_sec", new_value="5"),
            # Auto-creates audio_mix root + sets sub-field (string→float coerced, in range)
            JsonPathEntry(skill_name="vm", target="video-plan",
                          field="audio_mix.music_volume", new_value="0.12"),
            # Bogus field — should be skipped
            JsonPathEntry(skill_name="vm", target="video-plan",
                          field="does.not.exist", new_value="x"),
        ]
        patcher = JsonPathPatcher(whitelist=video_whitelist)
        result = patcher.apply(video_plan, entries)

        # Matches the ci-smoke.yml node assertion block:
        assert video_plan["scenes"][0]["duration_sec"] == 5
        assert video_plan["scenes"][0]["status"] == "pending"
        assert video_plan["audio_mix"]["music_volume"] == 0.12
        assert result.total_applied == 2
        assert result.total_skipped == 1
        assert result.cli_exit_code == 0

    def test_scenes_to_regen_tracking(self, video_plan, video_whitelist):
        entries = [
            JsonPathEntry(skill_name="vm", target="video-plan",
                          field="scenes[1].duration_sec", new_value=10),
        ]
        patcher = JsonPathPatcher(whitelist=video_whitelist)
        result = patcher.apply(video_plan, entries)
        # Scene 2 (1-based .i) should be flagged
        assert 2 in result.scenes_to_regen
        assert video_plan["scenes"][1]["status"] == "pending"

    def test_empty_entries_returns_exit_code_1(self, video_plan, video_whitelist):
        patcher = JsonPathPatcher(whitelist=video_whitelist)
        result = patcher.apply(video_plan, [])
        assert result.total_applied == 0
        assert result.cli_exit_code == 1

    def test_skip_action_recorded(self, video_plan, video_whitelist):
        entries = [
            JsonPathEntry(skill_name="vm", target="video-plan",
                          field="scenes[0].duration_sec", new_value=5,
                          action=EntryAction.SKIP, skip_reason="manually deferred"),
        ]
        patcher = JsonPathPatcher(whitelist=video_whitelist)
        result = patcher.apply(video_plan, entries)
        assert result.total_applied == 0
        assert result.total_skipped == 1
        assert "manually deferred" in result.skipped[0].reason


# ── Real-world Everest use case: Sentinel thresholds ──────────────────────────

class TestSentinelThresholdsUseCase:
    """The motivating use case from the audit: tune Sentinel thresholds via L3 analyzer."""

    def test_alert_threshold_tuning(self):
        config = {
            "thresholds": {
                "alert_threshold": 100,
                "retry_max": 3,
            }
        }
        wl = WhitelistConfig(
            target="sentinel-thresholds",
            allowed_paths={
                r"^thresholds\.alert_threshold$": dict(type="int", min=10, max=10000),
                r"^thresholds\.retry_max$":       dict(type="int", min=1, max=10),
            },
        )
        entries = [
            JsonPathEntry(skill_name="sentinel", target="sentinel-thresholds",
                          field="thresholds.alert_threshold", new_value="50"),
            # Out of range — should skip
            JsonPathEntry(skill_name="sentinel", target="sentinel-thresholds",
                          field="thresholds.retry_max", new_value="20"),
        ]
        result = JsonPathPatcher(whitelist=wl).apply(config, entries)
        assert config["thresholds"]["alert_threshold"] == 50
        assert config["thresholds"]["retry_max"] == 3  # unchanged
        assert result.total_applied == 1
        assert result.total_skipped == 1
        assert "above max" in result.skipped[0].reason


# ── JsonPathEntry fingerprint determinism ─────────────────────────────────────

class TestEntryFingerprint:
    def test_same_inputs_same_fingerprint(self):
        e1 = JsonPathEntry(skill_name="s", target="t", field="a.b", new_value=1)
        e2 = JsonPathEntry(skill_name="s", target="t", field="a.b", new_value=1)
        assert e1.fingerprint == e2.fingerprint

    def test_different_value_different_fingerprint(self):
        e1 = JsonPathEntry(skill_name="s", target="t", field="a.b", new_value=1)
        e2 = JsonPathEntry(skill_name="s", target="t", field="a.b", new_value=2)
        assert e1.fingerprint != e2.fingerprint
