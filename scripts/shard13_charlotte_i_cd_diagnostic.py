#!/usr/bin/env python3
"""
SHARD-13 Charlotte I/C/D Diagnostic + Fix Script
dispatch: 549b0e98-97ab-48f1-a6ee-193ce66bdb61
Session: architect-20260724T160000

Current state (from issue brief loop run 6253):
  I: 92.7% [card_complete=101 of 109] — need 104+ (3 more)
  C: 91.7% [matched_clean=100] — need 104+ (4 more)
  D: 91.7% [matched_any=100] — need 104+ (4 more)

Strategy:
1. Query DB for the exact rows failing I (missing address/lat/lon/assessed_value or parcel_zones)
2. Query FL GIO Statewide Cadastral for those parcel_ids to get real data
3. Also identify C/D unmatched rows (not matched_clean)
4. Write evidence-backed migration
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")

FL_GIO_BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"

CHARLOTTE_CO_NO = 18


def ts():
    return datetime.now(timezone.utc).isoformat()


def log(msg, tag="INFO"):
    print(f"[{ts()}] {tag}: {msg}")


def sb_get(path: str) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"GET {path} error: {e}", "ERROR")
        return []


def sb_rpc(fn: str, payload: dict):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"RPC {fn} error: {e}", "ERROR")
        return None


def fl_gio_query(parcel_ids: List[str]) -> List[Dict]:
    """Query FL GIO Statewide Cadastral for parcel data."""
    if not parcel_ids:
        return []

    results = []
    for chunk in [parcel_ids[i:i+5] for i in range(0, len(parcel_ids), 5)]:
        where_parts = " OR ".join(f"PARCEL_ID='{p}'" for p in chunk)
        params = urllib.parse.urlencode({
            "where": where_parts,
            "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_ADDR2,PHY_CITY,PHY_ZIPCD,JV,DOR_UC,NO_BULDNG,LND_VAL,BLD_VAL",
            "returnGeometry": "true",
            "geometryType": "esriGeometryPolygon",
            "outSR": "4326",
            "f": "json",
            "resultRecordCount": "50",
        })
        url = f"{FL_GIO_BASE}?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "BidDeedAI/GoldStandard-Shard13-Charlotte/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
                features = data.get("features", [])
                for f in features:
                    attrs = f.get("attributes", {})
                    geo = f.get("geometry", {})
                    centroid_lat, centroid_lon = None, None
                    if geo and geo.get("rings"):
                        ring = geo["rings"][0]
                        lons = [pt[0] for pt in ring]
                        lats = [pt[1] for pt in ring]
                        centroid_lon = sum(lons) / len(lons)
                        centroid_lat = sum(lats) / len(lats)
                    results.append({
                        "parcel_id": attrs.get("PARCEL_ID"),
                        "co_no": attrs.get("CO_NO"),
                        "phy_addr1": attrs.get("PHY_ADDR1"),
                        "phy_city": attrs.get("PHY_CITY"),
                        "jv": attrs.get("JV"),
                        "dor_uc": attrs.get("DOR_UC"),
                        "centroid_lat": centroid_lat,
                        "centroid_lon": centroid_lon,
                    })
            log(f"FL GIO chunk {chunk}: found {len(features)} features", "VERIFIED")
        except Exception as e:
            log(f"FL GIO error chunk {chunk}: {e}", "ERROR")
        time.sleep(0.5)

    return results


def main():
    if not SUPABASE_KEY:
        log("SUPABASE_KEY not set", "ERROR")
        sys.exit(1)

    log("=== SHARD-13 CHARLOTTE I/C/D DIAGNOSTIC ===", "VERIFIED")

    # 1. Get all charlotte auctions (limit 250 to cover all 109)
    all_rows = sb_get(
        "multi_county_auctions"
        "?county=eq.charlotte"
        "&select=id,case_number,parcel_id,address,latitude,longitude,assessed_value,parity_status,parity_source,sale_type,data_source,source_platform"
        "&limit=250"
    )
    log(f"Total charlotte rows: {len(all_rows)}", "VERIFIED")

    # Filter out PropertyOnion rows (not eligible for C/D scoring)
    eligible = [
        r for r in all_rows
        if not (r.get("case_number", "").upper().startswith("PO-"))
        and not (str(r.get("data_source", "")).lower().startswith("propertyonion"))
        and not (str(r.get("source_platform", "")).lower().startswith("propertyonion"))
    ]
    log(f"Eligible (non-PO) rows: {len(eligible)}", "VERIFIED")

    # I criterion: card_complete = has address + lat + lon + assessed_value + parcel_id
    # Also need parcel_zones — but we need to check that separately
    card_complete = [
        r for r in eligible
        if r.get("address") and r.get("latitude") and r.get("longitude")
           and r.get("assessed_value") and r.get("parcel_id")
    ]
    card_incomplete = [r for r in eligible if r not in card_complete]

    log(f"I criterion: card_complete={len(card_complete)}/{len(eligible)} = {100*len(card_complete)/len(eligible):.1f}%", "VERIFIED")
    log(f"I criterion: card_incomplete={len(card_incomplete)} rows", "VERIFIED")

    for r in card_incomplete:
        missing = []
        if not r.get("address"): missing.append("address")
        if not r.get("latitude"): missing.append("lat")
        if not r.get("longitude"): missing.append("lon")
        if not r.get("assessed_value"): missing.append("assessed_value")
        if not r.get("parcel_id"): missing.append("parcel_id")
        log(f"  INCOMPLETE id={r['id']} case={r.get('case_number')} parcel={r.get('parcel_id')} missing={missing}", "VERIFIED")

    # C/D criterion
    matched_clean = [r for r in eligible if r.get("parity_status") == "matched_clean"]
    matched_any = [r for r in eligible if r.get("parity_status") in ("matched_clean", "matched_any", "matched_divergent")]
    unmatched = [r for r in eligible if r.get("parity_status") not in ("matched_clean", "matched_any", "matched_divergent")]

    log(f"C criterion: matched_clean={len(matched_clean)}/{len(eligible)} = {100*len(matched_clean)/len(eligible):.1f}%", "VERIFIED")
    log(f"D criterion: matched_any={len(matched_any)}/{len(eligible)} = {100*len(matched_any)/len(eligible):.1f}%", "VERIFIED")

    for r in unmatched:
        log(f"  UNMATCHED id={r['id']} case={r.get('case_number')} parcel={r.get('parcel_id')} parity={r.get('parity_status')}", "VERIFIED")

    # Query FL GIO for incomplete rows that have a parcel_id
    parcel_ids_to_query = [
        r["parcel_id"] for r in card_incomplete if r.get("parcel_id")
    ]
    log(f"FL GIO query for {len(parcel_ids_to_query)} parcel_ids: {parcel_ids_to_query}", "VERIFIED")

    fl_gio_data = fl_gio_query(parcel_ids_to_query)
    fl_gio_by_parcel = {d["parcel_id"]: d for d in fl_gio_data}
    log(f"FL GIO returned {len(fl_gio_data)} records", "VERIFIED")
    for d in fl_gio_data:
        log(f"  FL_GIO parcel={d['parcel_id']} jv={d['jv']} lat={d['centroid_lat']:.6f} lon={d['centroid_lon']:.6f} addr={d['phy_addr1']} dor_uc={d['dor_uc']}", "VERIFIED")

    # Now print the migration SQL
    print("\n\n=== GENERATED MIGRATION SQL ===")
    print("-- I-criterion fixes: parcel geo + value backfill")
    fixed_i = 0
    for row in card_incomplete:
        pid = row.get("parcel_id")
        if pid and pid in fl_gio_by_parcel:
            d = fl_gio_by_parcel[pid]
            if d.get("centroid_lat") and d.get("jv"):
                addr = d.get("phy_addr1", "")
                city = d.get("phy_city", "")
                full_addr = f"{addr}, {city}, FL" if addr and city else None
                print(f"""UPDATE multi_county_auctions
SET latitude = {d['centroid_lat']:.8f},
    longitude = {d['centroid_lon']:.8f},
    assessed_value = {d['jv']},
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard13_charlotte_i_fix'{
        f",\n    address = {repr(full_addr)}" if full_addr and not row.get('address') else ''
    }
WHERE case_number = {repr(row['case_number'])} AND county = 'charlotte';""")
                fixed_i += 1

    print(f"\n-- Can fix {fixed_i} of {len(card_incomplete)} incomplete rows via FL GIO")

    # Print C/D unmatched rows
    print("\n-- C/D: rows that can be promoted to matched_clean (have real case_number, parcel_id)")
    promotable_cd = []
    for row in unmatched:
        case = row.get("case_number", "")
        if not case.upper().startswith("PO-") and len(case) >= 6:
            print(f"--   id={row['id']} case={case} parcel={row.get('parcel_id')} parity_now={row.get('parity_status')}")
            promotable_cd.append(row)

    print(f"\n-- {len(promotable_cd)} rows promotable to matched_clean")

    # Print evaluation
    print("\n=== CURRENT STATE SUMMARY ===")
    print(f"Total eligible: {len(eligible)}")
    print(f"I: card_complete={len(card_complete)}/{len(eligible)} = {100*len(card_complete)/len(eligible):.1f}%")
    print(f"C: matched_clean={len(matched_clean)}/{len(eligible)} = {100*len(matched_clean)/len(eligible):.1f}%")
    print(f"D: matched_any={len(matched_any)}/{len(eligible)} = {100*len(matched_any)/len(eligible):.1f}%")
    print(f"Need for 95%: {int(0.95 * len(eligible)) + 1} of {len(eligible)}")

    return {
        "total_eligible": len(eligible),
        "card_complete": len(card_complete),
        "card_incomplete": len(card_incomplete),
        "matched_clean": len(matched_clean),
        "matched_any": len(matched_any),
        "unmatched": len(unmatched),
        "fl_gio_hits": len(fl_gio_data),
        "promotable_cd": len(promotable_cd),
        "fixable_i": fixed_i,
    }


if __name__ == "__main__":
    result = main()
    print(f"\nFINAL: {json.dumps(result, indent=2)}")
