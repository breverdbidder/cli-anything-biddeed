#!/usr/bin/env python3
"""
Calhoun Clerk Foreclosure/Tax-Deed Harvest (2026-07-10, updated 2026-07-10 SHARD-12)
=========================================================
Calhoun's RealAuction tenants (calhoun.realforeclose.com, calhoun.realtaxdeed.com)
are genuinely dark right now -- confirmed live via .github/scripts/calendar_sweep_mca.py
(zero future auction dates discovered on either lane, this session). The
county's real inventory lives on the Clerk's own website:
  https://www.calhounclerk.com/foreclosure     (redirects to /court-services/property-sales/foreclosure-sales/)
  https://www.calhounclerk.com/tax-deed-sales  (redirects to /court-services/property-sales/tax-deed-sales/)

The foreclosure page publishes structured Status/Sale Date/Case Number/Judgement
Amount/Address/Parcel ID fields directly as page text (CARD_RE below). The
tax-deed page was redesigned at some point after this harvester was first written
and now embeds its listings as a JSON blob in a Vue component attribute
(`<tax-deed-sales :taxdeeds="[...]">`) instead -- CARD_RE never matched it, which
is why every prior run found td=0 despite the page genuinely listing sales
(verified live 2026-07-10: 5 cards). TAXDEED_ATTR_RE below extracts and
json.loads()'s that blob. The tax-deed page does not publish street address,
only parcel + a Property Appraiser deep link, so property_address is left null
for tax_deed rows rather than fabricated.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row upserted), 1 = fatal error, 2 = no new rows found
"""
import html
import json
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

TAXDEED_ATTR_RE = re.compile(r':taxdeeds="(?P<blob>\[.*?\])"', re.S)


def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def fetch_raw(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def fetch_text(url: str) -> str:
    raw = fetch_raw(url)
    text = re.sub(r"<script.*?</script>", "", raw, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&#8217;", "'").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text)


def parse_cards(text: str) -> list[dict]:
    return [m.groupdict() for m in CARD_RE.finditer(text)]


def parse_taxdeed_json(raw_html: str) -> list[dict]:
    m = TAXDEED_ATTR_RE.search(raw_html)
    if not m:
        return []
    return json.loads(html.unescape(m.group("blob")))


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
            "county": "calhoun",
            "case_number": c["case_number"],
            "sale_type": "foreclosure",
            "auction_type": "foreclosure",
            "auction_date": f"{yyyy}-{mm}-{dd}",
            "property_address": c["address"].strip(),
            "parcel_id": c["parcel_id"],
            "judgment_amount": float(c["judgment"].replace(",", "")),
            "auction_status": "upcoming" if c["status"].lower() == "scheduled" else c["status"].lower(),
            "state": "FL",
            "source_platform": "calhoun_clerk_scrape",
            "data_source": "calhoun_clerk_scrape",
            "source_url": fc_url,
        })

    td_url = PAGES["tax_deed"]
    td_raw = fetch_raw(td_url)
    td_cards = parse_taxdeed_json(td_raw)
    print(f">>> tax_deed: {len(td_cards)} card(s) found on {td_url}")
    for c in td_cards:
        iso_date = (c.get("iso_sale_date") or "").split(" ")[0]
        if not iso_date:
            continue
        opening_bid = c.get("opening_bid")
        rows.append({
            "county": "calhoun",
            "case_number": c["cert"],
            "sale_type": "tax_deed",
            "auction_type": "tax_deed",
            "auction_date": iso_date,
            "property_address": None,
            "parcel_id": c.get("parcel") or None,
            "opening_bid": float(opening_bid) if opening_bid not in (None, "") else None,
            "auction_status": "upcoming" if (c.get("status") or "").lower() == "scheduled" else (c.get("status") or "").lower(),
            "state": "FL",
            "source_platform": "calhoun_clerk_scrape",
            "data_source": "calhoun_clerk_scrape",
            "source_url": c.get("link") or td_url,
        })

    if not rows:
        print("NOTE: zero cards parsed from either page -- calhoun genuinely has no listed inventory")
        return 2

    # PostgREST bulk insert requires every object to carry the same key set.
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

    print(f"\nSUCCESS: upserted {len(rows)} calhoun row(s): {[r['case_number'] for r in rows]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
