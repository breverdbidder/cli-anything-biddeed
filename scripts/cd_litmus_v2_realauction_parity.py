#!/usr/bin/env python3
"""C/D LITMUS V2 — RealAuction source parity (primary) + FloridaBidder fallback.

ARIEL DIRECTIVE Jul 6 2026. For each priority county, re-counts live auction
cases on the official RealAuction platform ({county}.realforeclose.com /
{county}.realtaxdeed.com) for the dates already present in OUR frozen
calendar (multi_county_auctions), and compares source_count vs our_count.
Falls back to FloridaBidder.com when a county has no online RealAuction
platform for a sale_type. Writes one row per (county, source, sale_type) to
cd_litmus_parity_v2 (see migrations/20260706_cd_litmus_v2_realauction_parity.sql).

Honesty Protocol: a fetch that fails (blocked, timeout, no platform) is
recorded with status != 'ok' and source_count=NULL — never fabricated.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN") or ""

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

PRIORITY_COUNTIES = [
    "duval", "okeechobee", "bay", "desoto", "dixie", "escambia", "hendry",
    "highlands", "hillsborough", "levy", "palm_beach", "pasco", "polk",
    "sarasota", "broward", "hamilton",
]

MAX_DATES_PER_SIDE = 12  # cap live page loads per county/sale_type
DATE_LOOKBACK_DAYS = 14  # matches OUR frozen calendar window used for comparison


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED") -> None:
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def db_query(sql: str) -> list:
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json",
            "User-Agent": "curl/8.5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sql_lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def sb_insert(table: str, rows: list) -> int:
    # SUPABASE_SERVICE_ROLE_KEY is stale (401 on PostgREST as of 2026-07-09, same
    # root cause as the DB-password staleness documented in migrations/run_migration.js).
    # Insert via the Management API (SUPABASE_ACCESS_TOKEN) instead — same channel
    # already used for db_query() reads in this script.
    if not rows:
        return 0
    cols = ["county_slug", "source", "sale_type", "window_start", "window_end",
            "source_count", "our_count", "match_pct", "status", "notes"]
    values_sql = ",\n".join(
        "(" + ", ".join(sql_lit(r.get(c)) for c in cols) + ")" for r in rows
    )
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n{values_sql};"
    try:
        db_query(sql)
        return 201
    except urllib.error.HTTPError as e:
        log(f"insert {table} failed: {e.code} {e.read().decode()[:300]}", "ERROR", "VERIFIED")
        return e.code


def get_county_platform_config() -> dict:
    # county_auction_config.county_slug is inconsistently seeded (e.g. 'palmbeach'
    # not 'palm_beach') for some multi-word counties -- match underscore-insensitively
    # so PRIORITY_COUNTIES entries aren't silently dropped to the floridabidder
    # fallback when a working realauction config actually exists.
    norm_priority = {c.replace("_", ""): c for c in PRIORITY_COUNTIES}
    sql = "SELECT county_slug, fc_url, fc_method, td_url, td_method FROM county_auction_config"
    rows = db_query(sql)
    out = {}
    for r in rows:
        key = norm_priority.get(r["county_slug"].replace("_", ""))
        if key:
            out[key] = r
    return out


def get_cert_scope_cutoff() -> dict:
    rows = db_query("SELECT county_slug, snapshot_at FROM gold_standard_cert_scope WHERE active=true")
    return {r["county_slug"]: r["snapshot_at"] for r in rows}


def get_our_dates_and_count(county: str, sale_type: str, cutoff: str | None) -> tuple[list[str], int]:
    cutoff_clause = f"AND created_at <= '{cutoff}'" if cutoff else ""
    sql = f"""
    SELECT auction_date::text AS d, count(*) AS n
    FROM multi_county_auctions
    WHERE lower(county) = '{county}' AND sale_type = '{sale_type}'
      AND auction_date >= current_date - interval '{DATE_LOOKBACK_DAYS} days'
      {cutoff_clause}
    GROUP BY auction_date ORDER BY auction_date
    LIMIT {MAX_DATES_PER_SIDE}
    """
    rows = db_query(sql)
    dates = [r["d"] for r in rows]
    total = sum(r["n"] for r in rows)
    return dates, total


def count_cases_on_page(page, url: str) -> int | None:
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        text = page.inner_text("body")
    except Exception as e:
        log(f"  page load failed {url}: {e}", "WARN", "VERIFIED")
        return None
    return len(re.findall(r"Case\s*#\s*:", text, re.IGNORECASE))


def fetch_realauction_count(page, base_url: str, dates: list[str]) -> int | None:
    if not dates:
        return 0
    total = 0
    any_ok = False
    for d in dates:
        y, m, dd = d.split("-")
        mmddyyyy = f"{m}/{dd}/{y}"
        url = f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={mmddyyyy}"
        n = count_cases_on_page(page, url)
        if n is not None:
            total += n
            any_ok = True
        time.sleep(1.5)
    return total if any_ok else None


def fetch_floridabidder_count(page, county: str) -> int | None:
    slug = county.replace("_", "-")
    url = f"https://www.floridabidder.com/{slug}"
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        text = page.inner_text("body")
    except Exception as e:
        log(f"  floridabidder load failed {url}: {e}", "WARN", "VERIFIED")
        return None
    if "attention required" in text.lower() or "cloudflare" in text.lower():
        return None
    matches = re.findall(r"case\s*#|parcel\s*id", text, re.IGNORECASE)
    return len(matches) if matches else None


def main():
    if not SB_KEY or not MGMT_TOKEN:
        log("Missing SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ACCESS_TOKEN", "ERROR", "VERIFIED")
        sys.exit(1)

    # Optional CLI args restrict the run to a subset of PRIORITY_COUNTIES, so a
    # single invocation can stay well inside a runner's time budget instead of
    # risking a mid-run kill losing every row (rows are now inserted as they're
    # computed, not batched to the end -- see sb_insert call below).
    counties = sys.argv[1:] or PRIORITY_COUNTIES

    configs = get_county_platform_config()
    cutoffs = get_cert_scope_cutoff()
    log(f"Loaded config for {len(configs)} counties, {len(cutoffs)} frozen-scope cutoffs", tag="VERIFIED")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)

        for county in counties:
            cfg = configs.get(county, {})
            cutoff = cutoffs.get(county)
            for sale_type, url_key, method_key in (
                ("foreclosure", "fc_url", "fc_method"),
                ("tax_deed", "td_url", "td_method"),
            ):
                our_dates, our_count = get_our_dates_and_count(county, sale_type, cutoff)
                window_start = our_dates[0] if our_dates else None
                window_end = our_dates[-1] if our_dates else None
                base_url = cfg.get(url_key)
                is_online = cfg.get(method_key) == "online" and base_url

                if is_online:
                    log(f"{county}/{sale_type}: realauction {base_url} dates={our_dates}", tag="VERIFIED")
                    source_count = fetch_realauction_count(page, base_url, our_dates)
                    source = "realauction"
                    status = "ok" if source_count is not None else "unreachable"
                elif not our_dates:
                    log(f"{county}/{sale_type}: no OUR dates in window, no platform — skipping", tag="VERIFIED")
                    continue
                else:
                    log(f"{county}/{sale_type}: no online realauction platform, trying floridabidder fallback", tag="VERIFIED")
                    source_count = fetch_floridabidder_count(page, county)
                    source = "floridabidder"
                    status = "ok" if source_count is not None else "unreachable"

                match_pct = None
                if source_count is not None and (source_count or our_count):
                    denom = max(source_count, our_count) or 1
                    match_pct = round(100.0 * min(source_count, our_count) / denom, 1)

                row = {
                    "county_slug": county,
                    "source": source,
                    "sale_type": sale_type,
                    "window_start": window_start,
                    "window_end": window_end,
                    "source_count": source_count,
                    "our_count": our_count,
                    "match_pct": match_pct,
                    "status": status if (our_dates or is_online) else "no_platform",
                    "notes": f"dates_checked={our_dates}",
                }
                results.append(row)
                sc = sb_insert("cd_litmus_parity_v2", [row])
                log(f"  -> source_count={source_count} our_count={our_count} match_pct={match_pct} status={row['status']} (inserted HTTP {sc})", tag="VERIFIED")

        browser.close()

    log(f"Done: {len(results)} rows inserted this run across {len(counties)} counties", tag="VERIFIED")


if __name__ == "__main__":
    main()
