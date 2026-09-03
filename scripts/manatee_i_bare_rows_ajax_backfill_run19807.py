#!/usr/bin/env python3
"""
GOLD STANDARD (issue #19807, shard-5 pasco/manatee/sumter): manatee E+I
bare-row backfill, 3rd pass.

Denominator grew since scripts/manatee_i_bare_rows_ajax_backfill_10bc7bc6.py's
2nd pass (2026-08-13-ish) -- 10 NEW bare foreclosure stub rows (case_number +
auction_date only, scraped by the case_number-only manatee_clerk_foreclosure
list which carries no address/parcel, per scripts/clerk_ssot/parsers/
manatee.py's documented scope) now block both E (parcel_linked) and I
(card_complete). Live-verified 2026-09-03 via PostgREST: all 10 have
property_address=parcel_id=data_source=None, auction_status=scheduled.

REUSE-FIRST (guardrail 7): identical pipeline as the 10bc7bc6 script --
manatee.realforeclose.com AJAX auction-detail harvest (shard2_run2450's
harvest_date()/short_form() bridge), then Manatee GIS_PARCELS ArcGIS
FeatureServer for any case where the AJAX payload's parcel_id come back
missing, then lat/lon backfill via the same endpoint, then re-run
shard_manatee_i_zoning.py so newly-linked parcels get a parcel_zones row.
No new methodology invented -- only TARGET_CASES/TARGET_DATES rescoped.

dispatch_id: 33847d2f-ce63-400d-a68e-e2971b0c13bd
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
ARCGIS_URL = "https://services1.arcgis.com/t03WDvnSR7gSDOB2/arcgis/rest/services/GIS_PARCELS/FeatureServer/0/query"

# case_number -> auction_date (MM/DD/YYYY), live-queried from multi_county_auctions
# 2026-09-03 (this session). All 10 are the full remaining manatee E/I gap.
TARGET_CASES = {
    "2025CA002633AX": "10/14/2026",
    "2025CA002094AX": "11/03/2026",
    "2025CA002756AX": "12/02/2026",
    "2017CA002171AX": "12/02/2026",
    "2025CC003655AX": "10/01/2026",
    "2024CA001079AX": "10/02/2026",
    "2025CA001999AX": "10/02/2026",
    "2025CA002760AX": "12/01/2026",
    "2026CC000108AX": "09/30/2026",
    "2026CC000584AX": "09/22/2026",
}
TARGET_DATES = sorted(set(TARGET_CASES.values()))

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvest", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
harvest_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harvest_mod)


def short_form(full_case: str):
    m = re.match(r"^41(\d{4})(CA|CC)(\d{6})(?:CA|CC)AXMA$", full_case)
    if not m:
        return None
    yyyy, typ, num = m.groups()
    return f"{yyyy}{typ}{num}AX"


def normalize(addr: str, strip_unit: bool = True) -> str:
    a = addr.upper().strip()
    if strip_unit:
        a = re.sub(r"\s+(APT|UNIT|STE|SUITE|#)\s*\S+$", "", a, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", a).strip()


def parse_house_number_city(full_address: str):
    street_line = full_address.split(",")[0].strip()
    city = None
    parts = [p.strip() for p in full_address.split(",")]
    if len(parts) >= 2:
        city = parts[1].upper()
    norm_base = normalize(street_line, strip_unit=True)
    m = re.match(r"^(\d+)\s", norm_base)
    if not m:
        return None, None
    return m.group(1), city


def main():
    harvested = {}
    for d in TARGET_DATES:
        items = harvest_mod.harvest_date("manatee", "manatee", d, platform_domain="realforeclose.com")
        print(f"harvest {d}: {len(items)} items")
        for it in items:
            sf = short_form(it["case_number"])
            if sf in TARGET_CASES:
                harvested[sf] = it

    print(f"matched {len(harvested)} of {len(TARGET_CASES)} target cases via AJAX harvest")
    for c in set(TARGET_CASES) - set(harvested):
        print(f"  NOT FOUND in live calendar: {c}")

    if not harvested:
        raise SystemExit("Silent-failure guard: 0 target cases matched in AJAX harvest — aborting, no writes made")

    with httpx.Client(timeout=60) as client:
        updated_step1 = 0
        newly_linked_parcels = []
        for case_number, it in harvested.items():
            payload = {}
            if it.get("property_address"):
                payload["property_address"] = it["property_address"]
                parts = [p.strip() for p in it["property_address"].split(",")]
                if len(parts) >= 3:
                    payload["city"] = parts[1]
                    zip_m = re.search(r"(\d{5})", parts[-1])
                    if zip_m:
                        payload["zip"] = zip_m.group(1)
            pid = it.get("parcel_id")
            if pid and pid != "Property Appraiser" and re.match(r"^\d+$", pid):
                payload["parcel_id"] = pid
                newly_linked_parcels.append(pid)
            if it.get("assessed_value") is not None:
                payload["assessed_value"] = it["assessed_value"]
            if it.get("judgment_amount") is not None:
                payload["judgment_amount"] = it["judgment_amount"]
            if not payload:
                continue
            r = client.patch(f"{BASE}/multi_county_auctions", headers=HEADERS,
                              params={"case_number": f"eq.{case_number}", "county": "eq.manatee"},
                              content=json.dumps(payload))
            if r.status_code in (200, 204):
                updated_step1 += 1
                print(f"  updated {case_number}: {list(payload.keys())}")
            else:
                print(f"  update FAILED {case_number}: {r.status_code} {r.text[:200]}")

        print(f"step1 (address/parcel/value): {updated_step1} rows updated")

        no_parcel_cases = {cn: it for cn, it in harvested.items()
                            if not (it.get("parcel_id") and it["parcel_id"] != "Property Appraiser"
                                    and re.match(r"^\d+$", it.get("parcel_id") or ""))
                            and it.get("property_address")}
        for case_number, it in no_parcel_cases.items():
            hn, city = parse_house_number_city(it["property_address"])
            if not hn or not city:
                print(f"  {case_number}: cannot parse house_number/city from '{it['property_address']}'")
                continue
            where = f"PROP_CITYNAME='{city}' AND PROP_HN='{hn}'"
            r = client.post(ARCGIS_URL, data={
                "where": where, "outFields": "PARCEL_ID,PRIMARY_ADDRESS,PROP_HN,PROP_CITYNAME,LAT,LON",
                "f": "json", "returnGeometry": "false", "resultRecordCount": "50",
            })
            feats = r.json().get("features", []) if r.status_code == 200 else []
            norm_target = normalize(it["property_address"].split(",")[0], strip_unit=True)
            match = None
            for f in feats:
                a = f["attributes"]
                if normalize(a["PRIMARY_ADDRESS"], strip_unit=True) == norm_target:
                    match = a
                    break
            if not match and len(feats) == 1:
                match = feats[0]["attributes"]
            if match:
                payload = {"parcel_id": match["PARCEL_ID"]}
                if match.get("LAT") is not None:
                    payload["latitude"] = match["LAT"]
                if match.get("LON") is not None:
                    payload["longitude"] = match["LON"]
                r2 = client.patch(f"{BASE}/multi_county_auctions", headers=HEADERS,
                                   params={"case_number": f"eq.{case_number}", "county": "eq.manatee"},
                                   content=json.dumps(payload))
                if r2.status_code in (200, 204):
                    print(f"  GIS-resolved parcel for {case_number}: {match['PARCEL_ID']}")
                    newly_linked_parcels.append(match["PARCEL_ID"])
                else:
                    print(f"  GIS parcel update FAILED {case_number}: {r2.status_code} {r2.text[:200]}")
            else:
                print(f"  {case_number}: no exact GIS_PARCELS match for '{it['property_address']}' (hn={hn} city={city}, {len(feats)} candidates)")

        for case_number, it in harvested.items():
            pid = it.get("parcel_id")
            if not (pid and pid != "Property Appraiser" and re.match(r"^\d+$", pid)):
                continue
            r = client.get(f"{BASE}/multi_county_auctions", headers=HEADERS,
                            params={"select": "latitude,longitude", "case_number": f"eq.{case_number}",
                                    "county": "eq.manatee"})
            rows = r.json()
            if rows and rows[0].get("latitude") is not None:
                continue
            r3 = client.post(ARCGIS_URL, data={
                "where": f"PARCEL_ID='{pid}'", "outFields": "PARCEL_ID,LAT,LON",
                "f": "json", "returnGeometry": "false", "resultRecordCount": "5",
            })
            feats = r3.json().get("features", []) if r3.status_code == 200 else []
            if feats:
                a = feats[0]["attributes"]
                if a.get("LAT") is not None:
                    payload = {"latitude": a["LAT"], "longitude": a["LON"]}
                    r4 = client.patch(f"{BASE}/multi_county_auctions", headers=HEADERS,
                                       params={"case_number": f"eq.{case_number}", "county": "eq.manatee"},
                                       content=json.dumps(payload))
                    if r4.status_code in (200, 204):
                        print(f"  lat/lon backfilled for {case_number} via PARCEL_ID={pid}")

    print(f"newly_linked_parcels for zoning follow-up: {newly_linked_parcels}")

    print("\n--- re-running shard_manatee_i_zoning.py to link new parcels' zoning ---")
    result = subprocess.run([sys.executable, os.path.join(_here, "shard_manatee_i_zoning.py")],
                             capture_output=True, text=True)
    print(result.stdout[-4000:])
    if result.returncode != 0:
        print(result.stderr[-2000:], file=sys.stderr)


if __name__ == "__main__":
    main()
