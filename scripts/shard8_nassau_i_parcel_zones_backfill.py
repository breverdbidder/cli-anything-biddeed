#!/usr/bin/env python3
"""
Nassau County I criterion fix — parcel_zones backfill (2026-07-20, shard-8)

BACKGROUND:
The 2026-07-18 ghost-success purge migration (20260718_gold_standard_shard5_
sarasota_nassau_bay_gulf_ghost_success_purge.sql) correctly deleted 27 nassau
parcel_zones rows that had source='shard4_run581_v2/nassau_synthetic' and no
real zoning citations (one even carried parcel_id='Property Appraiser' sentinel).
This dropped I from 97.1% (33/34) to 20.6% (7/34).

GOAL: Re-backfill parcel_zones for the 27 gap nassau parcels using REAL data
from Nassau County PA's own ArcGIS endpoint (maps.ncpafl.com).

Source (VERIFIED by shard10_run2346 session, 2026-07-02):
  - maps.ncpafl.com/ncflpa_arcgis/NassauCountyPublicTaxMap/MapServer/144
    (dsp_strap field = parcel_id, geometry = parcel polygon)
  - maps.ncpafl.com/ncflpa_arcgis/GoMaps4_Citrix/MapServer/0
    (HOUSE_NO+STREET match -> ZoningDistrict field)

The 6-7 real parcel_zones rows from shard10_run2346 use jurisdiction_id=865
(Nassau County / Fernandina Beach — the single jurisdiction row for all of
nassau per prior session precedent).

APPROACH:
1. Query Supabase for nassau parcels in multi_county_auctions with parcel_id
   IS NOT NULL but no parcel_zones row
2. For each, query maps.ncpafl.com ArcGIS for the real ZoningDistrict
3. Map zone_code to existing zoning_districts row (jurisdiction_id=865)
4. Insert parcel_zones with source='shard8_run5361_nassau_ncpa_gis_backfill'

HONESTY PROTOCOL:
- All zone codes from live ArcGIS query (VERIFIED)
- If ArcGIS returns no result for a parcel, do NOT fabricate — leave it
- Parse failures: log and skip (never insert placeholder data)

IDEMPOTENT: WHERE NOT EXISTS guard on parcel_zones insert.
"""
import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
          or os.environ.get("SUPABASE_SERVICE_KEY")
          or os.environ.get("SUPABASE_KEY", ""))

if not SB_KEY:
    print("ERROR: No SUPABASE_SERVICE_ROLE_KEY/SUPABASE_SERVICE_KEY/SUPABASE_KEY set")
    raise SystemExit(1)

HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}
PREFER_REPR = {**HEADERS, "Prefer": "return=representation"}

NASSAU_JID = 865  # Jurisdiction ID for Nassau County (all municipalities combined)
ARCGIS_BASE = "https://maps.ncpafl.com/ncflpa_arcgis"
ZONING_LAYER = f"{ARCGIS_BASE}/GoMaps4_Citrix/MapServer/0"
PARCEL_LAYER = f"{ARCGIS_BASE}/NassauCountyPublicTaxMap/MapServer/144"
SOURCE_TAG = "shard8_run5361_nassau_ncpa_gis_backfill"

NOW_ISO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sb_get(path: str, params: dict = None) -> list:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(path: str, body: list, prefer: str = "return=minimal") -> tuple:
    data = json.dumps(body).encode()
    h = {**HEADERS, "Prefer": prefer}
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_rpc(fn: str, params: dict) -> tuple:
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=data,
        headers=HEADERS,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def arcgis_query(service_url: str, where: str, out_fields: str, timeout: int = 20) -> list:
    """Query an ArcGIS FeatureServer/MapServer layer and return features."""
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
    }
    url = f"{service_url}/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        if "error" in data:
            print(f"    ArcGIS error: {data['error']}")
            return []
        return data.get("features", [])
    except Exception as e:
        print(f"    ArcGIS request failed: {e}")
        return []


def get_zone_for_parcel_by_address(address: str, house_no: str, street: str) -> str | None:
    """Query GoMaps4_Citrix zoning layer by address components. Returns zone code or None."""
    if not house_no or not street:
        return None
    # Build WHERE clause matching the pattern used in shard10_run2346
    where = f"HOUSE_NO = '{house_no}' AND STREET LIKE '{street[:20].upper()}%'"
    features = arcgis_query(ZONING_LAYER, where, "ZoningDistrict,FutureLandUse,HOUSE_NO,STREET")
    if features:
        return features[0].get("attributes", {}).get("ZoningDistrict")
    return None


def get_zone_for_parcel_by_strap(strap: str) -> str | None:
    """Query parcel tax map layer by STRAP to get zoning. Returns zone code or None."""
    # The parcel layer (layer 144) maps STRAP -> geometry; zoning comes from the GoMaps layer.
    # Try address-based zoning lookup from the parcel record.
    where = f"dsp_strap = '{strap}'"
    features = arcgis_query(PARCEL_LAYER, where, "dsp_strap,HOUSE_NO,STREET,ZoningDistrict")
    if features:
        attrs = features[0].get("attributes", {})
        zone = attrs.get("ZoningDistrict")
        if zone:
            return zone
        # Fall through to address-based lookup
        house_no = attrs.get("HOUSE_NO", "")
        street = attrs.get("STREET", "")
        if house_no and street:
            return get_zone_for_parcel_by_address(
                f"{house_no} {street}", str(house_no), street
            )
    return None


def find_or_default_zone_district(zone_code: str, zone_districts: dict) -> int | None:
    """Find zoning_districts.id for zone_code under jurisdiction 865. Returns id or None."""
    return zone_districts.get(zone_code)


def main():
    print("=" * 60)
    print("NASSAU I FIX: parcel_zones backfill (shard-8 session 5361)")
    print("=" * 60)

    # Step 0: Evaluate before
    print("\n[0] BEFORE: pencil_dod_evaluate_county('nassau')")
    status, body = sb_rpc("pencil_dod_evaluate_county", {"p_county": "nassau"})
    print(f"  status={status} body={body[:500]}")

    # Step 1: Get all nassau MCA rows with parcel_id
    print("\n[1] Fetching nassau MCA rows with parcel_id...")
    rows = sb_get("multi_county_auctions", {
        "county": "eq.nassau",
        "parcel_id": "not.is.null",
        "select": "id,case_number,parcel_id,property_address,latitude,longitude",
        "limit": "200",
    })
    print(f"  Found {len(rows)} nassau rows with parcel_id")

    # Step 2: Find which parcel_ids already have parcel_zones
    print("\n[2] Checking existing parcel_zones for nassau (jid=865)...")
    existing_zones = sb_get("parcel_zones", {
        "jurisdiction_id": "eq.865",
        "select": "parcel_id",
        "limit": "200",
    })
    existing_parcel_ids = {r["parcel_id"] for r in existing_zones}
    print(f"  Existing parcel_zones rows: {len(existing_parcel_ids)}")

    # Step 3: Find gaps
    gap_rows = [r for r in rows if r["parcel_id"] not in existing_parcel_ids]
    print(f"\n[3] Gap rows (no parcel_zones): {len(gap_rows)}")
    for r in gap_rows[:5]:
        print(f"    {r['case_number']} | {r['parcel_id']} | {r.get('property_address','?')}")
    if len(gap_rows) > 5:
        print(f"    ... and {len(gap_rows) - 5} more")

    if not gap_rows:
        print("  No gaps found — I criterion may already be satisfied")
        return

    # Step 4: Load existing zoning_districts for jurisdiction 865
    print("\n[4] Loading zoning_districts for jurisdiction 865...")
    districts = sb_get("zoning_districts", {
        "jurisdiction_id": "eq.865",
        "select": "id,code,name",
        "limit": "100",
    })
    zone_map = {d["code"]: d["id"] for d in districts}
    print(f"  Loaded {len(zone_map)} district codes: {list(zone_map.keys())}")

    # Step 5: Query ArcGIS for each gap parcel
    print(f"\n[5] Querying maps.ncpafl.com ArcGIS for {len(gap_rows)} gap parcels...")
    parcel_zones_to_insert = []
    not_found = []
    errors = []

    for i, row in enumerate(gap_rows):
        parcel_id = row["parcel_id"]
        address = row.get("property_address", "")
        print(f"  [{i+1}/{len(gap_rows)}] {parcel_id} | {address[:40]}")

        zone_code = None

        # Try STRAP-based lookup first
        zone_code = get_zone_for_parcel_by_strap(parcel_id)

        # If no zone from STRAP, try address-based lookup
        if not zone_code and address:
            parts = address.split(" ", 1)
            if len(parts) >= 2 and parts[0].isdigit():
                zone_code = get_zone_for_parcel_by_address(
                    address, parts[0], parts[1].split(",")[0]
                )

        if zone_code:
            zone_code_clean = zone_code.strip().upper()
            dist_id = find_or_default_zone_district(zone_code_clean, zone_map)
            if dist_id is None:
                # Zone code not in our districts — skip, don't fabricate
                print(f"    UNKNOWN zone '{zone_code_clean}' — skip (not in zoning_districts jid=865)")
                not_found.append({"parcel_id": parcel_id, "reason": f"unknown zone: {zone_code_clean}"})
            else:
                print(f"    FOUND zone={zone_code_clean} dist_id={dist_id} ✓")
                parcel_zones_to_insert.append({
                    "parcel_id": parcel_id,
                    "tax_account": parcel_id,
                    "jurisdiction_id": NASSAU_JID,
                    "zone_code": zone_code_clean,
                    "zone_name": next(
                        (d["name"] for d in districts if d["code"] == zone_code_clean), zone_code_clean
                    ),
                    "source": SOURCE_TAG,
                    "created_at": NOW_ISO,
                    "updated_at": NOW_ISO,
                })
        else:
            print(f"    NOT FOUND — no ArcGIS result")
            not_found.append({"parcel_id": parcel_id, "reason": "no ArcGIS result"})

        # Rate limit
        time.sleep(0.5)

    print(f"\n  Results: {len(parcel_zones_to_insert)} insertable, {len(not_found)} not found")

    # Step 6: Insert parcel_zones
    if parcel_zones_to_insert:
        print(f"\n[6] Inserting {len(parcel_zones_to_insert)} parcel_zones rows...")
        status, resp = sb_post("parcel_zones", parcel_zones_to_insert,
                               prefer="resolution=ignore-duplicates,return=minimal")
        print(f"  status={status}")
        if status not in (200, 201, 204):
            print(f"  ERROR: {resp[:300]}")
            raise SystemExit(f"parcel_zones insert failed: {status}")
        else:
            print(f"  Successfully inserted {len(parcel_zones_to_insert)} parcel_zones rows")
    else:
        print("\n[6] No parcel_zones to insert")

    # Step 7: Evaluate after
    print("\n[7] AFTER: pencil_dod_evaluate_county('nassau')")
    status, body = sb_rpc("pencil_dod_evaluate_county", {"p_county": "nassau"})
    print(f"  status={status} body={body[:500]}")

    # Step 8: Log to ultraloop audit
    print("\n[8] Logging to gold_standard_ultraloop_audit...")
    after_eval = {}
    try:
        after_eval = json.loads(body) if status == 200 else {}
    except Exception:
        pass

    letter_i = after_eval.get("I", {})
    i_metric = letter_i.get("metric", 0)
    i_pass = letter_i.get("pass", False)

    audit_row = [{
        "dispatch_id": "0ddd603c-68ec-45c0-86b8-3b643c98faf3",
        "ultraloop_mode": "fallback",
        "county_slug": "nassau",
        "letter": "I",
        "claim": f"Backfilled {len(parcel_zones_to_insert)} parcel_zones rows from maps.ncpafl.com ArcGIS. Post-fix I metric={i_metric}, pass={i_pass}. Not-found: {len(not_found)} parcels (no ArcGIS result or unknown zone code).",
        "refuter_evidence": json.dumps({
            "inserted": len(parcel_zones_to_insert),
            "not_found": not_found[:10],
            "source": SOURCE_TAG,
            "arcgis_endpoint": ZONING_LAYER,
            "honesty_marker": "VERIFIED — zone codes from live ArcGIS response, not fabricated",
        }),
        "survived": i_pass,
        "created_at": NOW_ISO,
    }]
    st2, resp2 = sb_post("gold_standard_ultraloop_audit", audit_row,
                          prefer="resolution=ignore-duplicates,return=minimal")
    print(f"  audit insert: status={st2}")

    print("\n=== DONE ===")
    print(f"  Inserted: {len(parcel_zones_to_insert)} parcel_zones")
    print(f"  Not found: {len(not_found)}")
    print(f"  Nassau I metric after: {i_metric} | PASS: {i_pass}")

    if not_found:
        print("\n  Not-found parcels (no real zoning data from ArcGIS — NOT fabricated):")
        for nf in not_found:
            print(f"    {nf}")


if __name__ == "__main__":
    main()
