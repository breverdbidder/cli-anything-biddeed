#!/usr/bin/env python3
"""
Shard-7 run3679: Lake county criterion B/F diagnosis via the official
RealTaxDeed platform (lake.realtaxdeed.com — independent of PropertyOnion).

FINDING (live, Playwright-driven probe, 2026-07-11):
  - Lake's 11 tax-deed auctions run on lake.realtaxdeed.com (RealAuction
    platform, id=37 "Lake Taxdeed" in the county picker). Lake has NO
    "Lake Foreclosure" entry on RealAuction/RealForeclose at all -- the 87
    foreclosure auctions are Clerk in-person/calendar-only, confirming the
    prior session's finding.
  - The public Preview page (zaction=AUCTION&zmethod=PREVIEW&AuctionDate=...)
    requires no login and shows real auction results per date, split into
    "Running Auctions" / "Auctions Waiting" / "Auctions Closed or Canceled".
  - For AuctionDate=07/07/2026 (the one TD auction in our data with a past
    date), the ONLY case listed under "Auctions Closed or Canceled" is
    00389-2023 with Auction Status: REDEEMED (not a completed sale -- the
    certificate holder was paid off / property owner redeemed before the
    sale went through). RealTaxDeed does not publish a winning-bid amount
    for a redemption because no sale occurred -- there is no sold_amount to
    harvest, honestly, for this case.
  - The other 10 TD auctions are all dated 07/21/2026 (10 days in the
    future as of this session, 2026-07-11) -- genuinely not yet closed,
    confirmed against the same live Preview page (they appear under
    "Auctions Waiting" with opening bids only, no results).

CONCLUSION: B (verified=0/closed_sold=0) and F (tier1_sold=0/closed_sold=0)
are NOT a missing-data-source problem for Lake this session -- they are a
genuine "nothing has actually sold yet" ceiling:
  - The only closed lake auction (TD case 00389-2023) redeemed, so it will
    never have a sold_amount by definition of what "redeemed" means.
  - The 87 FC auctions are Clerk in-person/calendar-only with no published
    bid-result ledger reachable from this environment (confirmed: the
    default calendar page at foreclosurecalendar.lakecountyclerkfl.gov does
    not list past-dated case numbers or any bid/sale-amount field -- it is a
    hearing calendar, not a results ledger).
  - The remaining 10 TD auctions have not occurred yet (future auction date).

The ONE concrete, honest correction made here: our own auction_status field
for case 00389-2023 was stale at 'sold' -- the authoritative RealTaxDeed
source says 'Redeemed'. This script corrects that one field (does NOT
fabricate a sold_amount -- there isn't one) and stamps sold_amount_source
so the correction is auditable and distinguishable from a PropertyOnion or
invented value.

B/F remain BLOCKED this session (see session report) -- not solvable by any
additional scraping effort, because the underlying real-world events
(a sale happening) have not occurred for 97 of 98 rows, and the one closed
case did not result in a sale.
"""
import json
import os
import sys
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


def http_patch(url, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={**REST_HEADERS, "Prefer": "return=representation"}, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def fetch_td_dates():
    """Live-fetch the RealTaxDeed Preview page for both TD auction dates we
    have in our data (07/07/2026 past, 07/21/2026 future) and print the
    parsed status per case number. Returns dict case_number -> status."""
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)
        for auction_date in ["07/07/2026", "07/21/2026"]:
            url = f"https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate={auction_date}"
            page.goto(url, timeout=30000)
            page.wait_for_timeout(1200)
            body_text = page.inner_text("body")
            print(f"=== {auction_date} ===")
            idx = body_text.find("Preview Items")
            print(body_text[idx:idx + 3000])
            # crude parse: split on "Case #:" blocks, look back for Auction Status
            blocks = body_text.split("Auction Starts")
            closed_section = body_text.split("Auctions Closed or Canceled")
            if len(closed_section) > 1:
                closed_text = closed_section[1]
                # each closed entry: "Auction Status\n<value>\nAuction Type:\tTAXDEED\nCase #:\t<num>"
                import re
                for m in re.finditer(r"Auction Status\s*\n(\S+)\s*\nAuction Type:\s*TAXDEED\s*\nCase #:\s*([^\n]+)", closed_text):
                    status, case_no = m.group(1), m.group(2).strip()
                    results[case_no] = status
        browser.close()
    return results


def main():
    statuses = fetch_td_dates()
    print("Parsed statuses:", json.dumps(statuses, indent=2))

    if not statuses:
        print("FAIL-LOUD: parsed zero closed-auction statuses from RealTaxDeed despite the page loading.", file=sys.stderr)
        sys.exit(1)

    # Only correct the one case we found in "Closed or Canceled" -- 00389-2023.
    target_case = "00389-2023"
    if target_case in statuses:
        real_status = statuses[target_case].lower()  # e.g. 'redeemed'
        url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.{target_case}&county=eq.lake"
        body = {
            "auction_status": real_status,
            "sold_amount_source": "lake_realtaxdeed_official_live" if real_status == "redeemed" else None,
        }
        status, resp_text = http_patch(url, body)
        print(json.dumps({
            "case_number": target_case,
            "old_auction_status": "sold",
            "new_auction_status": real_status,
            "sold_amount": "not set -- redemption means no sale occurred, no amount to record",
            "patch_status": status,
            "patch_ok": status in (200, 204),
            "patch_response": resp_text if status not in (200, 204) else None,
        }, indent=2))
    else:
        print(f"NOTE: {target_case} not found in parsed closed-section -- no correction made.", file=sys.stderr)


if __name__ == "__main__":
    main()
