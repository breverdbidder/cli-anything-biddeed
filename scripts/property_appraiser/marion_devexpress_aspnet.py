#!/usr/bin/env python3
"""Marion County (pa.marion.fl.us) — DevExpress ASP.NET WebForms.

Batch parcel IDs in our Winner Data intake are the site's own "Prime Key",
so the PRC.aspx deep link works cold with no disclaimer-gate visit and no
Playwright needed: GET /PRC.aspx?key=<PrimeKey>&YR=2026&mName=False&mSitus=False
returns a fully server-rendered property record card. Guessed domain
property.marioncountyfl.org does NOT exist -- correct domain is
www.pa.marion.fl.us (mcpafl.org is a 403-blocked alias, not the live site).
"""
import re
import sys
import httpx

sys.path.insert(0, "scripts/property_appraiser")
from common import load_batch_parcels, write_parity_row

BASE_URL = "https://www.pa.marion.fl.us/PRC.aspx"


def _text(html):
    t = re.sub(r"<[^>]+>", "\n", html)
    t = re.sub(r"&nbsp;", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n+", "\n", t)
    return t


def scrape_parcel(prime_key):
    r = httpx.get(BASE_URL, params={"key": prime_key, "YR": "2026", "mName": "False", "mSitus": "False"},
                  timeout=30, follow_redirects=True)
    r.raise_for_status()
    return _text(r.text)


def extract_fields(text):
    real_parcel = None
    m = re.search(r"\n(\d{4}-\d{3}-\d{3})\n", text)
    if m:
        real_parcel = m.group(1)

    owner = None
    situs = None
    m = re.search(r"Property Information\n([^\n]+)", text)
    if m:
        owner = m.group(1).strip()

    m = re.search(r"Situs:\s*([^\n]+)", text)
    if m:
        situs = m.group(1).strip()

    # "Current Value" block renders as 8 stacked labels (Land Just Value,
    # Buildings, Miscellaneous, Total Just Value, Total Assessed Value,
    # Exemptions, Total Taxable, School Taxable) followed by their 8 $-amounts
    # in the same order -- NOT interleaved label/value pairs.
    just_value = None
    idx = text.find("Land Just Value")
    if idx != -1:
        nums = re.findall(r"\$[\d,]+", text[idx:idx + 600])
        if len(nums) >= 4:
            just_value = float(nums[3].replace("$", "").replace(",", ""))

    return real_parcel, situs, owner, just_value


def main():
    parcels = load_batch_parcels("marion")
    print(f"marion: {len(parcels)} batch parcels to verify")
    for rec in parcels:
        prime_key = rec["parcel_id"]
        print(f"--- {rec['case_number']} / PrimeKey {prime_key} ---")
        try:
            text = scrape_parcel(prime_key)
        except Exception as e:
            print(f"  SCRAPE FAILED: {e}")
            write_parity_row(rec["case_number"], "marion", "parcel_id",
                              ff_value=prime_key, appraiser_value=None,
                              verdict="unverified", note=f"scrape error: {e}")
            continue

        real_parcel, situs, owner, jv = extract_fields(text)
        resolved = "Prime Key:" in text and real_parcel is not None
        print(f"  real_parcel={real_parcel!r} situs={situs!r} owner={owner!r} just_value={jv!r}")

        row = write_parity_row(rec["case_number"], "marion", "parcel_id",
                                ff_value=prime_key,
                                appraiser_value=prime_key if resolved else None,
                                verdict=("pass" if resolved else "fail"),
                                note=("Prime Key resolved to a live property record card" if resolved
                                      else "Prime Key did not resolve on the live site"))
        print(f"  parcel_id verdict: {row['verdict']}")

        if resolved:
            row = write_parity_row(rec["case_number"], "marion", "address",
                                    ff_value=rec["address"], appraiser_value=situs)
            print(f"  address verdict: {row['verdict']}")

            row = write_parity_row(rec["case_number"], "marion", "owner_of_record",
                                    ff_value=rec["owner"], appraiser_value=owner)
            print(f"  owner_of_record verdict: {row['verdict']}")

            if rec["just_value"] is not None and jv is not None:
                row = write_parity_row(rec["case_number"], "marion", "just_value",
                                        ff_value=rec["just_value"], appraiser_value=jv,
                                        biddeed_value=float(rec["just_value"]), competitor_value=jv)
                print(f"  just_value verdict: {row['verdict']}")


if __name__ == "__main__":
    main()
