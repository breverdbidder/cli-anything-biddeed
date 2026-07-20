#!/usr/bin/env python3
"""GOLD STANDARD shard-11, dispatch 52bf028c-78fe-49ad-ae77-284c02a1f201 --
gadsden H (freshness, SLA 48h) live-refresh.

ROOT CAUSE (this session): gadsden's only real data source is the bespoke
clerk-sheet scrape (gadsdenclerk.com, source_platform='custom_clerk') and it
has never been wired to any recurring executor. The two daily GHA sweeps that
list gadsden as "covered" (calendar-sweep-dark-counties.yml,
calendar-sweep-gap-counties.yml) both only query realauction_subdomains and
hit RealForeclose/RealTaxDeed URLs -- gadsden is not on that platform at all,
so gadsden rows silently never get touched by either sweep. H regressed from
43.4h (PASS) at dispatch-brief snapshot time to 51+h (FAIL) purely from
wall-clock drift with zero scraper runs in between.

THIS SCRIPT (safe to re-run daily, unlike scripts/shard8_gadsden_bootstrap.py
which is explicitly NOT idempotent and must never be used for freshness):
  1. Fetches both live clerk sheets (FC + TD) with a real browser User-Agent.
  2. Parses case_number + key fields (judgment/opening_bid amount, address,
     redeemed/sale-price status) from each live sheet.
  3. Diffs against multi_county_auctions rows for county='gadsden' by
     case_number.
  4. For every row still present on the live sheet: PATCH last_seen_at (+
     last_changed_at only if any tracked field actually changed) to now().
  5. For rows no longer on the live sheet (already-processed/dropped cases):
     leave last_seen_at untouched -- they are not confirmed live anymore, so
     bumping their freshness would be a fabricated "still there" claim. This
     is consistent with the pencil evaluator's GREATEST() freshness formula:
     H measures the county's scrape activity, not any single row's staleness.
  6. FAIL-LOUD: if either sheet parses to 0 rows, or if the update touches 0
     rows despite >0 parsed rows, this script raises and does NOT silently
     no-op.

Usage: python3 scripts/shard11_gadsden_h_freshness_fetch.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

FC_URL = "https://www.gadsdenclerk.com/Foreclosures/Foreclosures_files/sheet001.htm"
TD_URL = "https://www.gadsdenclerk.com/Tax_deeds/Tax_deeds_files/sheet001.htm"

DRY_RUN = "--dry-run" in sys.argv


def log(msg: str) -> None:
    print(msg, flush=True)


def now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200:
            raise RuntimeError(f"FAIL-LOUD: {url} returned HTTP {r.status}, not 200")
        return r.read().decode("utf-8", errors="replace")


def parse_rows(html: str, case_suffix: str) -> list[dict]:
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    out = []
    for tr in trs:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        texts = [re.sub(r"<[^>]+>", " ", c).strip() for c in cells]
        texts = [re.sub(r"\s+", " ", t).replace("&nbsp;", "").strip() for t in texts]
        joined = " ".join(texts)
        m = re.search(rf"\b(\d{{8}}{case_suffix})\b", joined)
        if m:
            out.append(texts)
    return out


def money(s: str) -> float | None:
    s = (s or "").replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def rest_get(path: str) -> list[dict]:
    req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def rest_patch(table: str, filters: str, data: dict) -> tuple[int, str]:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={**HEADERS, "Prefer": "return=minimal"}, method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_rpc(func: str, params: dict) -> dict:
    body = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/{func}", data=body, headers=HEADERS, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main() -> None:
    log("=== gadsden H freshness fetch ===")
    log(f"Fetching live FC sheet: {FC_URL}")
    fc_html = fetch(FC_URL)
    log(f"Fetching live TD sheet: {TD_URL}")
    td_html = fetch(TD_URL)

    fc_rows = parse_rows(fc_html, "CA")
    td_rows = parse_rows(td_html, "TDC")
    log(f"Parsed {len(fc_rows)} FC rows, {len(td_rows)} TD rows from live sheets")
    if len(fc_rows) == 0 or len(td_rows) == 0:
        raise RuntimeError(
            f"FAIL-LOUD: parsed 0 rows from a live sheet (fc={len(fc_rows)}, "
            f"td={len(td_rows)}) -- source structure may have changed, aborting "
            "rather than silently no-op'ing."
        )

    # Build live lookup: case_number -> (judgment_or_opening_bid, address)
    live_fc = {}
    for r in fc_rows:
        case = re.search(r"\b(\d{8}CA)\b", " ".join(r)).group(1)
        live_fc[case] = {"amount": money(r[6] if len(r) > 6 else ""), "address": r[4] if len(r) > 4 else ""}

    live_td = {}
    for r in td_rows:
        case = re.search(r"\b(\d{8}TDC)\b", " ".join(r)).group(1)
        sale_price_raw = r[9] if len(r) > 9 else ""
        redeemed = "redeemed" in sale_price_raw.lower()
        live_td[case] = {
            "opening_bid": money(r[8] if len(r) > 8 else ""),
            "address": r[6] if len(r) > 6 else "",
            "redeemed": redeemed,
        }

    db_rows = rest_get(
        "multi_county_auctions?county=eq.gadsden&select=id,case_number,sale_type,"
        "judgment_amount,opening_bid,property_address,auction_status,last_seen_at,last_changed_at"
    )
    log(f"DB has {len(db_rows)} gadsden rows")

    ts = now_iso()
    updated = 0
    skipped_dropped = []
    field_changes = []

    for row in db_rows:
        case = row["case_number"]
        sale_type = row["sale_type"]
        live = live_fc.get(case) if sale_type == "foreclosure" else live_td.get(case)
        if live is None:
            skipped_dropped.append(case)
            continue

        payload = {"last_seen_at": ts, "updated_at": ts}
        changed = False

        if sale_type == "foreclosure":
            live_amt = live["amount"]
            db_amt = row.get("judgment_amount")
            if live_amt is not None and db_amt is not None and abs(live_amt - db_amt) > 0.01:
                payload["judgment_amount"] = live_amt
                payload["opening_bid"] = live_amt
                changed = True
        else:  # tax_deed
            live_bid = live["opening_bid"]
            db_bid = row.get("opening_bid")
            if live_bid is not None and db_bid is not None and abs(live_bid - db_bid) > 0.01:
                payload["opening_bid"] = live_bid
                changed = True
            live_status = "redeemed" if live["redeemed"] else "upcoming"
            if row.get("auction_status") != live_status:
                payload["auction_status"] = live_status
                changed = True

        if changed:
            payload["last_changed_at"] = ts
            field_changes.append(case)

        log(f"  {case} ({sale_type}): still live, {'FIELD CHANGE' if changed else 'unchanged'} -> refresh last_seen_at")

        if not DRY_RUN:
            status, body = rest_patch("multi_county_auctions", f"id=eq.{row['id']}", payload)
            if status not in (200, 204):
                raise RuntimeError(f"FAIL-LOUD: PATCH failed for {case}: HTTP {status} {body}")
        updated += 1

    log(f"Matched-and-refreshed: {updated} of {len(db_rows)} rows")
    log(f"Dropped from live sheet (left untouched, not bumped): {skipped_dropped}")
    log(f"Real field changes applied: {field_changes if field_changes else 'none'}")

    if updated == 0:
        raise RuntimeError(
            "FAIL-LOUD: parsed >0 rows on both live sheets but updated 0 DB rows -- "
            "this would be a silent no-op, aborting instead of pretending success."
        )

    if DRY_RUN:
        log("DRY RUN -- no writes performed.")
        return

    log("Verifying persisted last_seen_at...")
    check = rest_get(
        "multi_county_auctions?county=eq.gadsden&select=case_number,last_seen_at&order=case_number"
    )
    stale = [c["case_number"] for c in check if c["last_seen_at"] < ts]
    still_stale_but_matched = [c for c in stale if c not in skipped_dropped]
    if still_stale_but_matched:
        raise RuntimeError(
            f"FAIL-LOUD: post-write verify shows rows still stale despite being "
            f"matched live: {still_stale_but_matched}"
        )
    log("VERIFIED: all live-matched rows now carry last_seen_at >= this run's timestamp.")

    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": "gadsden"})
    log("Post-refresh pencil_dod_evaluate_county('gadsden'):")
    log(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
