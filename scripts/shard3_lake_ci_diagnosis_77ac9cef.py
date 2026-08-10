#!/usr/bin/env python3
"""GOLD STANDARD shard-3 (dispatch 77ac9cef-69e5-48e3-b76e-7bddb2b42d7d), lake C+I diagnosis.

Queries live DB to establish current baseline and find the 7 unmatched C rows.

Usage: python3 scripts/shard3_lake_ci_diagnosis_77ac9cef.py
"""
import json
import os
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(),
        method="POST",
        headers={**REST_HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def main():
    print("=== SHARD-3 LAKE C+I DIAGNOSIS (dispatch 77ac9cef) ===\n")

    # 1. Current evaluator state
    print("### pencil_dod_evaluate_county('lake') CURRENT STATE")
    result = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(json.dumps(result, indent=2))
    print()

    # 2. C: find cases not yet matched_clean (non-tier1 or null parity in denominator)
    print("### C: Rows NOT matched_clean in evaluator scope")
    # The evaluator filters by some date scope. Let's pull all lake rows that aren't matched_clean
    not_clean = rest_get(
        "multi_county_auctions"
        "?county=eq.lake"
        "&select=id,case_number,plaintiff,owner_name,property_address,parcel_id,parity_status,parity_source,data_source"
        "&parity_status=neq.matched_clean"
        "&order=case_number"
    )
    # Also get null parity_status rows
    null_parity = rest_get(
        "multi_county_auctions"
        "?county=eq.lake"
        "&select=id,case_number,plaintiff,owner_name,property_address,parcel_id,parity_status,parity_source,data_source"
        "&parity_status=is.null"
        "&order=case_number"
    )
    print(f"Not matched_clean (non-null): {len(not_clean)} rows")
    print(f"parity_status IS NULL: {len(null_parity)} rows")
    print("\nSample of not-matched rows (first 15):")
    for r in (not_clean + null_parity)[:15]:
        print(f"  case={r['case_number']} parity={r['parity_status']} source={r['parity_source']} "
              f"data_source={r['data_source']} plaintiff={r.get('plaintiff','')[:40]}")

    print()

    # 3. I: find cases with parcel_id but missing zone_code in the card view
    # The card requires: address, geo, value, AND parcel_zones zone_code
    print("### I: parcel-linked auctions missing zone_code in parcel_zones")
    with_parcel = rest_get(
        "multi_county_auctions"
        "?county=eq.lake"
        "&parcel_id=not.is.null"
        "&select=id,case_number,parcel_id,property_address,assessed_value,latitude,longitude"
        "&order=case_number"
        "&limit=200"
    )
    print(f"Total lake auctions with parcel_id: {len(with_parcel)}")

    # Check parcel_zones coverage for these
    parcel_ids = [r["parcel_id"] for r in with_parcel if r.get("parcel_id")]
    print(f"Distinct parcel_ids: {len(set(parcel_ids))}")

    # Get existing parcel_zones for lake
    lake_pz = rest_get(
        "parcel_zones"
        "?select=parcel_id,jurisdiction_id,zone_code,zone_name,source"
        "&or=(jurisdiction_id.eq.835,jurisdiction_id.eq.926,jurisdiction_id.eq.1030,"
        "jurisdiction_id.eq.1032,jurisdiction_id.eq.1034)"
        "&limit=500"
    )
    pz_by_pid = {r["parcel_id"]: r for r in lake_pz}
    print(f"parcel_zones rows for lake jurisdictions: {len(lake_pz)}")

    # Find unmatched parcel_ids
    unzoned_pids = [pid for pid in set(parcel_ids) if pid not in pz_by_pid]
    print(f"parcel_ids WITHOUT parcel_zones entry: {len(unzoned_pids)}")
    for pid in unzoned_pids[:10]:
        matching = [r for r in with_parcel if r.get("parcel_id") == pid]
        for m in matching[:1]:
            print(f"  parcel_id={pid} case={m['case_number']} addr={m.get('property_address','')} "
                  f"lat={m.get('latitude')} lon={m.get('longitude')}")

    print()

    # 4. Check existing zoning_districts for lake jurisdictions
    print("### zoning_districts for lake jurisdictions")
    lake_jurisids = [835, 926, 1030, 1032, 1034]
    for jid in lake_jurisids:
        zds = rest_get(
            f"zoning_districts?jurisdiction_id=eq.{jid}"
            "&select=id,code,name,category,far_regulated,density_regulated&limit=30"
        )
        print(f"  jurisdiction_id={jid}: {len(zds)} districts")
        for zd in zds:
            # Check zone_standards
            zs = rest_get(
                f"zone_standards?zoning_district_id=eq.{zd['id']}"
                "&select=id,max_density_du_acre,max_far,parking_per_1000sf"
                "&limit=1"
            )
            has_std = len(zs) > 0
            print(f"    code={zd['code']} cat={zd['category']} far_reg={zd.get('far_regulated')} "
                  f"dens_reg={zd.get('density_regulated')} has_standards={has_std}")

    print()

    # 5. Check the 10 target parcel_ids from lake_i_zoning_parcel_zones_9row_insert.sql
    TARGET_PARCEL_IDS = [
        "032225010000009000",  # Groveland case 2016CA002108
        "262125200500020900",  # Groveland case 2024CA001079
        "222125000300002600",  # Groveland case 2025CA000018
        "291926090009401800",  # Tavares case 2025CA000637
        "062026005000008600",  # Tavares case 2025CA000787
        "361925005000026800",  # Tavares case 2025CA001111
        "271926005000008000",  # Tavares case 2025CA002620
        "141826010000000401",  # Umatilla case 2025CA002679
        "062026005000001200",  # Tavares case 2025CA002688
        "102224001400032100",  # Mascotte case 2026CA000589
    ]
    print("### Status of 10 target parcel_ids (from prior reverted insert):")
    for pid in TARGET_PARCEL_IDS:
        pz_row = pz_by_pid.get(pid)
        # find auction row
        mca = [r for r in with_parcel if r.get("parcel_id") == pid]
        lat = mca[0].get("latitude") if mca else None
        lon = mca[0].get("longitude") if mca else None
        case = mca[0].get("case_number") if mca else "NOT FOUND"
        print(f"  parcel_id={pid} case={case} lat={lat} lon={lon}")
        print(f"    in parcel_zones: {pz_row is not None}")
        if pz_row:
            print(f"    zone_code={pz_row.get('zone_code')} jid={pz_row.get('jurisdiction_id')}")

    print("\n=== DIAGNOSIS COMPLETE ===")


if __name__ == "__main__":
    main()
