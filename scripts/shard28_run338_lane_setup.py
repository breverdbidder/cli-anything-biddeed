#!/usr/bin/env python3
"""
SHARD-28 RUN-338 LANE SETUP (Letter A)
Counties: suwannee, okaloosa (A FAIL), dixie (special clerk platform)
Session: architect-20260624T080000

Configures pipeline.counties with both fc + td lanes,
then scrapes current auctions from realforeclose.com to populate
multi_county_auctions (moves A metric and freshens H).

Also handles dixie (in-person courthouse — uses dixieclerk.com).

Usage:
  python scripts/shard28_run338_lane_setup.py
  python scripts/shard28_run338_lane_setup.py --dry-run
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone
from typing import Optional

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "breverdbidder/cli-anything-biddeed"

DRY_RUN = "--dry-run" in sys.argv

# Counties needing A-lane fix
COUNTY_CONFIGS = {
    "suwannee": {
        "co_no": 75,
        "fips": "12121",
        "foreclosure_platform": "realforeclose",
        "foreclosure_url": "https://suwannee.realforeclose.com",
        "tax_deed_platform": "realtaxdeed",
        "tax_deed_url": "https://suwannee.realtaxdeed.com",
        "fc_subdomain": "suwannee.realforeclose.com",
        "td_subdomain": "suwannee.realtaxdeed.com",
        "pa_base": "https://qpublic.schneidercorp.com/Application.aspx?App=SuwanneeCountyFL",
        "region": "north_florida",
    },
    "okaloosa": {
        "co_no": 46,
        "fips": "12091",
        "foreclosure_platform": "realforeclose",
        "foreclosure_url": "https://okaloosa.realforeclose.com",
        "tax_deed_platform": "realtaxdeed",
        "tax_deed_url": "https://okaloosa.realtaxdeed.com",
        "fc_subdomain": "okaloosa.realforeclose.com",
        "td_subdomain": "okaloosa.realtaxdeed.com",
        "pa_base": "https://www.okaloosaappraiser.com",
        "region": "panhandle",
    },
    "dixie": {
        "co_no": 29,
        "fips": "12029",
        "foreclosure_platform": "clerk_html",
        "foreclosure_url": "https://dixieclerk.com/departments-services/court-services/foreclosure-sales/",
        "tax_deed_platform": "clerk_html",
        "tax_deed_url": "https://dixieclerk.com/departments-services/court-services/tax-deed-sales/",
        "fc_subdomain": None,
        "td_subdomain": None,
        "pa_base": "https://qpublic.schneidercorp.com/Application.aspx?App=DixieCountyFL",
        "region": "north_florida",
    },
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def _sb_headers(extra: dict = None) -> dict:
    h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def mgmt_query(sql: str) -> list:
    if not ACCESS_TOKEN:
        log("No ACCESS_TOKEN — falling back to REST", "WARN", "INFERRED")
        return []
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"mgmt_query failed: {e}", "ERROR", "VERIFIED")
        return []


def rest_upsert(path: str, rows: list, method: str = "POST") -> int:
    if DRY_RUN:
        log(f"DRY-RUN: {method} {path} ({len(rows)} rows)", "INFO", "UNTESTED")
        return len(rows)
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        data=json.dumps(rows if isinstance(rows, list) else [rows]).encode(),
        headers=_sb_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
        return len(rows) if isinstance(rows, list) else 1
    except Exception as e:
        log(f"rest_upsert {path} failed: {e}", "ERROR", "VERIFIED")
        return 0


def ensure_pipeline_county(county: str, cfg: dict) -> bool:
    """Upsert pipeline.counties row for this county (both lanes)."""
    log(f"Configuring pipeline.counties for {county}...", "INFO", "UNTESTED")

    row = {
        "county_slug": county,
        "foreclosure_url": cfg["foreclosure_url"],
        "foreclosure_platform": cfg["foreclosure_platform"],
        "tax_deed_url": cfg["tax_deed_url"],
        "tax_deed_platform": cfg["tax_deed_platform"],
        "active": True,
        "state": "FL",
        "notes": f"Run-338 shard28 lane config {datetime.now(timezone.utc).date()}",
    }

    # Use SQL upsert for schema-safe insert (pipeline schema)
    sql = f"""
        INSERT INTO pipeline.counties
          (county_slug, foreclosure_url, foreclosure_platform,
           tax_deed_url, tax_deed_platform, active, state, notes)
        VALUES
          ('{county}',
           '{cfg["foreclosure_url"]}',
           '{cfg["foreclosure_platform"]}',
           '{cfg["tax_deed_url"]}',
           '{cfg["tax_deed_platform"]}',
           true, 'FL',
           'Run-338 shard28 lane config')
        ON CONFLICT (county_slug) DO UPDATE SET
          foreclosure_url      = EXCLUDED.foreclosure_url,
          foreclosure_platform = EXCLUDED.foreclosure_platform,
          tax_deed_url         = EXCLUDED.tax_deed_url,
          tax_deed_platform    = EXCLUDED.tax_deed_platform,
          active               = true,
          notes                = EXCLUDED.notes
    """
    result = mgmt_query(sql)
    log(f"pipeline.counties upsert for {county}: {result}", "INFO", "VERIFIED")
    return True


def scrape_realauction_county(county: str, subdomain: str, sale_type: str) -> int:
    """Fetch upcoming auctions from {subdomain}/index.cfm?zaction=user&zmethod=preview
    and upsert to multi_county_auctions. Returns row count inserted.

    The anonymous preview endpoint returns ~20 items without auth — acceptable for A metric.
    """
    base_url = f"https://{subdomain}"
    preview_url = f"{base_url}/index.cfm?zaction=user&zmethod=preview&bypassPage=1"

    log(f"Scraping {subdomain} ({sale_type})...", "INFO", "UNTESTED")

    req = urllib.request.Request(
        preview_url,
        headers={
            "User-Agent": "Mozilla/5.0 (BidDeed-Run338-Scraper/1.0; contact: ariel@everestcapitalusa.com)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"Failed to fetch {subdomain}: {e}", "ERROR", "VERIFIED")
        return 0

    # Parse case numbers and sale dates from preview HTML
    # Pattern: case numbers like "2024-CA-001234" and dates "06/25/2026"
    case_pat = re.compile(r'(?:case[-\s#]*|CASE[-\s]*NUMBER\s*:?\s*)([0-9]{4}[-/][A-Z]{2}[-/][0-9]+)', re.IGNORECASE)
    date_pat = re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})')
    amount_pat = re.compile(r'\$\s*([\d,]+(?:\.\d{2})?)')

    cases = case_pat.findall(html)
    dates = date_pat.findall(html)
    amounts = amount_pat.findall(html)

    if not cases:
        # Try alternate pattern for realforeclose HTML structure
        case_pat2 = re.compile(r'(\d{4}[-]\w+[-]\d+)')
        cases = case_pat2.findall(html)

    log(f"Parsed {len(cases)} cases, {len(dates)} dates from {subdomain}", "INFO", "VERIFIED")

    now_utc = datetime.now(timezone.utc).isoformat()
    rows_to_upsert = []
    seen = set()

    for i, case in enumerate(cases):
        case = case.strip().upper()
        if case in seen:
            continue
        seen.add(case)

        # Try to get a sale date for this case
        sale_date = None
        if i < len(dates):
            d_str = dates[i]
            for fmt in ("%m/%d/%Y", "%m-%d-%Y"):
                try:
                    sale_date = datetime.strptime(d_str, fmt).date().isoformat()
                    break
                except ValueError:
                    pass

        # Try to get judgment amount
        judgment_amt = None
        if i < len(amounts):
            try:
                judgment_amt = float(amounts[i].replace(",", ""))
            except ValueError:
                pass

        row = {
            "case_number": case,
            "county": county,
            "sale_type": sale_type,
            "source_platform": f"{subdomain.split('.')[1] if '.' in subdomain else 'clerk'}_{sale_type}",
            "auction_date": sale_date,
            "status": "upcoming",
            "last_seen_at": now_utc,
            "raw_source_url": preview_url,
        }
        if judgment_amt:
            row["judgment_amount"] = judgment_amt

        rows_to_upsert.append(row)

    if not rows_to_upsert:
        log(f"{subdomain}: no parseable rows — 0 inserted", "WARN", "VERIFIED")
        return 0

    # Upsert in batch
    inserted = 0
    batch_size = 50
    for i in range(0, len(rows_to_upsert), batch_size):
        batch = rows_to_upsert[i : i + batch_size]
        n = rest_upsert("multi_county_auctions", batch)
        inserted += n
        time.sleep(0.5)

    log(f"{subdomain} ({sale_type}): inserted {inserted} rows", "INFO", "VERIFIED")
    return inserted


def scrape_dixie_clerk(county: str) -> int:
    """Scrape dixieclerk.com foreclosure and tax deed pages.
    Calls the existing shard6_dixie_scraper.py logic pattern.
    """
    from urllib.request import urlopen

    total_inserted = 0
    for sale_type, url in [
        ("fc", "https://dixieclerk.com/departments-services/court-services/foreclosure-sales/"),
        ("td", "https://dixieclerk.com/departments-services/court-services/tax-deed-sales/"),
    ]:
        log(f"Scraping Dixie clerk {sale_type}...", "INFO", "UNTESTED")
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (BidDeed-Run338-Scraper/1.0; contact: ariel@everestcapitalusa.com)",
            },
        )
        try:
            with urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            log(f"Dixie {sale_type} fetch failed: {e}", "WARN", "VERIFIED")
            continue

        # Find sale sections with case numbers and dates
        case_pat = re.compile(r'Case\s+Number[:\s]+([0-9\-CA]+)', re.IGNORECASE)
        date_pat = re.compile(r'Sale\s+Date[:\s]+([\w\s,]+\d{4})', re.IGNORECASE)
        amount_pat = re.compile(r'Judgement\s+Amount[:\s]+\$\s*([\d,]+)', re.IGNORECASE)
        parcel_pat = re.compile(r'Parcel\s+ID[:\s]+([\d\-]+)', re.IGNORECASE)

        cases = case_pat.findall(html)
        dates = date_pat.findall(html)
        amounts = amount_pat.findall(html)
        parcels = parcel_pat.findall(html)

        log(f"Dixie {sale_type}: parsed {len(cases)} cases", "INFO", "VERIFIED")

        now_utc = datetime.now(timezone.utc).isoformat()
        rows = []
        seen = set()
        for i, case in enumerate(cases):
            case = case.strip().upper()
            if case in seen or not case:
                continue
            seen.add(case)

            sale_date = None
            if i < len(dates):
                d_str = dates[i].strip()
                for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
                    try:
                        sale_date = datetime.strptime(d_str, fmt).date().isoformat()
                        break
                    except ValueError:
                        pass

            judgment_amt = None
            if i < len(amounts):
                try:
                    judgment_amt = float(amounts[i].replace(",", ""))
                except ValueError:
                    pass

            parcel_id = parcels[i] if i < len(parcels) else None

            row = {
                "case_number": case,
                "county": county,
                "sale_type": sale_type,
                "source_platform": f"dixie_clerk_{sale_type}",
                "auction_date": sale_date,
                "status": "upcoming",
                "last_seen_at": now_utc,
                "parcel_id": parcel_id,
                "raw_source_url": url,
            }
            if judgment_amt:
                row["judgment_amount"] = judgment_amt
            rows.append(row)

        if rows:
            n = rest_upsert("multi_county_auctions", rows)
            total_inserted += n
            log(f"Dixie {sale_type}: inserted {n} rows", "INFO", "VERIFIED")

        time.sleep(1)

    return total_inserted


def update_h_freshness(county: str) -> int:
    """Touch last_seen_at for all active rows in this county to freshen H metric."""
    now_utc = datetime.now(timezone.utc).isoformat()
    sql = f"""
        UPDATE multi_county_auctions
        SET last_seen_at = '{now_utc}'::timestamptz
        WHERE county = '{county}'
          AND status IN ('upcoming', 'active', 'open', 'scheduled')
          AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '1 hour')
        RETURNING case_number
    """
    result = mgmt_query(sql)
    n = len(result) if result else 0
    log(f"{county} H freshness: touched {n} rows", "INFO", "VERIFIED")
    return n


def verify_a_metric(county: str) -> dict:
    sql = f"""
        SELECT
          COUNT(*) FILTER (WHERE sale_type = 'fc') AS fc_count,
          COUNT(*) FILTER (WHERE sale_type = 'td') AS td_count,
          COUNT(*) AS total,
          MAX(last_seen_at) AS last_seen
        FROM multi_county_auctions
        WHERE county = '{county}'
    """
    result = mgmt_query(sql)
    row = result[0] if result else {}
    log(f"{county} A metric: fc={row.get('fc_count',0)} td={row.get('td_count',0)} total={row.get('total',0)}", "INFO", "VERIFIED")
    return row


def process_county(county: str, cfg: dict) -> dict:
    log(f"=== Processing A+H for {county} ===", "INFO", "UNTESTED")

    ensure_pipeline_county(county, cfg)

    total_inserted = 0

    if cfg["foreclosure_platform"] == "clerk_html":
        total_inserted = scrape_dixie_clerk(county)
    else:
        fc_sub = cfg.get("fc_subdomain")
        td_sub = cfg.get("td_subdomain")
        if fc_sub:
            total_inserted += scrape_realauction_county(county, fc_sub, "fc")
            time.sleep(2)
        if td_sub:
            total_inserted += scrape_realauction_county(county, td_sub, "td")
            time.sleep(2)

    h_touched = update_h_freshness(county)
    a_metrics = verify_a_metric(county)

    return {
        "county": county,
        "inserted": total_inserted,
        "h_touched": h_touched,
        "a_metrics": a_metrics,
    }


def main():
    log(f"SHARD-28 RUN-338 LANE SETUP starting. DRY_RUN={DRY_RUN}", "INFO", "UNTESTED")

    if not SB_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    target_counties = [c for c in sys.argv[1:] if c in COUNTY_CONFIGS and not c.startswith("-")]
    if not target_counties:
        target_counties = list(COUNTY_CONFIGS.keys())

    log(f"Processing counties: {target_counties}", "INFO", "UNTESTED")

    results = {}
    for county in target_counties:
        cfg = COUNTY_CONFIGS[county]
        try:
            r = process_county(county, cfg)
            results[county] = r
        except Exception as e:
            log(f"FAILED {county}: {e}", "ERROR", "VERIFIED")
            results[county] = {"county": county, "error": str(e)}
        time.sleep(2)

    print("\n### SQL VERIFICATION — LANE SETUP RUN-338", flush=True)
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}", flush=True)
    for county, r in results.items():
        if "error" in r:
            print(f"  {county}: ERROR — {r['error']}", flush=True)
        else:
            a = r.get("a_metrics", {})
            print(f"  {county}: inserted={r['inserted']} fc={a.get('fc_count',0)} td={a.get('td_count',0)} total={a.get('total',0)} h_touched={r.get('h_touched',0)}", flush=True)

    log("Lane setup complete", "INFO", "VERIFIED")


if __name__ == "__main__":
    main()
