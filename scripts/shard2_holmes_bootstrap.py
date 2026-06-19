#!/usr/bin/env python3
"""
Holmes County FL Auction Bootstrap — shard2
============================================

Platform: holmesclerk.com (custom WordPress clerk site)
  Foreclosures: https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/
  Tax Deeds:    https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/

NOTE: holmes.realforeclose.com and holmes.realtaxdeed.com both 302-redirect to
the generic realauction.com homepage — Holmes County does NOT use the RealAuction
platform. Auction data lives on the clerk's own WordPress site.

Usage:
    python3 scripts/shard2_holmes_bootstrap.py
    python3 scripts/shard2_holmes_bootstrap.py --county holmes --limit 50

Author: BidDeed.AI / Everest Capital USA
"""

import os
import re
import sys
import logging
import argparse
from datetime import datetime, date, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup
from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("holmes-bootstrap")

# ── Config ───────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or ""
)

FORECLOSURE_URL = "https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/"
TAX_DEED_URL    = "https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (BidDeed-Holmes-Bootstrap/1.0; "
        "contact: ariel@everestcapitalusa.com)"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 30


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(date_str: str) -> Optional[str]:
    """Parse 'JUNE 11, 2026', 'June 11, 2026', or '7/7/2026' → ISO string, or None."""
    date_str = date_str.strip().rstrip(".")
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(date_str.title(), fmt).date().isoformat()
        except ValueError:
            pass
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            pass
    return None


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_foreclosures(html: str) -> list[dict]:
    """
    Parse holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/

    The page lists upcoming sales as plain text after the schedule heading.
    Each entry contains SALE DATE, FINAL JUDGMENT AMOUNT, PARCEL ID, and
    optionally PROPERTY ADDRESS. Plaintiff is the text before 'V.'.

    Example block:
        FIRST FEDERAL BANK V. AMBER LYNN GILLIS ..., ET AL.,
        SALE DATE: JUNE 11, 2026
        FINAL JUDGMENT AMOUNT: $332,326.88
        PARCEL ID: 1626.00-000-000-011.000
        PROPERTY ADDRESS: 1826 BECKWOOD LANE, WESTVILLE, FL 32464
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("nav, footer, header, script, style"):
        tag.decompose()

    body_text = soup.get_text(separator=" ", strip=True)

    marker = "The following properties are scheduled to be sold"
    idx = body_text.find(marker)
    if idx < 0:
        log.warning("parse_foreclosures: schedule marker not found")
        return []

    section = body_text[idx:]

    entries = []

    # Each foreclosure entry ends when the next one begins (next plaintiff block)
    # Split on FINAL JUDGMENT AMOUNT as the reliable per-entry anchor
    # Pattern captures: sale date, judgment $, parcel, address (optional)
    pattern = re.compile(
        r"SALE\s+DATE:\s*([A-Z]+ \d{1,2},?\s+\d{4})"
        r".*?FINAL\s+JUDGMENT\s+AMOUNT:\s*\$([\d,]+(?:\.\d{2})?)"
        r".*?PARCEL\s+ID:\s*([\w.\-]+)"
        r"(?:.*?PROPERTY\s+ADDRESS:\s*([^\n$]{5,150?}))?",
        re.DOTALL | re.IGNORECASE,
    )

    for m in pattern.finditer(section):
        sale_date_raw  = m.group(1).strip()
        judgment_raw   = m.group(2).replace(",", "")
        parcel_id      = m.group(3).strip()
        address_raw    = m.group(4).strip() if m.group(4) else None

        sale_date = _parse_date(sale_date_raw)
        if not sale_date:
            log.warning(f"  Could not parse foreclosure sale date: {sale_date_raw!r}")
            continue

        # Find plaintiff — text before 'V.' preceding this match
        pre_start = max(0, m.start() - 600)
        pre_text  = section[pre_start:m.start()]
        v_matches = list(re.finditer(r"\bV\.\s", pre_text, re.IGNORECASE))
        plaintiff = None
        if v_matches:
            p_end = v_matches[-1].start()
            raw_p = pre_text[:p_end].strip()
            # Take last 200 chars
            candidate = raw_p[-200:].strip()
            # Drop leading non-alpha
            candidate = re.sub(r"^[^A-Z]+", "", candidate).strip()
            plaintiff = candidate[:300] if candidate else None

        try:
            judgment_amount = float(judgment_raw)
        except ValueError:
            judgment_amount = None

        # Clean address — strip trailing navigator noise
        if address_raw:
            address_raw = re.sub(r"\s+(Foreclosures|Tax Deeds|CONTACT).*", "",
                                 address_raw, flags=re.IGNORECASE).strip()

        entries.append({
            "county":           "holmes",
            "state":            "FL",
            "sale_type":        "foreclosure",
            "auction_type":     "foreclosure",
            "auction_date":     sale_date,
            "parcel_id":        parcel_id,
            "property_address": address_raw,
            "plaintiff":        plaintiff,
            "judgment_amount":  judgment_amount,
            "auction_status":   (
                "upcoming" if sale_date >= date.today().isoformat() else "completed"
            ),
            "source_platform":  "holmes_clerk",
            "clerk_url":        FORECLOSURE_URL,
            "provenance":       f"holmes_bootstrap_{date.today().isoformat()}",
        })

    return entries


def parse_tax_deeds(html: str) -> list[dict]:
    """
    Parse holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/

    Each entry looks like:
        TD#2023-225 TRSTE, LLC PARCEL ID: 0811.04-001-000-041.000
        OPENING BID:$TBD SALE DATE:7/7/2026
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("nav, footer, header, script, style"):
        tag.decompose()

    body_text = soup.get_text(separator=" ", strip=True)

    entries = []

    # Each tax-deed block: TD#YYYY-NNN DEFENDANT PARCEL ID: ... OPENING BID:$ ... SALE DATE:...
    pattern = re.compile(
        r"(TD#\d{4}-\d+)"                       # group 1: TD number
        r"\s+([A-Z][A-Z ,.'&\-]+?)"             # group 2: defendant name
        r"\s*PARCEL\s+ID:\s*([\w.\-]+)"          # group 3: parcel
        r".*?OPENING\s+BID:\s*\$([\w,.*]+)"     # group 4: bid amount (TBD or number)
        r".*?SALE\s+DATE:\s*([\d/]+)",           # group 5: sale date
        re.DOTALL | re.IGNORECASE,
    )

    for m in pattern.finditer(body_text):
        td_number     = m.group(1).strip()
        defendant     = m.group(2).strip().rstrip(" ,")
        parcel_id     = m.group(3).strip()
        opening_raw   = m.group(4).strip().replace(",", "")
        sale_date_raw = m.group(5).strip()

        # Skip blank template row
        if not td_number or not parcel_id or td_number == "TD#":
            continue

        sale_date = _parse_date(sale_date_raw)
        if not sale_date:
            log.warning(f"  Could not parse tax deed sale date: {sale_date_raw!r}")
            continue

        bid_amount: Optional[float] = None
        if opening_raw.replace(".", "").replace("*", "").isdigit():
            try:
                bid_amount = float(opening_raw.replace("*", ""))
            except ValueError:
                pass

        entries.append({
            "county":           "holmes",
            "state":            "FL",
            "sale_type":        "tax_deed",
            "auction_type":     "tax_deed",
            "case_number":      td_number,
            "auction_date":     sale_date,
            "parcel_id":        parcel_id,
            # defendant stored in plaintiff field (no separate defendant col in schema)
            "plaintiff":        defendant,
            "opening_bid":      bid_amount,
            "auction_status":   (
                "upcoming" if sale_date >= date.today().isoformat() else "completed"
            ),
            "source_platform":  "holmes_clerk",
            "clerk_url":        TAX_DEED_URL,
            "provenance":       f"holmes_bootstrap_{date.today().isoformat()}",
        })

    return entries


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch(url: str) -> str:
    """GET url → HTML text, raise on non-200."""
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} fetching {url}")
    return r.text


# ── DB upsert ─────────────────────────────────────────────────────────────────

def upsert_auctions(sb, rows: list[dict], limit: int) -> int:
    """
    Insert rows into multi_county_auctions, skipping dupes.
    Dedup key: case_number (tax deeds) or (county + parcel_id + auction_date).
    Updates last_seen_at on existing rows.
    Returns number newly inserted.
    """
    if not rows:
        return 0

    rows = rows[:limit]
    inserted = 0
    now_ts = datetime.now(timezone.utc).isoformat()

    for row in rows:
        case_num = row.get("case_number")
        parcel   = row.get("parcel_id", "")
        adate    = row.get("auction_date", "")

        # Check for existing
        if case_num:
            check = (
                sb.table("multi_county_auctions")
                .select("id")
                .eq("county", "holmes")
                .eq("case_number", case_num)
                .limit(1)
                .execute()
            )
        else:
            check = (
                sb.table("multi_county_auctions")
                .select("id")
                .eq("county", "holmes")
                .eq("parcel_id", parcel)
                .eq("auction_date", adate)
                .limit(1)
                .execute()
            )

        if check.data:
            rec_id = check.data[0]["id"]
            sb.table("multi_county_auctions").update(
                {"last_seen_at": now_ts}
            ).eq("id", rec_id).execute()
            log.info(f"  EXISTS (last_seen_at updated): {case_num or parcel} @ {adate}")
            continue

        payload = {k: v for k, v in row.items() if v is not None}
        payload["last_seen_at"] = now_ts

        try:
            result = sb.table("multi_county_auctions").insert(payload).execute()
            if result.data:
                inserted += 1
                log.info(
                    f"  INSERTED: {case_num or parcel} @ {adate} "
                    f"({row.get('sale_type', '?')})"
                )
            else:
                log.warning(f"  INSERT returned no data for {case_num or parcel}")
        except Exception as e:
            log.error(f"  INSERT failed for {case_num or parcel}: {e}")

    return inserted


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Holmes County FL auction bootstrap")
    parser.add_argument("--county", default="holmes")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if args.county.lower() != "holmes":
        log.error(f"This script is Holmes-only. Got --county={args.county}")
        sys.exit(1)

    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE[_KEY] env vars required")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # ── Scrape ────────────────────────────────────────────────────────────────

    log.info(f"Fetching foreclosure sales: {FORECLOSURE_URL}")
    try:
        fc_html = fetch(FORECLOSURE_URL)
        fc_rows = parse_foreclosures(fc_html)
        log.info(f"Parsed {len(fc_rows)} foreclosure auction(s)")
        for r in fc_rows:
            log.info(f"  FC: parcel={r['parcel_id']} date={r['auction_date']} "
                     f"judgment=${r.get('final_judgment')}")
    except Exception as e:
        log.error(f"Foreclosure scrape failed: {e}")
        fc_rows = []

    log.info(f"Fetching tax deed sales: {TAX_DEED_URL}")
    try:
        td_html = fetch(TAX_DEED_URL)
        td_rows = parse_tax_deeds(td_html)
        log.info(f"Parsed {len(td_rows)} tax deed auction(s)")
        for r in td_rows:
            log.info(f"  TD: {r['case_number']} parcel={r['parcel_id']} "
                     f"date={r['auction_date']}")
    except Exception as e:
        log.error(f"Tax deed scrape failed: {e}")
        td_rows = []

    all_rows   = fc_rows + td_rows
    parsed_cnt = len(all_rows)

    # ── Upsert ────────────────────────────────────────────────────────────────

    if parsed_cnt > 0:
        log.info(f"Upserting {parsed_cnt} records to multi_county_auctions…")
        inserted = upsert_auctions(sb, all_rows, limit=args.limit)
    else:
        inserted = 0

    # ── Honesty gate ──────────────────────────────────────────────────────────
    # If we parsed records but inserted zero, verify they all pre-exist.
    if parsed_cnt > 0 and inserted == 0:
        existing = (
            sb.table("multi_county_auctions")
            .select("id", count="exact")
            .eq("county", "holmes")
            .execute()
        )
        existing_count = existing.count or 0
        if existing_count == 0:
            raise RuntimeError(
                f"FAIL-LOUD: parsed={parsed_cnt} records but inserted=0 "
                "and county has 0 existing rows — data loss. Aborting."
            )
        log.info(
            f"All {parsed_cnt} parsed rows already existed. "
            f"Total holmes rows in DB: {existing_count}"
        )

    print(f"INSERTED: {inserted} rows for holmes")

    # ── Final count ───────────────────────────────────────────────────────────
    total_r = (
        sb.table("multi_county_auctions")
        .select("id", count="exact")
        .eq("county", "holmes")
        .execute()
    )
    total = total_r.count or 0
    log.info(f"Holmes County total rows in multi_county_auctions: {total}")

    if parsed_cnt == 0:
        log.warning(
            "HONESTY: Clerk pages returned 0 parseable auctions. "
            "Possible causes: page structure changed, or county has no "
            "active auctions posted at this time."
        )


if __name__ == "__main__":
    main()
