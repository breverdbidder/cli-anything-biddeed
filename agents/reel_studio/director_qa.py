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
    return {"pass": ok, "reasons": reasons}


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


def review_variant(variant: dict, siblings: list[dict]) -> dict:
    scores = {
        "title_compliance": check_title_compliance(variant),
        "diversity": check_diversity(variant, siblings),
        "banned_terms": check_banned_terms(variant),
        "caption_readability": check_caption_readability(variant),
        "hook_clarity": check_hook_clarity(variant),
        "beat_timing_drift": check_beat_timing_drift(variant),
        "eleven_v3_proof": check_eleven_v3_proof(variant),
        "short_code_present": check_short_code(variant),
        "duration_32s": {"pass": None, "reason": "not_applicable_phase_a (no rendered video yet)"},
        "loop_seam_continuity": {"pass": None, "reason": "not_applicable_phase_a (no rendered video yet)"},
    }
    applicable = {k: v for k, v in scores.items() if v.get("pass") is not None}
    qa_pass = all(v["pass"] for v in applicable.values())
    return {"qa_scores": scores, "qa_pass": qa_pass}


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

    results = []
    for v in variants:
        siblings = [s for s in variants]
        report = review_variant(v, siblings)
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
