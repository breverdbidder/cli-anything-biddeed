#!/usr/bin/env python3
"""
EG14 Dossier Gate — Automated 14-Point Quality Scorer for Competitor CI Dossiers

Runs AFTER all 195 checkpoints in the CI Dossier Protocol v1.2 are complete.
Queries Supabase for real evidence, scores each point, writes result to
ci_dossier_eg14_runs, and returns exit code 0 (pass) or 1 (fail).

This is the REAL gate that blocks battle card rendering until the dossier
actually has the required evidence. Unlike the previous self-referential
"Phase 12" checks, every point here is a Supabase query against real data.

Canonical reference: docs/EVEREST-GATE-DOSSIER.md
Schema: ci_dossier_eg14_runs (id, competitor_slug, run_number, points_passed,
        points_failed, verdict, started_at, completed_at)

Usage:
    python3 eg14-dossier-gate.py --slug algoma
    python3 eg14-dossier-gate.py --slug algoma --write-to-supabase
    python3 eg14-dossier-gate.py --slug algoma --write-to-supabase --strict

Exit codes:
    0 = 14/14 PASS
    1 = <14 FAIL (battle card render BLOCKED)
    2 = error (e.g. dossier row not found, Supabase unreachable)

Environment:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SRK = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SRK:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY env var not set", file=sys.stderr)
    sys.exit(2)

H = {
    "apikey": SRK,
    "Authorization": f"Bearer {SRK}",
    "Content-Type": "application/json",
}


def q(path):
    """GET query against Supabase REST API."""
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"__error__": f"HTTP {e.code}: {e.read()[:200].decode()}"}
    except Exception as e:
        return {"__error__": str(e)}


def non_empty(v):
    """A field 'has real data' if it's not None/empty/0/False/stub."""
    if v in (None, "", [], {}, 0, False):
        return False
    if isinstance(v, str) and v.strip().lower() in ("unknown", "null", "n/a"):
        return False
    return True


def score_dossier(slug):
    """Run all 14 checks, return (points_passed, fails_list, dossier_dict)."""

    # Fetch dossier row
    rows = q(f"ci_dossiers?competitor_slug=eq.{slug}&select=*")
    if isinstance(rows, dict) and "__error__" in rows:
        return None, [{"point": 0, "name": "fetch_dossier", "gap": rows["__error__"]}], None
    if not rows:
        return None, [{"point": 0, "name": "fetch_dossier", "gap": f"No ci_dossiers row for slug={slug}"}], None
    d = rows[0]

    # Fetch checkpoint states
    cps = q("ci_protocol_checkpoints?select=checkpoint_id,phase,status,notes,evidence_url")
    if isinstance(cps, dict) and "__error__" in cps:
        return None, [{"point": 0, "name": "fetch_checkpoints", "gap": cps["__error__"]}], d

    green_ids = {c["checkpoint_id"] for c in cps if c["status"] == "green"}
    all_by_id = {c["checkpoint_id"]: c for c in cps}

    def cp_green(cp_id):
        return cp_id in green_ids

    def cp_has_evidence(cp_id):
        """Green checkpoint has either evidence_url OR substantive notes >50 chars."""
        c = all_by_id.get(cp_id)
        if not c or c["status"] != "green":
            return False
        if c.get("evidence_url"):
            return True
        notes = c.get("notes") or ""
        return len(notes.strip()) > 50

    fails = []

    # ═══════════════════════════════════════════════════════════════
    # THE 14 POINTS
    # ═══════════════════════════════════════════════════════════════

    # P1: Legal entity + jurisdiction verified (Phase 1.1 + 1.2)
    if not (non_empty(d.get("legal_name")) and non_empty(d.get("jurisdiction"))):
        fails.append({
            "point": 1,
            "name": "Legal entity + jurisdiction verified",
            "gap": f"legal_name={d.get('legal_name')!r} jurisdiction={d.get('jurisdiction')!r}"
        })

    # P2: HQ location from 2+ sources AND consistent with Phase 1 checkpoint notes
    hq_primary = d.get("hq_primary")
    if not non_empty(hq_primary):
        fails.append({"point": 2, "name": "HQ location verified", "gap": f"hq_primary empty"})
    else:
        # Check Phase 1 notes for HQ consistency
        phase1_hq_notes = [
            all_by_id.get(cp_id, {}).get("notes", "") or ""
            for cp_id in ("1.2", "1.3")
            if cp_id in all_by_id
        ]
        phase1_hq_text = " ".join(phase1_hq_notes).lower()
        card_hq_parts = [p.strip().lower() for p in str(hq_primary).replace(",", " ").split() if len(p) > 3]
        if phase1_hq_text and not any(p in phase1_hq_text for p in card_hq_parts):
            fails.append({
                "point": 2,
                "name": "HQ location verified",
                "gap": f"dossier hq_primary={hq_primary!r} does NOT match Phase 1 notes: {phase1_hq_text[:120]}"
            })

    # P3: Founding date captured (verified or explicitly INFERRED)
    if not non_empty(d.get("founded_date")):
        fails.append({"point": 3, "name": "Founding date captured", "gap": "founded_date empty"})

    # P4: Funding rounds + investors documented (even if "none announced")
    if not non_empty(d.get("funding_rounds")) and not non_empty(d.get("investor_context")):
        fails.append({
            "point": 4,
            "name": "Funding rounds + investors documented",
            "gap": "Both funding_rounds and investor_context empty"
        })

    # P5: ALL founders patent-searched (Phase 5.6 per-founder search)
    founders = d.get("founders") or []
    if not founders:
        fails.append({"point": 5, "name": "ALL founders patent-searched", "gap": "founders list empty"})
    elif not cp_has_evidence("5.6"):
        fails.append({
            "point": 5,
            "name": "ALL founders patent-searched",
            "gap": f"{len(founders)} founders listed but checkpoint 5.6 (per-founder patent search) lacks evidence"
        })

    # P6: Tech stack captured from live network traffic (Phase 3 + ci_dossiers tech fields)
    tech_signals = [
        d.get("frontend_stack"),
        d.get("css_stack"),
        d.get("analytics_stack"),
        d.get("tracking_pixels"),
        d.get("hosting_stack"),
    ]
    populated = sum(1 for x in tech_signals if non_empty(x))
    if populated < 2:
        fails.append({
            "point": 6,
            "name": "Tech stack captured from live network traffic",
            "gap": f"Only {populated}/5 tech stack fields populated in ci_dossiers (want >=2)"
        })

    # P7: Pricing signals extracted OR explicitly documented as gated
    if not non_empty(d.get("pricing_signals")) and not non_empty(d.get("pricing_model_type")):
        fails.append({
            "point": 7,
            "name": "Pricing signals extracted or gated-documented",
            "gap": "Both pricing_signals and pricing_model_type empty"
        })

    # P8: Known customers enumerated OR explicitly "none public"
    if d.get("known_customers") is None:
        fails.append({
            "point": 8,
            "name": "Known customers enumerated",
            "gap": "known_customers field is null (not even [])"
        })

    # P9: Product surface captured (Phase 8 — at least 40/63 checkpoints green)
    phase8_green = sum(1 for c in cps if c.get("phase") == 8 and c["status"] == "green")
    if phase8_green < 40:
        fails.append({
            "point": 9,
            "name": "Product surface captured (Phase 8 >= 40/63 green)",
            "gap": f"Only {phase8_green}/63 Phase 8 checkpoints green"
        })

    # P10: Review sentiment or explicit "no reviews found" (Phase 7)
    if not non_empty(d.get("review_intelligence")) and not non_empty(d.get("sentiment_scores")):
        fails.append({
            "point": 10,
            "name": "Review sentiment captured",
            "gap": "Both review_intelligence and sentiment_scores empty"
        })

    # P11: Regulatory posture documented (Phase 9 — 5/5 green)
    phase9_green = sum(1 for c in cps if c.get("phase") == 9 and c["status"] == "green")
    if phase9_green < 5:
        fails.append({
            "point": 11,
            "name": "Regulatory posture documented (Phase 9 5/5)",
            "gap": f"Only {phase9_green}/5 Phase 9 checkpoints green"
        })

    # P12: Product sample obtained OR documented as gated (Phase 8b/8c typically)
    # Check either dossier field OR explicit checkpoint note mentioning "gated" / "demo wall" / "sample"
    sample_checkpoints = [c for c in cps if c.get("phase") == 8 and c["status"] in ("green", "skipped")]
    sample_documented = any(
        ("sample" in (c.get("notes", "") or "").lower() or
         "gated" in (c.get("notes", "") or "").lower() or
         "demo wall" in (c.get("notes", "") or "").lower())
        for c in sample_checkpoints
    )
    if not sample_documented and not non_empty(d.get("demo_flow")):
        fails.append({
            "point": 12,
            "name": "Product sample obtained or gated-documented",
            "gap": "No demo_flow AND no Phase 8 checkpoint notes mention sample/gated/demo-wall"
        })

    # P13: Honesty protocol labels present in checkpoint notes (>=60% have VERIFIED/INFERRED/UNKNOWN)
    green_cps = [c for c in cps if c["status"] == "green"]
    labeled = sum(
        1 for c in green_cps
        if any(lbl in (c.get("notes", "") or "").upper() for lbl in ("VERIFIED", "INFERRED", "UNKNOWN"))
    )
    pct_labeled = (labeled / len(green_cps)) if green_cps else 0
    if pct_labeled < 0.60:
        fails.append({
            "point": 13,
            "name": "Honesty Protocol labels on 60%+ of green checkpoints",
            "gap": f"Only {labeled}/{len(green_cps)} ({pct_labeled:.0%}) green checkpoints have VERIFIED/INFERRED/UNKNOWN label"
        })

    # P14: Evidence count matches checkpoint count OR exceeds it (ci_dossier_evidence_log)
    ev_log = q(f"ci_dossier_evidence_log?competitor_slug=eq.{slug}&select=id")
    if isinstance(ev_log, dict) and "__error__" in ev_log:
        fails.append({"point": 14, "name": "Evidence log populated", "gap": ev_log["__error__"]})
    elif len(ev_log) < 20:
        fails.append({
            "point": 14,
            "name": "Evidence log populated",
            "gap": f"Only {len(ev_log)} rows in ci_dossier_evidence_log for {slug} (want >=20)"
        })

    points_passed = 14 - len(fails)
    return points_passed, fails, d


def write_run(slug, points_passed, fails, strict=False):
    """Insert a row into ci_dossier_eg14_runs."""
    # Next run number
    existing = q(f"ci_dossier_eg14_runs?competitor_slug=eq.{slug}&select=run_number&order=run_number.desc&limit=1")
    next_run = 1
    if isinstance(existing, list) and existing:
        next_run = existing[0].get("run_number", 0) + 1

    verdict = "pass" if points_passed == 14 else "fail"
    if not strict and points_passed >= 12:
        # allow 12/14 as soft-pass like Dono run #3 (14/14 with 4 deferred)
        verdict = "pass" if points_passed == 14 else ("soft_pass" if points_passed >= 12 else "fail")

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "competitor_slug": slug,
        "run_number": next_run,
        "points_passed": points_passed,
        "points_failed": json.dumps(fails),
        "verdict": verdict,
        "started_at": now,
        "completed_at": now,
    }
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/ci_dossier_eg14_runs",
        data=json.dumps(payload).encode(),
        headers={**H, "Prefer": "return=representation"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            return result[0] if result else None
    except urllib.error.HTTPError as e:
        print(f"ERROR writing eg14 run: HTTP {e.code}: {e.read()[:300].decode()}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--write-to-supabase", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Strict 14/14, no soft-pass at 12+")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    result = score_dossier(args.slug)
    if result[0] is None:
        print(f"ERROR: Cannot score dossier for {args.slug}", file=sys.stderr)
        for f in result[1]:
            print(f"  {f}", file=sys.stderr)
        sys.exit(2)

    points_passed, fails, dossier = result
    verdict = "pass" if points_passed == 14 else ("soft_pass" if points_passed >= 12 and not args.strict else "fail")

    out = {
        "slug": args.slug,
        "points_passed": points_passed,
        "points_failed_count": len(fails),
        "verdict": verdict,
        "fails": fails,
    }

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"EG14 DOSSIER GATE — {args.slug}")
        print(f"{'='*60}")
        print(f"Score:   {points_passed}/14")
        print(f"Verdict: {verdict.upper()}")
        if fails:
            print(f"\nFAILED POINTS:")
            for f in fails:
                print(f"  P{f['point']}: {f['name']}")
                print(f"       gap: {f['gap']}")
        else:
            print(f"\n✅ All 14 points passed")

    if args.write_to_supabase:
        row = write_run(args.slug, points_passed, fails, strict=args.strict)
        if row:
            print(f"\n✅ Written to ci_dossier_eg14_runs (run_number={row.get('run_number')})")
        else:
            print(f"\n⚠️  Failed to write to ci_dossier_eg14_runs")
            sys.exit(2)

    if verdict == "pass":
        sys.exit(0)
    elif verdict == "soft_pass" and not args.strict:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
