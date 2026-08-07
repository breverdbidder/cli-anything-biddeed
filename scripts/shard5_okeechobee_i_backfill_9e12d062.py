#!/usr/bin/env python3
"""
Gold Standard shard-5 okeechobee (dispatch 9e12d062): Letter I property-card
backfill for the 14 fresh calendar_sweep_mca_v3 tax-deed rows (2026TD082-095)
plus the disclosed residual 2026TD050 (matched_clean but missing address/lat/lon).

Adapted from scripts/shard8_okeechobee_i_pa_card_backfill.py (dispatch ed344dc4)
-- SAME source (Okeechobee PA Grizzly GIS), SAME parse/reproject logic. Only the
TARGET_PARCELS dict differs (new case numbers for this dispatch). Does not modify
or overwrite the original script's TARGET_PARCELS.
"""
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

TARGET_PARCELS = {
    "2026TD082": "1-17-34-33-0A00-00006-J000",
    "2026TD083": "1-05-37-35-0020-00300-0030",
    "2026TD084": "1-22-33-35-0010-00920-0060",
    "2026TD085": "1-18-37-35-0020-00290-0110",
    "2026TD086": "1-06-36-34-0010-00060-0010",
    "2026TD087": "1-06-36-34-0010-00360-0140",
    "2026TD088": "1-18-34-36-0A00-00004-0000",
    "2026TD089": "1-30-37-35-0010-00020-010A",
    "2026TD090": "1-18-34-36-0A00-00005-0000",
    "2026TD091": "1-03-38-35-0A00-00001-A000",
    "2026TD092": "1-04-38-36-0030-00030-0160",
    "2026TD093": "1-06-38-36-0A00-00007-0000",
    "2026TD094": "1-09-38-36-0050-00010-0040",
    "2026TD095": "1-23-38-36-0A00-00027-0000",
    "2026TD050": "1-25-37-35-0070-00060-1760",
}


def pin_no_dashes(parcel_id: str) -> str:
    return parcel_id.replace("-", "")


def fetch_pa_card(client: httpx.Client, parcel_id: str) -> Optional[Dict]:
    pin = pin_no_dashes(parcel_id)
    resp = client.post(
        PA_DETAILS_URL,
        data={"tempPIN": pin, "zoomPIN": "1", "save": "", "Show_Rec": "1"},
    )
    resp.raise_for_status()
    txt = resp.text

    if "gisDetails_PIN" not in txt or pin not in txt:
        return None

    result: Dict = {}

    m = re.search(r'<span class="gisLabels">Site:</span>\s*([^<]+)', txt)
    if m:
        addr = m.group(1).strip()
        addr = re.sub(r"\s+", " ", addr)
        if addr:
            result["property_address"] = addr

    m = re.search(
        r'<td class="gisLabels">Just</td><td class="gisDetails_numeric">\$([\d,]+)</td>',
        txt,
    )
    if m:
        result["assessed_value"] = float(m.group(1).replace(",", ""))

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
    if not SUPABASE_KEY:
        print("SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(1)

    pa_client = httpx.Client(timeout=30, follow_redirects=True)
    pa_client.get(PA_BASE)

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
        if fields_to_write:
            applied = patch_auction(db_client, case_number, fields_to_write)

        results.append({
            "case_number": case_number,
            "parcel_id": parcel_id,
            "status": "OK",
            "fields_found": fields_to_write,
            "applied": applied,
        })

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
