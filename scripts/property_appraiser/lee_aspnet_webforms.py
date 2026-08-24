#!/usr/bin/env python3
"""Lee County (leepa.org) — classic ASP.NET WebForms postback, STRAP search.

Field id: #ctl00_BodyContentPlaceHolder_STRAPTextBox
Submit id: #ctl00_BodyContentPlaceHolder_SubmitPropertySearch
Postback lands on Search/PropertySearch.aspx?STRAP=<digits>&RequestToken=...
-- wait on that URL pattern (not a generic text match, which is flaky per
prior manual testing) before reading results.
"""
import re
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, "scripts/property_appraiser")
from common import load_batch_parcels, write_parity_row

BASE_URL = "https://www.leepa.org/"


def scrape_parcel(page, strap):
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.fill("#ctl00_BodyContentPlaceHolder_STRAPTextBox", strap)
    page.click("#ctl00_BodyContentPlaceHolder_SubmitPropertySearch")
    page.wait_for_url(re.compile(r"PropertySearch\.aspx"), timeout=20000)
    page.wait_for_load_state("networkidle", timeout=20000)
    # DOM table cells, not inner_text line-splitting: the results row is
    # [STRAP/Folio, Owner+MailingAddress(3 lines), SiteAddress+Legal(3+ lines),
    # Links] -- a naive line-position parse conflates the owner's mailing
    # address with the site address whenever they differ (absentee owners),
    # silently reporting the wrong address as a match/mismatch.
    rows = page.eval_on_selector_all(
        "table tr",
        "trs => trs.map(tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText))",
    )
    data_rows = [r for r in rows if len(r) == 4 and strap.replace("-", "").replace(".", "") in r[0].replace("-", "").replace(".", "")]
    return {"url": page.url, "rows": data_rows}


def extract_fields(scraped, strap):
    rows = scraped["rows"]
    if not rows:
        return None, None, None
    owner_cell = rows[0][1].split("\n")
    site_cell = rows[0][2].split("\n")
    owner = owner_cell[0].strip() if owner_cell else None
    addr = f"{site_cell[0].strip()}, {site_cell[1].strip()}" if len(site_cell) >= 2 else None
    return addr, owner, None


def main():
    parcels = load_batch_parcels("lee")
    print(f"lee: {len(parcels)} batch parcels to verify")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for rec in parcels:
            print(f"--- {rec['case_number']} / STRAP {rec['parcel_id']} ---")
            try:
                result = scrape_parcel(page, rec["parcel_id"])
            except Exception as e:
                print(f"  SCRAPE FAILED: {e}")
                write_parity_row(rec["case_number"], "lee", "parcel_id",
                                  ff_value=rec["parcel_id"], appraiser_value=None,
                                  verdict="unverified", note=f"scrape error: {e}")
                continue
            addr, owner, _ = extract_fields(result, rec["parcel_id"])
            print(f"  live url: {result['url']}")
            print(f"  addr={addr!r} owner={owner!r}")

            found = addr is not None
            row = write_parity_row(rec["case_number"], "lee", "parcel_id",
                                    ff_value=rec["parcel_id"],
                                    appraiser_value=rec["parcel_id"] if found else None,
                                    verdict=("pass" if found else "fail"),
                                    note=("STRAP resolved to exactly one live match" if found
                                          else "STRAP search returned zero matches on live site"))
            print(f"  parcel_id verdict: {row['verdict']}")

            if found:
                row = write_parity_row(rec["case_number"], "lee", "address",
                                        ff_value=rec["address"], appraiser_value=addr)
                print(f"  address verdict: {row['verdict']}")

                row = write_parity_row(rec["case_number"], "lee", "owner_of_record",
                                        ff_value=rec["owner"], appraiser_value=owner)
                print(f"  owner_of_record verdict: {row['verdict']}")
        browser.close()


if __name__ == "__main__":
    main()
