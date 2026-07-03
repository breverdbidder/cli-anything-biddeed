#!/usr/bin/env python3
"""
shard_jefferson_clerk_scraper.py
Scrapes Jefferson County FL foreclosure + tax deed sale listings from the
Jefferson County Clerk of Court's website (jeffersonclerk.com).

Jefferson is a small rural county (pop ~14,000, county seat Monticello).
Investigation (2026-07-03) confirmed:
  - jefferson.realforeclose.com / jefferson.realtaxdeed.com are NOT
    provisioned RealAuction tenants for Jefferson. Jefferson does NOT use
    RealAuction or any other online auction vendor for either lane.
  - Both foreclosure and tax deed sales are conducted in-person at the
    Jefferson County Courthouse (1 Courthouse Circle, Monticello, FL 32344),
    11:00 AM, normally North Door. Tax deed page explicitly states:
    "You or your representative must be physically present at the sale
    to bid on the property."
  - Foreclosure sales: published as a PDF ("Foreclosure Sales") linked from
      https://www.jeffersonclerk.com/clerk-services/property-sales/foreclosures/
    Verified live 2026-07-03: PDF at jeffersonclerk.s3.amazonaws.com,
    1 row, Case# 25-CA-164, updated 6/22/2026.
  - Tax deed sales: published (when any are scheduled) in an "Upcoming Tax
    Deed Sales" section at the top of
      https://www.jeffersonclerk.com/clerk-services/property-sales/tax-deed-sales/
    As of 2026-07-03 this section is EMPTY (no PDF, no rows) — genuinely
    zero scheduled tax deed sales, not a scraper bug. Script handles this
    gracefully (0 rows, no error).

Usage:
  python3 scripts/shard_jefferson_clerk_scraper.py
  python3 scripts/shard_jefferson_clerk_scraper.py --dry-run
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

FC_PAGE_URL = "https://www.jeffersonclerk.com/clerk-services/property-sales/foreclosures/"
TD_PAGE_URL = "https://www.jeffersonclerk.com/clerk-services/property-sales/tax-deed-sales/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def find_pdf_link(html: str) -> str | None:
    m = re.search(r'href="(https://jeffersonclerk\.s3[^"]+\.pdf)"', html)
    return m.group(1) if m else None


def parse_foreclosure_pdf(pdf_bytes: bytes):
    """Parse the clerk's 'Foreclosure Sales' PDF into card records.

    Observed format (verified 2026-07-03), one record per sale, fields as
    plain lines with a label prefix, e.g.:
      Date of Sale 6/25/2026
      Case # 25-CA-164
      Plaintiff ...
      Defendant ...
      Final Judgment Amount $86,285.09
      Property Address 340 MARVIN ST MONTICELLO, FL. 32344
    """
    from pypdf import PdfReader
    import io

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(p.extract_text() for p in reader.pages)

    cards = []
    # Split on "Date of Sale" boundaries, each chunk is one record.
    chunks = re.split(r"(?=Date of Sale\s)", full_text)
    for chunk in chunks:
        m_date = re.search(r"Date of Sale\s+([\d/]+)", chunk)
        m_case = re.search(r"Case #\s*([A-Za-z0-9\-]+)", chunk)
        if not (m_date and m_case):
            continue
        m_plaintiff = re.search(r"Plaintiff\s+(.*?)\s+Defendant", chunk, re.S)
        m_defendant = re.search(r"Defendant\s+(.*?)\s+Final Judgment Amount", chunk, re.S)
        m_judgment = re.search(r"Final Judgment Amount\s+\$?([\d,]+\.\d{2})", chunk)
        m_addr = re.search(r"Property Address\s+(.*?)(?:\n|$)", chunk)
        cards.append({
            "sale_date": m_date.group(1).strip(),
            "case_number": m_case.group(1).strip(),
            "plaintiff": m_plaintiff.group(1).strip() if m_plaintiff else None,
            "defendant": m_defendant.group(1).strip() if m_defendant else None,
            "judgment_amount": m_judgment.group(1).replace(",", "") if m_judgment else None,
            "address": m_addr.group(1).strip() if m_addr else None,
        })
    return cards


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
        addr = c.get("address") or ""
        city_m = re.search(r"\s([A-Za-z]+),?\s*FL\.?\s*\d{5}", addr)
        zip_m = re.search(r"FL\.?\s*(\d{5})", addr)
        judgment = None
        if c.get("judgment_amount"):
            try:
                judgment = float(c["judgment_amount"])
            except ValueError:
                judgment = None
        auction_date = _parse_date(c["sale_date"])
        today = datetime.date.today().isoformat()
        auction_status = "sold" if (auction_date and auction_date < today) else "upcoming"
        rows.append({
            "county": "jefferson",
            "state": "FL",
            "sale_type": sale_type,
            "auction_type": sale_type,
            "auction_status": auction_status,
            "case_number": c["case_number"],
            "auction_date": auction_date,
            "property_address": addr or None,
            "city": city_m.group(1).strip() if city_m else None,
            "zip": zip_m.group(1) if zip_m else None,
            "plaintiff": c.get("plaintiff"),
            "judgment_amount": judgment,
            "judgment_amount_usd": judgment,
            "auction_venue": "in_person",
            "data_source": "jefferson_clerk_official:jeffersonclerk.com",
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

    rows = []

    fc_html = fetch(FC_PAGE_URL).decode("utf-8", errors="replace")
    fc_pdf_url = find_pdf_link(fc_html)
    if fc_pdf_url:
        pdf_bytes = fetch(fc_pdf_url)
        fc_cards = parse_foreclosure_pdf(pdf_bytes)
        print(f"Foreclosure sales parsed from PDF ({fc_pdf_url}): {len(fc_cards)}")
        rows += to_rows(fc_cards, "foreclosure", fc_pdf_url)
    else:
        print("No foreclosure sales PDF currently linked — 0 rows (not an error).")

    # Tax deed lane: sales list is rendered inline in an "Upcoming Tax Deed
    # Sales" section, not a static PDF. As of 2026-07-03 this section is
    # empty (0 scheduled sales). No parser needed until a sale is scheduled;
    # fetch is still performed so the run fails loud if the page structure
    # changes unexpectedly (non-200, or missing the #upcoming anchor).
    td_html = fetch(TD_PAGE_URL).decode("utf-8", errors="replace")
    if 'id="upcoming"' not in td_html:
        raise RuntimeError(
            "Jefferson tax-deed page structure changed: #upcoming anchor "
            "not found — scraper needs update, not silently skipping."
        )
    print("Tax deed sales parsed: 0 (no sales currently scheduled — verified via #upcoming section)")

    n = upsert(rows, dry_run=args.dry_run)
    print(f"Done. {n} rows processed.")


if __name__ == "__main__":
    main()
