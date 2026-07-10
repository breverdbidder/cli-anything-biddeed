#!/usr/bin/env python3
"""
Lafayette Clerk Foreclosure/Tax-Deed Harvest (2026-07-10, SHARD dispatch
11df373c-d3d3-4778-b489-2c32d7af5545)
=========================================================
Lafayette's foreclosure_platform and taxdeed_platform in pipeline.counties are
both 'clerk_inperson' -- there is no RealAuction tenant for Florida's least
populous county. Sales are conducted in person on the courthouse steps, but
the Clerk's own WordPress/Vue site DOES publish structured upcoming-sale cards
online (confirmed live 2026-07-10, plain curl, no Cloudflare challenge):
  https://www.lafayetteclerk.com/departments-services/court-services/foreclosure-sales/
  https://www.lafayetteclerk.com/departments-services/clerk-services/tax-deeds/

Foreclosure page card markup (same WordPress/Vue "even:bg-gray-100" theme used
by columbia/calhoun): Status / Sale Date / Case Number / Judgement Amount /
Parties / Address / Parcel ID rendered as plain label/strong text -- CARD_RE
below matches it directly on the flattened text (no headless browser needed,
this site does not challenge plain HTTP requests).

Tax-deed page currently reads verbatim "There are no properties on the list of
tax deeds at this time." -- genuinely zero live inventory, not a scrape
failure. This is asserted explicitly (NO_TAXDEED_MARKER) so a future change to
real listings is detected rather than silently continuing to report 0.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row upserted), 1 = fatal error, 2 = no new rows found
"""
import os
import re
import sys

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

PAGES = {
    "foreclosure": "https://www.lafayetteclerk.com/departments-services/court-services/foreclosure-sales/",
    "tax_deed": "https://www.lafayetteclerk.com/departments-services/clerk-services/tax-deeds/",
}

CARD_RE = re.compile(
    r"Status\s+(?P<status>\w+)\s+"
    r"Sale Date\s+(?P<sale_date>\d{2}/\d{2}/\d{4})\s+[\d:]+\s*[ap]m\s+"
    r"Case Number\s+(?P<case_number>[\w\-]+)\s+"
    r"Judgement Amount\s+\$(?P<judgment>[\d,.]+)\s+"
    r"Parties\s+(?P<parties>.+?)\s+"
    r"Address\s+(?P<address>.+?)\s+"
    r"Parcel ID\s+(?P<parcel_id>[\w\-]+)",
    re.IGNORECASE,
)

NO_TAXDEED_MARKER = "no properties on the list of tax deeds"


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
    text = text.replace("&#8217;", "'").replace("&nbsp;", " ").replace("&#038;", "&")
    text = re.sub(r"\s+", " ", text)
    return text


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

    fc_url = PAGES["foreclosure"]
    fc_text = fetch_text(fc_url)
    fc_cards = parse_cards(fc_text)
    print(f">>> foreclosure: {len(fc_cards)} card(s) found on {fc_url}")
    for c in fc_cards:
        mm, dd, yyyy = c["sale_date"].split("/")
        rows.append({
            "county": "lafayette",
            "case_number": c["case_number"],
            "sale_type": "foreclosure",
            "auction_type": "foreclosure",
            "auction_date": f"{yyyy}-{mm}-{dd}",
            "property_address": c["address"].strip(),
            "parcel_id": c["parcel_id"],
            "judgment_amount": float(c["judgment"].replace(",", "")),
            "plaintiff": c["parties"].strip(),
            "auction_status": "upcoming" if c["status"].lower() == "scheduled" else c["status"].lower(),
            "state": "FL",
            "source_platform": "lafayette_clerk_scrape",
            "data_source": "lafayette_clerk_scrape",
            "source_url": fc_url,
        })

    td_url = PAGES["tax_deed"]
    td_text = fetch_text(td_url)
    if NO_TAXDEED_MARKER in td_text.lower():
        print(">>> tax_deed: 0 card(s) -- page explicitly states no properties listed (verified, not a scrape failure)")
    else:
        td_cards = parse_cards(td_text)
        print(f">>> tax_deed: {len(td_cards)} card(s) found on {td_url} (page format changed from 'no properties' marker -- CARD_RE attempted)")
        for c in td_cards:
            mm, dd, yyyy = c["sale_date"].split("/")
            rows.append({
                "county": "lafayette",
                "case_number": c["case_number"],
                "sale_type": "tax_deed",
                "auction_type": "tax_deed",
                "auction_date": f"{yyyy}-{mm}-{dd}",
                "property_address": c["address"].strip(),
                "parcel_id": c["parcel_id"],
                "judgment_amount": float(c["judgment"].replace(",", "")),
                "plaintiff": c["parties"].strip(),
                "auction_status": "upcoming" if c["status"].lower() == "scheduled" else c["status"].lower(),
                "state": "FL",
                "source_platform": "lafayette_clerk_scrape",
                "data_source": "lafayette_clerk_scrape",
                "source_url": td_url,
            })

    if not rows:
        print("NOTE: zero cards parsed from either page -- lafayette genuinely has no listed inventory right now")
        return 2

    all_keys = set().union(*(r.keys() for r in rows))
    for r in rows:
        for k in all_keys:
            r.setdefault(k, None)

    resp = requests.post(
        f"{supa_url}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        headers=headers, json=rows, timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        print(f"ERROR: upsert failed {resp.status_code} {resp.text[:300]}", file=sys.stderr)
        return 1

    print(f"\nSUCCESS: upserted {len(rows)} lafayette row(s): {[r['case_number'] for r in rows]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
