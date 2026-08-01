#!/usr/bin/env python3
"""
Gold Standard alachua C/D gap fix (workflow run 14411591).

Root cause (CONFIRMED live 2026-08-01): the prior alachua matcher
(scripts/alachua_shard10_run6253_cd_harvest.py) only queries AREA=W on
alachua.realforeclose.com and only ever targets the foreclosure platform.
Two structural gaps left 5 rows with parity_status IS NULL:
  1. Case 01 2025 CA 002643 (auction_date 2026-07-23) lives in AREA=C on
     alachua.realforeclose.com -- AREA=W returns empty for that date.
  2. Cases 01 2025 CA 003415 (foreclosure, AREA=W, 2026-09-01) and
     TD 2026-020/021/022 (tax_deed, AREA=W, 2026-09-15 on
     alachua.realtaxdeed.com -- a different platform domain entirely) were
     never queried because the prior matcher only harvests dates strictly
     before today and only the foreclosure domain.

This script reuses the proven harvester functions verbatim from
scripts/shard2_run2450_ajax_realforeclose_harvest.py (fetch, decode_ajax_html,
parse_aitem_blocks -- the AREA-looping, multi-platform-capable harvester
already used successfully for dozens of other alachua matched_clean rows,
e.g. parity_source LIKE 'tier1:shard14_2a2b2667_ajax_harvest:%'). It does NOT
reimplement AJAX decoding or parsing.

All 5 target rows are confirmed live on the RealForeclose/RealTaxDeed public
auction calendar (case_number matches an AITEM block for the row's own
auction_date) -- consistent with parity_status='matched_clean' semantics
already used pipeline-wide for upcoming (not-yet-sold) auctions with a
confirmed live calendar listing.

None of the 5 rows are PropertyOnion-sourced (data_source is NULL or
'calendar_sweep_mca_v3' for all 5, verified via live query) -- no PropertyOnion
exclusion-rule conflict.

Honesty markers: CONFIRMED = case_number matched against live AJAX response.
"""
from __future__ import annotations
import json
import os
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
RUN_LABEL = "shard_run14411591_alachua_cd_gap_fix"

# (case_number, auction_date MM/DD/YYYY, platform_domain)
TARGETS = [
    ("01 2025 CA 002643", "07/23/2026", "realforeclose.com"),
    ("01 2025 CA 003415", "09/01/2026", "realforeclose.com"),
    ("TD 2026-020", "09/15/2026", "realtaxdeed.com"),
    ("TD 2026-021", "09/15/2026", "realtaxdeed.com"),
    ("TD 2026-022", "09/15/2026", "realtaxdeed.com"),
]


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def harvest_date_both_areas(date_mmddyyyy: str, platform_domain: str) -> dict:
    """Returns {case_number: aid} for all AITEM blocks found across AREA W+C."""
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
            continue
        try:
            data = json.loads(body)
        except Exception:
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
    log(f"alachua C/D gap fix (run14411591) — DRY_RUN={DRY_RUN}", "INFO", "VERIFIED")

    # Group targets by (date, platform) to avoid re-fetching the same calendar page
    by_date_platform: dict[tuple, list[str]] = {}
    for cn, d, platform in TARGETS:
        by_date_platform.setdefault((d, platform), []).append(cn)

    total_attempted = 0
    total_matched = 0

    for (date_mmddyyyy, platform), case_numbers in by_date_platform.items():
        log(f"=== Harvesting {platform} {date_mmddyyyy} for {case_numbers} ===", "INFO", "UNTESTED")
        found = harvest_date_both_areas(date_mmddyyyy, platform)
        log(f"{platform} {date_mmddyyyy}: {len(found)} AITEM case numbers found", "INFO", "VERIFIED")

        for cn in case_numbers:
            total_attempted += 1
            if cn in found:
                item = found[cn]
                parity_source = f"tier1:{RUN_LABEL}:{'foreclosure' if platform == 'realforeclose.com' else 'tax_deed'}:{date_mmddyyyy}"
                patch_body = {
                    "parity_status": "matched_clean",
                    "parity_source": parity_source,
                }
                parcel = item.get("parcel_id")
                if parcel and parcel.strip().lower() != "property appraiser":
                    patch_body["parcel_id"] = parcel
                log(f"  {cn}: matched aid={item['aid']} [CONFIRMED]", "INFO", "CONFIRMED")
                if rest_patch_row(cn, patch_body):
                    total_matched += 1
                else:
                    log(f"  {cn}: PATCH failed", "ERROR", "VERIFIED")
            else:
                log(f"  {cn}: NOT found in live AJAX for {platform} {date_mmddyyyy} — residual, not fabricating", "WARN", "VERIFIED")

    log("=== ALACHUA C/D GAP FIX COMPLETE ===", "INFO", "VERIFIED")
    log(f"Total attempted: {total_attempted}, matched: {total_matched}", "INFO", "VERIFIED")

    if total_attempted > 0 and total_matched == 0:
        raise RuntimeError(f"Silent failure: {total_attempted} rows attempted but 0 matched/written")

    print("\n### SQL VERIFICATION — ALACHUA C/D GAP FIX (run14411591)")
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"Total matched: {total_matched}/{total_attempted}")
    print(f"DRY_RUN: {DRY_RUN}")
    print("\nVerification query:")
    print("  SELECT public.pencil_dod_evaluate_county('alachua');")


if __name__ == "__main__":
    main()
