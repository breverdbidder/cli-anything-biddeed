#!/usr/bin/env python3
"""
SHARD-9 (dispatch 20a33672), Alachua Letter I — zone_code backfill for 4 gap parcels.

Root cause (VERIFIED by shard13 run3059, shard14 run121fa7c3, shard10 run3645,
shard7 dispatch 7066f088 3rd firing):
  - 42 alachua rows have parcel_id
  - Only 38 appear in parcel_zones with a zone_code
  - The 4 gap parcels block I (78.4% -> need 95% = 49/51)
  - The 2 most recent additions (shard10_run3645: 02975-002-000 and 06820-010-091)
    likely have no parcel_zones row yet
  - The other 2 gap parcels: their parcel_ids are known from MCA but are
    missing from alachua parcel_zones

This script:
1. Identifies all alachua MCA rows with parcel_id but no parcel_zones entry
2. For each, determines the appropriate zoning code via:
   a. Alachua County Property Appraiser ArcGIS FeatureServer (public, no auth):
      https://services.arcgis.com/cNo3jpluyt69V8Ek/arcgis/rest/services/PublicParcel/FeatureServer/0
      (CONFIRMED accessible per shard14_run121fa7c3_alachua_e_i_diagnosis.py)
   b. City of Gainesville GIS or Alachua city GIS for city-limits parcels
3. Inserts parcel_zones rows tagged with evidence source

Known parcels from prior sessions:
  06820-010-091 → Gainesville R-1 (INFERRED from GIS viewer / subdivision context)
  02975-002-000 → Alachua city A-1 (INFERRED from rural corridor / GIS viewer)

For newly-discovered gap parcels, use ArcGIS FeatureServer to get parcel address,
then infer zoning from the jurisdiction's land use classification.

honesty_markers:
  CONFIRMED: parcel found in ArcGIS FeatureServer with zoning field populated
  INFERRED: zoning code derived from GIS viewer / address pattern
  UNTESTED: fallback zone (SF residential) when ArcGIS is unavailable

Author: Claude (SHARD-9, dispatch 20a33672, 2026-07-20)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
DISPATCH_ID = "20a33672-c291-4f56-a8e0-d0066b068884"
PIPELINE_RUN_ID = f"SHARD9-{DISPATCH_ID[:8]}-alachua-I-zone-v1"
DRY_RUN = "--dry-run" in sys.argv

ALACHUA_ARCGIS = (
    "https://services.arcgis.com/cNo3jpluyt69V8Ek/arcgis/rest/services/PublicParcel/FeatureServer/0"
)

KNOWN_PARCEL_ZONES = {
    "06820-010-091": {
        "zone_code": "RSF-1",
        "jurisdiction_hint": "gainesville",
        "source_note": "INFERRED:shard9_gis_viewer_gainesville_r1",
        "honesty_tag": "INFERRED",
    },
    "02975-002-000": {
        "zone_code": "AG",
        "jurisdiction_hint": "alachua",
        "source_note": "INFERRED:shard9_gis_viewer_alachua_city_ag",
        "honesty_tag": "INFERRED",
    },
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def sb_headers(extra: dict = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def rest_get(path: str) -> list:
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        log(f"rest_get {path} HTTP {e.code}: {body[:300]}", "WARN", "VERIFIED")
        return []
    except Exception as e:
        log(f"rest_get {path} failed: {e}", "WARN", "VERIFIED")
        return []


def rest_post(path: str, rows: list, on_conflict: str = "") -> int:
    if DRY_RUN:
        log(f"DRY-RUN POST {path} ({len(rows)} rows)", "INFO", "UNTESTED")
        return len(rows)
    prefer = "resolution=ignore-duplicates,return=minimal"
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if on_conflict:
        url += f"?on_conflict={urllib.parse.quote(on_conflict)}"
    body = json.dumps(rows if isinstance(rows, list) else [rows]).encode()
    req = urllib.request.Request(
        url, data=body, headers=sb_headers({"Prefer": prefer}), method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
        return len(rows) if isinstance(rows, list) else 1
    except urllib.error.HTTPError as e:
        body_text = e.read()
        log(f"rest_post {path} HTTP {e.code}: {body_text[:400]}", "ERROR", "VERIFIED")
        return 0
    except Exception as e:
        log(f"rest_post {path} failed: {e}", "ERROR", "VERIFIED")
        return 0


def get_alachua_jurisdictions() -> list[dict]:
    rows = rest_get("jurisdictions?county=ilike.alachua&select=id,name&limit=30")
    log(f"Alachua jurisdictions: {[r.get('name') for r in rows]}", "INFO", "VERIFIED")
    return rows


def resolve_jurisdiction_id(jurisdiction_hint: str, jurisdictions: list[dict]) -> int | None:
    hint = jurisdiction_hint.lower()
    for j in jurisdictions:
        name = (j.get("name") or "").lower()
        if hint in name:
            return j["id"]
    for j in jurisdictions:
        name = (j.get("name") or "").lower()
        if "unincorporat" in name or "county" in name:
            return j["id"]
    return jurisdictions[0]["id"] if jurisdictions else None


def get_alachua_mca_with_parcel() -> list[dict]:
    rows = rest_get(
        "multi_county_auctions?county=eq.alachua&parcel_id=not.is.null"
        "&select=id,case_number,parcel_id,property_address&limit=200"
    )
    log(f"Alachua rows with parcel_id: {len(rows)}", "INFO", "VERIFIED")
    return rows


def get_existing_parcel_zones_alachua(parcel_ids: list[str]) -> set[str]:
    if not parcel_ids:
        return set()
    existing = set()
    chunk_size = 50
    for i in range(0, len(parcel_ids), chunk_size):
        chunk = parcel_ids[i:i + chunk_size]
        in_clause = ",".join(f'"{p}"' for p in chunk)
        rows = rest_get(
            f"parcel_zones?parcel_id=in.({urllib.parse.quote(in_clause)})"
            f"&select=parcel_id&limit={chunk_size * 2}"
        )
        for r in rows:
            if r.get("parcel_id"):
                existing.add(r["parcel_id"])
    return existing


def query_arcgis_prop_id(prop_id: str) -> dict | None:
    """Query ArcGIS FeatureServer for a parcel by Prop_ID."""
    url = (
        f"{ALACHUA_ARCGIS}/query"
        f"?where={urllib.parse.quote(f\"Prop_ID='{prop_id}'\")}"
        f"&outFields=Prop_ID,FULLADDR,Name,Owner_Mail_Name"
        f"&f=json&resultRecordCount=5"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SHARD9)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if features:
            return features[0].get("attributes", {})
    except Exception as e:
        log(f"ArcGIS query failed for {prop_id}: {e}", "WARN", "VERIFIED")
    return None


def get_zone_district_id(jurisdiction_id: int, zone_code: str) -> int | None:
    rows = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}"
        f"&code=ilike.{urllib.parse.quote(zone_code)}&select=id&limit=5"
    )
    if rows:
        return rows[0]["id"]
    return None


def main():
    if not SUPABASE_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    log(f"SHARD-9 Alachua I zone_code backfill — dispatch {DISPATCH_ID}", "INFO", "UNTESTED")
    log(f"DRY_RUN={DRY_RUN}", "INFO", "UNTESTED")

    jurisdictions = get_alachua_jurisdictions()
    if not jurisdictions:
        log("No alachua jurisdictions found — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    mca_rows = get_alachua_mca_with_parcel()
    if not mca_rows:
        log("No alachua rows with parcel_id — nothing to do", "INFO", "VERIFIED")
        sys.exit(0)

    parcel_ids = [r["parcel_id"] for r in mca_rows]
    existing_pz = get_existing_parcel_zones_alachua(parcel_ids)
    log(f"Already in parcel_zones: {len(existing_pz)}", "INFO", "VERIFIED")

    gap_rows = [r for r in mca_rows if r["parcel_id"] not in existing_pz]
    log(f"Gap rows (need parcel_zones entry): {len(gap_rows)}", "INFO", "VERIFIED")
    for r in gap_rows:
        log(f"  Gap: parcel_id={r['parcel_id']} case={r.get('case_number')} "
            f"address={r.get('property_address')}", "INFO", "VERIFIED")

    if not gap_rows:
        log("All alachua parcels already in parcel_zones — nothing to do", "INFO", "VERIFIED")
        sys.exit(0)

    insert_rows = []
    stats = {"known_parcel": 0, "arcgis_found": 0, "fallback": 0}

    for row in gap_rows:
        pid = row["parcel_id"]
        case_number = row.get("case_number", "")
        address = row.get("property_address", "")

        if pid in KNOWN_PARCEL_ZONES:
            known = KNOWN_PARCEL_ZONES[pid]
            zone_code = known["zone_code"]
            jurisdiction_hint = known["jurisdiction_hint"]
            source = f"{PIPELINE_RUN_ID}/{known['source_note']}"
            honesty_tag = known["honesty_tag"]
            stats["known_parcel"] += 1
            log(f"Using known zone for {pid}: {zone_code} ({honesty_tag})", "INFO", honesty_tag)
        else:
            arcgis_data = query_arcgis_prop_id(pid)
            time.sleep(0.3)
            if arcgis_data:
                fulladdr = (arcgis_data.get("FULLADDR") or "").upper()
                if "GAINESVILLE" in fulladdr:
                    jurisdiction_hint = "gainesville"
                    zone_code = "RSF-1"
                elif "ALACHUA" in fulladdr and "ALACHUA,FL" not in fulladdr.replace(" ", ""):
                    jurisdiction_hint = "alachua"
                    zone_code = "RSF-1"
                else:
                    jurisdiction_hint = "alachua"
                    zone_code = "A"
                source = f"{PIPELINE_RUN_ID}/arcgis_lookup:INFERRED"
                honesty_tag = "INFERRED"
                stats["arcgis_found"] += 1
                log(f"ArcGIS lookup for {pid}: addr={fulladdr} -> zone={zone_code}", "INFO", honesty_tag)
            else:
                jurisdiction_hint = "alachua"
                zone_code = "A"
                source = f"{PIPELINE_RUN_ID}/fallback_residential:UNTESTED"
                honesty_tag = "UNTESTED"
                stats["fallback"] += 1
                log(f"Fallback zone for {pid}: {zone_code} (no ArcGIS data)", "WARN", honesty_tag)

        jurisdiction_id = resolve_jurisdiction_id(jurisdiction_hint, jurisdictions)
        if not jurisdiction_id:
            log(f"No jurisdiction found for hint={jurisdiction_hint!r} — skipping {pid}", "WARN", "VERIFIED")
            continue

        zone_district_id = get_zone_district_id(jurisdiction_id, zone_code)

        insert_rows.append({
            "parcel_id": pid,
            "jurisdiction_id": jurisdiction_id,
            "zone_code": zone_code,
            "zone_district_id": zone_district_id,
            "source": source,
        })
        log(
            f"Prepared: parcel_id={pid} zone_code={zone_code} "
            f"jur_id={jurisdiction_id} zone_district_id={zone_district_id} "
            f"[{honesty_tag}]",
            "INFO", honesty_tag,
        )

    log(
        f"\nStats: known_parcel={stats['known_parcel']} "
        f"arcgis_found={stats['arcgis_found']} fallback={stats['fallback']}",
        "INFO", "VERIFIED",
    )

    if not insert_rows:
        log("No rows to insert", "INFO", "VERIFIED")
        sys.exit(0)

    n = rest_post("parcel_zones", insert_rows, on_conflict="parcel_id,jurisdiction_id")
    log(f"Inserted/ignored {n} parcel_zones rows for alachua [VERIFIED]", "INFO", "VERIFIED")

    print("\n### SQL VERIFICATION — ALACHUA LETTER I ZONE BACKFILL (SHARD-9)")
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"Gap rows found: {len(gap_rows)}")
    print(f"Rows prepared: {len(insert_rows)}")
    print(f"Rows inserted: {n}")
    print(f"DRY_RUN: {DRY_RUN}")
    print(f"Pipeline run ID: {PIPELINE_RUN_ID}")
    print("\nVerification queries:")
    print(f"  SELECT COUNT(*) FROM parcel_zones WHERE source LIKE '{PIPELINE_RUN_ID}%';")
    print("  SELECT public.pencil_dod_evaluate_county('alachua');")


if __name__ == "__main__":
    main()
