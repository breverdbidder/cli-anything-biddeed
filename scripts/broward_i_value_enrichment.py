#!/usr/bin/env python3
"""
Broward County criterion-I value enrichment.

Fetches REAL assessed_value / market_value from the Broward County Property
Appraiser (BCPA) public parcel-lookup endpoint (web.bcpa.net) for
multi_county_auctions rows where both values are NULL, and PATCHes them
into Supabase via PostgREST.

Source: https://web.bcpa.net/BcpaClient/search.aspx/getParcelInformation
  - POST JSON {folioNumber, taxyear:"", action:"CURRENT", use:""}
  - market_value  <- parcelInfo.justValue      ("Just/Market Value")
  - assessed_value <- parcelInfo.taxableAmountCounty (assessed/taxable value, SOH-capped)

Only rows with a real Broward folio-format parcel_id (12 digits, possibly
with 2 alpha chars e.g. 494123BD0110) are attempted. Placeholder parcel_ids
such as "Property Appraiser", "TIMESHARE", "MULTIPLE PARCELS" are skipped
(not a lookupable folio) and counted as misses.

No fabrication: if BCPA returns no record, or the JSON is missing usable
value fields, the row is skipped and logged as a miss. Nothing is guessed.
"""
import json
import os
import re
import sys
import time
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BCPA_ENDPOINT = "https://web.bcpa.net/BcpaClient/search.aspx/getParcelInformation"

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

FOLIO_RE = re.compile(r"^\d{4,6}[A-Z]{0,2}\d{2,6}$")


def sb_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS_SB)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(case_number, assessed_value, market_value):
    body = json.dumps({
        "assessed_value": assessed_value,
        "market_value": market_value,
    }).encode()
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.{urllib.parse_quote(case_number)}&county=eq.broward"
    req = urllib.request.Request(url, data=body, headers={**HEADERS_SB, "Prefer": "return=representation"}, method="PATCH")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def money_to_float(s):
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    if s in ("", "0"):
        try:
            return float(s)
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_bcpa(folio):
    body = json.dumps({"folioNumber": folio, "taxyear": "", "action": "CURRENT", "use": ""}).encode("utf-8")
    req = urllib.request.Request(
        BCPA_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read())
    except Exception as e:
        return None, f"http_error:{e}"

    d = payload.get("d")
    if not d:
        return None, "no_data"
    parcels = d.get("parcelInfok__BackingField") or []
    if not parcels:
        return None, "no_parcel_info"
    p = parcels[0]
    just_value = money_to_float(p.get("justValue"))
    taxable_county = money_to_float(p.get("taxableAmountCounty"))
    if just_value is None and taxable_county is None:
        return None, "no_value_fields"
    return {
        "market_value": just_value,
        "assessed_value": taxable_county if taxable_county is not None else just_value,
        "folioNumber": p.get("folioNumber"),
        "situsAddress1": p.get("situsAddress1"),
    }, None


import urllib.parse as _up
urllib.parse_quote = _up.quote


def main():
    rows = sb_get(
        "multi_county_auctions?select=case_number,parcel_id,property_address"
        "&county=eq.broward&assessed_value=is.null&market_value=is.null"
        "&data_source=eq.realforeclose"
    )
    print(f"Fetched {len(rows)} realforeclose rows missing both values.")

    enriched = []
    misses = []

    for row in rows:
        case_number = row["case_number"]
        parcel_id = (row.get("parcel_id") or "").strip()

        if not parcel_id or not FOLIO_RE.match(parcel_id):
            misses.append((case_number, parcel_id, "not_a_lookupable_folio"))
            continue

        data, err = fetch_bcpa(parcel_id)
        time.sleep(0.5)  # be polite to bcpa.net

        if err:
            misses.append((case_number, parcel_id, err))
            continue

        mv = data["market_value"]
        av = data["assessed_value"]
        if mv is None and av is None:
            misses.append((case_number, parcel_id, "empty_values"))
            continue

        try:
            sb_patch(case_number, av, mv)
        except Exception as e:
            misses.append((case_number, parcel_id, f"patch_error:{e}"))
            continue

        enriched.append((case_number, parcel_id, av, mv, data.get("situsAddress1")))
        print(f"ENRICHED {case_number} | {parcel_id} -> assessed={av} market={mv}")

    print("\n=== SUMMARY ===")
    print(f"Enriched: {len(enriched)}")
    print(f"Missed:   {len(misses)}")
    for c, p, av, mv, addr in enriched:
        print(f"  OK  {c} | {p} | assessed={av} market={mv} | {addr}")
    for c, p, reason in misses:
        print(f"  MISS {c} | {p} | {reason}")


if __name__ == "__main__":
    main()
