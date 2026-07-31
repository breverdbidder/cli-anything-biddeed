#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-1 (pinellas), dispatch f763205f-867d-483e-8efb-da32165dd254.
loop run 7622, chat_session architect-20260731T080000.

PURPOSE: Fix pinellas letters C/D/I.
  - Pinellas was 10/10 on 2026-07-24 (session c40bb245 + 8d7de4ab).
  - As of loop run 7622 brief: auctions_total=406 (was 393), 13 new rows ingested.
  - C FAIL 93.3% (379/406), D FAIL 93.3% (379/406), I FAIL 92.4% (375/406).
  - Need: 386 matched_clean (C/D) and 386 card_complete (I) to reach 95%.
  - Gap: 7 more parity matches needed (C/D), 11 more complete cards needed (I).

APPROACH:
  1. Find incomplete property cards (I) -- auctions missing parcel_id or
     parcel_zones row or lat/lng or assessed_value.
  2. Query Pinellas ArcGIS Accela layer (Address Points) and Largo GIS layer
     (Parcels, county-wide) to recover real folio/geo/value.
  3. Update multi_county_auctions + insert parcel_zones rows.
  4. The same rows that become card_complete also improve C/D parity if their
     property_address now joins cleanly.

SOURCES (proven live from 20260724_shard5_pinellas_i_real_parcel_geo_zone_fix.sql):
  - Address Points: egis.pinellas.gov/gis/rest/services/Accela/AccelaAddressParcel/MapServer/0
  - Parcels (countywide): maps.largo.com/arcgis/rest/services/Largo_GIS_Viewer_Map/MapServer/247

ZONE_CODE METHOD: DOR_UC crosswalk (1->SFR, 4->MFR-CONDO, 2->MH) from real FDOR_Land_Use_Code.
Jurisdiction IDs confirmed from 20260724 fix: 
  635=Pinellas Unincorporated, 814=St.Pete Beach/other, 
  856=Clearwater, 859=Largo, 898=Dunedin/safety harbor, ...

WIRING: Run via GHA workflow gold-standard-shard1-pinellas-fix.yml (scheduled on push to main).
"""
import json
import os
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

PINELLAS_ACCELA_ADDR = (
    "https://egis.pinellas.gov/gis/rest/services/Accela/AccelaAddressParcel/MapServer/0/query"
)
PINELLAS_LARGO_PARCELS = (
    "https://maps.largo.com/arcgis/rest/services/Largo_GIS_Viewer_Map/MapServer/247/query"
)

DOR_UC_MAP = {
    1: ("SFR", "Single Family Residential"),
    2: ("MH", "Mobile Home"),
    4: ("MFR-CONDO", "Multi-Family Residential Condominium"),
    11: ("SFR", "Single Family Residential"),
    25: ("MFR-CONDO", "Multi-Family Residential Condominium"),
}

MUNICIPALITY_TO_JID = {
    "ST PETE BEACH": 814,
    "SAINT PETE BEACH": 814,
    "ST. PETE BEACH": 814,
    "GULFPORT": 841,
    "CLEARWATER": 856,
    "LARGO": 859,
    "DUNEDIN": 829,
    "SAFETY HARBOR": 886,
    "TARPON SPRINGS": 898,
    "BELLEAIR": 818,
    "PINELLAS PARK": 869,
    "SEMINOLE": 891,
    "ST PETERSBURG": 893,
    "SAINT PETERSBURG": 893,
    "ST. PETERSBURG": 893,
    "OLDSMAR": 863,
    "PALM HARBOR": 635,
    "KENNETH CITY": 635,
    "UNINCORPORATED": 635,
}

SOURCE_TAG = "pinellas_shard1_run7622_i_fix"


def headers():
    return {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    }


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers=headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(path, filter_params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}?{filter_params}",
        data=body,
        headers={**headers(), "Prefer": "return=minimal"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def sb_post(path, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=body,
        headers={**headers(), "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def query_address_points(address):
    """Query Pinellas Accela Address Points layer by address."""
    if not address:
        return None
    parts = address.split(",")[0].strip().upper()
    params = urllib.parse.urlencode({
        "where": f"FULLADDR LIKE '{parts}%'",
        "outFields": "PIN_NUM,FULLADDR,MUNICIPALITY",
        "f": "json",
        "resultRecordCount": 5,
    })
    try:
        req = urllib.request.Request(
            f"{PINELLAS_ACCELA_ADDR}?{params}",
            headers={"User-Agent": "BidDeed-SHARD1-Pinellas"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        if feats:
            return feats[0].get("attributes", {})
    except Exception as e:
        print(f"  Accela address query error ({address}): {e}", flush=True)
    return None


def query_parcel_by_pin(pin):
    """Query Largo/countywide parcels layer by 18-digit PIN."""
    params = urllib.parse.urlencode({
        "where": f"ParcelId = '{pin}'",
        "outFields": "ParcelId,Parcel_Centroid_Latitude,Parcel_Centroid_Longitude,Assessed_Property_Value,FDOR_Land_Use_Code,Full_Site_Address_Line_1,Tax_District_Name",
        "f": "json",
        "resultRecordCount": 3,
    })
    try:
        req = urllib.request.Request(
            f"{PINELLAS_LARGO_PARCELS}?{params}",
            headers={"User-Agent": "BidDeed-SHARD1-Pinellas"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        if feats:
            return feats[0].get("attributes", {})
    except Exception as e:
        print(f"  Largo parcel query error (pin={pin}): {e}", flush=True)
    return None


def query_parcel_by_address(address):
    """Query Largo/countywide parcels layer by address."""
    if not address:
        return None
    parts = address.split(",")[0].strip().upper()
    # Try the first number + street name
    parts_split = parts.split(" ", 1)
    if len(parts_split) < 2:
        return None
    num = parts_split[0]
    street = parts_split[1]
    params = urllib.parse.urlencode({
        "where": f"Site_Address_Number = '{num}' AND Site_Address_Street_Name LIKE '{street[:20]}%'",
        "outFields": "ParcelId,Parcel_Centroid_Latitude,Parcel_Centroid_Longitude,Assessed_Property_Value,FDOR_Land_Use_Code,Full_Site_Address_Line_1,Tax_District_Name",
        "f": "json",
        "resultRecordCount": 5,
    })
    try:
        req = urllib.request.Request(
            f"{PINELLAS_LARGO_PARCELS}?{params}",
            headers={"User-Agent": "BidDeed-SHARD1-Pinellas"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        if feats:
            return feats[0].get("attributes", {})
    except Exception as e:
        print(f"  Largo address query error ({address}): {e}", flush=True)
    return None


def get_jid(municipality_name):
    if not municipality_name:
        return 635
    mn = municipality_name.strip().upper()
    for key, jid in MUNICIPALITY_TO_JID.items():
        if key in mn:
            return jid
    return 635


def get_zone_code(fdor_uc):
    """Return (zone_code, zone_name) from FDOR land use code."""
    if fdor_uc is None:
        return None, None
    try:
        uc = int(fdor_uc)
    except (ValueError, TypeError):
        return None, None
    return DOR_UC_MAP.get(uc, (None, None))


def main():
    print("=== SHARD-1 Pinellas I+C/D fix (run7622) ===", flush=True)

    # Step 1: Find pinellas rows with incomplete property cards
    # card_complete = parcel_id IS NOT NULL AND latitude IS NOT NULL AND longitude IS NOT NULL
    #                 AND assessed_value IS NOT NULL AND parcel_id IN (SELECT parcel_id FROM parcel_zones)
    # We need to find rows that FAIL at least one condition
    print("\nFetching incomplete pinellas property cards...", flush=True)

    # Get all pinellas rows that are missing something for card completion
    # We'll focus on those missing parcel_id OR missing geo OR missing assessed_value
    missing_parcel = sb_get(
        "multi_county_auctions",
        "county=eq.pinellas&parcel_id=is.null&select=id,case_number,property_address,county&limit=100",
    )
    print(f"  Rows missing parcel_id: {len(missing_parcel)}", flush=True)

    missing_geo = sb_get(
        "multi_county_auctions",
        "county=eq.pinellas&parcel_id=not.is.null&latitude=is.null&select=id,case_number,parcel_id,property_address,county&limit=100",
    )
    print(f"  Rows with parcel_id but missing lat/lng: {len(missing_geo)}", flush=True)

    missing_value = sb_get(
        "multi_county_auctions",
        "county=eq.pinellas&parcel_id=not.is.null&latitude=not.is.null&assessed_value=is.null&select=id,case_number,parcel_id,property_address,county&limit=100",
    )
    print(f"  Rows with parcel_id+geo but missing assessed_value: {len(missing_value)}", flush=True)

    # Get existing parcel_zones for pinellas jurisdictions
    pz_rows = sb_get(
        "parcel_zones",
        "jurisdiction_id=in.(635,814,818,829,841,856,859,863,869,886,891,893,898)&select=parcel_id&limit=5000",
    )
    existing_pz = {r["parcel_id"] for r in pz_rows}
    print(f"  Existing parcel_zones for pinellas jurisdictions: {len(existing_pz)}", flush=True)

    # Also find rows with parcel_id but no parcel_zones entry
    has_parcel_no_zone = sb_get(
        "multi_county_auctions",
        "county=eq.pinellas&parcel_id=not.is.null&latitude=not.is.null&assessed_value=not.is.null&select=id,case_number,parcel_id,property_address,county&limit=200",
    )
    # Filter to those not in existing_pz
    no_zone_rows = [r for r in has_parcel_no_zone if r.get("parcel_id") and r["parcel_id"] not in existing_pz]
    print(f"  Rows with all fields but no parcel_zones: {len(no_zone_rows)}", flush=True)

    # Step 2: Process missing_parcel rows (address lookups)
    fixes_applied = 0
    pz_inserts = []
    skipped = []

    print("\n--- Processing rows missing parcel_id ---", flush=True)
    for row in missing_parcel:
        addr = row.get("property_address")
        case = row.get("case_number")
        if not addr:
            print(f"  SKIP {case}: no address", flush=True)
            skipped.append((case, "no_address"))
            continue

        # Try Accela Address Points first
        accel_result = query_address_points(addr)
        time.sleep(0.2)

        if accel_result and accel_result.get("PIN_NUM"):
            pin = accel_result["PIN_NUM"]
            municipality = accel_result.get("MUNICIPALITY", "")
            print(f"  {case}: Accela found PIN={pin} municipality={municipality}", flush=True)

            # Now get geo/value from Largo parcels
            parcel_data = query_parcel_by_pin(pin)
            time.sleep(0.2)

            if parcel_data:
                lat = parcel_data.get("Parcel_Centroid_Latitude")
                lng = parcel_data.get("Parcel_Centroid_Longitude")
                assessed = parcel_data.get("Assessed_Property_Value")
                fdor_uc = parcel_data.get("FDOR_Land_Use_Code")
                tax_district = parcel_data.get("Tax_District_Name", "")

                patch = {"parcel_id": pin}
                if lat:
                    patch["latitude"] = lat
                if lng:
                    patch["longitude"] = lng
                if assessed:
                    patch["assessed_value"] = assessed

                status, _ = sb_patch(
                    "multi_county_auctions",
                    f"case_number=eq.{urllib.parse.quote(case)}",
                    patch,
                )
                if status in (200, 204):
                    fixes_applied += 1
                    print(f"    FIXED: parcel_id={pin} lat={lat} lng={lng} assessed={assessed}", flush=True)

                    # Insert parcel_zones if we have a zone code
                    zone_code, zone_name = get_zone_code(fdor_uc)
                    jid = get_jid(municipality or tax_district)
                    if zone_code and pin not in existing_pz:
                        pz_inserts.append({
                            "parcel_id": pin,
                            "jurisdiction_id": jid,
                            "zone_code": zone_code,
                            "zone_name": zone_name,
                            "source": f"{SOURCE_TAG}/accela_pin_{fdor_uc}",
                        })
                        existing_pz.add(pin)
                else:
                    print(f"    PATCH FAILED status={status}", flush=True)
                    skipped.append((case, f"patch_failed_{status}"))
            else:
                print(f"  {case}: PIN found but Largo parcel query returned nothing", flush=True)
                skipped.append((case, "largo_no_result"))
        else:
            # Try direct Largo address query
            parcel_data = query_parcel_by_address(addr)
            time.sleep(0.2)
            if parcel_data and parcel_data.get("ParcelId"):
                pin = parcel_data["ParcelId"]
                lat = parcel_data.get("Parcel_Centroid_Latitude")
                lng = parcel_data.get("Parcel_Centroid_Longitude")
                assessed = parcel_data.get("Assessed_Property_Value")
                fdor_uc = parcel_data.get("FDOR_Land_Use_Code")
                tax_district = parcel_data.get("Tax_District_Name", "")

                full_addr = parcel_data.get("Full_Site_Address_Line_1", "")
                print(f"  {case}: Largo found PIN={pin} addr={full_addr}", flush=True)

                patch = {"parcel_id": pin}
                if lat:
                    patch["latitude"] = lat
                if lng:
                    patch["longitude"] = lng
                if assessed:
                    patch["assessed_value"] = assessed

                status, _ = sb_patch(
                    "multi_county_auctions",
                    f"case_number=eq.{urllib.parse.quote(case)}",
                    patch,
                )
                if status in (200, 204):
                    fixes_applied += 1
                    print(f"    FIXED via Largo: parcel_id={pin}", flush=True)

                    zone_code, zone_name = get_zone_code(fdor_uc)
                    jid = get_jid(tax_district)
                    if zone_code and pin not in existing_pz:
                        pz_inserts.append({
                            "parcel_id": pin,
                            "jurisdiction_id": jid,
                            "zone_code": zone_code,
                            "zone_name": zone_name,
                            "source": f"{SOURCE_TAG}/largo_address_{fdor_uc}",
                        })
                        existing_pz.add(pin)
                else:
                    print(f"    PATCH FAILED status={status}", flush=True)
                    skipped.append((case, f"patch_failed_{status}"))
            else:
                print(f"  {case}: no match in Accela or Largo for addr={addr}", flush=True)
                skipped.append((case, "no_match"))

    # Step 3: Process rows missing geo (already have parcel_id)
    print("\n--- Processing rows with parcel_id but missing geo ---", flush=True)
    for row in missing_geo:
        case = row.get("case_number")
        pin = row.get("parcel_id")
        if not pin:
            continue

        parcel_data = query_parcel_by_pin(pin)
        time.sleep(0.2)

        if parcel_data:
            lat = parcel_data.get("Parcel_Centroid_Latitude")
            lng = parcel_data.get("Parcel_Centroid_Longitude")
            assessed = parcel_data.get("Assessed_Property_Value")
            fdor_uc = parcel_data.get("FDOR_Land_Use_Code")
            tax_district = parcel_data.get("Tax_District_Name", "")

            patch = {}
            if lat:
                patch["latitude"] = lat
            if lng:
                patch["longitude"] = lng
            if assessed:
                patch["assessed_value"] = assessed

            if patch:
                status, _ = sb_patch(
                    "multi_county_auctions",
                    f"case_number=eq.{urllib.parse.quote(case)}",
                    patch,
                )
                if status in (200, 204):
                    fixes_applied += 1
                    print(f"  {case}: geo/value backfilled for pin={pin}", flush=True)

                    zone_code, zone_name = get_zone_code(fdor_uc)
                    jid = get_jid(tax_district)
                    if zone_code and pin not in existing_pz:
                        pz_inserts.append({
                            "parcel_id": pin,
                            "jurisdiction_id": jid,
                            "zone_code": zone_code,
                            "zone_name": zone_name,
                            "source": f"{SOURCE_TAG}/geo_backfill_{fdor_uc}",
                        })
                        existing_pz.add(pin)
        else:
            print(f"  {case}: pin={pin} not found in Largo parcels", flush=True)
            skipped.append((case, f"pin_not_found_{pin}"))

    # Step 4: Process rows with parcel_id+geo+value but no parcel_zones
    print("\n--- Processing rows with all fields but no parcel_zones ---", flush=True)
    for row in no_zone_rows:
        case = row.get("case_number")
        pin = row.get("parcel_id")
        if not pin or pin in existing_pz:
            continue

        parcel_data = query_parcel_by_pin(pin)
        time.sleep(0.2)

        if parcel_data:
            fdor_uc = parcel_data.get("FDOR_Land_Use_Code")
            tax_district = parcel_data.get("Tax_District_Name", "")
            zone_code, zone_name = get_zone_code(fdor_uc)
            jid = get_jid(tax_district)

            if zone_code:
                pz_inserts.append({
                    "parcel_id": pin,
                    "jurisdiction_id": jid,
                    "zone_code": zone_code,
                    "zone_name": zone_name,
                    "source": f"{SOURCE_TAG}/zone_link_{fdor_uc}",
                })
                existing_pz.add(pin)
                print(f"  {case}: zone_code={zone_code} jid={jid} for pin={pin}", flush=True)
        else:
            print(f"  {case}: pin={pin} not found for zone lookup", flush=True)

    # Step 5: Insert parcel_zones
    print(f"\n--- Inserting {len(pz_inserts)} parcel_zones rows ---", flush=True)
    if pz_inserts:
        status, resp = sb_post(
            "parcel_zones",
            pz_inserts,
            prefer="resolution=ignore-duplicates,return=minimal",
        )
        print(f"  parcel_zones INSERT status={status}", flush=True)
        if status not in (200, 201, 204):
            print(f"  WARN: insert response: {resp[:200]}", flush=True)

    # Summary
    print("\n=== SUMMARY ===", flush=True)
    print(f"fixes_applied (geo/parcel updates): {fixes_applied}", flush=True)
    print(f"parcel_zones inserts attempted: {len(pz_inserts)}", flush=True)
    print(f"skipped rows: {len(skipped)}", flush=True)
    for s in skipped:
        print(f"  {s}", flush=True)

    print("\nTo verify, run:", flush=True)
    print("  SELECT public.pencil_dod_evaluate_county('pinellas');", flush=True)


if __name__ == "__main__":
    main()
