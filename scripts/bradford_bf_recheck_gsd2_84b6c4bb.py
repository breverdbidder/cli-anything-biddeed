#!/usr/bin/env python3
"""
bradford_bf_recheck_gsd2_84b6c4bb.py
Gold Standard shard-2 (dispatch 84b6c4bb), 2026-08-15

SCOPE: bradford B (verified independent outcomes >=95% of closed) and F
(tier1 sold-amount >=95% of closed). Both FAIL with closed_sold=0 — nothing
has sold yet per our records, so there is nothing yet to verify.

CONTEXT: This is the SAME two cases investigated in the immediately prior
session (shard1/3ce988ac, 2026-08-14), one day later. That session's explicit
recommendation was: "re-check bctelegraph.com and bradfordclerk.com again
once auction_date is >=7-10 days past ... (i.e. after ~2026-08-20/23)." This
session runs 2026-08-15 — only 2 days past auction_date (2026-08-13) for both
cases, i.e. still short of that recommended window. Per today's dispatch
instructions, the live re-check was still performed (rather than skipped
outright), on the theory that "most likely nothing new" should be VERIFIED
fresh, not assumed. Case 25000457CAAXMX (auction_date 2026-07-16, now 30 days
past, 6+ prior dedicated sessions exhausted: bradfordclerk.com, bctelegraph.com,
surplusindex.com, Wayback, RealAuction, officialrecords.bradfordclerk.com,
myfloridacounty.com ORI, civitekflorida.com OCRS, Box.com, courtlistener.com,
judyrecords.com, trellis.law) was explicitly NOT re-chased per instruction.

LIVE DB QUERY (2026-08-15) — VERIFIED:
  curl "$SUPABASE_URL/rest/v1/multi_county_auctions?select=*&county=eq.bradford
    &case_number=in.(25000439CAAXMX,25000487CAAXMX)"
  Both rows confirmed present, auction_date=2026-08-13 for both,
  auction_status still "upcoming", sold_amount/tier1_sold_amount/
  sale_result_date/winning_bidder all null for both. No prior write has
  landed for either case since the shard1/3ce988ac session (which also made
  zero writes).

INVESTIGATION THIS SESSION (2026-08-15, both cases):

  1. bradfordclerk.com/tax-deeds-and-foreclosure-sales/, /foreclosures/, and
     bare domain — curl with 2 different browser User-Agents (Chrome/Windows,
     Safari/macOS) => HTTP 403 on every path, Cloudflare "Just a moment..."
     managed-challenge page (title: "Just a moment...", contains
     "cf-browser-verification" / "challenge" markers) both times. Site-wide
     JS/cookie gate, unchanged from every prior session. No bypass attempted
     (Turnstile/Cloudflare-challenge bypass is a hard prohibition — this is a
     confirmed, standing dead end, not re-diagnosed further).

  2. bctelegraph.com — reachable, HTTP 200/301(->200). Checked via THREE
     angles, all fresh as of today:
       a. Direct site search (?s=25000439CAAXMX and ?s=25000487CAAXMX) — both
          case numbers DO return hits, but every linked article is one of the
          two editions already found in the prior session
          (legal-notices-for-7-23-26/, legal-notices-for-7-30-26/) — the same
          pre-sale "Notice of Foreclosure Sale" content, nothing new.
       b. category/legal-notices/ index page — confirms the two most recent
          editions on the site are legal-notices-for-8-6-26/ (HTTP 200) and
          legal-notices-for-8-13-26/ (HTTP 200, the newest available, dated
          the SAME DAY as the auction itself). Both of these editions are NEW
          relative to the prior session (which only checked up through
          7-30-26) and were fetched and grepped fresh today.
       c. Grepped both new editions (8-6-26: 170,141 bytes; 8-13-26: 227,539
          bytes) for case numbers and party names
          (25000439CAAXMX / 25000487CAAXMX / Barranco / Lemire /
          "Williams, Billy" / "Planet Home") — ZERO matches in either edition
          for either case. The 8-13-26 edition does contain other, unrelated
          foreclosure/"NOTICE OF SALE"/"Final Judgment"/"highest bidder"
          legal notices (confirmed via grep -c on those terms), so the page
          is a normal, populated weekly edition — it simply does not mention
          either of our two target cases, before OR after their Aug 13 sale
          date. No edition dated after 8-13-26 is indexed yet
          (legal-notices-for-8-14-26/ => HTTP 404, confirmed).
     This is consistent with the prior session's structural finding:
     bctelegraph publishes forward-looking notice-of-intent-to-sell content
     only, not post-sale disposition results, and even the pre-sale notice
     for 25000487CAAXMX was never found on this site in any edition checked
     to date (only 25000439CAAXMX had a pre-sale notice, in 7-23/7-30-26).

  3. No new source type was available to try beyond what shard1/3ce988ac
     already exhausted (officialrecords.bradfordclerk.com unreachable,
     civitekflorida OCRS / myfloridacounty ORI Turnstile-gated, no
     RealAuction-family mirror since Bradford sells in-person at the
     courthouse steps per the bctelegraph notice text itself).

CONCLUSION (2026-08-15): STILL STRUCTURALLY BLOCKED for both cases, 2 days
past auction_date. Root cause unchanged from yesterday's session: the
primary source (bradfordclerk.com) is Cloudflare-blocked site-wide, and the
only reachable secondary source (bctelegraph.com) has now been checked
through its newest available edition (8-13-26, the sale-date edition itself)
with zero post-sale content for either case. This is one day closer to, but
still short of, the ~7-10-day publication-lag window flagged by the prior
session as the point where a genuine re-check would be more likely to find
something. Continuing to re-check daily before that window does not change
the outcome — it only re-confirms the same absence of data, which is the
honest thing to report rather than force a claim.

ZERO WRITES MADE. No sold_amount / tier1_sold_amount / auction_status /
sale_result_date backfilled for either case. No foreclosure_outcomes row
inserted for bradford this session. Fabricating a sale amount here would be
a HONESTY PROTOCOL violation (BLANK > WRONG, 3x penalty for wrong VERIFIED
claims).

bradford B and F remain FAIL (closed_sold=0) after this session — confirmed
via fresh pencil_dod_evaluate_county RPC call below (evaluator JSON pasted
in the summary, both letters unchanged pre/post since no writes occurred).

RECOMMENDATION FOR NEXT SESSION: honor the prior session's window — the
highest-value re-check point is once auction_date is >=7-10 days past (i.e.
~2026-08-20 through 2026-08-23) for 25000439CAAXMX / 25000487CAAXMX. Re-check
bctelegraph.com's newest edition at that point and bradfordclerk.com (in case
the Cloudflare gate is ever relaxed for automated agents — unlikely but cheap
to re-verify). Do NOT re-attempt 25000457CAAXMX (6+ sessions exhausted, no
new source type identified since).
"""
import os
import sys
import json
import urllib.request

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
            "tier1_sold_amount,sale_result_date,parcel_id",
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

    print(f"\n=== {county} raw auction rows (2 cases re-checked this session) ===")
    rows = get_rows(county)
    for row in rows:
        flag = ""
        if row["case_number"] in ("25000439CAAXMX", "25000487CAAXMX"):
            flag = "  <-- re-investigated this session (2 days past auction_date), see docstring"
        elif row["case_number"] == "25000457CAAXMX":
            flag = "  <-- NOT re-investigated (6+ prior sessions exhausted)"
        print(json.dumps(row) + flag)

    print(
        "\n=== RESULT: ZERO WRITES ===\n"
        "No genuine independent-source sale result found for 25000439CAAXMX or "
        "25000487CAAXMX as of 2026-08-15 (2 days post auction_date). "
        "bradfordclerk.com is site-wide 403 (Cloudflare 'Just a moment...' "
        "challenge, confirmed with 2 UAs). bctelegraph.com's newest edition "
        "(legal-notices-for-8-13-26/, the sale-date edition itself, 227,539 "
        "bytes, contains OTHER unrelated foreclosure notices) has ZERO "
        "mentions of either case number or party name. "
        "legal-notices-for-8-14-26/ does not exist yet (HTTP 404). "
        "No new source type beyond what shard1/3ce988ac already exhausted."
    )

    print(f"\n=== {county} post-check (unchanged, no writes performed) ===")
    after = rpc_evaluate(county)
    print(json.dumps(after))

    assert after["B"]["pass"] == before["B"]["pass"], "unexpected B drift with zero writes"
    assert after["F"]["pass"] == before["F"]["pass"], "unexpected F drift with zero writes"
    print("\nOK: B/F unchanged as expected (no writes were made).")


if __name__ == "__main__":
    main()
