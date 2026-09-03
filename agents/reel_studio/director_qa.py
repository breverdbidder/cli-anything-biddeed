#!/usr/bin/env python3
"""DIRECTOR / QA -- agents/reel_studio/director_qa.py (issue #19782).

Critique loop, ported (checks re-implemented against this repo's actual
schema, not copy-pasted) from breverdbidder/agentic-video-maker's
self-correcting editor. Per variant, enforces:
  - 32.0s +/-0.1s duration           [video-level -- N/A until Phase B render]
  - beat timing drift <=0.3s         [script-level proxy: gaps/overlaps between
                                       consecutive script beats]
  - caption readability: <=5 words/group, contrast >=4.5   [word-count is
                                       text-level and checked now; contrast
                                       ratio is a rendered-frame property,
                                       N/A until Phase B]
  - hook clarity: title spoken by 2.0s   [text-level: beat0 ends <=2.0s]
  - loop-seam continuity (31.9s vs 0.0s frame diff)   [video-level, N/A phase A]
  - person-name/vendor-name/banned-term scan   [reuses factory/gtm/gate.py --
                                       the CP0 compliance checks, not reinvented]
  - eleven_v3 proof   [text-level: voice_tags.eleven_v3_tags present + non-empty]

Writes qa_scores jsonb + qa_pass to winnerdata.reel_variants. Never
merges/publishes (M8) -- qa_pass is an input to the human LMS review, not an
approval by itself. May request ONE re-render with a concrete note (Phase B
concern; in Phase A "re-render" means "regenerate via hook_writer," logged
as a recommendation, not auto-executed by this module).

CLI:
  python3 director_qa.py review --variant-id UUID
  python3 director_qa.py review-reel --reel-id UUID
  python3 director_qa.py eval
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "factory", "gtm"))
import gate  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import hook_writer  # noqa: E402 -- reuse validate_title / count_emoji / assert_diversity

DURATION_TARGET_S = 32.0
DURATION_TOLERANCE_S = 0.1
BEAT_DRIFT_TOLERANCE_S = 0.3
HOOK_CLARITY_DEADLINE_S = 2.0
MAX_CAPTION_WORDS = 5


def _text_blob(variant: dict) -> str:
    parts = [variant.get("title", "")]
    script = variant.get("script") or {}
    for beat in script.get("beats", []):
        parts.append(str(beat.get("line", "")))
    for g in variant.get("caption_groups") or []:
        parts.append(str(g.get("words", "")))
    parts.extend(variant.get("hashtags") or [])
    return "\n".join(parts)


def check_title_compliance(variant: dict) -> dict:
    ok, reasons = hook_writer.validate_title(variant.get("title", ""))
    return {"pass": ok, "reasons": reasons, "observed_title": variant.get("title", "")}


# ---------------------------------------------------------------------------
# issue #19792 PART 1 -- the 5 named checks the previous validator missed.
# Each records an "observed" value (not just pass/fail) per the issue's
# "qa_scores record the per-check result" requirement. The three text-only
# checks (ellipsis_form/emoji_placement/title_case) are also folded into
# validate_title() above so future generation self-enforces them; recorded
# again here as their own named entries so a single mismatch is traceable
# without re-deriving it from title_compliance.reasons.
# ---------------------------------------------------------------------------

def check_ellipsis_form(variant: dict) -> dict:
    title = variant.get("title", "")
    ok, reasons = hook_writer.check_ellipsis_form(title)
    return {"pass": ok, "reasons": reasons, "observed": title}


def check_emoji_placement(variant: dict) -> dict:
    title = variant.get("title", "")
    ok, reasons = hook_writer.check_emoji_placement(title)
    return {"pass": ok, "reasons": reasons, "observed": title}


def check_title_case(variant: dict) -> dict:
    title = variant.get("title", "")
    ok, reasons = hook_writer.check_title_case(title)
    return {"pass": ok, "reasons": reasons, "observed": title}


def check_payoff_leak(variant: dict, reel_facts: dict | None) -> dict:
    title = variant.get("title", "")
    if reel_facts is None:
        return {"pass": None, "reason": "not_applicable_no_reel_facts_provided", "observed": title}
    ok, reasons = hook_writer.check_payoff_leak(title, reel_facts)
    observed = {
        "title": title,
        "sold_amount": reel_facts.get("sold_amount"),
        "delta_pct": reel_facts.get("delta_pct"),
        "opening_bid": reel_facts.get("opening_bid"),
        "judgment_amount": reel_facts.get("judgment_amount"),
    }
    return {"pass": ok, "reasons": reasons, "observed": observed}


def check_archetype_data_match(variant: dict, reel_facts: dict | None) -> dict:
    archetype = (variant.get("variant_dna") or {}).get("archetype") or variant.get("archetype")
    if reel_facts is None:
        return {"pass": None, "reason": "not_applicable_no_reel_facts_provided", "observed": archetype}
    ok, reasons = hook_writer.check_archetype_data_match(
        archetype, reel_facts,
        third_party_bidder=reel_facts.get("third_party_bidder"),
        plaintiff_confirmed_bank=reel_facts.get("plaintiff_confirmed_bank"),
        auction_venue_online=reel_facts.get("auction_venue_online"),
    )
    observed = {
        "archetype": archetype,
        "phase": reel_facts.get("phase"),
        "third_party_bidder": reel_facts.get("third_party_bidder"),
        "plaintiff_confirmed_bank": reel_facts.get("plaintiff_confirmed_bank"),
        "auction_venue_online": reel_facts.get("auction_venue_online"),
    }
    return {"pass": ok, "reasons": reasons, "observed": observed}


def check_remote_bidder_honesty(variant: dict) -> dict:
    """Issue #19793 PART 2 -- non-blocking (pass=True) for every archetype
    except remote_bidder, where it scans the title + full script text for
    frictionless/bids-on-your-behalf/investment-advice language."""
    archetype = (variant.get("variant_dna") or {}).get("archetype") or variant.get("archetype")
    beats = (variant.get("script") or {}).get("beats", [])
    script_text = " ".join(str(b.get("line", "")) for b in beats)
    ok, reasons = hook_writer.check_remote_bidder_honesty_guardrail(archetype, variant.get("title", ""), script_text)
    return {"pass": ok, "reasons": reasons, "observed": {"archetype": archetype}}


def check_diversity(variant: dict, siblings: list[dict]) -> dict:
    dna_list = [s["variant_dna"] for s in siblings]
    ok, reasons = hook_writer.assert_diversity(dna_list)
    return {"pass": ok, "reasons": reasons}


def check_banned_terms(variant: dict) -> dict:
    blob = _text_blob(variant)
    checks = {
        "banned_terms": gate.check_banned_terms(blob),
        "person_name_detector": gate.check_person_name_detector(blob),
        "vendor_name_detector": gate.check_vendor_name_detector(blob),
        "homeowner_contact_scan": gate.check_homeowner_contact_scan(blob),
    }
    hook_writer_hits = hook_writer.scan_banned_terms(blob)
    all_pass = all(v[0] for v in checks.values()) and not hook_writer_hits
    detail = {k: v[1] for k, v in checks.items()}
    detail["hook_writer_scan_hits"] = hook_writer_hits
    return {"pass": all_pass, "detail": detail}


def check_caption_readability(variant: dict) -> dict:
    bad = [g for g in variant.get("caption_groups") or [] if len(str(g.get("words", "")).split()) > MAX_CAPTION_WORDS]
    return {
        "pass": len(bad) == 0,
        "over_limit_groups": len(bad),
        "contrast_ratio": "not_applicable_phase_a (no rendered frame yet)",
    }


def check_hook_clarity(variant: dict) -> dict:
    beats = (variant.get("script") or {}).get("beats", [])
    beat0 = next((b for b in beats if float(b.get("start_s", -1)) == 0), None)
    if beat0 is None:
        return {"pass": False, "reason": "no beat starting at 0s"}
    ok = float(beat0.get("end_s", 999)) <= HOOK_CLARITY_DEADLINE_S
    return {"pass": ok, "beat0_end_s": beat0.get("end_s")}


def check_beat_timing_drift(variant: dict) -> dict:
    beats = sorted((variant.get("script") or {}).get("beats", []), key=lambda b: float(b.get("start_s", 0)))
    if not beats:
        return {"pass": False, "reason": "no beats present"}
    max_drift = 0.0
    for i in range(1, len(beats)):
        gap = abs(float(beats[i]["start_s"]) - float(beats[i - 1]["end_s"]))
        max_drift = max(max_drift, gap)
    total_end = float(beats[-1]["end_s"])
    duration_ok = abs(total_end - DURATION_TARGET_S) <= max(DURATION_TOLERANCE_S, 1.0)  # script-level: looser than the 0.1s render-level spec
    return {"pass": max_drift <= BEAT_DRIFT_TOLERANCE_S and duration_ok, "max_gap_s": max_drift, "script_total_s": total_end}


def check_eleven_v3_proof(variant: dict) -> dict:
    tags = ((variant.get("voice_tags") or {}).get("eleven_v3_tags")) or []
    return {"pass": len(tags) > 0, "tag_count": len(tags)}


def check_short_code(variant: dict) -> dict:
    """Negative test (issue): 'a variant without its own short_code -> rejected'."""
    return {"pass": bool(variant.get("short_code"))}


def review_variant(variant: dict, siblings: list[dict], reel_facts: dict | None = None) -> dict:
    scores = {
        "title_compliance": check_title_compliance(variant),
        "diversity": check_diversity(variant, siblings),
        "banned_terms": check_banned_terms(variant),
        "caption_readability": check_caption_readability(variant),
        "hook_clarity": check_hook_clarity(variant),
        "beat_timing_drift": check_beat_timing_drift(variant),
        "eleven_v3_proof": check_eleven_v3_proof(variant),
        "short_code_present": check_short_code(variant),
        # issue #19792 PART 1 -- the 5 named checks the rubber-stamping
        # validator missed. payoff_leak/archetype_data_match need reel_facts
        # (parent biddeed_reels + sale-record data); pass=None/excluded from
        # qa_pass only when that context genuinely wasn't provided (unit
        # tests), never on a live review_reel() call, which always supplies it.
        "ellipsis_form": check_ellipsis_form(variant),
        "emoji_placement": check_emoji_placement(variant),
        "title_case": check_title_case(variant),
        "payoff_leak": check_payoff_leak(variant, reel_facts),
        "archetype_data_match": check_archetype_data_match(variant, reel_facts),
        "remote_bidder_honesty": check_remote_bidder_honesty(variant),
        "duration_32s": {"pass": None, "reason": "not_applicable_phase_a (no rendered video yet)"},
        "loop_seam_continuity": {"pass": None, "reason": "not_applicable_phase_a (no rendered video yet)"},
    }
    applicable = {k: v for k, v in scores.items() if v.get("pass") is not None}
    qa_pass = all(v["pass"] for v in applicable.values())
    return {"qa_scores": scores, "qa_pass": qa_pass}


def fetch_reel_facts(reel_id: str) -> dict:
    """Parent winnerdata.biddeed_reels facts + a best-effort sale-record
    lookup (public.multi_county_auctions) for the two data-dependent named
    checks (payoff_leak needs sold_amount/delta_pct/opening_bid/judgment;
    archetype_data_match needs third_party_bidder/plaintiff_confirmed_bank).
    A genuine miss on the auctions lookup leaves those two fields None
    (treated as "not confirmed" by check_archetype_data_match), never
    fabricated -- matches banned_names_for_case()'s existing miss handling
    in scripts/biddeed_reels_pipeline_bolt32.py."""
    rows = lib.run_sql(f"""
        select case_number, county, phase, sale_type, sold_amount, assessed_value,
               delta_pct, opening_bid, judgment_amount
        from winnerdata.biddeed_reels where id = {lib.sql_str(reel_id)};
    """)
    if not rows:
        return {}
    reel = rows[0]
    for k in ("sold_amount", "assessed_value", "delta_pct", "opening_bid", "judgment_amount"):
        if reel.get(k) is not None:
            reel[k] = float(reel[k])

    third_party_bidder = None
    plaintiff_confirmed_bank = None
    auction_venue_online = None
    try:
        import urllib.parse as up
        qcase = up.quote(reel["case_number"])
        qcounty = up.quote(reel["county"])
        arows = lib.pg_rest(
            "multi_county_auctions",
            f"select=sale_result,winning_bidder,plaintiff,auction_venue"
            f"&case_number=eq.{qcase}&county=ilike.{qcounty}&limit=1",
        )
        if arows:
            a = arows[0]
            third_party_bidder = (a.get("sale_result") == "SOLD_THIRD_PARTY") and bool(a.get("winning_bidder"))
            plaintiff = (a.get("plaintiff") or "").strip()
            plaintiff_confirmed_bank = bool(plaintiff) and any(
                kw in plaintiff.lower() for kw in ("bank", "mortgage", "n.a.", "n a ", "financial", "lending")
            )
            # issue #19793 PART 2 -- venue comes ONLY from auction_venue, the
            # sale record's own field. source_platform ('realforeclose' etc.)
            # is NOT used to infer online-ness -- that would be exactly the
            # "do not guess, do not default to online" mistake the issue
            # warns against. None (column absent/unset) stays None, not False.
            venue = a.get("auction_venue")
            if venue is not None:
                auction_venue_online = (str(venue).strip().lower() == "online")
    except Exception:
        pass  # genuine miss -- leave None, never fabricate

    reel["third_party_bidder"] = third_party_bidder
    reel["plaintiff_confirmed_bank"] = plaintiff_confirmed_bank
    reel["auction_venue_online"] = auction_venue_online
    return reel


def review_reel(reel_id: str) -> list[dict]:
    variants = lib.run_sql(f"""
        select id, variant_key, variant_dna, title, script, caption_groups,
               voice_tags, hashtags, short_code
        from winnerdata.reel_variants where reel_id = {lib.sql_str(reel_id)} order by variant_key;
    """)
    for v in variants:
        for col in ("variant_dna", "script", "caption_groups", "voice_tags"):
            if isinstance(v.get(col), str):
                v[col] = json.loads(v[col])

    reel_facts = fetch_reel_facts(reel_id)

    results = []
    for v in variants:
        siblings = [s for s in variants]
        report = review_variant(v, siblings, reel_facts)
        lib.run_sql(f"""
            update winnerdata.reel_variants
            set qa_scores = {lib.sql_jsonb(report['qa_scores'])},
                qa_pass = {lib.sql_bool(report['qa_pass'])},
                updated_at = now()
            where id = {lib.sql_str(v['id'])};
        """)
        results.append({"variant_id": v["id"], "variant_key": v["variant_key"], **report})
    return results


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rr = sub.add_parser("review-reel")
    rr.add_argument("--reel-id", required=True)
    sub.add_parser("eval")

    args = ap.parse_args()
    if args.cmd == "review-reel":
        print(json.dumps(review_reel(args.reel_id), indent=2, default=str))
    elif args.cmd == "eval":
        from eval_director_qa import run_eval  # noqa
        run_eval()


if __name__ == "__main__":
    main()
