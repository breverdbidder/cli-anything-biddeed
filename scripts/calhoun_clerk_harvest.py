#!/usr/bin/env python3
"""
Calhoun Clerk Foreclosure/Tax-Deed Harvest (2026-07-10)
=========================================================
Calhoun's RealAuction tenants (calhoun.realforeclose.com, calhoun.realtaxdeed.com)
are genuinely dark right now -- confirmed live via .github/scripts/calendar_sweep_mca.py
(zero future auction dates discovered on either lane, this session). The
county's real inventory lives on the Clerk's own website, which -- unlike most
FL clerk sites -- publishes structured Status/Sale Date/Case Number/Judgement
Amount/Address/Parcel ID fields directly on the page (no PDF needed):
  https://www.calhounclerk.com/foreclosure
  https://www.calhounclerk.com/tax-deed-sales

This gives us case_number + address + parcel_id + judgment_amount in one shot,
so criterion E (parcel linkage) is satisfied immediately on ingest for anything
this script picks up.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row upserted), 1 = fatal error, 2 = no new rows found
"""
import os
import re
import sys
import urllib.request

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

PAGES = {
    "foreclosure": "https://www.calhounclerk.com/foreclosure",
    "tax_deed": "https://www.calhounclerk.com/tax-deed-sales",
}

CARD_RE = re.compile(
    r"Status\s+(?P<status>\w+)\s+"
    r"Sale Date\s+(?P<sale_date>\d{2}/\d{2}/\d{4})\s+"
    r"Case Number\s+(?P<case_number>[\w\-]+)\s+"
    r"Judgement Amount\s+\$(?P<judgment>[\d,.]+)\s+"
    r"Address\s+(?P<address>.+?)\s+"
    r"Parcel ID\s+(?P<parcel_id>[\w\-]+)",
    re.IGNORECASE,
)


def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "ignore")
    text = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&#8217;", "'").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text)


def parse_cards(text: str) -> list[dict]:
    return [m.groupdict() for m in CARD_RE.finditer(text)]


def main() -> int:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    rows = []
    for sale_type, url in PAGES.items():
        text = fetch_text(url)
        cards = parse_cards(text)
        print(f">>> {sale_type}: {len(cards)} card(s) found on {url}")
        for c in cards:
            mm, dd, yyyy = c["sale_date"].split("/")
            rows.append({
                "county": "calhoun",
                "case_number": c["case_number"],
                "sale_type": sale_type,
                "auction_type": sale_type,
                "auction_date": f"{yyyy}-{mm}-{dd}",
                "property_address": c["address"].strip(),
                "parcel_id": c["parcel_id"],
                "judgment_amount": float(c["judgment"].replace(",", "")),
                "auction_status": "upcoming" if c["status"].lower() == "scheduled" else c["status"].lower(),
                "state": "FL",
                "source_platform": "calhoun_clerk_scrape",
                "data_source": "calhoun_clerk_scrape",
                "source_url": url,
            })

    if not rows:
        print("NOTE: zero cards parsed from either page -- calhoun genuinely has no listed inventory")
        return 2

    resp = requests.post(
        f"{supa_url}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        headers=headers, json=rows, timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        print(f"ERROR: upsert failed {resp.status_code} {resp.text[:300]}", file=sys.stderr)
        return 1

    print(f"\nSUCCESS: upserted {len(rows)} calhoun row(s): {[r['case_number'] for r in rows]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
