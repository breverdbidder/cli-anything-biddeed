#!/usr/bin/env python3
"""
bradford_bf_recheck_gsd4_41bd7ce3_10th.py
Gold Standard shard-4 (dispatch 41bd7ce3), 2026-08-15 — 10th dedicated B/F session.

SCOPE: bradford B (verified independent outcomes >=95% of closed) and F
(tier1 sold-amount >=95% of closed). Both FAIL with closed_sold=0.

CONTEXT / PRIOR WORK READ FIRST (per dispatch instructions):
  - scripts/bradford_bf_recheck_shard1_3ce988ac.py (2026-08-14, 8th+ session):
    established 25000439CAAXMX and 25000487CAAXMX (auction_date 2026-08-13)
    as the only "new" territory once past-due; found bradfordclerk.com
    Cloudflare-blocked site-wide, bctelegraph.com pre-sale-only (never
    post-sale results), civitekflorida/myfloridacounty Turnstile-gated,
    no RealAuction mirror (in-person courthouse sale). ZERO writes.
  - scripts/bradford_bf_recheck_gsd2_84b6c4bb.py (2026-08-15 08:26 UTC, SAME
    CALENDAR DAY as this session, ~8 hours earlier): re-ran the identical
    check for the same two cases (still only 2 days past auction_date),
    re-confirmed bradfordclerk.com 403 and bctelegraph.com's newest edition
    (legal-notices-for-8-13-26/, the sale-date edition itself) containing
    zero mentions of either case. ZERO writes.
  - supabase/migrations/20260813_gold_standard_bradford_bf_9th_reconfirm_case_specific_8389b490.sql
    (2026-08-13, 9th session): case/parcel-specific sweep on 25000457CAAXMX
    (bradfordappraiser.com/Schneider-qPublic vendor, bctelegraph, WebSearch)
    — also Cloudflare-gated, also zero hits. ZERO writes.

THIS SESSION'S DIAGNOSIS (STEP 2 — new-past-due check):
  Live query today (2026-08-15) shows bradford has 5 auctions (unchanged
  count from 84b6c4bb this morning), PLUS one genuinely new row not present
  in the 3ce988ac (08-14) row set: 24000431CAAXMX, auction_date 2026-08-20,
  parcel 00441-0-00100. Computed days-past-due for all 4 non-exhausted-beyond-
  hope cases as of TODAY (2026-08-15):
    25000457CAAXMX  2026-07-16   30 days past   (9+ sessions exhausted, not
                                                  re-chased per instruction)
    25000439CAAXMX  2026-08-13    2 days past   (checked THIS MORNING,
                                                  84b6c4bb, ~8h before this
                                                  session — zero elapsed
                                                  calendar days since)
    25000487CAAXMX  2026-08-13    2 days past   (same as above)
    24000431CAAXMX  2026-08-20   -5 days (FUTURE, not yet auctioned at all)

  CONCLUSION: no case has crossed a NEW past-due threshold since the
  84b6c4bb session ran earlier TODAY. The two 08-13 cases are still exactly
  2 days past (same as this morning — no calendar day has elapsed within the
  same session day). The new case (24000431CAAXMX) is 5 days in the future
  and structurally cannot have a sale outcome yet. Per the 3ce988ac session's
  own recommendation, the highest-value re-check point for the 08-13 cases is
  once they are >=7-10 days past (~2026-08-20/23) — still 5-8 days away.

STEP 3/4 — LIGHTWEIGHT LIVE SPOT-CHECK PERFORMED ANYWAY (honest re-verify,
not a full re-sweep of already-exhausted generic sources):
  1. bctelegraph.com/category/legal-notices/ — HTTP 200 (reachable, unchanged).
  2. bctelegraph.com/legal-notices-for-8-14-26/ — HTTP 404 (does not exist).
  3. bctelegraph.com/legal-notices-for-8-15-26/ — HTTP 404 (does not exist;
     bctelegraph is a weekly paper, no new edition expected mid-week beyond
     the 8-13-26 issue already checked this morning).
  4. bradfordclerk.com/tax-deeds-and-foreclosure-sales/ — HTTP 403
     (Cloudflare "Just a moment..." challenge, unchanged from every prior
     session including this morning's).
  No new source type identified beyond what 9 prior sessions already
  exhausted (bradfordclerk.com, bctelegraph.com, surplusindex.com, Wayback,
  officialrecords.bradfordclerk.com, civitekflorida OCRS, myfloridacounty
  ORI, Box.com, courtlistener.com, judyrecords.com, trellis.law,
  bradfordappraiser.com/qPublic-Schneider, WebSearch).

RESULT: ZERO WRITES. No sold_amount / tier1_sold_amount / sale_result_date /
auction_status backfilled. No foreclosure_outcomes or tax_deed_outcomes row
inserted. Fabricating an outcome here would violate the fail-loud / BLANK >
WRONG invariant.

bradford B and F remain FAIL (closed_sold=0) after this session — confirmed
via fresh pencil_dod_evaluate_county RPC call below, identical before/after
(H's freshness hours metric moved because that's cron-driven and untouched
by this session; B/F/A/C/D/E/G/I/J are byte-identical before vs after).

RECOMMENDATION FOR NEXT SESSION: this is now the 10th consecutive session on
the same structural block. Do NOT dispatch another generic B/F re-sweep for
bradford until EITHER (a) 25000439CAAXMX/25000487CAAXMX cross the >=7-10-day
publication-lag window (~2026-08-20 through 2026-08-23), where a bctelegraph
post-sale check has genuine incremental value, OR (b) a fundamentally new
source/method becomes available (e.g. a browser-automation path capable of
clearing bradfordclerk.com's Cloudflare Turnstile challenge, which is
currently a hard prohibition under this campaign's rules). Re-dispatching
same-day or next-day sweeps against unchanged auction_date windows burns
session budget without any possibility of new information — the residual is
a real-world publication-timing gate, not a research gap.
"""
import os
import sys
import json
import urllib.request
from datetime import date

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SB_URL or not KEY:
    print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

TODAY = date(2026, 8, 15)


def rpc_evaluate(county, retries=2):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"p_county": county}).encode(),
        headers=HEADERS,
        method="POST",
    )
    last_err = None
    for _ in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:  # transient network timeout, retry
            last_err = e
    raise last_err


def get_rows(county):
    import urllib.parse

    qs = urllib.parse.urlencode(
        {
            "county": f"ilike.{county}",
            "select": "id,case_number,auction_date,auction_status,sold_amount,"
            "tier1_sold_amount,sale_result_date,parcel_id,sale_type",
        }
    )
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/multi_county_auctions?{qs}", headers=HEADERS
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    county = "bradford"
    print(f"=== {county} pre-check ===")
    before = rpc_evaluate(county)
    print(json.dumps(before))

    print(f"\n=== {county} raw auction rows + days-past-due as of {TODAY.isoformat()} ===")
    rows = get_rows(county)
    exhausted = {"25000457CAAXMX"}
    checked_this_morning = {"25000439CAAXMX", "25000487CAAXMX"}
    for row in rows:
        d = date.fromisoformat(row["auction_date"])
        days_past = (TODAY - d).days
        status = "FUTURE" if days_past < 0 else f"{days_past}d past"
        flag = ""
        if row["case_number"] in exhausted:
            flag = "  <-- 9+ sessions exhausted, not re-chased"
        elif row["case_number"] in checked_this_morning:
            flag = "  <-- checked earlier TODAY (84b6c4bb), no elapsed calendar day since"
        else:
            flag = "  <-- NEW row this session, but FUTURE sale, no outcome possible yet"
        print(json.dumps(row) + f"  [{status}]" + flag)

    print(
        "\n=== RESULT: ZERO WRITES ===\n"
        "No case crossed a new past-due threshold since the 84b6c4bb session "
        "ran earlier today. Lightweight spot-check (bctelegraph 8-14/8-15 "
        "editions HTTP 404, bradfordclerk.com HTTP 403 Cloudflare) reconfirms "
        "no new information is available. See module docstring for full trail."
    )

    print(f"\n=== {county} post-check (unchanged, no writes performed) ===")
    after = rpc_evaluate(county)
    print(json.dumps(after))

    assert after["B"]["pass"] == before["B"]["pass"], "unexpected B drift with zero writes"
    assert after["F"]["pass"] == before["F"]["pass"], "unexpected F drift with zero writes"
    print("\nOK: B/F unchanged as expected (no writes were made).")


if __name__ == "__main__":
    main()
