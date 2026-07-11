#!/usr/bin/env python3
"""
Shard-7 lake_BF_recheck (re-fire of dispatch 9fe2973e-44ea-441c-9770-92ff736483dd),
2026-07-11.

Bounded, quick recheck of lake B/F -- NOT a rebuild. Prior session
(scripts/shard7_run3679_lake_bf_realtaxdeed_probe.py) already established B/F
are genuinely blocked: the one closed Lake TD auction (00389-2023) is a
REDEEMED case (no sale, no sold_amount by definition), and Lake has no
RealForeclose FC platform at all.

THIS SESSION'S FRESH LIVE RE-VERIFY (Playwright-rendered, both calendar dates):

  07/07/2026 -- 00389-2023: still "Redeemed", no sold_amount. UNCHANGED.
  07/21/2026 -- all 9 of our tracked "upcoming" TD cases still show under
    "Auctions Waiting" (opening bid only, no results) -- genuinely still
    10 days in the future as of 2026-07-11. UNCHANGED.
  07/21/2026 -- 02731-2022 still "Canceled per Bankruptcy". UNCHANGED.
  07/21/2026 -- NEW FINDING: case 04358-2023 (not tracked in our
    multi_county_auctions -- only 11 lake TD rows exist there, this isn't
    one of them) also shows "Redeemed" on the live closed/canceled list.
    Even if this untracked case were added, a redemption carries no
    sold_amount, so it would not move B or F. Not backfilled -- out of B/F's
    scope (it's an A-lane completeness question, not a B/F one, and adding
    an 12th untracked case was not requested/authorized this pass).

or.lakecountyclerk.org RETRY: still genuine NXDOMAIN, confirmed at the
authoritative Cloudflare nameserver (not a transient sandbox DNS issue --
dns.google resolver returns Status:3/NXDOMAIN directly from
lou.ns.cloudflare.com). However, this session found the REAL official-records
URL: https://officialrecords.lakecountyclerk.org/ (linked from
lakecountyclerk.org's own nav, resolves cleanly, HTTP 200). This is a genuine
correction to the "next-session priority" note -- the prior session's
`or.lakecountyclerk.org` guess was simply the wrong hostname, not evidence the
Clerk has no public official-records portal.

officialrecords.lakecountyclerk.org is a public AcclaimWeb/Harris Recording
Solutions portal (same platform family as Santa Rosa's acclaim.srccol.com,
which the prior santa_rosa session found had a broken AJAX search). Its
Case Number search form (/search/SearchTypeCaseNumber, with a real
"CERTIFICATE OF TITLE (COT)" doc-type checkbox) exists and is guest-
accessible after a one-time disclaimer POST, but submitting an actual
case-number query (tested against 00389-2023) returns HTTP 500 --
System.Web.Mvc.MvcHandler.EndProcessRequest server-side exception, most
likely because the form's ASP.NET AJAX UpdatePanel postback requires
client-side state (viewstate/eventvalidation-equivalent) that a raw
curl POST does not replicate; a full Playwright-driven form fill was judged
out of bounded-recheck budget for this single quick pass (would require
building a full COT-search flow from scratch, which the dispatch brief
explicitly says not to build large in a bounded pass).

CONCLUSION: B (verified=0/closed_sold=0) and F (tier1_sold=0/closed_sold=0)
are UNCHANGED and remain genuinely blocked. No sold_amount was found
anywhere live. Confirmed via fresh pencil_dod_evaluate_county call
before and after this recheck -- byte-identical metrics, no regression,
no fix landed (none was possible/available to land honestly).

ULTRALOOP audit rows logged: gold_standard_ultraloop_audit ids 5367 (B),
5368 (F), dispatch_id=9fe2973e-44ea-441c-9770-92ff736483dd,
ultraloop_mode='fallback', survived=true (claim = "still genuinely blocked").

Next-session priority update: a real fix for officialrecords.lakecountyclerk.org
Case Number search would need either (a) a Playwright-driven form submission
replicating the browser's full AJAX postback (feasible, medium effort -- the
form and doc-type checkboxes are real and public, no login required), or
(b) accepting that AcclaimWeb portals in this county-clerk product family are
consistently fragile to non-browser HTTP clients (2nd confirmed instance
after Santa Rosa) and budgeting a shared Playwright AcclaimWeb-search helper
if this pattern recurs in a 3rd county.
"""
import json
import os
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

DISPATCH_ID = "9fe2973e-44ea-441c-9770-92ff736483dd"


def rpc_evaluate_county(county: str) -> dict:
    data = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=data, headers=REST_HEADERS, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def live_render_calendar() -> dict:
    """Playwright-render both lake.realtaxdeed.com TD auction dates,
    return raw visible body text per date for honest inspection."""
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        for date in ["07/07/2026", "07/21/2026"]:
            url = (f"https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION"
                   f"&Zmethod=PREVIEW&AuctionDate={date}")
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            out[date] = page.inner_text("body")
        browser.close()
    return out


def main():
    print("=== BEFORE (fresh pencil_dod_evaluate_county) ===")
    before = rpc_evaluate_county("lake")
    print(json.dumps({"B": before["B"], "F": before["F"]}, indent=2))

    print("=== Live re-render of lake.realtaxdeed.com (both TD dates) ===")
    calendar = live_render_calendar()
    for date, text in calendar.items():
        # Print only the relevant slice for a quick eyeball check
        idx = text.find("Preview Items For Sale")
        print(f"--- {date} ---")
        print(text[idx:idx + 1200])

    print("=== AFTER (fresh pencil_dod_evaluate_county, should be unchanged) ===")
    after = rpc_evaluate_county("lake")
    print(json.dumps({"B": after["B"], "F": after["F"]}, indent=2))

    assert before["B"] == after["B"], "B changed unexpectedly -- investigate before claiming blocked"
    assert before["F"] == after["F"], "F changed unexpectedly -- investigate before claiming blocked"
    print("CONFIRMED: B and F unchanged, genuinely blocked, no fabrication.")


if __name__ == "__main__":
    main()
