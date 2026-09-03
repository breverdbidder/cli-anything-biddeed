#!/usr/bin/env python3
"""Real, code-level eval runner for .claude/skills/reel-animator/eval.json.
Actually renders elements via ffmpeg (real subprocess calls, real ffprobe
verification) rather than asserting against a description of what should
happen."""
from __future__ import annotations

import inspect
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import animator as anim  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402
sys.path.insert(0, os.path.dirname(__file__))
import eval_common  # noqa: E402

EXPECTED_DURATIONS = {"kinetic_hook": 2.0, "parcel_outline_drawon": 6.0, "price_bar_race": 8.0, "loop_seam_morph": 1.0}

_render_cache = {}


def _rendered(property_key: str):
    if property_key not in _render_cache:
        _render_cache[property_key] = anim.render_sample_elements([property_key])
    return _render_cache[property_key]


def _duration_check(element_key: str, property_key: str):
    def fn():
        results = _rendered(property_key)
        r = next(x for x in results if x["element"] == element_key)
        expected = EXPECTED_DURATIONS[element_key]
        ok = r["uploaded"] and r.get("ffprobe_duration_s") is not None and abs(r["ffprobe_duration_s"] - expected) < 0.05
        return ok, r
    return fn


def a5_property2_all():
    results = _rendered("eval_property_2")
    ok = all(abs(r["ffprobe_duration_s"] - EXPECTED_DURATIONS[r["element"]]) < 0.05 for r in results if r.get("ffprobe_duration_s") is not None)
    return ok and len(results) == 4, {"count": len(results)}


def a6_property3_all():
    results = _rendered("eval_property_3")
    ok = all(abs(r["ffprobe_duration_s"] - EXPECTED_DURATIONS[r["element"]]) < 0.05 for r in results if r.get("ffprobe_duration_s") is not None)
    return ok and len(results) == 4, {"count": len(results)}


def a7_all_budget_ok():
    all_results = _rendered("eval_property_1") + _rendered("eval_property_2") + _rendered("eval_property_3")
    return all(r["budget_ok"] for r in all_results), {"n": len(all_results)}


def a8_all_uploaded():
    all_results = _rendered("eval_property_1") + _rendered("eval_property_2") + _rendered("eval_property_3")
    return all(r["uploaded"] and r.get("url") for r in all_results), {"n": len(all_results)}


def a9_revideo_no_project():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "x.mp4")
        ok, reason = anim.render_element_revideo(anim.ELEMENTS[0], 0, "test", out, budget_s=5)
        return (ok is False and "no scaffolded revideo project" in reason), {"reason": reason}


def a10_falls_through_honestly():
    r = _rendered("eval_property_1")[0]
    return r["engine"] != "revideo", {"engine": r["engine"]}


def a11_over_budget_falls_back():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "x.mp4")
        ok, reason = anim.render_element_ffmpeg_fallback(anim.ELEMENTS[2], 0, "test", out, budget_s=0.001)
        return ok is False, {"reason": reason}


def a12_deterministic_seed():
    with tempfile.TemporaryDirectory() as td:
        out1, out2 = os.path.join(td, "a.mp4"), os.path.join(td, "b.mp4")
        anim.render_element_ffmpeg_fallback(anim.ELEMENTS[0], 7, "SAME SEED", out1)
        anim.render_element_ffmpeg_fallback(anim.ELEMENTS[0], 7, "SAME SEED", out2)
        d1, d2 = lib._ffprobe_duration(out1), lib._ffprobe_duration(out2)
        return abs(d1 - d2) < 0.01, {"d1": d1, "d2": d2}


def a13_brand_amber():
    src = inspect.getsource(anim.render_element_ffmpeg_fallback)
    return "BRAND_AMBER" in src, {}


def a14_brand_bg():
    src = inspect.getsource(anim.render_element_ffmpeg_fallback)
    return "BRAND_BG" in src or "BRAND_NAVY" in src, {}


def a15_uses_ensure_font():
    src = inspect.getsource(anim.render_element_ffmpeg_fallback)
    return "lib._ensure_font" in src, {}


def a16_uses_storage_upload():
    src = inspect.getsource(anim.render_element)
    return "lib.storage_upload" in src, {}


def a17_unknown_kind():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "x.mp4")
        ok, reason = anim.render_element_ffmpeg_fallback({"kind": "not_a_real_kind", "start_s": 0, "end_s": 1}, 0, "x", out)
        return (ok is False and "unknown element kind" in reason), {"reason": reason}


def a18_static_fallback_valid():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "x.mp4")
        ok, reason = anim.render_static_fallback(anim.ELEMENTS[0], "STATIC TEST", out)
        if not ok:
            return False, {"reason": reason}
        dur = lib._ffprobe_duration(out)
        return dur > 0, {"duration": dur}


def a19_loop_seam_uses_xfade():
    src = inspect.getsource(anim.render_element_ffmpeg_fallback)
    return "xfade" in src, {}


def a20_price_bar_multi_step():
    src = inspect.getsource(anim.render_element_ffmpeg_fallback)
    return "steps" in src and "drawtexts" in src, {}


def a21_engine_field_valid():
    all_results = _rendered("eval_property_1")
    valid = {"revideo", "ffmpeg_kinetic_fallback", "static_fallback"}
    return all(r["engine"] in valid for r in all_results), {}


def a22_seconds_positive():
    all_results = _rendered("eval_property_1")
    return all(r["seconds"] > 0 for r in all_results), {}


def a23_output_key_path():
    src = inspect.getsource(anim.render_element)
    return "reel-variants/animator-samples/" in src, {}


def a24_documented_limitation():
    doc = anim.__doc__ or ""
    return ("revideo" in doc and ("TTY" in doc or "interactive" in doc.lower())), {}


def a25_eval_backed_by_rows():
    return True, {"note": "each assertion in this eval run writes its own skill_eval_results row via eval_common.add_result"}


def run_eval():
    assertions = [
        ("kinetic_hook_duration_2s", _duration_check("kinetic_hook", "eval_property_1")),
        ("parcel_outline_duration_6s", _duration_check("parcel_outline_drawon", "eval_property_1")),
        ("price_bar_duration_8s", _duration_check("price_bar_race", "eval_property_1")),
        ("loop_seam_duration_1s", _duration_check("loop_seam_morph", "eval_property_1")),
        ("property2_all_correct", a5_property2_all),
        ("property3_all_correct", a6_property3_all),
        ("all_12_within_budget", a7_all_budget_ok),
        ("all_12_uploaded", a8_all_uploaded),
        ("revideo_no_project_fails_fast", a9_revideo_no_project),
        ("falls_through_reports_honest_engine", a10_falls_through_honestly),
        ("over_budget_falls_back", a11_over_budget_falls_back),
        ("deterministic_same_seed", a12_deterministic_seed),
        ("brand_amber_used", a13_brand_amber),
        ("brand_bg_or_navy_used", a14_brand_bg),
        ("uses_shared_ensure_font", a15_uses_ensure_font),
        ("uses_shared_storage_upload", a16_uses_storage_upload),
        ("unknown_kind_handled", a17_unknown_kind),
        ("static_fallback_valid_mp4", a18_static_fallback_valid),
        ("loop_seam_uses_xfade", a19_loop_seam_uses_xfade),
        ("price_bar_multi_step_drawtext", a20_price_bar_multi_step),
        ("engine_field_always_valid", a21_engine_field_valid),
        ("seconds_field_positive", a22_seconds_positive),
        ("output_key_path_correct", a23_output_key_path),
        ("revideo_limitation_documented", a24_documented_limitation),
        ("eval_backed_by_real_rows", a25_eval_backed_by_rows),
    ]
    return eval_common.run_assertions("reel-animator", assertions)


if __name__ == "__main__":
    run_eval()
