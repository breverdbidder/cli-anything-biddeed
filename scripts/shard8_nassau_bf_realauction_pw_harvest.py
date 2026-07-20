#!/usr/bin/env python3
"""SHARD-8 (marion/nassau, dispatch 0ddd603c): nassau B/F fix via Playwright
live render of nassauclerk.realforeclose.com (2026-07-20).

BACKGROUND: two prior sessions (scripts/shard_nassau_run_cd_bf_reharvest.py,
scripts/shard7_run2753_nassau_bf_c_blocked_diagnosis.py) correctly diagnosed
B/F as BLOCKED because the sold-status widget (ASTAT_MSGA/B/C/D,
ASTAT_MSG_SOLDTO_*) only exists in the client-side-JS-rendered PREVIEW page,
not in the bare-HTTP AJAX response, and Firecrawl (the only headless-render
tool those sessions had) was 402 Insufficient Credits fleet-wide. That correct
diagnosis stands: no sold_amount was fabricated, verified=0/closed_sold=0 was
left honest. Firecrawl is STILL out of credits today (re-verified live before
writing this script). This script unblocks the SAME data via a different
render path: the `playwright` package + chromium browser are locally
installed in this environment (not previously available/attempted) and
render the identical PREVIEW page client-side, exposing the same
ASTAT_MSGA/B/C/D + ASTAT_MSG_SOLDTO_MSG markup Firecrawl would have.

METHOD: for each of nassau's 13 distinct past auction_dates (29 foreclosure
cases total, all sale_type=foreclosure -- nassau has 0 past tax_deed cases),
render https://nassauclerk.realforeclose.com/index.cfm?zaction=AUCTION&
Zmethod=PREVIEW&AuctionDate=MM/DD/YYYY with Playwright/Chromium, parse the
"Auctions Closed or Canceled" (Area_C) AITEM blocks, and match case_number
against our known 29. Only rows whose live ASTAT_MSGA == "Auction Sold" AND
carry a parsed dollar ASTAT_MSGD amount are written as sold outcomes --
Canceled/Redeemed/other statuses are left untouched (sold_amount stays NULL),
exactly matching the honest-blocked precedent this script continues.

WRITES (idempotent, WHERE sold_amount IS NULL guards):
  1. UPDATE multi_county_auctions: sold_amount, sold_amount_source,
     sold_amount_captured_at, tier1_sold_amount, tier1_sale_status='sold',
     tier1_authoritative=true, tier1_verified_at.
  2. INSERT foreclosure_outcomes: case_number, county, sale_type,
     auction_date, winning_bid, outcome, winner_name, winner_type,
     data_source='realauction_live:nassau_pw_harvest_20260720' (independent,
     NOT propertyonion, NOT promote -- satisfies pencil_dod_evaluate_county's
     B numerator EXISTS clause).

Fail-loud (HARD GUARDRAILS #2): if any PREVIEW page is fetched successfully
(parsed>0 AITEMs) but zero of our 29 case numbers are found across ALL dates,
raise -- that would indicate a parsing regression, not genuine absence.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "nassau"
DATA_SOURCE_TAG = "realauction_live:nassau_pw_harvest_20260720"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")


def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body, prefer="return=representation"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()) if prefer.startswith("return=representation") else None


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


STATUS_RE = re.compile(r'<div class="ASTAT_MSGA ASTAT_LBL">([^<]*)</div>')
AMOUNT_RE = re.compile(r'<div class="ASTAT_MSGD Astat_DATA">([^<]*)</div>')
SOLDTO_RE = re.compile(r'<div class="ASTAT_MSG_SOLDTO_MSG Astat_DATA">([^<]*)</div>')
CASE_RE = re.compile(r'Case Number">Case #:</td>\s*<td[^>]*>\s*(?:<a[^>]*>)?\s*([A-Z0-9]+)')


def parse_closed_area(html):
    """Extract AITEM blocks from the 'Auctions Closed or Canceled' (Area_C) section only."""
    m = re.search(r'<div id="Area_C"[^>]*>(.*?)<div class="Head_C"|<div id="Area_C"[^>]*>(.*)$', html, re.S)
    if not m:
        return []
    area_html = m.group(1) or m.group(2) or ""
    items = []
    for am in re.finditer(r'<div id="AITEM_(\d+)"[^>]*>(.*?)(?=<div id="AITEM_|\Z)', area_html, re.S):
        aid, body = am.group(1), am.group(2)
        status_m = STATUS_RE.search(body)
        case_m = CASE_RE.search(body)
        amount_m = AMOUNT_RE.search(body)
        soldto_m = SOLDTO_RE.search(body)
        items.append({
            "aid": aid,
            "status": (status_m.group(1).strip() if status_m else None),
            "case_number": (case_m.group(1).strip() if case_m else None),
            "amount_raw": (amount_m.group(1).strip() if amount_m else None),
            "sold_to": (soldto_m.group(1).strip() if soldto_m else None),
        })
    return items


def to_float(amount_raw):
    if not amount_raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", amount_raw)
    return float(cleaned) if cleaned else None


def main():
    log("=== SHARD-8 NASSAU B/F FIX (RealAuction live Playwright render) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE B: {baseline['B']}", "VERIFIED")
    log(f"BASELINE F: {baseline['F']}", "VERIFIED")

    rows = rest_get(
        "multi_county_auctions?select=id,case_number,sale_type,auction_date,sold_amount"
        f"&county=eq.{COUNTY}&auction_date=lt.now()&sold_amount=is.null"
        "&order=auction_date.asc"
    )
    rows = [r for r in rows if r.get("case_number")]
    log(f"target rows (past auction_date, sold_amount NULL): {len(rows)}", "VERIFIED")
    by_case = {r["case_number"].upper(): r for r in rows}

    dates = sorted({r["auction_date"][:10] for r in rows})
    log(f"distinct auction dates to render: {len(dates)} -> {dates}", "VERIFIED")

    found = {}
    total_aitems = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)
        for d in dates:
            y, m, day = d.split("-")
            mmddyyyy = f"{m}/{day}/{y}"
            url = f"https://nassauclerk.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate={mmddyyyy}"
            try:
                page.goto(url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(2000)
                html = page.content()
            except Exception as exc:
                log(f"{d}: FETCH FAILED {exc}", "UNTESTED")
                continue
            items = parse_closed_area(html)
            total_aitems += len(items)
            log(f"{d}: {len(items)} closed/canceled AITEMs parsed", "VERIFIED")
            for it in items:
                cn = (it["case_number"] or "").upper()
                if cn in by_case:
                    found[cn] = {**it, "url": url, "auction_date": d}
        browser.close()

    log(f"total AITEMs parsed across {len(dates)} dates: {total_aitems}", "VERIFIED")
    if total_aitems > 0 and not found:
        raise RuntimeError(
            "FAIL-LOUD: parsed>0 AITEMs across all dates but matched 0 of our "
            f"{len(rows)} target case numbers -- parsing regression, not genuine absence."
        )

    sold_matches = {cn: v for cn, v in found.items() if v["status"] == "Auction Sold" and to_float(v["amount_raw"])}
    log(f"matched {len(found)}/{len(rows)} target cases in closed/canceled area; "
        f"{len(sold_matches)} are 'Auction Sold' with a parsed dollar amount", "VERIFIED")
    for cn, v in found.items():
        if cn not in sold_matches:
            log(f"  {cn}: status='{v['status']}' amount_raw='{v['amount_raw']}' -> not counted (not sold or no amount)", "VERIFIED")

    now_iso = ts()
    mca_patched = 0
    outcomes_inserted = 0
    for cn, v in sold_matches.items():
        amt = to_float(v["amount_raw"])
        row = by_case[cn]
        rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {
            "sold_amount": amt,
            "sold_amount_source": DATA_SOURCE_TAG,
            "sold_amount_captured_at": now_iso,
            "tier1_sold_amount": amt,
            "tier1_sale_status": "sold",
            "tier1_authoritative": True,
            "tier1_verified_at": now_iso,
        })
        mca_patched += 1
        log(f"  PATCHED mca case={cn} sold_amount={amt}", "VERIFIED")

        rest_post("foreclosure_outcomes", {
            "case_number": cn,
            "county": COUNTY,
            "sale_type": "foreclosure",
            "auction_date": v["auction_date"],
            "winning_bid": amt,
            "outcome": "sold",
            "winner_name": v.get("sold_to"),
            "winner_type": v.get("sold_to"),
            "data_source": DATA_SOURCE_TAG,
            "source_url": v["url"],
            "enriched_at": now_iso,
        }, prefer="return=minimal")
        outcomes_inserted += 1

    log(f"mca_patched={mca_patched} outcomes_inserted={outcomes_inserted}", "VERIFIED")

    promoted = rpc("promote_tier1_from_outcomes", {})
    log(f"promote_tier1_from_outcomes: {promoted}", "VERIFIED")

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER B: {after['B']}", "VERIFIED")
    log(f"AFTER F: {after['F']}", "VERIFIED")

    print("\n=== SQL VERIFICATION ===")
    print(f"-- {now_iso}")
    print("SELECT county, sold_amount_source, COUNT(*) FROM multi_county_auctions "
          "WHERE county='nassau' AND sold_amount IS NOT NULL GROUP BY county, sold_amount_source;")
    print(f"mca_patched={mca_patched} outcomes_inserted={outcomes_inserted}")
    print(f"BASELINE B={baseline['B']} F={baseline['F']}")
    print(f"AFTER    B={after['B']} F={after['F']}")


if __name__ == "__main__":
    main()
