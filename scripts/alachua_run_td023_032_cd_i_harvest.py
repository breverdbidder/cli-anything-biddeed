#!/usr/bin/env python3
"""Gold Standard alachua C/D/I harvest for TD 2026-023..032 (10 rows).

Reuses fetch/decode_ajax_html/parse_aitem_blocks verbatim from
scripts/shard2_run2450_ajax_realforeclose_harvest.py (proven working method,
see commit 846bcc0a for TD 2026-020/021/022 precedent on this exact platform).
"""
import json
import os
import sys
import time
import urllib.parse
import http.cookiejar

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shard2_run2450_ajax_realforeclose_harvest import fetch, decode_ajax_html, parse_aitem_blocks

TARGET_DATES = ["09/15/2026", "09/22/2026", "10/06/2026"]
PLATFORM = "realtaxdeed.com"
SUBDOMAIN = "alachua"


def harvest_date_both_areas(date_mmddyyyy):
    base = f"https://{SUBDOMAIN}.{PLATFORM}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    status, _ = fetch(preview_url, jar)
    print(f"  PREVIEW {date_mmddyyyy}: status={status}")
    if status != 200:
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
            print(f"    AREA={area} fetch failed: {e}")
            continue
        print(f"    AREA={area}: status={status} len={len(body)}")
        if status != 200:
            continue
        try:
            data = json.loads(body)
        except Exception as e:
            print(f"    AREA={area} JSON parse failed: {e} body[:200]={body[:200]!r}")
            continue
        ret_html = data.get("retHTML") or ""
        decoded = decode_ajax_html(ret_html)
        items = parse_aitem_blocks(decoded, "alachua")
        print(f"    AREA={area}: {len(items)} AITEM blocks found")
        for it in items:
            cn = it.get("case_number")
            if cn:
                found[cn] = it
        time.sleep(0.4)
    return found


all_found = {}
for d in TARGET_DATES:
    print(f"=== {d} ===")
    all_found.update(harvest_date_both_areas(d))

print()
print(f"TOTAL cases found across all dates: {len(all_found)}")
for cn, it in sorted(all_found.items()):
    print(json.dumps({"case_number": cn, **{k: v for k, v in it.items() if k != "case_number"}}, default=str))

with open("/tmp/alachua_harvest_result.json", "w") as f:
    json.dump(all_found, f, indent=2, default=str)
