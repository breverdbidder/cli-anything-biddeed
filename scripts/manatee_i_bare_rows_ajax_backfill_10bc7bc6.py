#!/usr/bin/env python3
"""
Manatee I: backfill the 4 bare foreclosure stub rows (case_number only, scraped
2026-08-10 from records.manateeclerk.com's foreclosure-sales list which carries
NO address/parcel per scripts/clerk_ssot/parsers/manatee.py's documented scope)
via the manatee.realforeclose.com AJAX auction-detail endpoint, reusing
scripts/shard2_run2450_ajax_realforeclose_harvest.py's harvest_date()/
parse_aitem_blocks() verbatim (per REUSE-FIRST guardrail).

Target rows (all sale_type=foreclosure, auction_status=scheduled):
  2025CA000375AX (2026-08-18), 2025CA001774AX (2026-08-19),
  2026CC000780AX (2026-08-25), 2023CA005502AX (2026-10-01)

Case-number format bridge: DB stores the short clerk form ("2025CA000375AX"),
RealForeclose's AJAX payload returns the full circuit-court form
("412025CA000375CAAXMA" / "...CCAXMA" for county-court CC cases). Bridged via
short_form() regex, not fuzzy matching.

After address/parcel_id land, parcel_id -> lat/lon/assessed_value is filled via
Manatee County GIS_PARCELS ArcGIS FeatureServer (same endpoint + exact-match
strategy as scripts/shard_manatee_e_linkage.py), then the newly-linked
parcel_ids are run through scripts/shard_manatee_i_zoning.py's ZONEOFFICIAL
point-in-polygon lookup for the zoning_code/parcel_zones half of the I gate.

dispatch_id: 10bc7bc6-eefb-4073-8d69-18a6a83788a0
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

TARGET_CASES = {
    "2025CA000375AX", "2025CA001774AX", "2026CC000780AX", "2023CA005502AX",
    # 2nd pass (found on re-diagnosis after 1st pass landed -- these bare rows
    # were already in the DB (created_at 2026-08-10/13) but not enumerated in
    # the 1st-pass incomplete-row snapshot; same manatee_clerk_foreclosure
    # scraper source, same "case_number only" shape):
    "2025CA002070AX", "2026CC000389AX", "2025CA003113AX", "2025CA000787AX",
    "2025CA002407AX", "2024CA000222AX", "2025CA002328AX", "2026CC000196AX",
    "2025CA001396AX", "2018CA006069AX", "2024CA001607AX", "2024CA001000AX",
    "2025CC000770AX", "2024CA000642AX", "2024CA001278AX", "2025CA000884AX",
    "2025CA001855AX",
}
TARGET_DATES = [
    "08/18/2026", "08/19/2026", "08/25/2026", "10/01/2026",
    "08/26/2026", "09/01/2026", "09/02/2026", "09/08/2026", "09/09/2026",
    "09/10/2026", "09/16/2026", "09/29/2026", "09/30/2026", "10/14/2026",
    "11/10/2026",
]

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
    # Step 1: AJAX harvest address/parcel_id/judgment_amount/assessed_value for the 4 dates
    harvested = {}
    for d in TARGET_DATES:
        items = harvest_mod.harvest_date("manatee", "manatee", d, platform_domain="realforeclose.com")
        print(f"harvest {d}: {len(items)} items")
        for it in items:
            sf = short_form(it["case_number"])
            if sf in TARGET_CASES:
                harvested[sf] = it

    print(f"matched {len(harvested)} of {len(TARGET_CASES)} target cases via AJAX harvest")
    for c in TARGET_CASES - set(harvested):
        print(f"  NOT FOUND in live calendar: {c}")

    if not harvested:
        raise SystemExit("Silent-failure guard: 0 of 4 target cases matched in AJAX harvest — aborting, no writes made")

    with httpx.Client(timeout=60) as client:
        # Step 2: write property_address / parcel_id / judgment_amount / assessed_value
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

        # Step 3: for cases whose parcel_id came back missing/garbage (e.g. "Property
        # Appraiser" placeholder from the harvest), resolve via GIS_PARCELS address match.
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

        # Step 4: fill lat/lon for parcels that already had parcel_id written in step1
        # but no lat/lon yet, via the same GIS_PARCELS endpoint keyed by PARCEL_ID.
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

    # Step 5: run the existing zoning script so the new parcels get parcel_zones rows
    print("\n--- re-running shard_manatee_i_zoning.py to link new parcels' zoning ---")
    result = subprocess.run([sys.executable, os.path.join(_here, "shard_manatee_i_zoning.py")],
                             capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)


if __name__ == "__main__":
    main()
