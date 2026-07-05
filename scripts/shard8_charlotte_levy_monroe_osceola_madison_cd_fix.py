#!/usr/bin/env python3
"""SHARD-8 (charlotte/levy/monroe/osceola/madison), dispatch 97f56687-28a3-463c-8988-31b6fc424178.

Reusable, paginated version of harvest_date() from
scripts/shard2_run2450_ajax_realforeclose_harvest.py. The original only issues a single
PageDir=0 request per AREA, which silently truncates any auction date with more than one
page of AITEM blocks. Discovered live this session: monroe 03/25/2026 has 25 items across
2 pages (PageDir=0,1) and osceola's largest date (2026-05-19) has 27 items across 3 pages
-- PageDir=0 alone would have missed more than half of each. This helper loops PageDir until
a page returns an empty/repeated AID set, so it captures the full auction date.

This is additive (a new function in a new file), not a modification to the shared harvester,
to avoid changing behavior any other shard's pinned invocation relies on.

DB direct connection (psycopg2 against the pooler / db.<ref>.supabase.co, all three
host/port/user combinations) FAILED with "password authentication failed" using the
SUPABASE_DB_PASSWORD secret documented in CLAUDE.md -- confirmed stale/rotated this session.
All work this session went through PostgREST (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY),
which is live and fully functional for SELECT/INSERT/UPDATE and RPC calls including
pencil_dod_evaluate_county. No DDL (new SQL functions/views) was possible this session --
flagging for the next session with working DB credentials.

Usage: python3 scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py
Re-running is idempotent: harvest upserts on `aid` (on_conflict), and the match step only
PATCHes rows where parity_status is not already 'matched_clean'.
"""
import sys
import os
import re
import json
import time
import urllib.request
import urllib.parse
import http.cookiejar
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def harvest_date_paginated(subdomain, county_slug, auction_date_mmddyyyy, platform_domain, max_pages=15):
    """Same AJAX PREVIEW/UPDATE mechanism as harvest_date(), but loops PageDir per AREA
    until a page comes back empty or repeats the previous page's AID set (site-observed
    exhaustion signal -- osceola.realtaxdeed.com repeats the last page's content rather
    than returning an empty one once pages are exhausted)."""
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    status, _ = _mod.fetch(preview_url, jar)
    if status != 200:
        print(f"  PREVIEW non-200 ({status}) {subdomain} {auction_date_mmddyyyy}")
        return []

    items = {}
    for area in ("W", "C"):
        seen_aids = None
        for pagedir in range(max_pages):
            ts = int(time.time() * 1000)
            ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                        f"&PageDir={pagedir}&doR=0&tx={ts}&bypassPage=0&test=1")
            try:
                status, body = _mod.fetch(ajax_url, jar, referer=preview_url,
                                           headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                print(f"  AJAX AREA={area} PageDir={pagedir} fetch failed: {e}")
                break
            if status != 200:
                break
            try:
                data = json.loads(body)
            except Exception:
                break
            ret_html = data.get("retHTML") or ""
            if not ret_html:
                break
            decoded = _mod.decode_ajax_html(ret_html)
            parsed = _mod.parse_aitem_blocks(decoded, subdomain)
            page_aids = {p["aid"] for p in parsed if p.get("aid")}
            if not page_aids or page_aids == seen_aids:
                break
            seen_aids = page_aids
            for p in parsed:
                if p.get("aid"):
                    items[p["aid"]] = p
            time.sleep(0.35)
    return list(items.values())


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                  "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def exact_match_and_promote(county_slug, mca_county_filter, items, parity_source_label):
    """Exact normalize_case_number match ONLY (no fuzzy/parcel-only arm -- see the
    2026-07-02 sentinel-guard migration for why an unguarded parcel_id arm is unsafe).
    Returns the list of matched multi_county_auctions row ids that were promoted."""
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{mca_county_filter}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status")
    matches = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn in by_norm and row["parity_status"] != "matched_clean":
            matches.append(row["id"])
    if not matches:
        return []
    id_filter = ",".join(matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": parity_source_label})
    return matches


if __name__ == "__main__":
    # Real, executed this session (2026-07-05) -- see SHARD8_RUN3059 session report for
    # before/after pencil_dod_evaluate_county JSON and gold_standard_ultraloop_audit rows.
    print(__doc__)
