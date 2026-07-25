#!/usr/bin/env python3
"""SHARD-1 run6288 santa_rosa criterion I (property-card completeness) backfill.

Issue: 87/92 cards complete (94.6%), need 88/92 (95.0%) to pass.
6 new auctions have been added to the county since the prior fix (gtm22j_santa_rosa_i_backfill.py
fixed cards for 86-row baseline; county now has 92 rows, so 6 new rows need enrichment).

This script:
1. Identifies the 5 santa_rosa rows with incomplete property cards
2. Fetches real data from authoritative sources:
   - Santa Rosa County Property Appraiser: https://parcelview.srcpa.gov/
   - ArcGIS FeatureServer (official parcel polygons, 2025-03-20 vintage):
     https://services.arcgis.com/Eg4L1xEv2R3abuQd/arcgis/rest/services/ParcelsOpenData/FeatureServer/0
   - US Census Bureau geocoder (no key required):
     https://geocoding.geo.census.gov/geocoder/locations/onelineaddress
3. Applies ONLY real, sourced data — no fabrication, no county centroids, no median fallbacks
4. Any row that cannot be verified from real sources is SKIPPED (BLANK > WRONG)

Honesty protocol: all claims tagged VERIFIED/INFERRED/UNKNOWN.
Idempotent: guards check NULL before patching.

Run: python3 scripts/shard1_santa_rosa_i_run6288.py
     python3 scripts/shard1_santa_rosa_i_run6288.py --dry-run
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
DRY_RUN = "--dry-run" in sys.argv
COUNTY = "santa_rosa"


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    if DRY_RUN:
        print(f"  [DRY RUN] PATCH {path} <- {body}")
        return [body]
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def rest_post(path, body):
    if DRY_RUN:
        print(f"  [DRY RUN] POST {path} <- {body}")
        return [body]
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json",
                 "Prefer": "return=representation,resolution=ignore-duplicates"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def rpc_call(fn, args=None):
    body = args or {}
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def fetch_srcpa_parcel(parcel_id):
    """Fetch parcel data from Santa Rosa County Property Appraiser.
    Returns dict with assessed_value, market_value, and zoning info.
    VERIFIED: srcpa.gov parcelview API confirmed live in prior sessions.
    """
    try:
        url = f"https://parcelview.srcpa.gov/api/parcel/{urllib.parse.quote(parcel_id)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return data
    except Exception as e:
        print(f"    srcpa.gov fetch failed for {parcel_id}: {e}")
        return None


def fetch_arcgis_centroid(par_num_clean):
    """Fetch parcel centroid from Santa Rosa ArcGIS FeatureServer.
    VERIFIED: endpoint confirmed live in prior session (gtm22j_santa_rosa_i_backfill.py).
    par_num_clean: parcel ID without dashes (e.g. '401N280090379000010')
    Returns (lat, lon) or None.
    """
    try:
        base = "https://services.arcgis.com/Eg4L1xEv2R3abuQd/arcgis/rest/services/ParcelsOpenData/FeatureServer/0"
        where = urllib.parse.quote(f"PAR_NUM='{par_num_clean}'")
        url = f"{base}/query?where={where}&outFields=PAR_NUM&returnCentroid=true&f=json&outSR=4326"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if features and features[0].get("centroid"):
            c = features[0]["centroid"]
            return c.get("y"), c.get("x")
    except Exception as e:
        print(f"    ArcGIS centroid fetch failed: {e}")
    return None, None


def fetch_census_geocode(address):
    """Geocode address via US Census Bureau geocoder.
    VERIFIED: confirmed free, no key, returns lat/lon for Florida addresses.
    Returns (lat, lon) or (None, None).
    """
    try:
        encoded = urllib.parse.quote(address)
        url = (f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
               f"?address={encoded}&benchmark=2020&format=json")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        matches = data.get("result", {}).get("addressMatches", [])
        if matches:
            coords = matches[0].get("coordinates", {})
            return coords.get("y"), coords.get("x")
    except Exception as e:
        print(f"    Census geocoder failed for '{address}': {e}")
    return None, None


def identify_incomplete_cards():
    """Query DB to find santa_rosa rows with incomplete property cards.
    Card requires: property_address + lat + lon + (assessed_value OR market_value) + parcel_id
    Returns list of row dicts.
    """
    # Fetch all santa_rosa rows with their card fields
    rows = rest_get(
        "multi_county_auctions"
        "?county=eq.santa_rosa"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value"
        "&order=case_number"
    )
    print(f"Total santa_rosa rows: {len(rows)}")
    incomplete = []
    for row in rows:
        has_address = bool(row.get("property_address") and row["property_address"].strip())
        has_lat = row.get("latitude") is not None
        has_lon = row.get("longitude") is not None
        has_value = row.get("assessed_value") is not None or row.get("market_value") is not None
        has_parcel = row.get("parcel_id") is not None
        card_complete = has_address and has_lat and has_lon and has_value and has_parcel
        if not card_complete:
            incomplete.append({
                "row": row,
                "missing": {
                    "address": not has_address,
                    "lat": not has_lat,
                    "lon": not has_lon,
                    "value": not has_value,
                    "parcel_id": not has_parcel,
                },
            })
    print(f"Incomplete cards: {len(incomplete)}")
    return incomplete, len(rows)


def main():
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)

    print("=== santa_rosa letter-I property-card backfill (run6288) ===")
    if DRY_RUN:
        print("*** DRY RUN — no writes ***")

    # Step 1: identify incomplete cards
    incomplete, total = identify_incomplete_cards()
    complete_before = total - len(incomplete)
    pct_before = 100.0 * complete_before / total if total > 0 else 0
    print(f"\nBEFORE: {complete_before}/{total} = {pct_before:.1f}%")
    print(f"Target: {int(total * 0.95)} ({95.0:.1f}%)")
    print(f"Need to fix: {max(0, int(total * 0.95) - complete_before + (1 if (total*0.95) != int(total*0.95) else 0))} rows\n")

    if pct_before >= 95.0:
        print("Already at or above 95%. Nothing to do.")
        # Still run verification
        result = rpc_call("pencil_dod_evaluate_county", {"p_county": COUNTY})
        print(f"\nVERIFICATION (pencil_dod_evaluate_county):\n{json.dumps(result, indent=2)}")
        return

    # Step 2: for each incomplete row, try to fetch real data
    fixed_count = 0
    for item in incomplete:
        row = item["row"]
        missing = item["missing"]
        case_num = row["case_number"]
        parcel_id = row.get("parcel_id")

        print(f"\n--- Case: {case_num} | Parcel: {parcel_id} ---")
        print(f"  Missing: {[k for k, v in missing.items() if v]}")

        if missing["parcel_id"]:
            print(f"  SKIP: no parcel_id — cannot look up from property appraiser (BLANK > WRONG)")
            continue

        patch_fields = {}
        parcel_zones_insert = None
        evidence = []

        # Normalize parcel_id to PAR_NUM format (remove dashes for ArcGIS)
        par_num_clean = (parcel_id or "").replace("-", "")

        # 2a. Try srcpa.gov for assessed/market value
        if missing["value"]:
            srcpa_data = fetch_srcpa_parcel(parcel_id)
            time.sleep(0.5)
            if srcpa_data:
                # Try to extract assessed and market values from the response
                # Structure may vary; try common field names
                for fld_assessed in ["assessedValue", "assessed_value", "CoAssessedValue", "coAssessedValue"]:
                    if srcpa_data.get(fld_assessed):
                        try:
                            patch_fields["assessed_value"] = float(str(srcpa_data[fld_assessed]).replace(",", ""))
                            evidence.append(f"assessed_value={patch_fields['assessed_value']} from srcpa.gov parcelview (field {fld_assessed}) [VERIFIED]")
                            break
                        except (ValueError, TypeError):
                            pass
                for fld_mkt in ["justValue", "just_value", "marketValue", "market_value", "JustValue"]:
                    if srcpa_data.get(fld_mkt):
                        try:
                            patch_fields["market_value"] = float(str(srcpa_data[fld_mkt]).replace(",", ""))
                            evidence.append(f"market_value={patch_fields['market_value']} from srcpa.gov parcelview (field {fld_mkt}) [VERIFIED]")
                            break
                        except (ValueError, TypeError):
                            pass
            else:
                print(f"  srcpa.gov unavailable for {parcel_id} — value left null [UNKNOWN]")

        # 2b. Try lat/lon
        if missing["lat"] or missing["lon"]:
            address = row.get("property_address", "").strip()
            if address and address not in {"", "TBD", "UNKNOWN", "N/A"}:
                # Try Census geocoder
                lat, lon = fetch_census_geocode(f"{address}, FL")
                time.sleep(0.5)
                if lat and lon:
                    patch_fields["latitude"] = lat
                    patch_fields["longitude"] = lon
                    evidence.append(f"lat={lat}, lon={lon} from Census geocoder for '{address}' [VERIFIED]")
                else:
                    # Try ArcGIS centroid
                    lat, lon = fetch_arcgis_centroid(par_num_clean)
                    time.sleep(0.5)
                    if lat and lon:
                        patch_fields["latitude"] = lat
                        patch_fields["longitude"] = lon
                        evidence.append(f"lat={lat}, lon={lon} from ArcGIS FeatureServer centroid PAR_NUM={par_num_clean} [VERIFIED]")
                    else:
                        print(f"  No geo from Census or ArcGIS for {case_num} — lat/lon left null [UNKNOWN]")
            else:
                # No address — try ArcGIS centroid directly
                lat, lon = fetch_arcgis_centroid(par_num_clean)
                time.sleep(0.5)
                if lat and lon:
                    patch_fields["latitude"] = lat
                    patch_fields["longitude"] = lon
                    evidence.append(f"lat={lat}, lon={lon} from ArcGIS FeatureServer centroid PAR_NUM={par_num_clean} (no address on tax roll) [VERIFIED]")
                else:
                    print(f"  No address + no ArcGIS centroid for {case_num} — lat/lon left null [UNKNOWN]")

        # 2c. Address missing — if parcel has address in srcpa data
        if missing["address"]:
            # This field is tricky — only set from a real source
            # We skip address synthesis; it would be INFERRED
            print(f"  Address missing — cannot fabricate safely. Leaving null [BLANK > WRONG]")

        # Check if we have enough to write
        if not patch_fields:
            print(f"  No real data found for {case_num} — SKIPPED (BLANK > WRONG)")
            continue

        # Check if this patch actually fixes the card
        will_fix_lat = "latitude" in patch_fields and missing["lat"]
        will_fix_lon = "longitude" in patch_fields and missing["lon"]
        will_fix_value = ("assessed_value" in patch_fields or "market_value" in patch_fields) and missing["value"]

        # After patch, would the card be complete?
        post_missing = {
            "address": missing["address"] and "property_address" not in patch_fields,
            "lat": missing["lat"] and "latitude" not in patch_fields,
            "lon": missing["lon"] and "longitude" not in patch_fields,
            "value": missing["value"] and "assessed_value" not in patch_fields and "market_value" not in patch_fields,
            "parcel_id": missing["parcel_id"],
        }
        will_be_complete = not any(post_missing.values())

        print(f"  Patch: {patch_fields}")
        for e in evidence:
            print(f"    evidence: {e}")
        print(f"  Card complete after patch: {will_be_complete}")

        # Apply patch
        result = rest_patch(
            f"multi_county_auctions?case_number=eq.{case_num}&county=eq.{COUNTY}",
            patch_fields)
        print(f"  PATCHED {case_num}: {list(patch_fields.keys())}")

        if will_be_complete:
            fixed_count += 1

    print(f"\n=== Summary ===")
    print(f"Incomplete rows processed: {len(incomplete)}")
    print(f"Cards newly completed: {fixed_count}")
    complete_after = complete_before + fixed_count
    pct_after = 100.0 * complete_after / total if total > 0 else 0
    print(f"AFTER (estimated): {complete_after}/{total} = {pct_after:.1f}%")
    print(f"I PASS threshold: 95.0%  -> {'PASS' if pct_after >= 95.0 else 'STILL FAIL'}")

    # Step 3: live verification
    print(f"\n=== VERIFICATION: pencil_dod_evaluate_county('{COUNTY}') ===")
    try:
        result = rpc_call("pencil_dod_evaluate_county", {"p_county": COUNTY})
        print(json.dumps(result, indent=2))
        # Extract I metric
        if isinstance(result, list) and result:
            ev = result[0].get("pencil_dod_evaluate_county", result[0])
            i_data = ev.get("I", {})
            print(f"\nLetter I: pass={i_data.get('pass')}, metric={i_data.get('metric')}, detail={i_data.get('detail')}")
    except Exception as e:
        print(f"Evaluation RPC failed: {e}")
        print("UNTESTED — could not run live evaluator")


if __name__ == "__main__":
    main()
