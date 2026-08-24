#!/usr/bin/env python3
"""Broward County (web.bcpa.net) — AngularJS SPA shell over legacy ASPX
WebMethods (search.aspx/GetData etc). bcpa.net (bare domain) is a separate
marketing site with no search; the real app lives at web.bcpa.net.

Must enter via the #/Record-Search hash route (direct nav to search.aspx
breaks -- it depends on jQuery/Angular pre-loaded by the parent shell).
Quick-search box #txtField handles name/address/folio; Enter navigates
straight to the parcel result, no separate submit-button click needed.
"""
import re
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, "scripts/property_appraiser")
from common import load_batch_parcels, write_parity_row

BASE_URL = "https://web.bcpa.net/bcpaclient/#/Record-Search"


def scrape_parcel(page, folio, first):
    if first:
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    else:
        # Same-hash goto() is a no-op in an already-loaded Angular SPA -- the
        # prior parcel view stays rendered and #txtField becomes invisible.
        # Clicking the SPA's own "New Search" control (#searchURL) does NOT
        # restore visibility either; only a full reload re-initializes the
        # search view.
        page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.fill("#txtField", folio)
    page.keyboard.press("Enter")
    page.wait_for_timeout(4000)
    body = page.inner_text("body")
    return body


def extract_fields(body):
    prop_id = None
    m = re.search(r"Property ID:\s*\n([^\n]+)", body)
    if m:
        prop_id = m.group(1).strip()

    owner = None
    m = re.search(r"Property Owner\(s\):\s*\n(.*?)\nMailing Address:", body, re.DOTALL)
    if m:
        owner = " / ".join(l.strip() for l in m.group(1).split("\n") if l.strip())

    addr = None
    m = re.search(r"Property Address:\s*\n([^\n]+)", body)
    if m:
        addr = m.group(1).strip()

    just_value = None
    idx = body.find("Property Assessment")
    if idx != -1:
        nums = re.findall(r"\$[\d,]+", body[idx:idx + 600])
        if len(nums) >= 3:
            just_value = float(nums[2].replace("$", "").replace(",", ""))

    return prop_id, addr, owner, just_value


def main():
    parcels = load_batch_parcels("broward")
    print(f"broward: {len(parcels)} batch parcels to verify")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1600, "height": 1200})
        page = context.new_page()
        for i, rec in enumerate(parcels):
            print(f"--- {rec['case_number']} / folio {rec['parcel_id']} ---")
            try:
                body = scrape_parcel(page, rec["parcel_id"], first=(i == 0))
            except Exception as e:
                print(f"  SCRAPE FAILED: {e}")
                write_parity_row(rec["case_number"], "broward", "parcel_id",
                                  ff_value=rec["parcel_id"], appraiser_value=None,
                                  verdict="unverified", note=f"scrape error: {e}")
                continue

            prop_id, addr, owner, jv = extract_fields(body)
            print(f"  prop_id={prop_id!r} addr={addr!r} owner={owner!r} just_value={jv!r}")

            resolved = prop_id is not None
            row = write_parity_row(rec["case_number"], "broward", "parcel_id",
                                    ff_value=rec["parcel_id"], appraiser_value=prop_id,
                                    verdict=("pass" if resolved else "fail"),
                                    note=("folio resolved to a live parcel record" if resolved
                                          else "folio search returned no parcel record"))
            print(f"  parcel_id verdict: {row['verdict']}")

            if resolved:
                row = write_parity_row(rec["case_number"], "broward", "address",
                                        ff_value=rec["address"], appraiser_value=addr)
                print(f"  address verdict: {row['verdict']}")

                row = write_parity_row(rec["case_number"], "broward", "owner_of_record",
                                        ff_value=rec["owner"], appraiser_value=owner)
                print(f"  owner_of_record verdict: {row['verdict']}")

                if rec["just_value"] is not None and jv is not None:
                    row = write_parity_row(rec["case_number"], "broward", "just_value",
                                            ff_value=rec["just_value"], appraiser_value=jv,
                                            biddeed_value=float(rec["just_value"]), competitor_value=jv)
                    print(f"  just_value verdict: {row['verdict']}")
        browser.close()


if __name__ == "__main__":
    main()
