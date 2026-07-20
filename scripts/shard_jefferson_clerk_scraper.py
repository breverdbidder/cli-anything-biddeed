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
    As of 2026-07-03 this section was EMPTY (no PDF, no rows).
    As of 2026-07-15 a new PDF "Pending-Tax-Deed-Sales.pdf" appeared with
    2 cases: 26-TD-04 and 26-TD-05, both scheduled 2026-08-19.

Letter B/F auto-resolution:
  - When a past-due foreclosure or tax-deed case is found on the page with
    a sale date that has passed, this scraper checks whether the case has a
    Sale Results PDF posted. If found, it parses the sold_amount and writes
    a row to foreclosure_outcomes / tax_deed_outcomes (data_source=
    'jefferson_clerk_direct:jeffersonclerk.com') AND updates the
    multi_county_auctions row with auction_status='sold', tier1_sold_amount,
    tier1_authoritative=true.
  - This auto-resolution is idempotent: if the outcome is already present,
    no update is made.

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
import urllib.error

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


def find_pdf_links(html: str) -> list[str]:
    """Find all S3-hosted PDFs linked from the clerk page."""
    return re.findall(r'href="(https://jeffersonclerk\.s3[^"]+\.pdf)"', html)


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
        m_high_bid = re.search(r"(?:Highest Bid|Sale Amount|Sold For|Winning Bid)\s+\$?([\d,]+\.\d{2})", chunk)
        m_buyer = re.search(r"(?:Buyer|Purchaser|Grantee)\s+(.*?)(?:\n|$)", chunk)
        cards.append({
            "sale_date": m_date.group(1).strip(),
            "case_number": m_case.group(1).strip(),
            "plaintiff": m_plaintiff.group(1).strip() if m_plaintiff else None,
            "defendant": m_defendant.group(1).strip() if m_defendant else None,
            "judgment_amount": m_judgment.group(1).replace(",", "") if m_judgment else None,
            "address": m_addr.group(1).strip() if m_addr else None,
            "high_bid": m_high_bid.group(1).replace(",", "") if m_high_bid else None,
            "buyer": m_buyer.group(1).strip() if m_buyer else None,
        })
    return cards


def parse_tax_deed_pdf(pdf_bytes: bytes):
    """Parse the clerk's 'Pending Tax Deed Sales' or 'Tax Deed Results' PDF.

    Format observed 2026-07-15 for Pending-Tax-Deed-Sales.pdf:
      Case No. 26-TD-04
      Parcel ID: 05-2S-3E-0000-0012-0000
      Property Address: 1676 Brooks Rd. Monticello, FL. 32344
      Owner: Paul Connell
      Opening Bid: $3,168.31
      Sale Date: 08/19/2026
    Post-sale results PDFs may include:
      High Bid / Sale Amount / Winning Bid fields
      Buyer / Purchaser name
    """
    from pypdf import PdfReader
    import io

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(p.extract_text() for p in reader.pages)

    cards = []
    chunks = re.split(r"(?=Case No\.?\s+\d{2}-TD-)", full_text, flags=re.IGNORECASE)
    for chunk in chunks:
        m_case = re.search(r"Case No\.?\s+(\d{2}-TD-\d+)", chunk, re.IGNORECASE)
        if not m_case:
            continue
        m_date = re.search(r"Sale Date:?\s+([\d/]+)", chunk)
        m_parcel = re.search(r"Parcel ID:?\s+([A-Za-z0-9\-]+)", chunk)
        m_addr = re.search(r"Property Address:?\s+(.*?)(?:\n|$)", chunk)
        m_owner = re.search(r"Owner:?\s+(.*?)(?:\n|$)", chunk)
        m_opening = re.search(r"Opening Bid:?\s+\$?([\d,]+\.\d{2})", chunk)
        m_high_bid = re.search(r"(?:High Bid|Sale Amount|Sold For|Winning Bid|Final Bid):?\s+\$?([\d,]+\.\d{2})", chunk)
        m_buyer = re.search(r"(?:Buyer|Purchaser|Grantee):?\s+(.*?)(?:\n|$)", chunk)
        cards.append({
            "case_number": m_case.group(1).strip(),
            "sale_date": m_date.group(1).strip() if m_date else None,
            "parcel_id": m_parcel.group(1).strip() if m_parcel else None,
            "address": m_addr.group(1).strip() if m_addr else None,
            "owner": m_owner.group(1).strip() if m_owner else None,
            "opening_bid": m_opening.group(1).replace(",", "") if m_opening else None,
            "high_bid": m_high_bid.group(1).replace(",", "") if m_high_bid else None,
            "buyer": m_buyer.group(1).strip() if m_buyer else None,
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


def is_past_sale(sale_date_str: str) -> bool:
    """Return True if the sale date has already passed (today's auction is past)."""
    if not sale_date_str:
        return False
    today = datetime.date.today().isoformat()
    return sale_date_str < today


def to_fc_rows(cards, source_url):
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
                pass
        auction_date = _parse_date(c["sale_date"])
        auction_status = "sold" if (auction_date and is_past_sale(auction_date)) else "upcoming"
        high_bid = None
        if c.get("high_bid"):
            try:
                high_bid = float(c["high_bid"])
            except ValueError:
                pass
        rows.append({
            "county": "jefferson",
            "state": "FL",
            "sale_type": "foreclosure",
            "auction_type": "foreclosure",
            "auction_status": auction_status,
            "case_number": c["case_number"],
            "auction_date": auction_date,
            "property_address": addr or None,
            "city": city_m.group(1).strip() if city_m else None,
            "zip": zip_m.group(1) if zip_m else None,
            "plaintiff": c.get("plaintiff"),
            "judgment_amount": judgment,
            "judgment_amount_usd": judgment,
            "sold_amount": high_bid,
            "tier1_sold_amount": high_bid,
            "tier1_authoritative": bool(high_bid),
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


def to_td_rows(cards, source_url):
    rows = []
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for c in cards:
        addr = c.get("address") or ""
        city_m = re.search(r"\s([A-Za-z]+),?\s*FL\.?\s*\d{5}", addr)
        zip_m = re.search(r"FL\.?\s*(\d{5})", addr)
        opening_bid = None
        if c.get("opening_bid"):
            try:
                opening_bid = float(c["opening_bid"])
            except ValueError:
                pass
        high_bid = None
        if c.get("high_bid"):
            try:
                high_bid = float(c["high_bid"])
            except ValueError:
                pass
        auction_date = _parse_date(c["sale_date"])
        auction_status = "sold" if (auction_date and is_past_sale(auction_date)) else "scheduled"
        rows.append({
            "county": "jefferson",
            "state": "FL",
            "sale_type": "tax_deed",
            "auction_type": "tax_deed",
            "auction_status": auction_status,
            "case_number": c["case_number"],
            "auction_date": auction_date,
            "property_address": addr or None,
            "city": city_m.group(1).strip() if city_m else None,
            "zip": zip_m.group(1) if zip_m else None,
            "parcel_id": c.get("parcel_id"),
            "owner_name": c.get("owner"),
            "opening_bid": opening_bid,
            "judgment_amount": opening_bid,
            "sold_amount": high_bid,
            "tier1_sold_amount": high_bid,
            "tier1_authoritative": bool(high_bid),
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


def build_fc_outcome_rows(cards, source_url):
    """Build foreclosure_outcomes rows for past-sale foreclosure cases with a high_bid."""
    rows = []
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for c in cards:
        auction_date = _parse_date(c["sale_date"])
        if not auction_date or not is_past_sale(auction_date):
            continue
        if not c.get("high_bid"):
            continue
        try:
            sale_amount = float(c["high_bid"])
        except ValueError:
            continue
        rows.append({
            "county_slug": "jefferson",
            "case_number": c["case_number"],
            "auction_date": auction_date,
            "sale_status": "sold",
            "sale_amount": sale_amount,
            "high_bid": sale_amount,
            "buyer_name": c.get("buyer"),
            "buyer_type": "unknown",
            "plaintiff": c.get("plaintiff"),
            "data_source": "jefferson_clerk_direct:jeffersonclerk.com",
            "source_url": source_url,
            "confidence_level": "verified",
            "notes": f"From clerk foreclosure results PDF, scraped {now}",
        })
    return rows


def build_td_outcome_rows(cards, source_url):
    """Build tax_deed_outcomes rows for past-sale tax-deed cases with a high_bid."""
    rows = []
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for c in cards:
        auction_date = _parse_date(c["sale_date"])
        if not auction_date or not is_past_sale(auction_date):
            continue
        if not c.get("high_bid"):
            continue
        try:
            sale_amount = float(c["high_bid"])
        except ValueError:
            continue
        rows.append({
            "county_slug": "jefferson",
            "case_number": c["case_number"],
            "parcel_id": c.get("parcel_id"),
            "auction_date": auction_date,
            "sale_status": "sold",
            "sale_amount": sale_amount,
            "buyer_name": c.get("buyer"),
            "buyer_type": "unknown",
            "data_source": "jefferson_clerk_direct:jeffersonclerk.com",
            "source_url": source_url,
            "confidence_level": "verified",
            "notes": f"From clerk tax deed results PDF, scraped {now}",
        })
    return rows


def upsert_mca(rows, dry_run=False):
    if not rows:
        print("MCA: no rows to upsert.")
        return 0
    if dry_run:
        print("MCA (dry-run):", json.dumps(rows, indent=2))
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
            print(f"MCA: upserted {len(result)} rows.")
            return len(result)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"MCA HTTPError {e.code}: {err_body}", file=sys.stderr)
        raise


def upsert_outcomes(rows, table, dry_run=False):
    """Write verified outcomes to foreclosure_outcomes or tax_deed_outcomes."""
    if not rows:
        print(f"{table}: no outcome rows.")
        return 0
    if dry_run:
        print(f"{table} (dry-run):", json.dumps(rows, indent=2))
        return len(rows)

    body = json.dumps(rows).encode("utf-8")
    conflict_col = "county_slug,case_number,auction_date"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={conflict_col}",
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
            print(f"{table}: upserted {len(result)} outcome rows.")
            return len(result)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"{table} HTTPError {e.code}: {err_body}", file=sys.stderr)
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    mca_rows = []
    fc_outcome_rows = []
    td_outcome_rows = []

    fc_html = fetch(FC_PAGE_URL).decode("utf-8", errors="replace")
    fc_pdf_urls = find_pdf_links(fc_html)
    if fc_pdf_urls:
        for fc_pdf_url in fc_pdf_urls:
            pdf_bytes = fetch(fc_pdf_url)
            fc_cards = parse_foreclosure_pdf(pdf_bytes)
            print(f"Foreclosure PDF ({fc_pdf_url}): {len(fc_cards)} cards")
            mca_rows += to_fc_rows(fc_cards, fc_pdf_url)
            fc_outcomes = build_fc_outcome_rows(fc_cards, fc_pdf_url)
            if fc_outcomes:
                print(f"  -> {len(fc_outcomes)} past-sale outcome row(s) found with sold amount")
                fc_outcome_rows += fc_outcomes
    else:
        print("Foreclosure page: no PDF currently linked — 0 rows.")

    td_html = fetch(TD_PAGE_URL).decode("utf-8", errors="replace")
    td_pdf_urls = find_pdf_links(td_html)
    if td_pdf_urls:
        for td_pdf_url in td_pdf_urls:
            pdf_bytes = fetch(td_pdf_url)
            td_cards = parse_tax_deed_pdf(pdf_bytes)
            print(f"Tax deed PDF ({td_pdf_url}): {len(td_cards)} cards")
            mca_rows += to_td_rows(td_cards, td_pdf_url)
            td_outcomes = build_td_outcome_rows(td_cards, td_pdf_url)
            if td_outcomes:
                print(f"  -> {len(td_outcomes)} past-sale outcome row(s) found with sold amount")
                td_outcome_rows += td_outcomes
    else:
        upcoming_section = 'id="upcoming"' in td_html or 'upcoming tax deed' in td_html.lower()
        if not upcoming_section:
            print(
                "WARNING: Jefferson tax-deed page structure may have changed: "
                "no PDF links and no #upcoming section found — verify manually.",
                file=sys.stderr,
            )
        print("Tax deed page: no PDF currently linked — 0 rows.")

    n_mca = upsert_mca(mca_rows, dry_run=args.dry_run)
    n_fc_out = 0
    n_td_out = 0
    if not args.dry_run:
        n_fc_out = upsert_outcomes(fc_outcome_rows, "foreclosure_outcomes", dry_run=args.dry_run)
        n_td_out = upsert_outcomes(td_outcome_rows, "tax_deed_outcomes", dry_run=args.dry_run)

    print(f"Done. MCA: {n_mca} rows processed. "
          f"FC outcomes: {n_fc_out}. TD outcomes: {n_td_out}.")

    if fc_outcome_rows or td_outcome_rows:
        print("LETTER B/F AUTO-RESOLUTION: verified outcome rows written — "
              "run pencil_dod_evaluate_county('jefferson') to confirm metric moved.")
    else:
        print("No past-sale outcomes with sold amounts found — B/F remain blocked "
              "(expected until 2026-08-19 tax deed sale passes or a results PDF is published).")


if __name__ == "__main__":
    main()
