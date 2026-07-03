#!/usr/bin/env python3
"""
SHARD-3 BRADFORD LANE SETUP
County: bradford (0/10 -> full lane onboarding)

bradford was NEVER registered in auction_counties (zero rows) and has zero
rows in multi_county_auctions. realauction_multi_product_counties_v confirms
bradford.realforeclose.com + bradford.realtaxdeed.com are LIVE real platforms
(subdomain='bradford', sale_types_live=[foreclosure, tax_deed, tdm]).

A prior session fabricated bradford data (synthetic seeds) and it was reverted
as ghost-success (see git log 5c8958cb). This script does NOT use synthetic
fallback -- real scrape only. If the live scrape yields nothing, that is
reported honestly, not papered over.

HONESTY PROTOCOL: every claim tagged VERIFIED/INFERRED/UNTESTED.
FAIL-LOUD: parsed>0 AND inserted=0 raises.
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

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
DRY_RUN = "--dry-run" in sys.argv

COUNTY = "bradford"
FC_FQDN = "bradford.realforeclose.com"
TD_FQDN = "bradford.realtaxdeed.com"


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def _sb_headers(extra: dict = None) -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def rest_get(path: str, params: dict = None) -> list:
    qs = urllib.parse.urlencode(params or {})
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(url, headers=_sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"rest_get {path} HTTP {e.code}: {e.read()[:200]}", "WARN", "VERIFIED")
        return []
    except Exception as e:
        log(f"rest_get {path} failed: {e}", "WARN", "VERIFIED")
        return []


def rest_upsert(path: str, rows: list) -> int:
    if not rows:
        return 0
    if DRY_RUN:
        log(f"DRY-RUN upsert {path} ({len(rows)} rows)", "INFO", "UNTESTED")
        return len(rows)
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        data=json.dumps(rows).encode(),
        headers=_sb_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
        return len(rows)
    except urllib.error.HTTPError as e:
        log(f"rest_upsert {path} HTTP {e.code}: {e.read()[:300]}", "ERROR", "VERIFIED")
        return 0
    except Exception as e:
        log(f"rest_upsert {path} failed: {e}", "ERROR", "VERIFIED")
        return 0


def http_head_check(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "BidDeed-Shard3-Probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def upsert_realauction_subdomain(sale_type: str, platform: str, fqdn: str, is_active: bool,
                                  parity_verdict: str, http_status: int) -> int:
    now_utc = datetime.now(timezone.utc).isoformat()
    subdomain_bare = fqdn.split(".")[0]
    row = {
        "county_slug": COUNTY, "sale_type": sale_type, "platform": platform,
        "subdomain": subdomain_bare, "fqdn": fqdn,
        "is_active": is_active, "po_lots_count": 0, "parity_verdict": parity_verdict,
        "http_status": http_status, "last_verified": now_utc[:10],
        "state_code": "FL", "fips_county": "12007", "platform_id": f"realauction_{platform}",
    }
    n = rest_upsert("realauction_subdomains", [row])
    log(f"  realauction_subdomains upsert {fqdn}: {n} rows", "INFO", "VERIFIED" if not DRY_RUN else "UNTESTED")
    return n


def upsert_auction_counties(fc_status: int, td_status: int) -> int:
    row = {
        "fips_county": "12007",
        "state_code": "FL",
        "state_fips": "12",
        "county_name": "Bradford",
        "county_fips": "007",
        "foreclosure_platform_id": "realauction_realforeclose",
        "foreclosure_url": f"https://{FC_FQDN}",
        "tax_deed_platform_id": "realauction_realtaxdeed",
        "tax_deed_url": f"https://{TD_FQDN}",
        "status": "discovered",
        "notes": f"shard3 lane setup: fc HTTP {fc_status}, td HTTP {td_status}",
    }
    n = rest_upsert("auction_counties", [row])
    log(f"  auction_counties upsert bradford: {n} rows", "INFO", "VERIFIED" if not DRY_RUN else "UNTESTED")
    return n


def scrape_realauction(subdomain: str, sale_type: str) -> int:
    """Real unauthenticated PREVIEW scrape. FAIL-LOUD on parsed>0/inserted=0."""
    preview_url = f"https://{subdomain}/index.cfm?zaction=user&zmethod=preview&bypassPage=1"
    log(f"Scraping {subdomain} ({sale_type}) via PREVIEW...", "INFO", "UNTESTED")
    req = urllib.request.Request(
        preview_url,
        headers={
            "User-Agent": "Mozilla/5.0 (BidDeed-Shard3-Scraper/1.0; contact: ariel@everestcapitalusa.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"Failed to fetch {subdomain}: {e}", "WARN", "VERIFIED")
        return 0

    case_pats = [
        re.compile(r'(?:case[-\s#]*|CASE[-\s]*NUMBER\s*:?\s*)([0-9]{4}[-/][A-Z]{2,3}[-/][0-9]+)', re.IGNORECASE),
        re.compile(r'\b(\d{4}-(?:CA|CC|TDD|TD|GT|CF)-\d+)\b'),
        re.compile(r'\b(\d{4}-[A-Z]{2,3}-\d+)\b'),
    ]
    date_pat = re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})')

    cases = []
    for pat in case_pats:
        found = pat.findall(html)
        if found:
            cases = found
            break
    dates = date_pat.findall(html)
    log(f"  {subdomain}: parsed {len(cases)} cases, {len(dates)} dates", "INFO", "VERIFIED")

    if not cases:
        log(f"  {subdomain}: no case numbers found in static HTML (JS-rendered calendar likely empty of "
            f"parseable content in unauthenticated preview) -- reporting 0, NOT seeding synthetic data",
            "INFO", "VERIFIED")
        return 0

    now_utc = datetime.now(timezone.utc).isoformat()
    rows, seen = [], set()
    platform_short = "realforeclose" if "realforeclose" in subdomain else "realtaxdeed"
    for i, case in enumerate(cases):
        case = case.strip().upper()
        if case in seen:
            continue
        seen.add(case)
        sale_date = None
        if i < len(dates):
            for fmt in ("%m/%d/%Y", "%m-%d-%Y"):
                try:
                    sale_date = datetime.strptime(dates[i], fmt).date().isoformat()
                    break
                except ValueError:
                    pass
        rows.append({
            "case_number": case, "county": COUNTY, "sale_type": sale_type,
            "source_platform": platform_short, "auction_date": sale_date,
            "last_seen_at": now_utc, "source_url": preview_url,
        })

    inserted = 0
    for i in range(0, len(rows), 50):
        batch = rows[i:i + 50]
        n = rest_upsert("multi_county_auctions", batch)
        inserted += n
        time.sleep(0.3)

    if len(rows) > 0 and inserted == 0:
        raise RuntimeError(f"FAIL-LOUD: {subdomain} parsed {len(rows)} rows but inserted 0.")

    log(f"{subdomain} ({sale_type}): inserted {inserted} rows", "INFO", "VERIFIED")
    return inserted


def main():
    log("=== BRADFORD LANE SETUP (shard-3) ===", "INFO", "UNTESTED")
    results = {"county": COUNTY, "dry_run": DRY_RUN}

    fc_status = http_head_check(f"https://{FC_FQDN}")
    td_status = http_head_check(f"https://{TD_FQDN}")
    log(f"Bradford FC HEAD {FC_FQDN}: HTTP {fc_status}", "INFO", "VERIFIED")
    log(f"Bradford TD HEAD {TD_FQDN}: HTTP {td_status}", "INFO", "VERIFIED")
    results["fc_http_status"] = fc_status
    results["td_http_status"] = td_status

    fc_reachable = fc_status in (200, 301, 302, 403)
    td_reachable = td_status in (200, 301, 302, 403)

    upsert_realauction_subdomain("foreclosure", "realforeclose", FC_FQDN, fc_reachable,
                                  "shard3-lane-setup" if fc_reachable else "unreachable", fc_status)
    time.sleep(0.5)
    upsert_realauction_subdomain("tax_deed", "realtaxdeed", TD_FQDN, td_reachable,
                                  "shard3-lane-setup" if td_reachable else "unreachable", td_status)
    time.sleep(0.5)

    upsert_auction_counties(fc_status, td_status)

    fc_inserted = scrape_realauction(FC_FQDN, "foreclosure") if fc_reachable else 0
    time.sleep(1)
    td_inserted = scrape_realauction(TD_FQDN, "tax_deed") if td_reachable else 0

    results["fc_inserted"] = fc_inserted
    results["td_inserted"] = td_inserted
    results["a_criterion_pass"] = fc_inserted > 0 and td_inserted > 0

    log(f"RESULT: {json.dumps(results)}", "INFO", "VERIFIED")
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    main()
