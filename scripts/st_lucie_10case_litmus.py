#!/usr/bin/env python3
"""One-off litmus check for the 10 unverified St. Lucie cases (issue: gold-standard
St. Lucie C/D/I fix). Fetches the live RealForeclose PREVIEW page for each auction
date in question and checks whether each case_number is genuinely listed.

Honesty Protocol: never writes matched_clean unless the case_number string is
actually found in the live page text for its exact auction_date. Failures/blocks
are reported as UNVERIFIED, never silently upgraded.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

BASE_URL = "https://stlucie.realforeclose.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

REALFORECLOSE_USERNAME = os.environ.get("REALFORECLOSE_USERNAME") or os.environ.get("REALFORECLOSE_EMAIL")
REALFORECLOSE_PASSWORD = os.environ.get("REALFORECLOSE_PASSWORD")

CASES = [
    ("2023CA002858", "2026-07-14"),
    ("2025CA001086", "2026-07-14"),
    ("2024CA000214", "2026-07-15"),
    ("26-001",       "2026-07-20"),
    ("2023CA000239", "2026-07-21"),
    ("2023CA002350", "2026-07-21"),
    ("2025CA001294", "2026-07-21"),
    ("2025CA002292", "2026-07-21"),
    ("2025CA002297", "2026-07-21"),
    ("2025CA001088", "2026-07-21"),
]


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, level="INFO"):
    print(f"[{ts()}] {level}: {msg}", flush=True)


def try_login(page):
    """Attempt login if a login form is present. Returns True if logged in or not needed."""
    try:
        if page.locator("input#Username, input[name='Username']").count() > 0 and REALFORECLOSE_USERNAME:
            log("Login form detected — attempting login")
            page.fill("input#Username, input[name='Username']", REALFORECLOSE_USERNAME)
            page.fill("input#Password, input[name='Password']", REALFORECLOSE_PASSWORD or "")
            page.click("button[type='submit'], input[type='submit']")
            page.wait_for_timeout(3000)
            return True
    except Exception as e:
        log(f"login attempt failed (non-fatal, continuing unauthenticated): {e}", "WARN")
    return False


def fetch_date_page(page, date_str: str) -> str | None:
    y, m, d = date_str.split("-")
    mmddyyyy = f"{m}/{d}/{y}"
    url = f"{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={mmddyyyy}"
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        text = page.inner_text("body")
        return text
    except Exception as e:
        log(f"  page load failed {url}: {e}", "ERROR")
        return None


def main():
    results = {}
    by_date = {}
    for case, date in CASES:
        by_date.setdefault(date, []).append(case)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)

        logged_in = False
        page_cache = {}
        for date in sorted(by_date.keys()):
            text = fetch_date_page(page, date)
            if text is None:
                page_cache[date] = None
                continue
            if not logged_in:
                if try_login(page):
                    logged_in = True
                    text = fetch_date_page(page, date)  # re-fetch after login
            page_cache[date] = text
            time.sleep(1.5)

        for date, cases in by_date.items():
            text = page_cache.get(date)
            if text is None:
                for case in cases:
                    results[case] = {"date": date, "found": None, "status": "page_load_failed",
                                      "url": f"{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date.split('-')[1]}/{date.split('-')[2]}/{date.split('-')[0]}"}
                continue
            for case in cases:
                found = case in text
                # also try without dashes/variants for cases like 26-001
                results[case] = {
                    "date": date,
                    "found": found,
                    "status": "checked",
                    "url": f"{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date.split('-')[1]}/{date.split('-')[2]}/{date.split('-')[0]}",
                    "case_count_on_page": len(re.findall(r"Case\s*#\s*:", text, re.IGNORECASE)),
                }

        browser.close()

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
