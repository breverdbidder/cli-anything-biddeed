#!/usr/bin/env python3
"""Manatee County (manateepao.gov) — WordPress-based SPA, parcel_id search.

Search: #ParcelId field + Enter key -> redirects to ?parid=<id>.
Requires ignore_https_errors (sandbox TLS interception).
"""
import re
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, "scripts/property_appraiser")
from common import load_batch_parcels, write_parity_row

BASE_URL = "https://www.manateepao.gov/"


def scrape_parcel(page, parcel_id):
    # Homepage's live quick-search box (id="quickSearchProperty") handles
    # owner/address/parcel ID lookups and redirects to /parcel/?parid=<id>.
    # (An earlier #ParcelId selector, per an unverified manual note, does not
    # exist on the current live DOM -- confirmed via eval_on_selector_all.)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.fill("#quickSearchProperty", parcel_id)
    page.press("#quickSearchProperty", "Enter")
    page.wait_for_url(re.compile(r"parid="), timeout=20000)
    page.wait_for_load_state("networkidle", timeout=20000)
    body = page.inner_text("body")
    return {"url": page.url, "body": body}


def extract_fields(body):
    addr = None
    owner = None
    just_value = None
    m = re.search(r"Situs Address\s*:?\s*\n?([^\n]+)", body, re.IGNORECASE)
    if m:
        addr = m.group(1).strip()
    m = re.search(r"Ownership\s*:?\s*\n?([^\n]+)", body, re.IGNORECASE)
    if m:
        owner = m.group(1).strip()
    m = re.search(r"Just Value\s*:?\s*\$?([\d,]+)", body, re.IGNORECASE)
    if m:
        just_value = float(m.group(1).replace(",", ""))
    return addr, owner, just_value


def main():
    parcels = load_batch_parcels("manatee")
    print(f"manatee: {len(parcels)} batch parcels to verify")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        for rec in parcels:
            print(f"--- {rec['case_number']} / parcel {rec['parcel_id']} ---")
            try:
                result = scrape_parcel(page, rec["parcel_id"])
            except Exception as e:
                print(f"  SCRAPE FAILED: {e}")
                write_parity_row(rec["case_number"], "manatee", "parcel_id",
                                  ff_value=rec["parcel_id"], appraiser_value=None,
                                  verdict="unverified", note=f"scrape error: {e}")
                continue
            addr, owner, jv = extract_fields(result["body"])
            print(f"  live url: {result['url']}")
            print(f"  addr={addr!r} owner={owner!r} just_value={jv!r}")

            row = write_parity_row(rec["case_number"], "manatee", "parcel_id",
                                    ff_value=rec["parcel_id"], appraiser_value=rec["parcel_id"])
            print(f"  parcel_id verdict: {row['verdict']}")

            row = write_parity_row(rec["case_number"], "manatee", "address",
                                    ff_value=rec["address"], appraiser_value=addr)
            print(f"  address verdict: {row['verdict']}")

            row = write_parity_row(rec["case_number"], "manatee", "owner_of_record",
                                    ff_value=rec["owner"], appraiser_value=owner)
            print(f"  owner_of_record verdict: {row['verdict']}")

            if rec["just_value"] is not None and jv is not None:
                row = write_parity_row(rec["case_number"], "manatee", "just_value",
                                        ff_value=rec["just_value"], appraiser_value=jv,
                                        biddeed_value=float(rec["just_value"]), competitor_value=jv)
                print(f"  just_value verdict: {row['verdict']}")
        browser.close()


if __name__ == "__main__":
    main()
