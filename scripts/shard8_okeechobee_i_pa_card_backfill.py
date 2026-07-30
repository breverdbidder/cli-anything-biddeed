#!/usr/bin/env python3
"""
Gold Standard shard-8 okeechobee (dispatch ed344dc4-9b86-4f5a-97af-26ea782adcbe): Letter I
property-card backfill for the 22 rows failing card_complete.

Source: Okeechobee County Property Appraiser official GIS (Grizzly GIS / floridapa.com
platform), www.okeechobeepa.com -- NOT FL GIO (fl_parcels), NOT the Clerk's
TaxSmartWebLive site.

Pipeline per parcel:
  1. GET https://www.okeechobeepa.com/ to establish ASPSESSIONID cookie
  2. Strip dashes from the folio PIN (e.g. '1-25-37-35-0070-00060-1760' ->
     '12537350070000601760')
  3. POST https://www.okeechobeepa.com/gis/gisSideMenu_3_Details/showDetails/
     with tempPIN=<PIN>&zoomPIN=1&save=&Show_Rec=1
  4. Parse the "Site:" line for property_address, the "Just" <td class=gisLabels>
     row for assessed_value, and the zoomParcel('X+Y', ...) JS call for
     Florida State Plane East (EPSG:2236) coordinates
  5. Reproject EPSG:2236 -> EPSG:4269 (NAD83 lat/lon) via pyproj
  6. PATCH multi_county_auctions for the matching case_number, ONLY writing
     fields with a real sourced value -- never null out or guess.

Fail-loud invariant: if a parcel is not found, or a specific field can't be
parsed out of the response, that field/row is left untouched and reported as
a residual gap. No fabricated/estimated/interpolated values.
"""
import argparse
import json
import os
import re
import sys
from typing import Dict, Optional

import httpx
from pyproj import Transformer

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

PA_BASE = "https://www.okeechobeepa.com/"
PA_DETAILS_URL = "https://www.okeechobeepa.com/gis/gisSideMenu_3_Details/showDetails/"

TRANSFORMER = Transformer.from_crs("EPSG:2236", "EPSG:4269", always_xy=True)

# The 22 case_number -> parcel_id (folio PIN) pairs failing Letter I this session.
TARGET_PARCELS = {
    "2026TD041": "1-08-34-33-0A00-00012-O000",
    "2026TD044": "1-22-34-33-0A00-00021-P000",
    "2026TD050": "1-25-37-35-0070-00060-1760",
    "2026TD053": "1-10-36-35-0A00-00004-A000",
    "2026TD054": "1-04-37-35-0010-00000-025A",
    "2026TD056": "1-18-37-35-0020-00020-0170",
    "2026TD057": "1-22-37-35-0040-0000D-0130",
    "2026TD058": "1-24-37-35-0A00-00004-A000",
    "2026TD059": "1-25-37-35-0120-00110-0780",
    "2026TD060": "1-33-37-35-0010-00000-0073",
    "2026TD061": "1-35-37-35-0020-00000-0670",
    "2026TD062": "1-15-37-36-0A00-00002-1090",
    "2026TD063": "1-17-37-36-0A00-00003-0292",
    "2026TD064": "1-17-37-36-0A00-00003-041E",
    "2026TD065": "1-17-37-36-0A00-00003-150D",
    "2026TD066": "1-18-37-36-0A00-00010-0290",
    "2026TD068": "1-31-37-36-0010-00010-0190",
    "2026TD069": "1-04-38-36-0020-00000-0760",
    "2026TD073": "1-05-38-36-0040-00050-0120",
    "2026TD074": "1-05-38-36-0070-00270-0240",
    "2026TD077": "1-06-38-36-0A00-00002-0000",
    "2026TD078": "1-10-36-35-0040-00000-0150",
}


def pin_no_dashes(parcel_id: str) -> str:
    return parcel_id.replace("-", "")


def fetch_pa_card(client: httpx.Client, parcel_id: str) -> Optional[Dict]:
    """Fetch and parse the Okeechobee PA property card for one parcel."""
    pin = pin_no_dashes(parcel_id)
    resp = client.post(
        PA_DETAILS_URL,
        data={"tempPIN": pin, "zoomPIN": "1", "save": "", "Show_Rec": "1"},
    )
    resp.raise_for_status()
    txt = resp.text

    if "gisDetails_PIN" not in txt or pin not in txt:
        return None  # parcel not found on this site

    result: Dict = {}

    # property_address: from the "Site:" line
    m = re.search(r'<span class="gisLabels">Site:</span>\s*([^<]+)', txt)
    if m:
        addr = m.group(1).strip()
        addr = re.sub(r"\s+", " ", addr)
        if addr:
            result["property_address"] = addr

    # assessed_value: the "Just" labeled numeric cell
    m = re.search(
        r'<td class="gisLabels">Just</td><td class="gisDetails_numeric">\$([\d,]+)</td>',
        txt,
    )
    if m:
        result["assessed_value"] = float(m.group(1).replace(",", ""))

    # lat/lon: from zoomParcel('X+Y', ...) EPSG:2236 state plane feet
    m = re.search(r"zoomParcel\('([\d.]+)\+([\d.]+)'", txt)
    if m:
        x, y = float(m.group(1)), float(m.group(2))
        lon, lat = TRANSFORMER.transform(x, y)
        result["latitude"] = lat
        result["longitude"] = lon

    return result


def patch_auction(client: httpx.Client, case_number: str, fields: Dict) -> bool:
    if not fields:
        return False
    url = f"{BASE}/multi_county_auctions?case_number=eq.{case_number}&county=eq.okeechobee"
    resp = client.patch(url, headers={**HEADERS, "Prefer": "return=minimal"}, json=fields)
    return resp.status_code in (200, 204)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(1)

    pa_client = httpx.Client(timeout=30, follow_redirects=True)
    pa_client.get(PA_BASE)  # bootstrap ASPSESSIONID cookie

    db_client = httpx.Client(timeout=30, follow_redirects=True)

    results = []
    for case_number, parcel_id in TARGET_PARCELS.items():
        try:
            card = fetch_pa_card(pa_client, parcel_id)
        except Exception as e:
            results.append({
                "case_number": case_number, "parcel_id": parcel_id,
                "status": "ERROR", "error": str(e),
            })
            continue

        if card is None:
            results.append({
                "case_number": case_number, "parcel_id": parcel_id,
                "status": "NOT_FOUND",
            })
            continue

        fields_to_write = {k: v for k, v in card.items() if v is not None}

        applied = False
        if fields_to_write and not args.dry_run:
            applied = patch_auction(db_client, case_number, fields_to_write)

        results.append({
            "case_number": case_number,
            "parcel_id": parcel_id,
            "status": "OK",
            "fields_found": fields_to_write,
            "applied": applied if not args.dry_run else "DRY_RUN",
        })

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
