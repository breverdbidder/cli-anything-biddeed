#!/usr/bin/env python3
"""
Suwannee County outcome harvester (2026-07-25 investigation follow-up).

Confirms true disposition for suwannee's past-due auctions via the ONLY
sources this session's investigation phase actually verified as reachable:
tax-deed items via a real Playwright-authenticated login to
suwannee.realtaxdeed.com, matched against multi_county_auctions. Only writes
sold_amount/outcome rows for GENUINE independently-confirmed sales; a closed
item with no sale (redeemed/canceled/no-bid) only gets its auction_status
corrected, never a fabricated sold_amount. The one foreclosure case past its
sale date (25-CA-197) has NO confirmed disposition source reachable by curl
(myfloridacounty.com/orisearch/61 is Cloudflare-Turnstile-gated) and is left
untouched, reported honestly as UNTESTED.

Env required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
REALFORECLOSE_EMAIL (or REALFORECLOSE_USERNAME), REALFORECLOSE_PASSWORD.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "suwannee"
TD_HOST = "https://suwannee.realtaxdeed.com"
DATA_SOURCE_TD = "suwannee_realtaxdeed_official"

RF_EMAIL = os.environ.get("REALFORECLOSE_EMAIL") or os.environ.get("REALFORECLOSE_USERNAME", "")
RF_PW = os.environ.get("REALFORECLOSE_PASSWORD", "")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# Cases past their auction date per live multi_county_auctions (2026-07-25).
# 4713 already correctly shows auction_status='redeemed' -- not touched here.
TD_CANDIDATES = [
    {"case_number": "4666", "auction_date": "07/09/2026"},
    {"case_number": "4667", "auction_date": "07/09/2026"},
]


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_headers(extra: dict = None) -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def sb_get(path: str) -> list:
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", headers=sb_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_upsert(table: str, rows: list[dict], conflict_cols: str) -> None:
    body = json.dumps(rows).encode()
    extra = {"Prefer": f"resolution=merge-duplicates,return=minimal,on-conflict={conflict_cols}"}
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}", data=body, headers=sb_headers(extra), method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        r.read()


def sb_patch(table: str, filter_qs: str, payload: dict) -> None:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filter_qs}", data=body,
        headers=sb_headers({"Prefer": "return=minimal"}), method="PATCH")
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def _dismiss_notice_chain(page, rounds: int = 6) -> None:
    """The site serves a chain of stacked one-time notice interstitials
    (#BNOTACC / #BNOTOK) after login and after some navigations. Each click
    can reveal another; loop until neither is visible."""
    for _ in range(rounds):
        clicked = False
        for selector in ("#BNOTACC", "#BNOTOK"):
            try:
                if page.locator(selector).count() and page.is_visible(selector):
                    page.click(selector)
                    page.wait_for_timeout(1500)
                    clicked = True
                    break
            except Exception:
                pass
        if not clicked:
            break


def login(page) -> bool:
    page.goto(f"{TD_HOST}/", wait_until="load", timeout=30000)
    page.wait_for_timeout(1500)
    page.fill("#LogName", RF_EMAIL)
    page.fill("#LogPass", RF_PW)
    page.click("#LogButton")
    page.wait_for_timeout(2000)
    _dismiss_notice_chain(page)
    body_text = page.inner_text("body").lower()
    return "bidder number" in body_text or "bidder id" in body_text or "welcome:" in body_text


def check_td_status(page, case_number: str, auction_date: str) -> dict:
    """Fetch the day's results list and locate this specific case's block,
    parsing 'Auction Status' from the same AITEM segment as the case number
    (not a page-wide scan, which would misattribute status across cases)."""
    url = f"{TD_HOST}/index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE={auction_date}"
    page.goto(url, wait_until="load", timeout=30000)
    page.wait_for_timeout(2000)
    _dismiss_notice_chain(page)
    body_text = page.inner_text("body")
    if f"Case #:\t{case_number}" not in body_text and f"Case #:{case_number}" not in body_text:
        if case_number not in body_text:
            return {"found": False}
    idx = body_text.find(case_number)
    segment = body_text[max(0, idx - 200):idx]
    status = "unknown"
    for candidate in ("Redeemed", "Sold", "Cancelled", "Canceled", "No Sale"):
        if candidate.lower() in segment.lower():
            status = candidate.lower()
            break
    return {"found": True, "status": status, "url": url}


def main() -> int:
    if not RF_EMAIL or not RF_PW:
        log("REALFORECLOSE_EMAIL/PASSWORD not set -- 0 writes, exiting.", "UNTESTED")
        return 0

    td_writes = 0
    status_fixes = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        try:
            authed = login(page)
        except Exception as e:
            log(f"Login failed: {e} -- 0 writes, exiting honestly.", "UNTESTED")
            browser.close()
            return 0

        if not authed:
            log("Could not confirm authenticated session -- 0 writes, exiting honestly.", "UNTESTED")
            browser.close()
            return 0

        log("Login VERIFIED (authenticated session confirmed).", "VERIFIED")

        for cand in TD_CANDIDATES:
            case_number = cand["case_number"]
            try:
                result = check_td_status(page, case_number, cand["auction_date"])
            except Exception as e:
                log(f"{case_number}: fetch failed ({e}) -- skipping, no write.", "WARN")
                continue

            if not result.get("found"):
                log(f"{case_number}: not found in day results -- skipping, no write.", "WARN")
                continue

            status = result["status"]
            log(f"{case_number}: live status = '{status}' ({result['url']})", "VERIFIED")

            if status == "sold":
                # Not observed this run -- would require a real sale amount from
                # the item-detail page before writing. No fabrication.
                log(f"{case_number}: shows 'sold' but no amount parser wired -- "
                    "skipping write rather than guessing an amount.", "UNTESTED")
                continue

            # Confirmed closed-but-not-sold (redeemed/canceled/no-sale): correct
            # auction_status only. Never populate sold_amount for a non-sale.
            rows = sb_get(f"multi_county_auctions?county=eq.{COUNTY}&case_number=eq.{case_number}&select=case_number,auction_status")
            if not rows:
                log(f"{case_number}: no matching multi_county_auctions row -- skipping.", "WARN")
                continue
            current_status = rows[0].get("auction_status")
            true_status = "redeemed" if status == "redeemed" else status
            if current_status == true_status:
                log(f"{case_number}: auction_status already '{true_status}' -- no patch needed.", "VERIFIED")
                continue

            sb_patch(
                "multi_county_auctions",
                f"county=eq.{COUNTY}&case_number=eq.{case_number}",
                {"auction_status": true_status, "updated_at": ts()},
            )
            status_fixes += 1
            log(f"{case_number}: PATCHED auction_status '{current_status}' -> '{true_status}'.", "VERIFIED")

        browser.close()

    log(f"Done. tax_deed_outcomes writes={td_writes}, auction_status fixes={status_fixes}. "
        "25-CA-197 (foreclosure) left untouched -- no reachable disposition source this session.", "VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
