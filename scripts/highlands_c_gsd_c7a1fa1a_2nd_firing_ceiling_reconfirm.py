#!/usr/bin/env python3
"""Gold Standard shard-11 2nd firing, dispatch c7a1fa1a — highlands letter C
(parity_clean) ceiling re-confirmation. 2026-08-28 session.

=============================================================================
BASELINE (live, pencil_dod_evaluate_county('highlands'), this session,
verified via REST RPC POST /rest/v1/rpc/pencil_dod_evaluate_county):
  C: pass=false, metric=89.3, detail="matched_clean=359"   (need >=382/402)
  D: pass=true,  metric=96.0, detail="matched_any=386"
  auctions_total=402
No writes were made in this session — see CONCLUSION below.

=============================================================================
EVALUATOR CONTRACT RE-READ THIS SESSION (confirmed current/live — grepped
supabase/migrations/ for every CREATE OR REPLACE FUNCTION
public.pencil_dod_evaluate_county and confirmed 20260810_gold_standard_
shard3_lake_clerk_ssot_cd_recognition.sql is the newest, no superseding
migration exists):

  auctions_total := count(*) WHERE lower(county)=<county> AND
    (COALESCE(data_source,'')<>'propertyonion' OR COALESCE(tier1_authoritative,false)=true)

  matched_clean (C) := count(*) FILTER (WHERE
    (parity_status='matched_clean' AND parity_source LIKE 'tier1%')
    OR parity_status IN ('PARITY_OK','CLERK_VERIFIED'))

  matched_any (D) := count(*) FILTER (WHERE
    (parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE 'tier1%')
    OR parity_status IN ('PARITY_OK','CLERK_VERIFIED','CLERK_SSOT_CANCELLED'))

For highlands specifically: raw `county=eq.highlands` row count (402) EQUALS
the scoped auctions_total (402) — unlike polk/other counties, highlands has
zero propertyonion-sourced rows being excluded, so no denominator-scoping
trap applies here. Verified by pulling all 402 raw rows and re-applying the
propertyonion exclusion clause in Python: 402 -> 402, no change.

=============================================================================
SCOPED DIAGNOSIS (this session, reproducing the evaluator's exact FILTER
expression in Python against a fresh full pull of all 402 scoped rows):

  matched_clean = 359/402  (reproduces the live evaluator exactly)
  matched_any   = 386/402  (reproduces the live evaluator exactly)

  Distribution of the 43 rows failing matched_clean:
    27 x CLERK_SSOT_CANCELLED  (26 parity_source='highlands_clerk_tax_deed',
                                 1 parity_source='highlands_realtdm_cancelled_reschedule_*')
    12 x matched_clean, parity_source='shard8_run6046_litmus_fallback:*'
         (does NOT start with 'tier1' -- fails the LIKE 'tier1%%' clause
         despite parity_status already being 'matched_clean')
     2 x matched_divergent, parity_source='shard8_run6046_synthetic_placeholder:*'
         (case_number = 'HIGHLANDS-FC-2026-001' / '-002', literal bootstrap
         placeholders, not real clerk case numbers)
     2 x PHANTOM_NOT_ON_CLERK (1 parity_source='shard8_run6046_litmus_fallback:*'
         case 25000402GCAXMX auction_date 2026-09-02 [future];
         1 parity_source='highlands_clerk_foreclosure' case 25000681GCAXMX
         auction_date 2026-08-26 [2 days past])

  ROOT-CAUSE BUCKETING PER GUARDRAIL INVESTIGATION:

  Bucket A (27 CLERK_SSOT_CANCELLED) -- CORRECTLY EXCLUDED FROM C, NOT A BUG.
    Precedent checked live this session: supabase/migrations/20260812_
    shard1_calhoun_c_diagnose_d_ssot_cancelled_fix.sql explicitly documents
    the fleet-wide convention -- CLERK_SSOT_CANCELLED rows are genuine
    clerk-confirmed cancellations with no live match to cleanly re-match
    against, so they intentionally count toward D (matched_any) but NOT C
    (matched_clean). Re-labeling them into C would require inventing a live
    match that does not exist -- explicitly banned by that migration's own
    reasoning and by this campaign's fabrication guardrail. highlands' own
    prior session (scripts/gold_standard_highlands_cd_20260826_realtdm_
    phantom_recheck.py) independently reached the identical conclusion for
    26 of these 27 rows: live-reverified against highlands.realtdm.com with
    NO status filter, found genuinely "CANCELED - RESCHEDULE", and
    deliberately routed them to CLERK_SSOT_CANCELLED (D-only), not C. This
    session concurs -- Bucket A is a genuine, already-correctly-labeled
    exclusion, not an unexploited lever. Checked gold_standard_exclusions
    table for a highlands precedent (SELECT * WHERE county_slug='highlands'
    -> 0 rows) and confirmed via grep that gold_standard_exclusions is NOT
    referenced anywhere inside pencil_dod_evaluate_county's SQL body -- so
    writing to that table would have ZERO effect on the live C metric even
    if used. Not used, to avoid a no-op that looks like a fix.

  Bucket B (12 shard8_run6046_litmus_fallback "matched_clean") -- GENUINE
    DATA CEILING, RE-CONFIRMED THIS SESSION VIA TWO NEW INDEPENDENT METHODS.
    These rows were labeled 'matched_clean' by a 2026-07-xx session
    (scripts/shard8_run6046_highlands_cdij_fix.py, PHASE 4) using a
    SELF-AUTHORED heuristic: "absent from live calendar + has parcel_id or
    address => probably redeemed, mark matched_clean" -- NOT an independent
    clerk re-check. That parity_source deliberately does not start with
    'tier1' for exactly this reason (multiple later sessions flagged it as
    fabrication-adjacent and declined to upgrade it without real
    verification: scripts/highlands_cd_realtdm_active_redemption_fix.py
    2026-08-24, scripts/gold_standard_highlands_cd_20260826_realtdm_
    phantom_recheck.py 2026-08-26, and migrations/20260827_gold_standard_
    shard1_8f944a71_highlands_cd_repast_harvest_blocked.sql 2026-08-27 all
    independently investigated this identical 12(-ish)-row cluster and all
    declined to promote it for the same reason).

    THIS SESSION independently re-attempted verification via THREE
    live methods, none tried in exactly this combination before:
      1. Direct AJAX POST (urllib, no browser) against highlands.
         realforeclose.com's UPDATE/FNC=LOAD endpoint for the target rows'
         auction dates (08/18, 08/19, 08/26/2026) -- returned the SPA HTML
         shell instead of JSON for every date/area combination. The AJAX
         contract that scripts/shard8_run6046_highlands_cdij_fix.py's
         harvest_date() relies on is no longer returning JSON from this
         environment -- platform-side change or anti-bot gate, not
         something fixable without a real browser session.
      2. Real headless-browser render (Playwright/Chromium, NOT Firecrawl --
         a genuinely new tool vs. prior sessions which only had Firecrawl or
         raw urllib) of the PREVIEW page for all 4 target dates
         (08/11, 08/18, 08/19, 08/26/2026). Sanity-checked the harness first
         against a KNOWN-good date (highlands.realtaxdeed.com 09/02/2026,
         confirmed real by the 20260813_shard3_highlands_cd_live_verify.sql
         migration) -- found 14 real case tokens, proving the browser-render
         method works end-to-end. Then ran it against all 4 target
         foreclosure dates on realforeclose.com: ZERO case tokens found on
         any of them (0 total, not just 0 matches -- the calendar itself is
         empty for these past dates on this platform).
      3. Direct fetch of the Highlands Clerk's own foreclosure sale
         calendar PDF (https://webfiles.highlandsclerkfl.gov/ForeClosure/
         ClerkSaleCalendar.pdf, HTTP 200, live, fetched 2026-08-28,
         independent of the auction platform), extracted full text via
         pypdf, and searched for all 14 target case-number prefixes
         (11 shard8_run6046_litmus_fallback foreclosure cases + 2 synthetic
         placeholders + 1 PHANTOM_NOT_ON_CLERK case). Result: the PDF
         calendar as of 2026-08-28 4:00 PM only lists FUTURE sale dates
         (September 02 and September 23, 2026) -- confirms the clerk's own
         published calendar does not retain past-date listings either, and
         NONE of the 14 target case numbers appear anywhere in the document
         (all absent, confirmed by exact substring search).

    Firecrawl (the one remaining known-working lever from the 2026-08-27
    session, used historically to reach RealAuction's authenticated
    bid-history/results pages) was re-tested live this session with a
    trivial unrelated call (https://example.com) -- still returns HTTP 402
    "Insufficient credits to perform this request", identical to the
    2026-08-27 finding. Same account, same key, confirmed still exhausted.

  Bucket C (2 HIGHLANDS-FC-2026-00{1,2} synthetic placeholders) -- NOT REAL
    CASES. Literal bootstrap placeholder case numbers (not clerk-issued case
    number format), already correctly excluded from C via matched_divergent
    per the 2026-07-xx session's own labeling. Nothing to fix -- there is no
    real case behind these rows to verify.

  Bucket D (2 PHANTOM_NOT_ON_CLERK, cases 25000402GCAXMX / 25000681GCAXMX) --
    Checked directly against all 3 live sources above. Neither appears on
    the realforeclose.com preview calendar (checked 09/02/2026 for the
    first, a genuine future date, via Playwright -- empty; checked
    08/26/2026 for the second -- empty) nor on the Highlands Clerk PDF
    calendar (both prefixes absent). No resolution available this session.

=============================================================================
MATHEMATICAL CEILING CHECK (why no partial fix was attempted on Bucket B/D):
  Current: matched_clean = 359/402 = 89.3%
  Need:    >=382/402 (95%) => gap = 23 rows
  Maximum theoretically recoverable this session (ALL 16 non-CLERK_SSOT_
  CANCELLED failing rows, i.e. all of Bucket B + Bucket C + Bucket D,
  converted to a genuine tier1 match): 359 + 16 = 375/402 = 93.3%
  93.3% < 95% -- EVEN A COMPLETE SWEEP OF EVERY NON-CANCELLED FAILING ROW
  CANNOT CLEAR THE THRESHOLD. Bucket A (27 CLERK_SSOT_CANCELLED) is the only
  bucket large enough to matter, and it is correctly excluded from C by
  fleet-wide precedent (see calhoun migration above) -- forcing those rows
  into C would be a known-regression pattern this repo has already flagged
  and reverted once (lake C 94.1->31.7 in the 20260810 migration's own
  changelog was the OPPOSITE direction of that same class of mistake).

=============================================================================
CONCLUSION: This is a genuine, independently re-confirmed data ceiling, not
an unexploited lever. Three sessions prior to this one (2026-08-24,
2026-08-26, 2026-08-27) and this session (2026-08-28, using two additional
independent methods: raw AJAX POST re-test + real headless-browser render +
direct clerk PDF fetch, none of which had been combined in exactly this way
before) all reach the same result: the 16 non-cancelled failing rows have no
live, non-PropertyOnion, non-fabricated source to re-verify against, and
even a perfect sweep of all 16 would still fall 7 rows short of 95%
(375/402=93.3% < 382/402=95%). No DB writes were made. Per BLANK > WRONG and
the HARD GUARDRAILS in this repo's CLAUDE.md, forcing a match label onto
these rows without a live, independently-verifiable clerk source would be
fabrication and was correctly declined by every session that has looked at
this cluster, including this one.

RESIDUAL / NEXT-SESSION LEVERS (not attempted this session, in descending
order of plausibility):
  a. Once Firecrawl account credits are restored, re-run
     scripts/realauction_bidhistory.py (parameterized for highlands
     realforeclose, per the leon-B / prior highlands sessions' pattern)
     against the RESULTS/bid-history page (a different, authenticated
     endpoint than the public preview calendar this session tested) for
     08/18, 08/19, 08/26/2026 -- this endpoint was never reachable in any
     session to date due to the same shared credit exhaustion, not because
     it was tried and failed.
  b. Fix the hcpao.org parcel-detail URL pattern (this session's guess of
     /Search/Parcel/<STRAP> redirected to the generic search shell, not a
     working deep link) and check for a recent Certificate of Title / deed
     transfer near the 08/18-08/26/2026 auction dates on the 11 Bucket-B
     parcels -- would be a 4th independent, non-PropertyOnion source
     (Highlands County Property Appraiser) that could confirm a sale
     actually closed. Even if fully successful, this can raise C to at most
     93.3% -- would still need Bucket A (CLERK_SSOT_CANCELLED) reconsidered,
     which per the fleet-wide calhoun precedent should NOT be attempted.
  c. Re-examine whether auctions_total should exclude genuinely-cancelled
     auctions from the DENOMINATOR entirely (a scoring-logic question, not a
     data question) -- explicitly OUT OF SCOPE per this campaign's
     guardrail #4 (do not modify pencil_dod_evaluate_county without
     separately proving a distinct evaluator bug). Flagging for architect
     review only, not attempted here.

=============================================================================
VERIFICATION (before/after IDENTICAL this session -- no writes made)
=============================================================================
Live call: POST {SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
           body {"p_county":"highlands"}

BEFORE:
{
  "C": {"pass": false, "metric": 89.3, "detail": "matched_clean=359"},
  "D": {"pass": true,  "metric": 96.0, "detail": "matched_any=386"},
  "auctions_total": 402
}

AFTER (identical -- confirmed via a second live call at end of session):
{
  "C": {"pass": false, "metric": 89.3, "detail": "matched_clean=359"},
  "D": {"pass": true,  "metric": 96.0, "detail": "matched_any=386"},
  "auctions_total": 402
}

metric_moved: NO. C remains 89.3% (359/402). This is the honest, mathematically
provable ceiling for this session -- not an unexploited lever.

Usage:
  python3 scripts/highlands_c_gsd_c7a1fa1a_2nd_firing_ceiling_reconfirm.py
  (Re-runs the live evaluator call and the scoped Python diagnosis, prints
  results. Makes ZERO writes to the database -- this is a diagnosis-only
  reconfirmation script.)

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
from collections import Counter

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def evaluate(county: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"p_county": county}).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def fetch_all_rows(county: str) -> list:
    url = (
        f"{BASE}/multi_county_auctions?select=case_number,parity_status,"
        f"parity_source,data_source,tier1_authoritative,sale_type,auction_date"
        f"&county=eq.{county}&order=case_number"
    )
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def is_matched_clean(r: dict) -> bool:
    ps = r.get("parity_status")
    src = r.get("parity_source") or ""
    if ps == "matched_clean" and src.startswith("tier1"):
        return True
    if ps in ("PARITY_OK", "CLERK_VERIFIED"):
        return True
    return False


def is_matched_any(r: dict) -> bool:
    if is_matched_clean(r):
        return True
    ps = r.get("parity_status")
    src = r.get("parity_source") or ""
    if ps in ("matched_clean", "matched_divergent") and src.startswith("tier1"):
        return True
    if ps == "CLERK_SSOT_CANCELLED":
        return True
    return False


def main() -> None:
    print("=== LIVE EVALUATOR (before) ===")
    before = evaluate("highlands")
    print(json.dumps({"C": before.get("C"), "D": before.get("D"),
                       "auctions_total": before.get("auctions_total")}, indent=2))

    print("\n=== SCOPED DIAGNOSIS (Python reproduction of evaluator FILTER) ===")
    rows = fetch_all_rows("highlands")
    scoped = [r for r in rows if (r.get("data_source") or "") != "propertyonion"
              or r.get("tier1_authoritative") is True]
    print(f"raw rows: {len(rows)}  scoped auctions_total: {len(scoped)}")

    mc = sum(1 for r in scoped if is_matched_clean(r))
    ma = sum(1 for r in scoped if is_matched_any(r))
    print(f"matched_clean (reproduced): {mc}/{len(scoped)}")
    print(f"matched_any (reproduced):   {ma}/{len(scoped)}")

    failing = [r for r in scoped if not is_matched_clean(r)]
    dist = Counter((r.get("parity_status"), (r.get("parity_source") or "")[:35]) for r in failing)
    print(f"\nfailing matched_clean rows: {len(failing)}")
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")

    non_cancelled = [r for r in failing if r.get("parity_status") != "CLERK_SSOT_CANCELLED"]
    ceiling = mc + len(non_cancelled)
    print(f"\nnon-cancelled failing (max theoretical lever): {len(non_cancelled)}")
    print(f"ceiling if ALL non-cancelled rows converted: {ceiling}/{len(scoped)} "
          f"= {round(100*ceiling/len(scoped),1)}%  (need >=95%)")

    print("\n=== LIVE EVALUATOR (after — identical, no writes made) ===")
    after = evaluate("highlands")
    print(json.dumps({"C": after.get("C"), "D": after.get("D"),
                       "auctions_total": after.get("auctions_total")}, indent=2))

    print(f"\nmetric_moved: {'NO' if before.get('C') == after.get('C') else 'YES'}")


if __name__ == "__main__":
    main()
