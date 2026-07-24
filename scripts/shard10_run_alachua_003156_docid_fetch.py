#!/usr/bin/env python3
"""
Shard-10 Gold Standard, case 01 2025 CA 003156 (alachua).
Fetch isol.alachuaclerk.org SearchDetail.aspx?docid=3696051 via Playwright
headless Chromium (page lazy-loads via client JS per prior session findings).
Extract grantor/grantee + legal description for E/I/J parcel research.
Read-only reconnaissance. No DB writes.
"""
import json
from playwright.sync_api import sync_playwright

DOCID = "3696051"
URL = f"http://isol.alachuaclerk.org/RealEstate/SearchDetail.aspx?docid={DOCID}&ms=0"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        try:
            page.goto(URL, wait_until="networkidle", timeout=45000)
        except Exception as e:
            print(f"goto error: {e}")
        page.wait_for_timeout(3000)

        # Dump full rendered text
        body_text = page.inner_text("body")
        print("=== BODY TEXT (General tab) ===")
        print(body_text[:6000])

        # Click "Legal Description" tab
        try:
            page.click("text=Legal Description", timeout=10000)
            page.wait_for_timeout(3000)
            legal_text = page.inner_text("body")
            print("\n=== BODY TEXT (Legal Description tab) ===")
            print(legal_text[:6000])
            with open("/tmp/alachua_003156_legal_page.html", "w") as f:
                f.write(page.content())
        except Exception as e:
            print(f"Legal Description tab click error: {e}")

        # Try to find tabs - Legal Description tab
        html = page.content()
        with open("/tmp/alachua_003156_docid_page.html", "w") as f:
            f.write(html)
        print("\n=== HTML length ===", len(html))

        browser.close()

if __name__ == "__main__":
    main()
