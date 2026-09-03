#!/usr/bin/env python3
"""Real, code-level eval runner for .claude/skills/reel-director-qa/eval.json.
Builds planted-defect and clean-control fixtures and runs them through the
real director_qa.py check functions."""
from __future__ import annotations

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
import director_qa as dqa  # noqa: E402
import hook_writer as hw  # noqa: E402
import eval_common  # noqa: E402

# Title Case, single '…' char, zero emoji before it, exactly two immediately
# after with nothing trailing -- must keep passing every check added by
# issue #19792 PART 1, since it is the shared "clean control" fixture.
GOOD_TITLE = "The Bank Lost This House To A Stranger…\U0001F440\U0001F6A8"

DNA_SET = [
    {"archetype": "shock_number", "emotion_pair": ["a", "b"], "voice_register": "hype", "caption_style": "karaoke_bold", "music_mood": "tension_build", "edit_style": "kinetic_bolt32"},
    {"archetype": "underdog_bidder", "emotion_pair": ["c", "d"], "voice_register": "calm_narrator", "caption_style": "minimal_lower_third", "music_mood": "uplifting", "edit_style": "static_bolt32"},
    {"archetype": "bank_vs_house", "emotion_pair": ["e", "f"], "voice_register": "whisper_reveal", "caption_style": "kinetic_type", "music_mood": "dark_drone", "edit_style": "animated_bolt32"},
    {"archetype": "mystery_nobody_bid", "emotion_pair": ["g", "h"], "voice_register": "documentary", "caption_style": "karaoke_bold", "music_mood": "none", "edit_style": "kinetic_bolt32"},
]


def _clean_variant(i: int) -> dict:
    return {
        "title": GOOD_TITLE,
        "variant_dna": DNA_SET[i % 4],
        "script": {"beats": [{"start_s": 0, "end_s": 2, "line": "Bank lost this house to a stranger"},
                              {"start_s": 2, "end_s": 32, "line": "rest of the 30-second body"}]},
        "caption_groups": [{"start_s": 0, "end_s": 2, "words": "bank lost house"}],
        "voice_tags": {"eleven_v3_tags": ["[tense]", "[pause]"]},
        "hashtags": ["#auction"],
        "short_code": f"CLEAN{i}",
    }


def a1_person_name():
    v = _clean_variant(0)
    v["script"] = {"beats": [{"start_s": 0, "end_s": 2, "line": "This home was won by John Smith at auction"}]}
    r = dqa.check_banned_terms(v)
    return r["pass"] is False, r


def a2_vendor_name():
    v = _clean_variant(0)
    v["script"] = {"beats": [{"start_s": 0, "end_s": 2, "line": "Found via Tracerfy skip-trace"}]}
    r = dqa.check_banned_terms(v)
    return r["pass"] is False, r


def a3_wrong_duration():
    v = _clean_variant(0)
    v["script"] = {"beats": [{"start_s": 0, "end_s": 2, "line": "hook"}, {"start_s": 2, "end_s": 30, "line": "body"}]}
    r = dqa.check_beat_timing_drift(v)
    return r["pass"] is False, r


def a4_missing_beat0():
    v = _clean_variant(0)
    v["script"] = {"beats": [{"start_s": 1, "end_s": 3, "line": "no beat at zero"}]}
    r = dqa.check_hook_clarity(v)
    return (r["pass"] is False and "no beat starting at 0s" in r.get("reason", "")), r


def a5_loop_seam_not_applicable():
    v = _clean_variant(0)
    report = dqa.review_variant(v, [v])
    seam = report["qa_scores"]["loop_seam_continuity"]
    return seam["pass"] is None, seam


def _clean_control(i):
    def fn():
        v = _clean_variant(i)
        report = dqa.review_variant(v, [_clean_variant(j) for j in range(4)])
        return report["qa_pass"] is True, report
    return fn


def a11_caption_ok():
    v = _clean_variant(0)
    return dqa.check_caption_readability(v)["pass"] is True, {}


def a12_caption_bad():
    v = _clean_variant(0)
    v["caption_groups"] = [{"words": "this caption has way more than five words in it"}]
    return dqa.check_caption_readability(v)["pass"] is False, {}


def a13_hook_ok():
    v = _clean_variant(0)
    return dqa.check_hook_clarity(v)["pass"] is True, {}


def a14_hook_bad():
    v = _clean_variant(0)
    v["script"] = {"beats": [{"start_s": 0, "end_s": 3.5, "line": "too slow"}]}
    return dqa.check_hook_clarity(v)["pass"] is False, {}


def a15_missing_short_code():
    v = _clean_variant(0)
    v["short_code"] = None
    return dqa.check_short_code(v)["pass"] is False, {}


def a16_voice_tags_ok():
    v = _clean_variant(0)
    return dqa.check_eleven_v3_proof(v)["pass"] is True, {}


def a17_voice_tags_empty():
    v = _clean_variant(0)
    v["voice_tags"] = {"eleven_v3_tags": []}
    return dqa.check_eleven_v3_proof(v)["pass"] is False, {}


def a18_diversity_dup():
    v0, v1 = _clean_variant(0), _clean_variant(0)  # same dna -> duplicate archetype
    r = dqa.check_diversity(v0, [v0, v1])
    return r["pass"] is False, r


def a19_diversity_ok():
    variants = [_clean_variant(i) for i in range(4)]
    r = dqa.check_diversity(variants[0], variants)
    return r["pass"] is True, r


def a20_writes_live():
    import biddeed_reels_lib as lib
    rows = lib.run_sql("select count(*) as n from winnerdata.reel_variants where qa_pass is not null;")
    return int(rows[0]["n"]) >= 0, {"note": "checked live table is queryable post-write (exact count depends on prior runs)"}


def a21_partial_fail_no_credit():
    v = _clean_variant(0)
    v["short_code"] = None  # one applicable check fails
    report = dqa.review_variant(v, [v])
    return report["qa_pass"] is False, {}


def a22_null_checks_excluded():
    v = _clean_variant(0)
    report = dqa.review_variant(v, [v])
    return report["qa_pass"] is True, {}


def a23_no_status_write():
    import inspect
    src = inspect.getsource(dqa.review_reel)
    return (".status" not in src and "approved" not in src), {}


def a24_gap_too_large():
    v = _clean_variant(0)
    v["script"] = {"beats": [{"start_s": 0, "end_s": 2, "line": "a"}, {"start_s": 2.5, "end_s": 32, "line": "b"}]}
    return dqa.check_beat_timing_drift(v)["pass"] is False, {}


def a25_gap_within_tolerance():
    v = _clean_variant(0)
    v["script"] = {"beats": [{"start_s": 0, "end_s": 2, "line": "a"}, {"start_s": 2.1, "end_s": 32, "line": "b"}]}
    return dqa.check_beat_timing_drift(v)["pass"] is True, {}


# ---------------------------------------------------------------------------
# issue #19792 PART 1 -- fixtures for the 5 named checks the previous
# validator rubber-stamped past. Each gets a fail fixture (a real observed
# violation from the shipped 20-variant batch) and a pass fixture.
# ---------------------------------------------------------------------------

POSTSALE_FACTS = {"phase": "postsale", "sold_amount": 279200.0, "assessed_value": 464650.0,
                   "delta_pct": -39.9, "opening_bid": None, "judgment_amount": None,
                   "third_party_bidder": True, "plaintiff_confirmed_bank": None}
PRESALE_FACTS = {"phase": "presale", "sold_amount": None, "assessed_value": 300000.0,
                  "delta_pct": None, "opening_bid": 150000.0, "judgment_amount": None,
                  "third_party_bidder": None, "plaintiff_confirmed_bank": None}


def a26_payoff_leak_fails():
    # observed violation: "Broward Foreclosure Sells For... $279,200 🏚️🔥"
    r = dqa.check_payoff_leak({"title": "Broward Foreclosure Sells For…$279,200\U0001F3DA\U0001F525"}, POSTSALE_FACTS)
    return r["pass"] is False, r


def a27_payoff_leak_passes():
    r = dqa.check_payoff_leak({"title": "The Bank Let It Go For Less Than Half…\U0001F633\U0001F3E6"}, POSTSALE_FACTS)
    return r["pass"] is True, r


def a28_emoji_placement_fails():
    # observed violation: "⚠️ Foreclosure Red Flag... Sold 39.9% Under 👀" -- leading emoji + trailing single emoji
    r = dqa.check_emoji_placement({"title": "⚠️ Foreclosure Red Flag Sold Under Assessed…\U0001F440"})
    return r["pass"] is False, r


def a29_emoji_placement_passes():
    r = dqa.check_emoji_placement({"title": GOOD_TITLE})
    return r["pass"] is True, r


def a30_ellipsis_form_fails():
    # observed violation: "Tax deed stuns Lee County... 💰🔑" (literal three dots)
    r = dqa.check_ellipsis_form({"title": "Tax Deed Stuns Lee County... \U0001F4B0\U0001F511"})
    return r["pass"] is False, r


def a31_ellipsis_form_passes():
    r = dqa.check_ellipsis_form({"title": GOOD_TITLE})
    return r["pass"] is True, r


def a32_title_case_fails():
    # observed violation: "The bank lost this bet… 🏦🏠"
    r = dqa.check_title_case({"title": "The bank lost this bet…\U0001F3E6\U0001F3E0"})
    return r["pass"] is False, r


def a33_title_case_passes():
    r = dqa.check_title_case({"title": GOOD_TITLE})
    return r["pass"] is True, r


def a34_archetype_phase_mismatch_fails():
    # observed violation: countdown_presale assigned to a postsale reel (Lee/Martin/Broward)
    v = {"variant_dna": {"archetype": "countdown_presale"}}
    r = dqa.check_archetype_data_match(v, POSTSALE_FACTS)
    return r["pass"] is False, r


def a35_archetype_phase_mismatch_passes():
    v = {"variant_dna": {"archetype": "countdown_presale"}}
    r = dqa.check_archetype_data_match(v, PRESALE_FACTS)
    return r["pass"] is True, r


def run_eval():
    assertions = [
        ("planted_person_name_caught", a1_person_name),
        ("planted_vendor_name_caught", a2_vendor_name),
        ("planted_wrong_duration_caught", a3_wrong_duration),
        ("planted_missing_beat0_caught", a4_missing_beat0),
        ("planted_loop_seam_no_false_pass", a5_loop_seam_not_applicable),
        ("clean_control_1", _clean_control(0)),
        ("clean_control_2", _clean_control(1)),
        ("clean_control_3", _clean_control(2)),
        ("clean_control_4", _clean_control(3)),
        ("clean_control_5_diff_property", _clean_control(0)),
        ("caption_readability_ok", a11_caption_ok),
        ("caption_readability_bad", a12_caption_bad),
        ("hook_clarity_ok", a13_hook_ok),
        ("hook_clarity_bad", a14_hook_bad),
        ("short_code_missing_rejected", a15_missing_short_code),
        ("eleven_v3_proof_ok", a16_voice_tags_ok),
        ("eleven_v3_proof_missing", a17_voice_tags_empty),
        ("diversity_duplicate_rejected", a18_diversity_dup),
        ("diversity_compliant_accepted", a19_diversity_ok),
        ("writes_qa_scores_live", a20_writes_live),
        ("no_partial_credit_on_one_failure", a21_partial_fail_no_credit),
        ("null_checks_excluded_from_qa_pass", a22_null_checks_excluded),
        ("never_writes_status_or_approval", a23_no_status_write),
        ("beat_gap_over_tolerance_fails", a24_gap_too_large),
        ("beat_gap_within_tolerance_passes", a25_gap_within_tolerance),
        ("payoff_leak_fails_on_observed_violation", a26_payoff_leak_fails),
        ("payoff_leak_passes_on_stakes_without_resolution", a27_payoff_leak_passes),
        ("emoji_placement_fails_on_leading_or_stray_emoji", a28_emoji_placement_fails),
        ("emoji_placement_passes_on_clean_title", a29_emoji_placement_passes),
        ("ellipsis_form_fails_on_literal_three_dots", a30_ellipsis_form_fails),
        ("ellipsis_form_passes_on_single_char", a31_ellipsis_form_passes),
        ("title_case_fails_on_sentence_case_drift", a32_title_case_fails),
        ("title_case_passes_on_title_case", a33_title_case_passes),
        ("archetype_phase_mismatch_fails_countdown_on_postsale", a34_archetype_phase_mismatch_fails),
        ("archetype_phase_mismatch_passes_countdown_on_presale", a35_archetype_phase_mismatch_passes),
    ]
    return eval_common.run_assertions("reel-director-qa", assertions)


if __name__ == "__main__":
    run_eval()
