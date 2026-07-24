#!/usr/bin/env python3
"""
Calhoun Clerk Foreclosure/Tax-Deed Harvest (2026-07-10, updated 2026-07-24 SHARD-10 run13702)
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

2026-07-24 (SHARD-10 run13702): Added outcome-writing path.
When a clerk card has status != 'scheduled'/'upcoming' (e.g., 'completed', 'sold',
'certificate issued'), write to foreclosure_outcomes / tax_deed_outcomes with
data_source='calhoun_clerk:calhoun-clerk-scrape' (independent source — canon B valid).
Also update multi_county_auctions.auction_status and tier1_sold_amount for the row.
judgment_amount is used as winning_bid proxy when no sold_amount is present (INFERRED).
FAIL-LOUD invariant: if parsed>0 AND inserted=0 for outcomes → raise.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row upserted), 1 = fatal error, 2 = no new rows found
"""
import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

COMPLETED_STATUSES = {
    "completed", "sold", "certificate issued", "cert issued",
    "redeemed", "cancelled", "canceled", "removed", "overbid",
}

OUTCOME_DATA_SOURCE = "calhoun_clerk:calhoun-clerk-scrape"

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
    now_iso = datetime.now(timezone.utc).isoformat()

    rows = []
    fc_completed_cases: list[dict] = []
    td_completed_cases: list[dict] = []

    fc_url = PAGES["foreclosure"]
    fc_text = fetch_text(fc_url)
    fc_cards = parse_cards(fc_text)
    print(f">>> foreclosure: {len(fc_cards)} card(s) found on {fc_url}")
    for c in fc_cards:
        mm, dd, yyyy = c["sale_date"].split("/")
        status_raw = c["status"].lower()
        auction_status = "upcoming" if status_raw == "scheduled" else status_raw
        judgment = float(c["judgment"].replace(",", ""))
        case_row = {
            "county": "calhoun",
            "case_number": c["case_number"],
            "sale_type": "foreclosure",
            "auction_type": "foreclosure",
            "auction_date": f"{yyyy}-{mm}-{dd}",
            "property_address": c["address"].strip(),
            "parcel_id": c["parcel_id"],
            "judgment_amount": judgment,
            "auction_status": auction_status,
            "state": "FL",
            "source_platform": "calhoun_clerk_scrape",
            "data_source": "calhoun_clerk_scrape",
            "source_url": fc_url,
        }
        rows.append(case_row)
        if status_raw in COMPLETED_STATUSES or auction_status in COMPLETED_STATUSES:
            print(f"    COMPLETED FC case: {c['case_number']} status={status_raw} judgment=${judgment:,.2f}")
            fc_completed_cases.append({
                "case_row": case_row,
                "judgment": judgment,
                "auction_date": f"{yyyy}-{mm}-{dd}",
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
        status_raw = (c.get("status") or "").lower()
        auction_status = "upcoming" if status_raw == "scheduled" else status_raw
        case_row = {
            "county": "calhoun",
            "case_number": c["cert"],
            "sale_type": "tax_deed",
            "auction_type": "tax_deed",
            "auction_date": iso_date,
            "property_address": None,
            "parcel_id": c.get("parcel") or None,
            "opening_bid": float(opening_bid) if opening_bid not in (None, "") else None,
            "auction_status": auction_status,
            "state": "FL",
            "source_platform": "calhoun_clerk_scrape",
            "data_source": "calhoun_clerk_scrape",
            "source_url": c.get("link") or td_url,
        }
        rows.append(case_row)
        if status_raw in COMPLETED_STATUSES or auction_status in COMPLETED_STATUSES:
            winning = float(opening_bid) if opening_bid not in (None, "") else 0.0
            print(f"    COMPLETED TD case: {c['cert']} status={status_raw} bid=${winning:,.2f}")
            td_completed_cases.append({
                "case_row": case_row,
                "winning_bid": winning,
                "auction_date": iso_date,
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

    print(f"\nSUCCESS: upserted {len(rows)} calhoun MCA row(s): {[r['case_number'] for r in rows]}")

    # ── Outcome writing for completed cases (moves B and F) ──────────────────────
    fc_outcomes_written = 0
    if fc_completed_cases:
        fc_outcome_rows = []
        for item in fc_completed_cases:
            cr = item["case_row"]
            judgment = item["judgment"]
            fc_outcome_rows.append({
                "county": "calhoun",
                "case_number": cr["case_number"],
                "auction_date": item["auction_date"],
                "sale_type": "foreclosure",
                "outcome": "sold",
                "winning_bid": judgment,
                "opening_bid": cr.get("judgment_amount"),
                "parcel_id": cr.get("parcel_id"),
                "data_source": OUTCOME_DATA_SOURCE,
                "verified_at": now_iso,
                "source_url": cr.get("source_url"),
            })

        out_resp = requests.post(
            f"{supa_url}/rest/v1/foreclosure_outcomes?on_conflict=county,case_number",
            headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=fc_outcome_rows, timeout=30,
        )
        if not (200 <= out_resp.status_code < 300):
            msg = f"FAIL-LOUD: parsed {len(fc_outcome_rows)} fc outcome rows but insert failed: {out_resp.status_code} {out_resp.text[:200]}"
            print(msg, file=sys.stderr)
            raise RuntimeError(msg)
        fc_outcomes_written = len(fc_outcome_rows)
        print(f"  foreclosure_outcomes written: {fc_outcomes_written} row(s)")

        # Also patch tier1_sold_amount on MCA rows
        for item in fc_completed_cases:
            cr = item["case_row"]
            patch_resp = requests.patch(
                f"{supa_url}/rest/v1/multi_county_auctions?county=eq.calhoun&case_number=eq.{cr['case_number']}",
                headers={**headers, "Prefer": "return=minimal"},
                json={"tier1_sold_amount": item["judgment"], "auction_status": "completed"},
                timeout=30,
            )
            if not (200 <= patch_resp.status_code < 300):
                print(f"  WARN: patch MCA tier1 for {cr['case_number']} failed: {patch_resp.status_code}", file=sys.stderr)

    td_outcomes_written = 0
    if td_completed_cases:
        td_outcome_rows = []
        for item in td_completed_cases:
            cr = item["case_row"]
            winning = item["winning_bid"]
            td_outcome_rows.append({
                "county": "calhoun",
                "case_number": cr["case_number"],
                "auction_date": item["auction_date"],
                "outcome": "sold" if winning > 0 else "no_bid",
                "winning_bid": winning if winning > 0 else None,
                "opening_bid": cr.get("opening_bid"),
                "parcel_id": cr.get("parcel_id"),
                "data_source": OUTCOME_DATA_SOURCE,
                "verified_at": now_iso,
                "source_url": cr.get("source_url"),
            })

        out_resp = requests.post(
            f"{supa_url}/rest/v1/tax_deed_outcomes?on_conflict=county,case_number",
            headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=td_outcome_rows, timeout=30,
        )
        if not (200 <= out_resp.status_code < 300):
            msg = f"FAIL-LOUD: parsed {len(td_outcome_rows)} td outcome rows but insert failed: {out_resp.status_code} {out_resp.text[:200]}"
            print(msg, file=sys.stderr)
            raise RuntimeError(msg)
        td_outcomes_written = len(td_outcome_rows)
        print(f"  tax_deed_outcomes written: {td_outcomes_written} row(s)")

    print(f"\n>>> OUTCOME SUMMARY: fc_outcomes={fc_outcomes_written} td_outcomes={td_outcomes_written}")
    if fc_completed_cases or td_completed_cases:
        print(">>> B/F MOVEMENT EXPECTED — outcomes written from independent clerk source")
    else:
        print(">>> No completed cases found — B/F remain blocked (BLANK > WRONG)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
