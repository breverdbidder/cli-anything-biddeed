#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-10 run 6253 — Alachua C/D parity harvest.

Uses the proven RealForeclose AJAX pattern from shard2_run2450 to harvest
parity data for alachua.realforeclose.com auction dates that have unmatched
rows in multi_county_auctions.

Strategy:
1. Fetch all alachua MCA rows with parity_status IS NULL
2. Group by auction_date
3. For each auction_date, hit the AJAX endpoint
4. Match by case_number normalization
5. Promote parity_status to 'matched_clean'

Known structural blocks (NOT attempted here — verified by prior sessions):
  - 4 rows with auction_date=2026-08-18 (future, will not yet be held on 2026-07-24)
  - 9 rows with RealForeclose placeholder "Property Appraiser" in Parcel ID
  
The only rows worth attempting are:
  - Newly-added rows (since 2026-07-21) with auction_date that has already passed
  - Or rows where the parity_source was lost/reset

Honesty markers:
  CONFIRMED: case_number matched against live AJAX response
  STRUCTURAL_BLOCK: auction not yet held / placeholder parcel
"""
from __future__ import annotations
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, date

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
DRY_RUN = "--dry-run" in sys.argv
DISPATCH_ID = "a36233a1-0145-43b9-a8f0-75acc7594181"
PIPELINE_RUN_ID = "SHARD10-6253-alachua-CD"

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

AJAX_SUBS = [
    ("@A", '<div class="'),
    ("@B", "</div>"),
    ("@C", 'class="'),
    ("@D", "<div>"),
    ("@E", "AUCTION"),
    ("@F", "</td><td"),
    ("@G", "</td></tr>"),
    ("@H", "<tr><td "),
    ("@I", "table"),
    ("@J", 'p_back="NextCheck='),
    ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]

# Future auction date that should NOT be promoted
FUTURE_BLOCK_DATE = "2026-08-18"
TODAY = date.today()


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def sb_headers(extra: dict = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def rest_get(path: str, timeout: int = 60) -> list:
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        log(f"rest_get {path} HTTP {e.code}: {body[:300]}", "WARN", "VERIFIED")
        return []
    except Exception as e:
        log(f"rest_get {path} failed: {e}", "WARN", "VERIFIED")
        return []


def rest_patch_row(case_number: str, body: dict) -> bool:
    if DRY_RUN:
        log(f"DRY-RUN PATCH case={case_number}", "INFO", "UNTESTED")
        return True
    cn_enc = urllib.parse.quote(case_number, safe="")
    path = f"multi_county_auctions?county=ilike.alachua&case_number=eq.{cn_enc}"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers=sb_headers({"Prefer": "return=minimal"}),
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        body_text = e.read()
        log(f"PATCH {case_number} HTTP {e.code}: {body_text[:300]}", "ERROR", "VERIFIED")
        return False
    except Exception as e:
        log(f"PATCH {case_number} failed: {e}", "ERROR", "VERIFIED")
        return False


def norm_case_number(cn: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def decode_ajax(raw: str) -> str:
    """Apply RealForeclose AJAX token substitutions."""
    result = raw
    for token, replacement in AJAX_SUBS:
        result = result.replace(token, replacement)
    return result


def parse_aitem_blocks(html: str) -> list[dict]:
    """Parse AITEM blocks from decoded RealForeclose AJAX HTML."""
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts:
        return items
    starts.append(len(html))
    for i in range(len(starts) - 1):
        block = html[starts[i]:starts[i + 1]]
        aid_m = re.search(r'aid="(\d+)"', block)
        if not aid_m:
            continue
        aid = aid_m.group(1)
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            block, re.DOTALL
        )
        data = {}
        for lbl, val in rows:
            lbl_clean = re.sub(r"<[^>]+>", "", lbl).strip().rstrip(":")
            val_clean = re.sub(r"<[^>]+>", "", val).strip()
            data[lbl_clean] = val_clean

        case_raw = data.get("Case #") or data.get("Case#") or data.get("Case Number")
        parcel_raw = data.get("Parcel ID") or data.get("Parcel #")
        items.append({
            "aid": aid,
            "case_number_raw": case_raw,
            "case_number_norm": norm_case_number(case_raw) if case_raw else None,
            "parcel_id_raw": parcel_raw,
            "raw_data": data,
        })
    return items


def is_real_parcel_id(pid: str) -> bool:
    if not pid:
        return False
    return bool(re.search(r"\d", pid)) and pid.strip().lower() != "property appraiser"


def fetch_realforeclose_ajax(auction_date: str) -> list[dict]:
    """
    Fetch AJAX calendar from alachua.realforeclose.com for a given date.
    Returns parsed AITEM blocks, or [] on any error.
    """
    base_url = "https://alachua.realforeclose.com"
    date_fmt = datetime.strptime(auction_date, "%Y-%m-%d").strftime("%m/%d/%Y")

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    # Step 1: GET preview page to establish session cookie
    preview_url = (
        f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
        f"&AUCTIONDATE={urllib.parse.quote(date_fmt)}"
    )
    try:
        req = urllib.request.Request(preview_url, headers={"User-Agent": UA_DESKTOP})
        with opener.open(req, timeout=15) as r:
            r.read()
        log(f"Preview GET {date_fmt}: {r.status}", "INFO", "VERIFIED")
    except Exception as e:
        log(f"Preview GET failed for {auction_date}: {e}", "WARN", "VERIFIED")
        return []

    time.sleep(0.5)

    # Step 2: AJAX UPDATE request
    ajax_url = (
        f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=UPDATE"
        f"&FNC=LOAD&AREA=W&AUCTIONDATE={urllib.parse.quote(date_fmt)}"
        f"&bypassPage=1&STARTPAGE=1"
    )
    try:
        req2 = urllib.request.Request(
            ajax_url,
            headers={
                "User-Agent": UA_DESKTOP,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": preview_url,
            }
        )
        with opener.open(req2, timeout=20) as r:
            raw_body = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"AJAX UPDATE failed for {auction_date}: {e}", "WARN", "VERIFIED")
        return []

    try:
        payload = json.loads(raw_body)
        ret_html = payload.get("retHTML", "")
    except json.JSONDecodeError:
        log(f"AJAX response not JSON for {auction_date}: {raw_body[:200]}", "WARN", "VERIFIED")
        return []

    if not ret_html:
        log(f"AJAX retHTML empty for {auction_date}", "WARN", "VERIFIED")
        return []

    decoded = decode_ajax(ret_html)
    items = parse_aitem_blocks(decoded)
    log(f"AJAX {auction_date}: found {len(items)} AITEM blocks", "INFO", "VERIFIED")
    return items


def main():
    if not SUPABASE_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    log(f"SHARD-10 run 6253 Alachua C/D harvest — DRY_RUN={DRY_RUN}", "INFO", "VERIFIED")

    # Fetch rows without parity_status
    unmatched = rest_get(
        "multi_county_auctions?county=ilike.alachua"
        "&parity_status=is.null"
        "&select=id,case_number,auction_date,parcel_id,property_address"
        "&limit=100"
    )
    log(f"Alachua rows with parity_status IS NULL: {len(unmatched)}", "INFO", "VERIFIED")

    if not unmatched:
        log("No unmatched rows — nothing to harvest", "INFO", "VERIFIED")
        sys.exit(0)

    # Group by auction_date
    by_date: dict[str, list] = {}
    for r in unmatched:
        ad = r.get("auction_date")
        if not ad:
            continue
        by_date.setdefault(ad, []).append(r)

    # Filter: skip known future-blocked dates
    actionable_dates = []
    for ad, rows in sorted(by_date.items()):
        ad_date = datetime.strptime(ad[:10], "%Y-%m-%d").date()
        if ad_date >= TODAY:
            log(f"Skipping future date {ad} ({len(rows)} rows) — not yet held", "INFO", "VERIFIED")
        else:
            log(f"Will harvest {ad} ({len(rows)} rows)", "INFO", "VERIFIED")
            actionable_dates.append((ad, rows))

    if not actionable_dates:
        log("All unmatched rows are on future dates — structural ceiling, nothing actionable", 
            "WARN", "VERIFIED")
        sys.exit(0)

    # Harvest each date
    total_matched = 0
    total_attempted = 0

    for auction_date, mca_rows in actionable_dates:
        log(f"\n=== Harvesting {auction_date} ({len(mca_rows)} rows) ===", "INFO", "UNTESTED")
        items = fetch_realforeclose_ajax(auction_date)
        time.sleep(1)

        if not items:
            log(f"No AITEM blocks for {auction_date} — date may be post-sale or unavailable", 
                "WARN", "VERIFIED")
            continue

        # Build lookup by normalized case number
        by_norm_case = {item["case_number_norm"]: item for item in items if item.get("case_number_norm")}
        log(f"AJAX items with case numbers: {len(by_norm_case)}", "INFO", "VERIFIED")

        for mca_row in mca_rows:
            cn = mca_row.get("case_number")
            if not cn:
                continue
            total_attempted += 1
            cn_norm = norm_case_number(cn)
            if cn_norm in by_norm_case:
                item = by_norm_case[cn_norm]
                parcel_raw = item.get("parcel_id_raw")
                parcel_real = parcel_raw if is_real_parcel_id(parcel_raw) else None

                patch_body = {
                    "parity_status": "matched_clean",
                    "parity_source": f"tier1:{PIPELINE_RUN_ID}:realforeclose:{auction_date}",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                if parcel_real and not mca_row.get("parcel_id"):
                    patch_body["parcel_id"] = parcel_real
                    log(f"  {cn}: matched + parcel_id={parcel_real} [CONFIRMED]", "INFO", "CONFIRMED")
                else:
                    log(f"  {cn}: matched (no real parcel in AJAX) [CONFIRMED]", "INFO", "CONFIRMED")

                if rest_patch_row(cn, patch_body):
                    total_matched += 1
                else:
                    log(f"  {cn}: PATCH failed", "ERROR", "VERIFIED")
            else:
                log(f"  {cn}: not found in AJAX for {auction_date} — structural block", 
                    "WARN", "VERIFIED")

    log(f"\n=== C/D HARVEST COMPLETE ===", "INFO", "VERIFIED")
    log(f"Total attempted: {total_attempted}, matched: {total_matched}", "INFO", "VERIFIED")

    print(f"\n### SQL VERIFICATION — ALACHUA C/D HARVEST (SHARD-10 run 6253)")
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"Unmatched rows found: {len(unmatched)}")
    print(f"Actionable dates (past): {len(actionable_dates)}")
    print(f"Total matched: {total_matched}/{total_attempted}")
    print(f"DRY_RUN: {DRY_RUN}")
    print("\nVerification query:")
    print("  SELECT public.pencil_dod_evaluate_county('alachua');")
    print("  SELECT COUNT(*) FILTER (WHERE parity_status='matched_clean') FROM multi_county_auctions WHERE county='alachua';")


if __name__ == "__main__":
    main()
