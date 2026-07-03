#!/usr/bin/env python3
"""
shard_liberty_clerk_scraper.py
Scrapes Liberty County FL foreclosure + tax deed sale listings from the
Liberty County Clerk of Court's website (server-rendered Vue page — no
login, no WAF block observed with a standard browser User-Agent).

Liberty is Florida's least-populous county (~8,000 residents). Investigation
(2026-07-03) confirmed:
  - liberty.realforeclose.com / liberty.realtaxdeed.com are NOT provisioned
    RealAuction tenants for Liberty — they return the generic RealAuction
    marketing shell page (sample listings from Maryland/NJ counties, zero
    occurrences of the string "liberty" in the response body). Liberty does
    NOT use RealAuction online auctions.
  - The REAL, authoritative source is the Liberty County Clerk's own site:
      https://libertyclerk.com/courts/foreclosure-sales/
      https://libertyclerk.com/courts/tax-deeds/
    Foreclosure sales are held in-person at 11:00 AM on the courthouse
    front steps (same in-person pattern as Brevard/Lake/Hernando).

Usage:
  python3 scripts/shard_liberty_clerk_scraper.py
  python3 scripts/shard_liberty_clerk_scraper.py --dry-run
"""

import os
import re
import sys
import json
import argparse
import datetime
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

FC_URL = "https://libertyclerk.com/courts/foreclosure-sales/"
TD_URL = "https://libertyclerk.com/courts/tax-deeds/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_sale_cards(html: str):
    """Parse the clerk site's repeated 'Status/Sale Date/Case Number/...' card blocks."""
    cards = []
    # Each card is a <div ...grid...> block containing labeled fields.
    blocks = re.split(r'(?=<div class="w-full grid md:grid-cols-3)', html)
    for b in blocks:
        if "Case Number" not in b or "Sale Date" not in b:
            continue

        def field(label):
            m = re.search(
                rf'{label}</label>\s*<strong[^>]*>([^<]*)</strong>', b
            )
            return m.group(1).strip() if m else None

        case_number = field("Case Number")
        sale_date = field("Sale Date")
        status = field("Status")
        judgment = field("Judgement Amount") or field("Judgment Amount")
        parties = field("Parties")
        addr_m = re.search(r'Address</label>\s*<a[^>]*>([^<]*)</a>', b)
        address = addr_m.group(1).strip() if addr_m else None

        if case_number and sale_date:
            cards.append({
                "case_number": case_number,
                "sale_date": sale_date,
                "status": status,
                "judgment_amount": judgment,
                "parties": parties,
                "address": address,
            })
    return cards


def _parse_money(s):
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(s):
    if not s:
        return None
    for fmt in ("%m/%d/%Y",):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def to_rows(cards, sale_type, source_url):
    rows = []
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for c in cards:
        addr = c["address"] or ""
        city_m = re.search(r",\s*([A-Za-z ]+),\s*FL", addr)
        zip_m = re.search(r"FL\s*(\d{5})", addr)
        rows.append({
            "county": "liberty",
            "state": "FL",
            "sale_type": sale_type,
            "auction_type": sale_type,
            "auction_status": "upcoming" if (c["status"] or "").lower() == "active" else (c["status"] or "upcoming"),
            "case_number": c["case_number"],
            "auction_date": _parse_date(c["sale_date"]),
            "property_address": addr or None,
            "city": city_m.group(1).strip() if city_m else None,
            "zip": zip_m.group(1) if zip_m else None,
            "plaintiff": (c["parties"].split(" VS ")[0].strip() if c["parties"] and " VS " in c["parties"] else None),
            "judgment_amount": _parse_money(c["judgment_amount"]),
            "judgment_amount_usd": _parse_money(c["judgment_amount"]),
            "auction_venue": "in_person",
            "data_source": "liberty_clerk_official:libertyclerk.com",
            "source_platform": "clerk_html",
            "source_url": source_url,
            "clerk_url": source_url,
            "provenance": "primary_scrape",
            "is_operational": True,
            "scrape_timestamp": now,
            "scraped_at": now,
            "last_seen_at": now,
        })
    return rows


def upsert(rows, dry_run=False):
    if not rows:
        print("No rows to upsert.")
        return 0
    if dry_run:
        print(json.dumps(rows, indent=2))
        return len(rows)

    body = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"Upserted {len(result)} rows.")
            return len(result)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"HTTPError {e.code}: {err_body}", file=sys.stderr)
        # Retry without on_conflict if the constraint doesn't exist
        req2 = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            data=body,
            method="POST",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
        with urllib.request.urlopen(req2, timeout=30) as resp2:
            result = json.loads(resp2.read().decode("utf-8"))
            print(f"Inserted {len(result)} rows (fallback, no upsert).")
            return len(result)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fc_html = fetch(FC_URL)
    fc_cards = parse_sale_cards(fc_html)
    print(f"Foreclosure sales parsed: {len(fc_cards)}")

    td_html = fetch(TD_URL)
    td_cards = parse_sale_cards(td_html)
    print(f"Tax deed sales parsed: {len(td_cards)}")

    rows = to_rows(fc_cards, "foreclosure", FC_URL) + to_rows(td_cards, "tax_deed", TD_URL)
    n = upsert(rows, dry_run=args.dry_run)
    print(f"Done. {n} rows processed.")


if __name__ == "__main__":
    main()
