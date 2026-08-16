#!/usr/bin/env python3
"""Gold Standard shard-1 (dispatch 6a9e3c3a): st_lucie letter C investigation.

RESULT: NO FIX APPLIED. This is a diagnose-and-document run that concludes
the current C=83.7% is a genuinely correct data state, not a matcher bug or
a fixable gap -- so per Honesty Protocol / SHIP GATE this script performs
ZERO writes. It exists to record the evidence trail so a future session
does not re-attempt the same (already-exhausted) reclassification idea.

============================================================================
BACKGROUND
============================================================================
pencil_dod_evaluate_county() (live def: supabase/migrations/
20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql) computes,
for st_lucie, over ALL 221 multi_county_auctions rows (0 excluded by the
propertyonion/tier1_authoritative filter -- every row is already eligible):

  matched_clean := count(*) FILTER (
      (parity_status='matched_clean' AND parity_source LIKE 'tier1%')
      OR parity_status IN ('PARITY_OK','CLERK_VERIFIED'))
  matched_any   := matched_clean's rows OR (matched_divergent tier1%)
                    OR parity_status='CLERK_SSOT_CANCELLED'

Live breakdown of all 221 st_lucie rows (verified via Supabase REST,
2026-08-16):
  matched_clean (tier1%)  123
  PARITY_OK                62   <- clerk_ssot clean-match mark
  ---------------------------------  matched_clean total = 185 (83.7%)
  CLERK_SSOT_CANCELLED     35   <- clerk_ssot found + recorded a CANCELLED
                                    tax-deed auction (auction_status is also
                                    'CANCELLED' on every one of these rows --
                                    fully consistent, not a parity-only flag)
  matched_divergent         1   <- 2025CA001832, multi-parcel foreclosure,
                                    explicitly left untouched by the prior
                                    2026-08-06 session (stlucie_dispatch_
                                    group1_cd_fix.py) pending new evidence
  ---------------------------------  total = 221

matched_any = 185 + 35 + 1 = 221 -> D = 100% (already passing).
Threshold for C: 221 * 0.95 = 209.95 -> need matched_clean >= 210.
Current matched_clean = 185. Gap = 25 rows minimum, and the ONLY pool of
rows that could move (matched_any-but-not-matched_clean) is exactly the 36
rows above (35 CLERK_SSOT_CANCELLED + 1 matched_divergent).

============================================================================
ROOT-CAUSE FINDING (why this is NOT fixable by reclassification)
============================================================================
Ran scripts/clerk_ssot/parsers/st_lucie.py::parse_tax_deed() live against
acclaimweb.stlucieclerk.gov/TributeWeb/ (the St Lucie Clerk's own official
tax-deed sale system -- the authoritative clerk source of truth, i.e.
EXACTLY the pre-authorized clerk/official-records litmus fallback source)
during this session:

  parsed 119 rows, 45 cancelled/redeemed/pulled (full clerk-side window)

Cross-matched all 35 DB rows currently marked CLERK_SSOT_CANCELLED against
this fresh live pull by case_number:
  - 35/35 found in the live clerk feed
  - 35/35 still show a CANCEL_STATUSES status (REDM/BANKRUPTCY/PULL) live,
    right now
  - 0 mismatches (no row where the live clerk record has flipped back to
    a live "SALE" status)

So the clerk source of truth -- the SAME litmus-fallback source this
finding is evaluated against -- independently reconfirms, today, that all
35 rows are genuinely cancelled/redeemed/pulled tax-deed auctions. This is
not a PropertyOnion coverage gap and not a stale DB snapshot; it is a
verified-correct divergence. Per the same migration's own documented
rationale (20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql,
lines 18-27): CLERK_SSOT_CANCELLED is intentionally counted as matched_any
(D) but NOT matched_clean (C), because "it represents a divergence that
clerk_ssot found and corrected" -- the exact same class as
matched_divergent. Recognizing it as matched_clean would misrepresent a
cancelled auction as a clean parity match, which is precisely the class of
anomaly the ULTRALOOP adversarial-verify stage exists to reject.

The 36th row, 2025CA001832 (matched_divergent), was independently confirmed
by the 2026-07-18 session as a genuine multi-parcel foreclosure divergence
(live RealForeclose AJAX shows "MULTIPLE PARCELS" vs our single-parcel DB
row) and the 2026-08-06 session explicitly declined to touch it pending new
evidence. This session found no new evidence for it either -- 1 row, 0.45%
of the total, immaterial to the 95% threshold regardless.

============================================================================
CONCLUSION
============================================================================
There is no legitimate lever left: every non-matched_clean row in the
matched_any-eligible pool is either (a) a clerk-confirmed cancelled auction
(35 rows, reconfirmed live this session) or (b) a documented multi-parcel
divergence (1 row, previously confirmed, no new evidence found). Promoting
any of these to matched_clean would fabricate a "clean match" the source of
truth itself contradicts. C stays at 185/221 = 83.7% (FAIL) as a correct,
evidence-backed data state -- not a pipeline defect.

If C is ever to reach >=95% for st_lucie, it requires either:
  (a) new upstream auction rows arriving that ARE clean matches (raises the
      matched_clean numerator without touching the 36 known-bad rows), or
  (b) an evaluator-formula change to stop counting confirmed-cancelled
      auctions toward the C/D denominator at all -- which is a cross-county
      formula change outside this dispatch's scope and would need its own
      adversarially-reviewed migration, not a per-county data patch.

Usage:
  python3 scripts/gold_standard_shard1_6a9e3c3a_stlucie_c_parity_fix.py
  (re-runs the live clerk cross-check + prints the before/after RPC eval;
   before == after by design, since zero writes are performed)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "clerk_ssot", "parsers"))

COUNTY = "st_lucie"
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== st_lucie C parity investigation (dispatch 6a9e3c3a) ===")
    before = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BEFORE C: {before['C']}", "VERIFIED")
    log(f"BEFORE D: {before['D']}", "VERIFIED")

    rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&parity_status=eq.CLERK_SSOT_CANCELLED"
        "&select=case_number,auction_status,parity_status,sale_type,auction_date")
    log(f"DB rows currently CLERK_SSOT_CANCELLED: {len(rows)}", "VERIFIED")

    import st_lucie  # scripts/clerk_ssot/parsers/st_lucie.py
    live = st_lucie.parse_tax_deed()
    live_cancelled = sum(1 for r in live if r["cancelled"])
    log(f"Live clerk pull (acclaimweb.stlucieclerk.gov): {len(live)} rows, "
        f"{live_cancelled} cancelled/redeemed/pulled", "VERIFIED")

    by_case = {r["case_number"]: r for r in live}
    still_cancelled, not_found, mismatches = 0, [], []
    for r in rows:
        cn = r["case_number"]
        live_row = by_case.get(cn)
        if not live_row:
            not_found.append(cn)
            continue
        if live_row["cancelled"]:
            still_cancelled += 1
        else:
            mismatches.append((cn, live_row["raw_comment"]))

    log(f"Cross-check: {still_cancelled}/{len(rows)} still cancelled live, "
        f"{len(not_found)} not found in live window, {len(mismatches)} mismatches",
        "VERIFIED")
    if mismatches:
        log(f"MISMATCHES (would need review, NOT auto-promoted): {mismatches}", "VERIFIED")
    else:
        log("Zero mismatches -- all 35 CLERK_SSOT_CANCELLED rows independently "
            "reconfirmed cancelled by a fresh live clerk pull. No fix applied "
            "(would be fabrication). See script docstring for full reasoning.",
            "VERIFIED")

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER C: {after['C']}", "VERIFIED")
    log(f"AFTER D: {after['D']}", "VERIFIED")

    print("\n### BEFORE/AFTER (expected identical -- zero writes performed)")
    print(json.dumps({"before": {k: before[k] for k in ("C", "D")},
                       "after": {k: after[k] for k in ("C", "D")}}, indent=2))


if __name__ == "__main__":
    main()
