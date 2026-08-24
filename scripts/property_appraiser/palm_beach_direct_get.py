#!/usr/bin/env python3
"""Palm Beach County (pbcpao.gov) — ASP.NET MVC, direct server-rendered GET.

No form submission needed: GET /Property/Details?parcelId=<PCN> returns full
HTML with an embedded `var model = {...}` JSON blob. Plain httpx, no
Playwright required -- cheapest platform in the set.
"""
import json
import re
import sys
import httpx

sys.path.insert(0, "scripts/property_appraiser")
from common import load_batch_parcels, write_parity_row

BASE_URL = "https://pbcpao.gov/Property/Details"


def _extract_model(html):
    start = html.index("var model = ") + len("var model = ")
    depth = 0
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(html[start:i + 1])
    raise ValueError("unbalanced model blob")


def scrape_parcel(pcn):
    r = httpx.get(BASE_URL, params={"parcelId": pcn}, timeout=30, follow_redirects=True)
    r.raise_for_status()
    return _extract_model(r.text)


def main():
    parcels = load_batch_parcels("palm_beach")
    print(f"palm_beach: {len(parcels)} batch parcels to verify")
    for rec in parcels:
        print(f"--- {rec['case_number']} / PCN {rec['parcel_id']} ---")
        try:
            model = scrape_parcel(rec["parcel_id"])
        except Exception as e:
            print(f"  SCRAPE FAILED: {e}")
            write_parity_row(rec["case_number"], "palm_beach", "parcel_id",
                              ff_value=rec["parcel_id"], appraiser_value=None,
                              verdict="unverified", note=f"scrape error: {e}")
            continue

        pd = model.get("propertyDetail") or {}
        pcn_live = pd.get("PCN")
        addr = f"{pd.get('AddressLine1', '').strip()}, {pd.get('AddressLine3', '').strip()}"
        owner = pd.get("OwnerName")
        assessed = None
        values = model.get("valuesInfo") or model.get("assessedValues")
        if isinstance(values, list) and values:
            av = values[0].get("AssessedValue") or values[0].get("TaxableValue")
            assessed = float(av) if av else None
        print(f"  pcn={pcn_live!r} addr={addr!r} owner={owner!r} assessed={assessed!r}")

        row = write_parity_row(rec["case_number"], "palm_beach", "parcel_id",
                                ff_value=rec["parcel_id"], appraiser_value=pcn_live)
        print(f"  parcel_id verdict: {row['verdict']}")

        row = write_parity_row(rec["case_number"], "palm_beach", "address",
                                ff_value=rec["address"], appraiser_value=addr)
        print(f"  address verdict: {row['verdict']}")

        row = write_parity_row(rec["case_number"], "palm_beach", "owner_of_record",
                                ff_value=rec["owner"], appraiser_value=owner)
        print(f"  owner_of_record verdict: {row['verdict']}")

        if rec["just_value"] is not None and assessed is not None:
            row = write_parity_row(rec["case_number"], "palm_beach", "just_value",
                                    ff_value=rec["just_value"], appraiser_value=assessed,
                                    biddeed_value=float(rec["just_value"]), competitor_value=assessed)
            print(f"  just_value verdict: {row['verdict']}")


if __name__ == "__main__":
    main()
