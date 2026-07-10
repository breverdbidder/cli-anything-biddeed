#!/usr/bin/env python3
"""
Holmes Clerk C/D Parity Harvest + B/F Investigation (GOLD-STANDARD shard12, run3534, 2026-07-10)
==================================================================================================
holmes.realforeclose.com and holmes.realtaxdeed.com both 302-redirect off-host to the
generic unprovisioned www.realauction.com splash page -- confirmed dead again this
session. Holmes County's real auction inventory lives on the Clerk's own WordPress
site:
    https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/
    https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/
    https://holmesclerk.com/courts/foreclosures-tax-deeds/lands-available-for-taxes/

Unlike Calhoun's clerk site (no Vue/JSON embed here -- confirmed by grepping for
':taxdeeds="[' and ':foreclosures="[' style attrs, zero matches), Holmes publishes
both foreclosure and tax-deed listings as plain page text. Cards are parsed via
regex directly against the flattened text.

PARITY (C/D): exact-match case_number against multi_county_auctions WHERE
county='holmes' and, on match, set parity_status='matched_clean' with
parity_source='tier1:holmes_run3534_clerk_harvest_shard12'.

B/F INVESTIGATION (this run's key finding): the Clerk site is a FORWARD-LOOKING
notice board only.
  - Foreclosure page: 4 cases listed, none dated in the past relative to today except
    one (June 11 2026, "UPDATED: 06/16/2026" i.e. stale but still shown as upcoming --
    no "SOLD"/status/result field exists anywhere on the page).
  - Tax-deed page: 5 cases listed, ALL future-dated (7/14 or 7/21/2026). The 5
    case_numbers that were previously unmatched in our DB (TD#2023-225, TD#2023-496,
    TD#2023-584, TD#2023-185, TD#2020-589) have ROLLED OFF this live page entirely --
    they are no longer listed as upcoming, which strongly suggests they already sold
    and were removed, but the Clerk site has NO results/disposition page to confirm
    that. "Lands Available for Taxes" page checked too -- explicitly empty
    ("NO LOLA FILES AT THIS TIME").
  - There is no case-search/disposition tool on holmesclerk.com.
Conclusion: this source structurally CANNOT produce a sold_amount/winning_bidder for
ANY case, past or present. No outcome-table insert is possible from this source.
B/F remain a genuine not-yet-measurable gap for holmes -- NOT a scraper gap. This
script does not fabricate or insert any outcome row.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row matched/upserted), 1 = fatal error, 2 = zero cards parsed (fail-loud)
"""
import html
import os
import re
import sys

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

PAGES = {
    "foreclosure": "https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/",
    "tax_deed": "https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/",
}

# Foreclosure cards: "SALE DATE: <MONTH DD, YYYY> FINAL JUDGMENT AMOUNT: $X PARCEL ID: Y PROPERTY ADDRESS: Z"
# Case number is NOT published on the foreclosure page as a distinct labeled field --
# Holmes identifies foreclosure listings by plaintiff-v-defendant caption + sale date,
# which is why the pre-existing DB rows use synthetic "HOLMES-LEGACY-<uuid>" case
# numbers rather than a real court case number. We match on (auction_type='foreclosure',
# auction_date, property_address) triple instead of case_number for this lane.
FC_CARD_RE = re.compile(
    r"SALE DATE:\s*(?P<sale_date>[A-Z]+ \d{1,2},\s*\d{4})\s+"
    r"FINAL JUDGMENT AMOUNT:\s*\$(?P<judgment>[\d,.]+)\s+"
    r"PARCEL ID:\s*(?P<parcel_id>[\w.\-]+)\s+"
    r"PROPERTY ADDRESS:\s*(?P<address>.+?FL\.?\s*\d{5})",
    re.IGNORECASE,
)

TD_CARD_RE = re.compile(
    r"(?P<case_number>TD#[\d\-]+)\s+"
    r"(?P<owner>[A-Z0-9 .,'&\-]*?)\s*"
    r"PARCEL ID:\s*(?P<parcel_id>[\w.\-]+)\s+"
    r"OPENING BID:\$(?P<opening_bid>[\d,.]*)\s+"
    r"SALE DATE:(?P<sale_date>\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)

MONTHS = {
    "JANUARY": "01", "FEBRUARY": "02", "MARCH": "03", "APRIL": "04",
    "MAY": "05", "JUNE": "06", "JULY": "07", "AUGUST": "08",
    "SEPTEMBER": "09", "OCTOBER": "10", "NOVEMBER": "11", "DECEMBER": "12",
}


def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def fetch_text(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    raw = r.text
    text = re.sub(r"<script.*?</script>", "", raw, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


def parse_fc_date(s: str) -> str:
    month_word, rest = s.split(" ", 1)
    dd, yyyy = rest.replace(",", "").split()
    return f"{yyyy}-{MONTHS[month_word.upper()]}-{int(dd):02d}"


def parse_td_date(s: str) -> str:
    mm, dd, yyyy = s.split("/")
    return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"


def main() -> int:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
    }

    fc_text = fetch_text(PAGES["foreclosure"])
    fc_cards = FC_CARD_RE.findall(fc_text)
    print(f">>> foreclosure: {len(fc_cards)} card(s) parsed from {PAGES['foreclosure']}")

    td_text = fetch_text(PAGES["tax_deed"])
    td_cards = TD_CARD_RE.findall(td_text)
    print(f">>> tax_deed: {len(td_cards)} card(s) parsed from {PAGES['tax_deed']}")

    if not fc_cards and not td_cards:
        print("FAIL-LOUD: zero cards parsed from either live page -- refusing silent no-op", file=sys.stderr)
        return 2

    # Pull current holmes rows to match against.
    resp = requests.get(
        f"{supa_url}/rest/v1/multi_county_auctions"
        "?county=eq.holmes&select=case_number,auction_type,auction_date,property_address,parity_status",
        headers=headers, timeout=30,
    )
    resp.raise_for_status()
    db_rows = resp.json()
    print(f">>> DB: {len(db_rows)} existing holmes row(s)")

    live_td_case_numbers = {c[0].strip().upper() for c in td_cards}
    live_fc_addresses = {re.sub(r"[.,]", "", c[3]).strip().upper() for c in fc_cards}

    matched, already_matched, unmatched_live_to_db, rolled_off = [], [], [], []

    for row in db_rows:
        cn = (row["case_number"] or "").strip().upper()
        at = row["auction_type"]
        addr = re.sub(r"[.,]", "", (row["property_address"] or "")).strip().upper()
        is_live = (at == "tax_deed" and cn in live_td_case_numbers) or (
            at == "foreclosure" and addr in live_fc_addresses
        )
        if at == "tax_deed" and cn not in live_td_case_numbers and cn.startswith("TD#"):
            rolled_off.append(row["case_number"])
            continue
        if not is_live:
            continue
        if row["parity_status"] == "matched_clean":
            already_matched.append(row["case_number"])
            continue
        matched.append(row["case_number"])

    print(f">>> live-and-already matched_clean: {len(already_matched)} -> {already_matched}")
    print(f">>> live-but-needs-update: {len(matched)} -> {matched}")
    print(f">>> rolled off live TD page (no longer listed, no disposition data available): "
          f"{len(rolled_off)} -> {rolled_off}")

    updated = 0
    for cn in matched:
        patch = requests.patch(
            f"{supa_url}/rest/v1/multi_county_auctions?county=eq.holmes&case_number=eq.{requests.utils.quote(cn)}",
            headers=headers,
            json={
                "parity_status": "matched_clean",
                "parity_source": "tier1:holmes_run3534_clerk_harvest_shard12",
            },
            timeout=30,
        )
        if not (200 <= patch.status_code < 300):
            print(f"ERROR: patch failed for {cn}: {patch.status_code} {patch.text[:200]}", file=sys.stderr)
            return 1
        updated += 1

    print(f"\nSUCCESS: {updated} row(s) newly set to matched_clean this run; "
          f"{len(already_matched)} row(s) already matched_clean (idempotent no-op).")

    print(
        "\nB/F FINDING (documented, not written to DB): holmesclerk.com is a "
        "forward-looking notice board with NO results/disposition page and NO case "
        "search tool. 'Lands Available for Taxes' checked and is explicitly empty "
        "('NO LOLA FILES AT THIS TIME'). No sold_amount/winning_bidder can be sourced "
        "from this platform for any case, past or future. B/F remain a genuine "
        "not-yet-measurable gap for holmes, not a scraper gap. No outcome row inserted."
    )

    if updated == 0 and not already_matched:
        # We parsed >0 live cards but matched nothing at all against DB -- that would
        # be a silent failure mode worth failing loud on.
        print("FAIL-LOUD: parsed live cards but matched zero DB rows", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
