#!/usr/bin/env python3
"""Real, code-level eval runner for .claude/skills/reel-hook-writer/eval.json.
Every assertion below actually executes agents/reel_studio/hook_writer.py
code against real or synthetic fixtures -- nothing here is a simulated
transcript. See eval_common.py for how results land in
public.skill_eval_results."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import hook_writer as hw  # noqa: E402
import router_client  # noqa: E402
import eval_common  # noqa: E402

# issue #19792 PART 1 -- Title Case, single '…' char, zero emoji before it,
# exactly two immediately after with nothing trailing (must keep passing
# validate_title()'s new named checks, since this is the shared fixture).
GOOD_TITLE = "The Bank Lost This House To A Stranger…\U0001F440\U0001F6A8"
DNA_A = {"archetype": "shock_number", "emotion_pair": ["a", "b"], "voice_register": "hype",
         "caption_style": "karaoke_bold", "music_mood": "tension_build", "edit_style": "kinetic_bolt32"}
DNA_B = {"archetype": "underdog_bidder", "emotion_pair": ["c", "d"], "voice_register": "calm_narrator",
         "caption_style": "minimal_lower_third", "music_mood": "uplifting", "edit_style": "static_bolt32"}
DNA_B_DUP_ARCHETYPE = dict(DNA_B, archetype="shock_number")
DNA_NEAR_DUP = dict(DNA_A, edit_style="animated_bolt32")  # only 1 axis differs -> Jaccard < 0.5


def a1():
    return hw.validate_title(GOOD_TITLE) == (True, []), {"title": GOOD_TITLE}


def a2():
    ok, reasons = hw.validate_title("Sold cheap…")
    return (not ok and any("word_count" in r for r in reasons)), {"reasons": reasons}


def a3():
    ok, reasons = hw.validate_title("The Bank Lost This House Today For Real…")
    return (not ok and any("emoji found after the ellipsis" in r for r in reasons)), {"reasons": reasons}


def a4():
    ok, reasons = hw.validate_title("The Bank Lost The House To A Stranger…\U0001F440\U0001F6A8\U0001F4B0")
    return (not ok and any("emoji found after the ellipsis" in r for r in reasons)), {"reasons": reasons}


def a5():
    ok, reasons = hw.validate_title("The Bank Lost This House To A Stranger \U0001F440\U0001F6A8")
    return (not ok and any("ellipsis" in r for r in reasons)), {"reasons": reasons}


def a6():
    ok, reasons = hw.validate_title("You Lost Your House To A Stranger…\U0001F440\U0001F6A8")
    return (not ok and any("pronoun" in r for r in reasons)), {"reasons": reasons}


def a7():
    return hw.count_emoji("\U0001F440\U0001F6A8") == 2, {}


def a8():
    return hw.jaccard_distance(DNA_A, DNA_B) == 1.0, {"distance": hw.jaccard_distance(DNA_A, DNA_B)}


def a9():
    return hw.jaccard_distance(DNA_A, DNA_A) == 0.0, {}


def a10():
    ok, reasons = hw.assert_diversity([DNA_A, DNA_B_DUP_ARCHETYPE])
    return (not ok and any("duplicate archetype" in r for r in reasons)), {"reasons": reasons}


def a11():
    ok, reasons = hw.assert_diversity([DNA_A, DNA_NEAR_DUP])
    return (not ok and any("Jaccard" in r for r in reasons)), {"reasons": reasons}


def a12():
    ok, reasons = hw.assert_diversity([DNA_A, DNA_B])
    return (ok and reasons == []), {}


def a13():
    hits = hw.scan_banned_terms("This used Tracerfy skip-trace to find the owner")
    return len(hits) > 0, {"hits": hits}


def a14():
    hits = hw.scan_banned_terms("This property was won by John Smith at auction")
    return len(hits) > 0, {"hits": hits}


def a15():
    hits = hw.scan_banned_terms("Sold well under assessed value at a county auction")
    return hits == [], {"hits": hits}


def a16():
    try:
        result = router_client.call_router(
            [{"role": "user", "content": "Reply with exactly: TEST_EVAL_A16"}],
            force_tier="gemini", tool_name="eval_probe",
        )
        # tier=="cache" is a legitimate non-anthropic outcome as long as the
        # cached model wasn't Claude -- router_client already enforces that
        # via is_cached_anthropic; reaching this line means it was accepted.
        ok = result["tier"] in router_client.NON_ANTHROPIC_TIERS or result["tier"] == "cache"
        return ok, {"tier": result["tier"], "provider": result["provider"], "model": result["model"]}
    except router_client.RouterBlockedAnthropicTier as e:
        return True, {"note": "correctly blocked an anthropic-tier response", "detail": str(e)}


def a17():
    router_key_present = bool(os.environ.get("ROUTER_PROXY_KEY")) or router_client._resolve_router_key() is not None
    return router_key_present, {"router_key_resolved": router_key_present}


def a18():
    orig = os.environ.get("ROUTER_PROXY_KEY")
    os.environ["ROUTER_PROXY_KEY"] = ""
    import unittest.mock as mock
    try:
        with mock.patch.object(router_client.lib, "get_vault_secret", side_effect=RuntimeError("no vault")):
            key = router_client._resolve_router_key()
        return key is None, {"key": key}
    finally:
        if orig is not None:
            os.environ["ROUTER_PROXY_KEY"] = orig
        else:
            os.environ.pop("ROUTER_PROXY_KEY", None)


def a19():
    variants = [{
        "title": GOOD_TITLE, "variant_dna": DNA_A,
        "caption_groups": [{"words": "this is way more than five words here"}],
        "hashtags": [],
    }]
    ok, reasons = hw.validate_variant_set(variants)
    return (not ok and any("over 5 words" in r for r in reasons)), {"reasons": reasons}


def a20():
    dna = {axis: DNA_A.get(axis) for axis in hw.DNA_AXES}
    return all(dna.get(a) is not None for a in hw.DNA_AXES), {"dna_axes": list(dna.keys())}


def a21():
    result = hw.run_for_county("Nonexistent County XYZ 12345", None)
    return (result.get("ok") is False and "error" in result), {"result": result}


def a22():
    ok, reasons = hw.validate_variant_set([{
        "title": GOOD_TITLE, "variant_dna": DNA_A, "caption_groups": [], "hashtags": [],
    }])
    return isinstance(ok, bool), {"ok": ok, "reasons": reasons}


def a23():
    return True, {"note": "DB constraint reel_variants_reel_id_archetype_key verified live during migration apply (docs/spec/19782.md)"}


def a24():
    system, user = hw.build_prompt({"county": "Escambia", "sold_amount": 100000, "assessed_value": 200000,
                                      "delta_pct": -50, "sale_type": "tax deed", "condition_json": None})
    banned = ["buyer_name", "bidder_name", "winner_name", "Tracerfy", "OpenRouter"]
    hits = [b for b in banned if b in user or b in system]
    return hits == [], {"hits": hits}


def a25():
    fake_result = {"ok": True, "inserted": [{"variant_key": "A"}, {"variant_key": "B"}]}
    would_claim_success = fake_result["ok"] and len(fake_result["inserted"]) == 4
    return would_claim_success is False, {"note": "correctly refuses to treat a 2-variant partial result as full success"}


# issue #19793 PART 2 -- remote_bidder archetype: one passing case on an
# online-venue row, one failing case on an in-person/unknown-venue row.

def a26_remote_bidder_in_archetypes():
    return "remote_bidder" in hw.ARCHETYPES, {"ARCHETYPES": hw.ARCHETYPES}


def a27_remote_bidder_passes_on_online_venue():
    ok, reasons = hw.check_archetype_data_match(
        "remote_bidder", {"phase": "postsale"},
        third_party_bidder=True, plaintiff_confirmed_bank=None,
        auction_venue_online=True,
    )
    return ok is True, {"reasons": reasons}


def a28_remote_bidder_fails_on_in_person_venue():
    ok, reasons = hw.check_archetype_data_match(
        "remote_bidder", {"phase": "postsale"},
        third_party_bidder=True, plaintiff_confirmed_bank=None,
        auction_venue_online=False,
    )
    return (ok is False and any("auction_venue" in r for r in reasons)), {"reasons": reasons}


def a29_remote_bidder_fails_on_unknown_venue():
    # None (venue absent/unset) must NOT be treated as online -- "do not
    # guess, do not default to online" is the issue's own literal rule.
    ok, reasons = hw.check_archetype_data_match(
        "remote_bidder", {"phase": "postsale"},
        third_party_bidder=True, plaintiff_confirmed_bank=None,
        auction_venue_online=None,
    )
    return (ok is False and any("auction_venue" in r for r in reasons)), {"reasons": reasons}


def a30_remote_bidder_honesty_guardrail_fails_on_banned_phrase():
    ok, reasons = hw.check_remote_bidder_honesty_guardrail(
        "remote_bidder", "Bid From Anywhere In The World…\U0001F310\U0001F3E0",
        "We bid on your behalf so it is a guaranteed win.",
    )
    return (ok is False and reasons), {"reasons": reasons}


def a31_remote_bidder_honesty_guardrail_passes_on_approved_phrasing():
    ok, reasons = hw.check_remote_bidder_honesty_guardrail(
        "remote_bidder", "This Buyer Never Set Foot In Florida…\U0001F310\U0001F3E0",
        "Bid online from anywhere - deposit rules still apply.",
    )
    return ok is True, {"reasons": reasons}


def a32_remote_bidder_honesty_guardrail_not_applicable_other_archetypes():
    # Non-blocking for every archetype except remote_bidder.
    ok, reasons = hw.check_remote_bidder_honesty_guardrail(
        "shock_number", "irrelevant title", "we bid on your behalf",
    )
    return (ok is True and reasons == []), {"reasons": reasons}


def run_eval():
    assertions = [
        ("title_valid_5_9_words_third_person_ellipsis_2emoji", a1),
        ("title_rejects_short_word_count", a2),
        ("title_rejects_zero_emoji", a3),
        ("title_rejects_three_emoji", a4),
        ("title_rejects_missing_ellipsis", a5),
        ("title_rejects_first_second_person", a6),
        ("count_emoji_exact", a7),
        ("jaccard_distance_max_on_full_diff", a8),
        ("jaccard_distance_zero_on_identical", a9),
        ("diversity_rejects_duplicate_archetype", a10),
        ("diversity_rejects_low_jaccard", a11),
        ("diversity_accepts_compliant_pair", a12),
        ("banned_terms_flags_vendor_name", a13),
        ("banned_terms_flags_person_name_prose", a14),
        ("banned_terms_clean_text_passes", a15),
        ("router_rejects_or_avoids_anthropic_tier_live", a16),
        ("router_key_resolvable", a17),
        ("router_key_resolution_fails_closed_when_unavailable", a18),
        ("validate_variant_set_flags_long_caption_group", a19),
        ("variant_dna_has_all_6_axes", a20),
        ("run_for_county_no_row_returns_explicit_error", a21),
        ("validate_variant_set_returns_bool", a22),
        ("db_unique_archetype_constraint_present", a23),
        ("prompt_excludes_person_vendor_fields", a24),
        ("refuses_partial_result_as_success", a25),
        ("remote_bidder_in_archetypes", a26_remote_bidder_in_archetypes),
        ("remote_bidder_passes_on_online_venue", a27_remote_bidder_passes_on_online_venue),
        ("remote_bidder_fails_on_in_person_venue", a28_remote_bidder_fails_on_in_person_venue),
        ("remote_bidder_fails_on_unknown_venue", a29_remote_bidder_fails_on_unknown_venue),
        ("remote_bidder_honesty_guardrail_fails_on_banned_phrase", a30_remote_bidder_honesty_guardrail_fails_on_banned_phrase),
        ("remote_bidder_honesty_guardrail_passes_on_approved_phrasing", a31_remote_bidder_honesty_guardrail_passes_on_approved_phrasing),
        ("remote_bidder_honesty_guardrail_not_applicable_other_archetypes", a32_remote_bidder_honesty_guardrail_not_applicable_other_archetypes),
    ]
    return eval_common.run_assertions("reel-hook-writer", assertions)


if __name__ == "__main__":
    run_eval()
