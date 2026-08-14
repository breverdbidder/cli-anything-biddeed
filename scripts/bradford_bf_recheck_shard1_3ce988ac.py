#!/usr/bin/env python3
"""
bradford_bf_recheck_shard1_3ce988ac.py
Gold Standard shard-1 (dispatch 3ce988ac-bdcf-4554-aaa2-1f9b7653bc45), 2026-08-14

SCOPE: bradford B + F (both FAIL/null — closed_sold=0, no bradford row has
sold_amount set). This is the 8th+ dedicated session confirming this specific
structural block (see GOLD_STANDARD_SHARD*BRADFORD*SESSION_REPORT.md files in
repo root for the full history: shard1/42aaf1fb x2, shard2/5a29383b,
shard4/8389b490, shard4/191b679e, shard4/49342bab, shard6/f68d2ec5,
shard7/3645, shard10/96a9bc5d, shard11/dc2817a3 + refire addendum).

WHAT'S NEW THIS SESSION vs prior sessions:
  Live query 2026-08-14 shows bradford now has 5 auctions, 3 with auction_date
  in the past while auction_status still says "upcoming":
    - 25000457CAAXMX, 2026-07-16 (29 days past) — ALREADY exhausted across
      6 prior dedicated sessions (bradfordclerk.com, bctelegraph.com,
      surplusindex.com, Wayback, RealAuction N/A, officialrecords.bradfordclerk.com,
      myfloridacounty.com ORI [Turnstile-gated], civitekflorida.com OCRS
      [Turnstile-gated], Box.com doc link, courtlistener.com, judyrecords.com,
      trellis.law). NOT RE-CHASED this session per explicit instruction —
      would repeat known-dead approaches.
    - 25000439CAAXMX, 2026-08-13 (1 day past) — genuinely new: previously only
      investigated for letter E (parcel/address discovery, resolved 2026-07-19,
      SHARD1/42aaf1fb 2nd firing). Never before investigated for B/F sale outcome
      because its auction date had not yet passed in any prior session.
    - 25000487CAAXMX, 2026-08-13 (1 day past) — genuinely new: previously only
      investigated for letter E (parcel 00868-0-01801, SHARD7/3645). A prior
      session (SHARD7/3645) explicitly caught and REFUTED a false B/F-adjacent
      match attempt on this exact case number (a bctelegraph.com notice printed
      "04-2025-CA-487" which doesn't disambiguate from an unrelated case on the
      same page, and contained no case number in the quoted "evidence" at all).
      That refutation is respected here — no attempt is made to reuse that dead
      lead.

INVESTIGATION THIS SESSION (2026-08-14, both new cases):

  1. bradfordclerk.com/tax-deeds-and-foreclosure-sales/ (and /foreclosures/,
     /tax-deeds/, bare domain) — direct curl (2 UAs) => HTTP 403 on every path,
     Cloudflare "Just a moment..." managed challenge page (JS/cookie gate).
     WebFetch => HTTP 403 Forbidden. Site-wide block, consistent with every
     prior session's finding. No bypass attempted (CAPTCHA/Turnstile bypass is
     a hard prohibition).

  2. bctelegraph.com legal notices (7-23-26 edition) — reachable, HTTP 200.
     Contains ONE matching case: 25000439CAAXMX (Planet Home Lending, LLC v.
     Jonattan H. Barranco Pinto, 7594 SW 130TH STREET, STARKE FL 32091,
     "Notice of Foreclosure Sale" for 11:00 AM Aug 13 2026 at the Bradford
     County Courthouse front lobby). This is a PRE-SALE notice of intent to
     sell — it contains no winning-bid / sale amount, by definition (it was
     published 3 weeks before the sale even occurred). 25000487CAAXMX does NOT
     appear in this edition at all.
     Also checked 7-30-26 edition — same pre-sale notice content repeated
     (still forward-looking to the same Aug 13 sale), no post-sale results.
     No later edition (e.g. covering the week of/after Aug 13) is indexed/
     searchable yet — bctelegraph is a weekly paper and, per every prior
     session's finding, does not appear to publish post-sale results/
     certificates of sale as legal notices in the first place (only notices
     of intent to sell). This is a structural characteristic of the source,
     not a search failure.

  3. officialrecords.bradfordclerk.com — curl timeout (HTTP code 000),
     unreachable. Consistent with prior sessions.

  4. civitekflorida.com/ocrs/ and myfloridacounty.com/ori/ — HTTP 301/302
     redirects into their respective portal front-ends, both previously
     confirmed Turnstile/CAPTCHA-gated by prior sessions. Not re-attempted
     past the redirect (no CAPTCHA bypass).

  5. Wayback Machine — closest snapshot of the clerk's sales page is
     2024-05-24 (over 2 years stale). No use for a 2026-08-13 sale result.

  6. bradford.realforeclose.com / bradford.realtaxdeed.com — HTTP 403 both.
     Confirms prior sessions' finding that Bradford does NOT sell via a
     RealAuction-family online platform — the bctelegraph notice text itself
     says the sale occurs "at the Bradford County Courthouse front lobby"
     (in-person courthouse-steps sale), so there is no third-party auction
     platform that would independently publish a result either.

  7. judyrecords.com, trellis.law, courtlistener.com-style web search for both
     case numbers — no indexed sale-outcome content for either case. Only the
     same pre-sale Final Judgment / Notice of Sale content already found in
     step 2 comes back for 25000439CAAXMX. Nothing at all comes back for
     25000487CAAXMX beyond the earlier (refuted) E-letter parcel work.

CONCLUSION (2026-08-14): STILL STRUCTURALLY BLOCKED for both new cases.
  Root cause is NOT "no lead was tried" — every independent-source avenue used
  successfully elsewhere in this campaign was tried and dead-ended:
    - Primary source (bradfordclerk.com) is Cloudflare-blocked site-wide.
    - Secondary source (bctelegraph.com) only carries PRE-sale notices, never
      post-sale results, and only 1 day has elapsed since the auction date —
      even if the clerk does eventually publish something (deed/COS), FL
      county clerks commonly lag days-to-weeks per prior sessions' own notes
      on other counties. 1-day-past is not long enough to conclude "never
      published," but there is nothing published YET as of this check.
    - Tertiary/portal sources are Turnstile-gated (no bypass) or offline.
    - No online-auction-platform mirror exists because Bradford sells
      in-person at the courthouse.

  ZERO WRITES MADE. No sold_amount / tier1_sold_amount / auction_status /
  sale_result_date backfilled for either case. No foreclosure_outcomes /
  tax_deed_outcomes row inserted. Fabricating a sale amount here would be a
  HONESTY PROTOCOL violation — BLANK > WRONG.

  bradford B and F remain FAIL (closed_sold=0) after this session, same as
  every prior session. This is the expected, honest outcome for a genuinely
  blocked county-clerk data source with a same-day-lag publication gap, not a
  research failure.

RECOMMENDATION FOR NEXT SESSION: re-check bctelegraph.com and
bradfordclerk.com again once auction_date is >=7-10 days past for
25000439CAAXMX / 25000487CAAXMX (i.e. after ~2026-08-20/23) — clerk
publication lag may resolve by then. Do NOT re-attempt 25000457CAAXMX (6
sessions exhausted) unless a genuinely new source type appears.
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

    print(f"\n=== {county} raw auction rows (2 new cases under investigation) ===")
    rows = get_rows(county)
    for row in rows:
        flag = ""
        if row["case_number"] in ("25000439CAAXMX", "25000487CAAXMX"):
            flag = "  <-- investigated this session (see module docstring)"
        elif row["case_number"] == "25000457CAAXMX":
            flag = "  <-- NOT re-investigated (6 prior sessions exhausted)"
        print(json.dumps(row) + flag)

    print(
        "\n=== RESULT: ZERO WRITES ===\n"
        "No genuine independent-source sale result found for 25000439CAAXMX or "
        "25000487CAAXMX as of 2026-08-14 (1 day post auction_date). "
        "bradfordclerk.com is site-wide 403 (Cloudflare). bctelegraph.com only "
        "carries the pre-sale notice already on file, no post-sale results. "
        "officialrecords.bradfordclerk.com / civitekflorida OCRS / "
        "myfloridacounty ORI remain unreachable or Turnstile-gated. No "
        "RealAuction-family mirror exists (in-person courthouse sale). "
        "See module docstring for the full per-source trail."
    )

    print(f"\n=== {county} post-check (unchanged, no writes performed) ===")
    after = rpc_evaluate(county)
    print(json.dumps(after))

    assert after["B"]["pass"] == before["B"]["pass"], "unexpected B drift with zero writes"
    assert after["F"]["pass"] == before["F"]["pass"], "unexpected F drift with zero writes"
    print("\nOK: B/F unchanged as expected (no writes were made).")


if __name__ == "__main__":
    main()
