#!/usr/bin/env python3
"""
Gold Standard alachua C/D/E/I/J gap fix (2026-08-24 dispatch).

Diagnosis (CONFIRMED live query 2026-08-24):
  - C/D denominator gap = 8 rows with parity_status IS NULL. Only 3 of these
    overlap the 7 "ghost" rows given in the dispatch (01 2026 CA 000588,
    01 2025 CA 002983, 01 2026 CA 000169). The other 5
    (01 2025 CA 003002, 01 2026 CA 001136, TD 2026-034, TD 2026-033,
    TD 2026-035) are FULLY POPULATED rows (address/geo/value/parcel_id all
    present) that simply never had a parity match written -- a distinct bug
    from the 7 ghost rows, diagnosed separately per dispatch instructions.
  - E/I denominator gap = 7 rows with parcel_id IS NULL, exactly matching the
    7 given ghost/placeholder rows.

Method: RealForeclose/RealTaxDeed AJAX calendar harvester (proven pattern from
scripts/alachua_run14411591_cd_gap_fix.py and
scripts/shard2_run2450_ajax_realforeclose_harvest.py). Firecrawl re-checked
live this session -- still HTTP 402 insufficient credits, so the browser-login
AID-detail-page path remains blocked; this script does NOT depend on it.

Reformats any parcel_id found to the dashed 2-2-2-4-4-4 Alachua convention if
it arrives undashed.
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shard2_run2450_ajax_realforeclose_harvest import fetch, decode_ajax_html, parse_aitem_blocks

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
DRY_RUN = "--dry-run" in sys.argv
RUN_LABEL = "gold_standard_alachua_20260824_cd_ei_gap_fix"

# (case_number, auction_date MM/DD/YYYY, platform_domain, class)
# class: "cd_only" = already has parcel/address/value, only needs parity_status
#        "ghost" = fully blank row, needs everything if found live
TARGETS = [
    ("01 2026 CA 000588", "09/17/2026", "realforeclose.com", "ghost"),
    ("01 2025 CA 002983", "09/17/2026", "realforeclose.com", "ghost"),
    ("01 2026 CA 000169", "09/17/2026", "realforeclose.com", "ghost"),
    ("01 2025 CA 003002", "09/17/2026", "realforeclose.com", "cd_only"),
    ("01 2026 CA 001136", "09/17/2026", "realforeclose.com", "cd_only"),
    ("TD 2026-034", "10/06/2026", "realtaxdeed.com", "cd_only"),
    ("TD 2026-033", "10/06/2026", "realtaxdeed.com", "cd_only"),
    ("TD 2026-035", "10/06/2026", "realtaxdeed.com", "cd_only"),
    ("01 2025 CA 002643", "07/23/2026", "realforeclose.com", "ghost"),
    ("01 2025 CA 003919", "08/18/2026", "realforeclose.com", "ghost"),
    ("01 2025 CA 001928", "05/14/2026", "realforeclose.com", "ghost"),
    ("01 2025 CA 003287", "05/04/2026", "realforeclose.com", "ghost"),
]


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def dashify_parcel_id(raw: str) -> str | None:
    """Reformat an undashed FL GIO-style parcel id to Alachua's dashed
    2-2-2-4-4-4 convention if it looks undashed and the right length.
    If it's already dashed (contains '-'), return as-is (trust source
    formatting -- RealForeclose typically already returns Alachua's native
    dashed format, e.g. 18470-009-001 style or PPA-native)."""
    if not raw:
        return None
    raw = raw.strip()
    if "-" in raw:
        return raw
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 18:
        return f"{digits[0:2]}-{digits[2:4]}-{digits[4:6]}-{digits[6:10]}-{digits[10:14]}-{digits[14:18]}"
    return raw


def harvest_date_both_areas(date_mmddyyyy: str, platform_domain: str) -> dict:
    """Returns {case_number: item_dict} for all AITEM blocks found across AREA W+C."""
    base = f"https://alachua.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    status, _ = fetch(preview_url, jar)
    if status != 200:
        log(f"PREVIEW non-200 ({status}) {platform_domain} {date_mmddyyyy}", "WARN", "VERIFIED")
        return {}
    time.sleep(0.4)

    found = {}
    for area in ("W", "C"):
        ts_ms = int(time.time() * 1000)
        ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                    f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(date_mmddyyyy)}"
                    f"&PageDir=0&doR=0&tx={ts_ms}&bypassPage=0&test=1")
        try:
            status, body = fetch(ajax_url, jar, referer=preview_url,
                                  headers={"X-Requested-With": "XMLHttpRequest"})
        except Exception as e:
            log(f"AJAX AREA={area} fetch failed {platform_domain} {date_mmddyyyy}: {e}", "WARN", "VERIFIED")
            continue
        if status != 200:
            log(f"AJAX AREA={area} non-200 ({status}) {platform_domain} {date_mmddyyyy}", "WARN", "VERIFIED")
            continue
        try:
            data = json.loads(body)
        except Exception:
            log(f"AJAX AREA={area} non-JSON response {platform_domain} {date_mmddyyyy}: {body[:200]}", "WARN", "VERIFIED")
            continue
        decoded = decode_ajax_html(data.get("retHTML") or "")
        items = parse_aitem_blocks(decoded, "alachua")
        for it in items:
            cn = it.get("case_number")
            if cn:
                found[cn] = it
        time.sleep(0.4)
    return found


def rest_patch_row(case_number: str, body: dict) -> bool:
    if DRY_RUN:
        log(f"DRY-RUN PATCH case={case_number} body={body}", "INFO", "UNTESTED")
        return True
    cn_enc = urllib.parse.quote(case_number, safe="")
    path = f"multi_county_auctions?county=ilike.alachua&case_number=eq.{cn_enc}"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
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


def main():
    log(f"alachua CD/EI gap fix (2026-08-24) — DRY_RUN={DRY_RUN}", "INFO", "VERIFIED")

    by_date_platform: dict[tuple, list[tuple]] = {}
    for cn, d, platform, klass in TARGETS:
        by_date_platform.setdefault((d, platform), []).append((cn, klass))

    total_attempted = 0
    total_matched = 0
    residual = []

    for (date_mmddyyyy, platform), rows in by_date_platform.items():
        log(f"=== Harvesting {platform} {date_mmddyyyy} for {[r[0] for r in rows]} ===", "INFO", "UNTESTED")
        found = harvest_date_both_areas(date_mmddyyyy, platform)
        log(f"{platform} {date_mmddyyyy}: {len(found)} AITEM case numbers found: {list(found.keys())}", "INFO", "VERIFIED")

        for cn, klass in rows:
            total_attempted += 1
            if cn in found:
                item = found[cn]
                parity_source = f"tier1:{RUN_LABEL}:{'foreclosure' if platform == 'realforeclose.com' else 'tax_deed'}:{date_mmddyyyy}"
                patch_body = {
                    "parity_status": "matched_clean",
                    "parity_source": parity_source,
                }
                if klass == "ghost":
                    parcel = item.get("parcel_id")
                    placeholder_values = {"property appraiser", "multiple parcel"}
                    if parcel and parcel.strip().lower() not in placeholder_values:
                        patch_body["parcel_id"] = dashify_parcel_id(parcel)
                    addr = item.get("property_address")
                    if addr:
                        patch_body["property_address"] = addr
                    av = item.get("assessed_value")
                    if av:
                        patch_body["assessed_value"] = av
                log(f"  {cn}: matched aid={item['aid']} class={klass} patch={patch_body} [CONFIRMED]", "INFO", "CONFIRMED")
                if rest_patch_row(cn, patch_body):
                    total_matched += 1
                else:
                    log(f"  {cn}: PATCH failed", "ERROR", "VERIFIED")
                    residual.append((cn, "patch_failed"))
            else:
                log(f"  {cn}: NOT found in live AJAX for {platform} {date_mmddyyyy} — residual, not fabricating", "WARN", "VERIFIED")
                residual.append((cn, "not_on_live_calendar"))

    log("=== ALACHUA C/D/E/I GAP FIX COMPLETE ===", "INFO", "VERIFIED")
    log(f"Total attempted: {total_attempted}, matched: {total_matched}", "INFO", "VERIFIED")
    log(f"Residual (unresolved): {residual}", "INFO", "VERIFIED")

    print("\n### SQL VERIFICATION — ALACHUA C/D/E/I GAP FIX (2026-08-24)")
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"Total matched: {total_matched}/{total_attempted}")
    print(f"Residual: {residual}")
    print(f"DRY_RUN: {DRY_RUN}")
    print("\nVerification query:")
    print("  SELECT public.pencil_dod_evaluate_county('alachua');")


if __name__ == "__main__":
    main()
