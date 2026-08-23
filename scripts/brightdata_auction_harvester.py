#!/usr/bin/env python3
"""SummitLeads Sprint 1b — Bright Data Scraping Browser winner harvester.

STATUS: UNTESTED this session. BRIGHTDATA_API_KEY / BRIGHTDATA_BROWSER_WSS
were not present in this session's environment (confirmed: `env | grep -i
bright` returned nothing, despite the secrets existing in the repo since
2026-08-23 ~12:51 UTC — the cc-runner-ghonly.yml job never passed them
through its env: block; fixed in the same commit series as this file, see
.github/workflows/cc-runner-ghonly.yml). No prior session has ever
exercised connect_over_cdp against Bright Data from this repo. The next
run of cc-runner-ghonly.yml WILL have these secrets and can execute this
for real — treat the first live run as a validation run, not a rubber
stamp: watch its log for the FATAL-on-login-failure path below actually
firing correctly, and confirm new_sightings > 0 via a live re-query
before trusting this in the daily cron.

Why the DOM interaction is medium- (not zero-) confidence despite being
untested here: county_outcome_harvester.py already POSTs the exact same
LogName/LogPass/LogButton form fields directly over HTTP against these
same realforeclose.com sites and that flow is live-verified (see its
`scrape_realforeclose_results()` / pre-enrichment login). This script
performs the equivalent interaction through a real browser (fill+click
instead of a raw form POST) so that Bright Data's residential exit IPs
carry the session past the datacenter-IP block that killed #18527 — the
selectors are carried over unchanged, not guessed fresh.

Scope: last 14 days, SOLD auctions only, on BOTH realforeclose.com
(foreclosure) and realtaxdeed.com (tax deed) for a caller-supplied county
list (no fabricated "certified counties" list -- pass --counties or set
COUNTIES env, comma-separated).

Writes to public.auction_buyer_sightings + upserts public.auction_buyer_profiles.
Neither table had an existing ETL script anywhere in this repo prior to
this file (verified: `grep -rl auction_buyer_profiles --include=*.py .`
returned nothing) -- the normalizer here is new, not reused, because
nothing to reuse existed. Login failure is FATAL (sys.exit(2)), never a
silent WARN, per spec -- a false "0 results, no error" run must not look
identical to "the site had nothing new."
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
RF_EMAIL = os.environ.get("REALFORECLOSE_EMAIL", "")
RF_PASSWORD = os.environ.get("REALFORECLOSE_PASSWORD", "")
BRIGHTDATA_WSS = os.environ.get("BRIGHTDATA_BROWSER_WSS", "")
DAYS_BACK = int(os.environ.get("DAYS_BACK", "14"))
THROTTLE_SECONDS = 3.0


def log(msg: str, tag: str = "INFO") -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {tag}: {msg}", flush=True)


def normalize_buyer_name(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", "", name.lower())
    return re.sub(r"\s+", " ", n).strip()


def sb_headers() -> dict:
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }


def sb_upsert(table: str, rows: list[dict], conflict_cols: str) -> int:
    if not rows:
        return 0
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=json.dumps(rows).encode(),
        headers={**sb_headers(), "Prefer": f"resolution=merge-duplicates,on-conflict={conflict_cols},return=minimal"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
    return len(rows)


def login(page, host: str) -> None:
    """Authenticate against a realforeclose.com/realtaxdeed.com site.

    Selectors per issue #19392 comment (confirmed live #18529): #LogName,
    #LogPass, #LogButton. FATAL on failure -- never proceed unauthenticated
    and never report a silent 0-result run as if the site had nothing new.
    """
    page.goto(f"{host}/index.cfm", timeout=30000)
    try:
        page.fill("#LogName", RF_EMAIL, timeout=10000)
        page.fill("#LogPass", RF_PASSWORD, timeout=10000)
        page.click("#LogButton", timeout=10000)
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception as e:
        log(f"login form interaction failed on {host}: {e}", "ERROR")
        log("FATAL: aborting to prevent a silent zero-result run", "ERROR")
        sys.exit(2)
    content = page.content()
    if "logout" not in content.lower():
        snippet = re.sub(r"\s+", " ", content)[:600]
        log(f"login FAILED on {host} — session not established. Excerpt: {snippet}", "ERROR")
        log("FATAL: aborting to prevent a silent zero-result run", "ERROR")
        sys.exit(2)
    log(f"login OK: {host}")


def scrape_sold_auctions(page, host: str, county: str, sale_kind: str, days_back: int) -> list[dict]:
    """Walk the daily auction calendar for the last `days_back` days and pull
    per-case winner ("Name On Title") + plaintiff from each SOLD auction's
    detail page. Detail-page regexes mirror parse_auction_detail_page() in
    county_outcome_harvester.py (same site family, already live-verified).
    """
    results: list[dict] = []
    today = date.today()
    auction_type = "F" if sale_kind == "foreclosure" else "T"
    for offset in range(days_back):
        d = today - timedelta(days=offset)
        date_str = d.strftime("%m/%d/%Y")
        url = f"{host}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={urllib.parse.quote(date_str)}&AUCTIONTYPE={auction_type}"
        time.sleep(THROTTLE_SECONDS)
        try:
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            log(f"  {county} {sale_kind} {date_str}: page load failed: {e}", "WARN")
            continue
        html = page.content()
        case_nums = re.findall(r'CaseNo["\']?\s*[:=]\s*["\']?([A-Za-z0-9\-]{5,40})', html)
        status_sold = re.findall(r'(?:Status|Result)[^<]*</td>\s*<td[^>]*>\s*(SOLD|Sold)', html)
        if not case_nums:
            continue
        for case_num in set(case_nums):
            detail_url = f"{host}/index.cfm?zaction=AUCTION&Zmethod=DETAIL&CASENUM={urllib.parse.quote(case_num)}"
            time.sleep(THROTTLE_SECONDS)
            try:
                page.goto(detail_url, timeout=20000)
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:
                log(f"    detail {case_num} failed: {e}", "WARN")
                continue
            dhtml = page.content()
            m_winner = re.search(r'Name\s+On\s+Title[^<]*</td>\s*<td[^>]*>([^<]+)', dhtml, re.IGNORECASE)
            m_plaintiff = re.search(r'Plaintiff[^<]*</td>\s*<td[^>]*>\s*([^<]{5,200}?)\s*</td>', dhtml, re.IGNORECASE)
            m_addr = re.search(r'Property\s+Address[^<]*</td>\s*<td[^>]*>([^<]+)', dhtml, re.IGNORECASE)
            m_amount = re.search(r'(?:Winning|High|Final)\s*Bid[^>]*>[^<]*\$([\d,\.]+)', dhtml, re.IGNORECASE)
            winner = (m_winner.group(1).strip() if m_winner else None)
            if not winner or winner.lower() in ("n/a", "pending", ""):
                continue
            results.append({
                "county": county,
                "sale_type": sale_kind,
                "case_number": case_num,
                "auction_date": d.isoformat(),
                "property_address": m_addr.group(1).strip() if m_addr else None,
                "sold_amount": float(m_amount.group(1).replace(",", "")) if m_amount else None,
                "plaintiff": m_plaintiff.group(1).strip() if m_plaintiff else None,
                "buyer_type": "unknown",
                "winning_bidder": winner,
                "detail_url": detail_url,
            })
        log(f"  {county} {sale_kind} {date_str}: {len(case_nums)} cases checked")
    return results


def upsert_sightings_and_profiles(sightings: list[dict]) -> int:
    if not sightings:
        return 0
    profile_rows = {}
    for s in sightings:
        norm = normalize_buyer_name(s["winning_bidder"])
        p = profile_rows.setdefault(norm, {
            "buyer_name": s["winning_bidder"],
            "buyer_name_normalized": norm,
            "entity_type": "business" if re.search(r"\bllc\b|\binc\b|\btrust\b|\bcorp\b", norm) else "person",
            "counties_active": set(),
            "total_wins": 0,
        })
        p["counties_active"].add(s["county"])
        p["total_wins"] += 1

    profile_payload = [
        {
            "buyer_name": p["buyer_name"],
            "buyer_name_normalized": p["buyer_name_normalized"],
            "entity_type": p["entity_type"],
            "counties_active": sorted(p["counties_active"]),
        }
        for p in profile_rows.values()
    ]
    sb_upsert("auction_buyer_profiles", profile_payload, conflict_cols="buyer_name_normalized")

    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/auction_buyer_profiles?select=id,buyer_name_normalized&buyer_name_normalized=in.("
        + ",".join(urllib.parse.quote(n) for n in profile_rows) + ")",
        headers=sb_headers(),
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        id_map = {r["buyer_name_normalized"]: r["id"] for r in json.loads(resp.read())}

    sighting_rows = []
    for s in sightings:
        norm = normalize_buyer_name(s["winning_bidder"])
        pid = id_map.get(norm)
        if not pid:
            continue
        sighting_rows.append({
            "buyer_profile_id": pid,
            "case_number": s["case_number"],
            "county": s["county"],
            "sale_type": s["sale_type"],
            "auction_date": s["auction_date"],
            "property_address": s["property_address"],
            "sold_amount": s["sold_amount"],
            "plaintiff": s["plaintiff"],
            "buyer_type": s["buyer_type"],
        })
    return sb_upsert("auction_buyer_sightings", sighting_rows, conflict_cols="case_number,county,auction_date")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--counties", default=os.environ.get("COUNTIES", ""),
                     help="comma-separated county slugs, e.g. marion,putnam,broward")
    args = ap.parse_args()
    counties = [c.strip() for c in args.counties.split(",") if c.strip()]

    if not counties:
        log("No --counties/COUNTIES supplied. This script does not invent a "
            "'certified counties' list -- pass the counties to harvest explicitly.", "ERROR")
        return 2
    if not BRIGHTDATA_WSS:
        log("BRIGHTDATA_BROWSER_WSS absent from environment. Cannot connect. "
            "This is the exact secret-wiring gap fixed in cc-runner-ghonly.yml "
            "this session -- the NEXT dispatch of that workflow should have it.", "ERROR")
        return 2
    if not RF_EMAIL or not RF_PASSWORD:
        log("REALFORECLOSE_EMAIL/REALFORECLOSE_PASSWORD absent -- required for login.", "ERROR")
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("playwright not installed in this environment.", "ERROR")
        return 2

    total_sightings = 0
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(BRIGHTDATA_WSS)
        try:
            context = browser.new_context()
            page = context.new_page()
            all_results: list[dict] = []
            for county in counties:
                for sale_kind, fqdn_tmpl in (
                    ("foreclosure", "https://{c}.realforeclose.com"),
                    ("tax_deed", "https://{c}.realtaxdeed.com"),
                ):
                    host = fqdn_tmpl.format(c=county)
                    log(f"=== {county} {sale_kind} ({host}) ===")
                    login(page, host)
                    results = scrape_sold_auctions(page, host, county, sale_kind, DAYS_BACK)
                    log(f"  {county} {sale_kind}: {len(results)} winners found")
                    all_results.extend(results)
            n = upsert_sightings_and_profiles(all_results)
            total_sightings = n
        finally:
            browser.close()

    log(f"Bright Data harvest complete: {total_sightings} sighting row(s) upserted "
        f"across {len(counties)} counties. Re-query auction_buyer_sightings "
        f"count before vs after to confirm new_sightings > 0 — this log line "
        f"is not itself proof.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
