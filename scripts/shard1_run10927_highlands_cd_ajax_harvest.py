#!/usr/bin/env python3
"""GOLD STANDARD SHARD-1 (run 10927) — highlands C/D AJAX harvest.

Targets multi_county_auctions rows for highlands with
parity_status IN ('mca_only','bootstrap_placeholder') and attempts
to match them against the live RealTaxDeed/RealForeclose calendars.

This uses the proven AJAX harvest mechanism (FNC=LOAD, FNC=UPDATE)
already used in shard10_run3645_highlands_cd_harvest.py and
shard12_run3534_highlands_cd_harvest.py.

Usage:
  python3 scripts/shard1_run10927_highlands_cd_ajax_harvest.py

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
DISPATCH_ID = "b6f8ef4b-ed4b-4268-8d5f-f4a64383862e"

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

HIGHLANDS_RTD_URL = "https://highlands.realtaxdeed.com/index.cfm"
HIGHLANDS_RFC_URL = "https://highlands.realforeclose.com/index.cfm"
LABEL_PREFIX = f"tier1:shard1_run10927_{DISPATCH_ID[:8]}_highlands_cd"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table: str, params: str, limit: int = 2000) -> list:
    url = f"{BASE}/{table}?{params}&limit={limit}"
    req = urllib.request.Request(url, headers={**HEADERS, "Prefer": ""})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_patch(table: str, filters: str, data: dict) -> tuple:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={**HEADERS, "Prefer": "return=minimal"}, method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _parse_aitem_blocks(html: str) -> list[dict]:
    """Extract case items from RealAuction AJAX HTML response."""
    items = []
    blocks = re.split(r'<div[^>]+class=["\']?AITEM["\']?', html)[1:]
    for block in blocks:
        # Extract case number
        case_m = re.search(r'(?:Case\s*#|Case\s*Number)\s*:?\s*</[^>]+>\s*<[^>]+>([A-Z0-9\-]+)', block, re.I)
        if not case_m:
            case_m = re.search(r'Case\s*(?:Number|#)\s*:?\s*([A-Z0-9\-]+)', block, re.I)
        parcel_m = re.search(r'Parcel\s*(?:ID)?:?\s*</td>\s*<td[^>]*>([^<]+)', block, re.I)
        case_number = case_m.group(1).strip() if case_m else None
        parcel_id = parcel_m.group(1).strip() if parcel_m else None
        if case_number and len(case_number) > 3:
            items.append({"case_number": case_number, "parcel_id": parcel_id})
    return items


def _try_ajax_fetch(base_url: str, auction_date: str, page: int = 0) -> str | None:
    """Try to fetch a page of AJAX results for a given date."""
    params = {
        "zaction": "AUCTION",
        "Zmethod": "UPDATE",
        "FNC": "LOAD",
        "DTD": auction_date,
        "myDate": auction_date,
        "PageDir": str(page),
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"    AJAX fetch error ({base_url}, {auction_date}, page {page}): {e}")
        return None


def harvest_auction_date(base_url: str, auction_date: str, sale_type: str) -> list[dict]:
    """Harvest all pages of a single auction date."""
    all_items = []
    for page in range(5):  # max 5 pages per date
        html = _try_ajax_fetch(base_url, auction_date, page)
        if not html:
            break
        items = _parse_aitem_blocks(html)
        log(f"    {sale_type} {auction_date} page {page}: {len(items)} items")
        if not items:
            break
        all_items.extend(items)
        # Check if there's a next page indicator
        if "nextpage" not in html.lower() and len(items) < 20:
            break
        time.sleep(0.5)
    return all_items


def main():
    log("=== HIGHLANDS C/D AJAX HARVEST (shard1_run10927) ===")

    # Fetch all unmatched rows
    unmatched = sb_get(
        "multi_county_auctions",
        "county=ilike.highlands"
        "&parity_status=in.(mca_only,bootstrap_placeholder)"
        "&select=id,case_number,parcel_id,auction_date,sale_type",
        limit=500,
    )
    log(f"Unmatched highlands rows: {len(unmatched)}")

    if not unmatched:
        log("No unmatched rows — C/D already resolved.")
        return

    # Filter out synthetic placeholders
    real_rows = [r for r in unmatched
                 if r.get("case_number") and not r["case_number"].startswith("HIGHLANDS-")]
    log(f"Real (non-synthetic) unmatched rows: {len(real_rows)}")

    # Build lookup by case_number
    cn_to_id: dict[str, int] = {}
    for r in real_rows:
        cn = (r["case_number"] or "").strip().upper()
        if cn:
            cn_to_id[cn] = r["id"]

    # Group by (sale_type, auction_date)
    by_date: dict[tuple, list] = {}
    for r in real_rows:
        key = (r.get("sale_type", ""), r.get("auction_date", ""))
        if key[1]:  # skip rows without an auction_date
            by_date.setdefault(key, []).append(r)

    log(f"Unique (sale_type, auction_date) combinations to harvest: {len(by_date)}")

    total_matched = 0
    remaining_cn = set(cn_to_id.keys())

    for (sale_type, auction_date), rows in sorted(by_date.items()):
        if not remaining_cn:
            break  # all matched
        base_url = HIGHLANDS_RTD_URL if sale_type == "tax_deed" else HIGHLANDS_RFC_URL
        items = harvest_auction_date(base_url, auction_date, sale_type)
        time.sleep(1.0)

        for item in items:
            cn_raw = (item.get("case_number") or "").strip()
            # Try exact match and normalized match
            for cn_variant in [cn_raw.upper(), re.sub(r"[^A-Z0-9]", "", cn_raw.upper())]:
                if cn_variant in remaining_cn:
                    row_id = cn_to_id[cn_variant]
                    status, body = sb_patch(
                        "multi_county_auctions",
                        f"id=eq.{row_id}",
                        {
                            "parity_status": "matched_clean",
                            "parity_source": f"{LABEL_PREFIX}:{sale_type}:{auction_date}",
                        }
                    )
                    if status in (200, 204):
                        total_matched += 1
                        remaining_cn.discard(cn_variant)
                        log(f"  MATCH {cn_variant} -> matched_clean (row {row_id})")
                    else:
                        log(f"  PATCH FAIL {cn_variant}: status={status} {body[:200]}")
                    break

    log(f"\nHIGHLANDS C/D RESULT: matched={total_matched} of {len(real_rows)} real unmatched rows")
    log(f"Still unmatched after harvest: {len(remaining_cn)}")
    if remaining_cn:
        log("Unmatched case numbers (may have been redeemed/cancelled — BLANK>WRONG, not forced):")
        for cn in sorted(remaining_cn)[:20]:
            log(f"  {cn}")


if __name__ == "__main__":
    main()
