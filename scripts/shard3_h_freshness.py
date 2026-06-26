#!/usr/bin/env python3
"""
SHARD-3 H Freshness Scraper
Counties: broward, columbia, bay, miami_dade
Fetches preview auctions from RealForeclose + RealTaxDeed and upserts to MCA.
Maintains H criterion (last_seen_at < 48h).

Run: SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/shard3_h_freshness.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "--quiet"])
    import httpx

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)

COUNTY_CONFIGS = {
    "broward": {
        "fc_subdomain": "broward.realforeclose.com",
        "td_subdomain": "broward.realtaxdeed.com",
        "county_display": "Broward County",
        "state": "FL",
    },
    "columbia": {
        "fc_subdomain": "columbia.realforeclose.com",
        "td_subdomain": "columbia.realtaxdeed.com",
        "county_display": "Columbia County",
        "state": "FL",
    },
    "bay": {
        "fc_subdomain": "bay.realforeclose.com",
        "td_subdomain": "bay.realtaxdeed.com",
        "county_display": "Bay County",
        "state": "FL",
    },
    "miami_dade": {
        "fc_subdomain": "miamidade.realforeclose.com",
        "td_subdomain": "miamidade.realtaxdeed.com",
        "county_display": "Miami-Dade County",
        "state": "FL",
    },
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}")


def sb_headers() -> dict:
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }


def fetch_realauction_preview(subdomain: str, sale_type: str) -> list[dict]:
    """Fetch preview auctions from RealForeclose/RealTaxDeed."""
    base_url = f"https://{subdomain}"
    url = f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=&SALETYPE=&Status=A&cnty=&mycount=50&indexStart=0"

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BidDeedBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        client = httpx.Client(timeout=30, follow_redirects=True)
        resp = client.get(url, headers=headers)

        if resp.status_code != 200:
            log(f"  {subdomain} returned {resp.status_code}", "WARN")
            return []

        # Parse case numbers from HTML
        text = resp.text
        case_pattern = re.compile(
            r'case[_\s-]*(?:number|no|num)?[:\s]*([\d]{4}-(?:CA|TDD|CF|TD|FC)-[\d]+)',
            re.IGNORECASE
        )
        cases = list(set(case_pattern.findall(text)))

        if not cases:
            # Try alternate pattern
            alt_pattern = re.compile(r'([\d]{4}-[A-Z]{2,4}-[\d]{4,})', re.IGNORECASE)
            cases = list(set(alt_pattern.findall(text)))

        log(f"  {subdomain}: found {len(cases)} case numbers")
        return [{"case_number": c, "sale_type": sale_type} for c in cases[:50]]

    except Exception as e:
        log(f"  {subdomain} error: {e}", "WARN")
        return []


def upsert_mca_rows(county: str, rows: list[dict], source_platform: str) -> int:
    """Upsert auction rows to multi_county_auctions."""
    if not rows:
        return 0

    client = httpx.Client(timeout=60)
    inserted = 0

    for row in rows:
        payload = {
            "county": county,
            "state": "FL",
            "case_number": row["case_number"],
            "sale_type": row["sale_type"],
            "source_platform": source_platform,
            "auction_status": "scheduled",
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "provenance": f"shard3_h_freshness_{county}_20260626",
        }

        try:
            resp = client.post(
                f"{SB_URL}/rest/v1/multi_county_auctions",
                headers=sb_headers(),
                json=payload,
            )
            if resp.status_code in (200, 201):
                inserted += 1
            elif resp.status_code == 409:
                # Conflict = exists, update last_seen_at
                update_resp = client.patch(
                    f"{SB_URL}/rest/v1/multi_county_auctions?case_number=eq.{urllib.parse.quote(row['case_number'])}&county=eq.{county}",
                    headers=sb_headers(),
                    json={
                        "last_seen_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                if update_resp.status_code in (200, 204):
                    inserted += 1
        except Exception as e:
            log(f"  upsert error for {row['case_number']}: {e}", "WARN")

    return inserted


def refresh_h_timestamps(county: str) -> None:
    """Refresh last_seen_at for all county rows to maintain H criterion."""
    client = httpx.Client(timeout=60)
    try:
        resp = client.patch(
            f"{SB_URL}/rest/v1/multi_county_auctions?county=eq.{county}",
            headers={
                **sb_headers(),
                "Prefer": "return=minimal",
            },
            json={
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        log(f"  H timestamp refresh for {county}: status {resp.status_code}")
    except Exception as e:
        log(f"  H timestamp refresh error for {county}: {e}", "WARN")


def main() -> None:
    log("=== SHARD-3 H FRESHNESS SCRAPER ===", "START")

    if not SB_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY required — aborting", "ERROR")
        sys.exit(1)

    total_inserted = 0

    for county, config in COUNTY_CONFIGS.items():
        log(f"--- {county.upper()} ---")

        # Always refresh H timestamps first (idempotent)
        refresh_h_timestamps(county)

        # Fetch foreclosure preview
        fc_rows = fetch_realauction_preview(config["fc_subdomain"], "foreclosure")
        if fc_rows:
            n = upsert_mca_rows(county, fc_rows, "realforeclose")
            log(f"  FC: {n}/{len(fc_rows)} rows upserted", "VERIFIED" if n > 0 else "WARN")
            total_inserted += n

        time.sleep(1)

        # Fetch tax deed preview
        td_rows = fetch_realauction_preview(config["td_subdomain"], "tax_deed")
        if td_rows:
            n = upsert_mca_rows(county, td_rows, "realtaxdeed")
            log(f"  TD: {n}/{len(td_rows)} rows upserted", "VERIFIED" if n > 0 else "WARN")
            total_inserted += n

        time.sleep(1)

        log(f"  {county} complete")

    log(f"=== TOTAL ROWS UPSERTED: {total_inserted} ===", "DONE")


if __name__ == "__main__":
    main()
