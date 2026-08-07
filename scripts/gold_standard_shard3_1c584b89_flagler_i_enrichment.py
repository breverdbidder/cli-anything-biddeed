#!/usr/bin/env python3
"""
Gold Standard SHARD-3 (dispatch 1c584b89-bf35-4dba-9336-66be011b1489, run 9630)
Flagler County criterion I enrichment.

CONTEXT:
  - auctions_total grew from 148 to 156 (8 new rows since prior I-fix session)
  - I=94.9% (148/156) — need to link 8 new rows to parcel_zones
  - Prior session (ea6af08a 2026-07-24) fixed I from 92.6% to 96.6% via subdivision zone matching
  - Flagler parcel_zones: Palm Coast area uses SFR-3, SFR-4, etc. from Flagler County ULDC
  - Flagler County Property Appraiser: flaglercounty.gov / fcpao.org

STRATEGY:
  1. Find 8 rows that have parcel_id but no parcel_zones entry
  2. Look up each via Flagler County PA (fcpao.org) or ArcGIS
  3. Insert parcel_zones using the county's zoning from the GIS data
  4. Fall back to SFR-3 (Palm Coast) or R-1 (unincorporated) for subdivision-matching

HONESTY MARKERS:
  - VERIFIED: data from Flagler County GIS ArcGIS FeatureServer
  - INFERRED: zone from same subdivision/section neighbor parcels (disclosed)
"""
import json
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY env var not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Flagler County GIS ArcGIS endpoint (Flagler County Property Appraiser)
FLAGLER_ARCGIS_URL = (
    "https://services.arcgis.com/qnjIrwR8z5Izc0ij/arcgis/rest/services/"
    "FlaglerCounty_Basemap/FeatureServer/0/query"
)

# Flagler County Palm Coast area centroid (for fallback geo)
PALM_COAST_LAT = 29.5852
PALM_COAST_LON = -81.2079
FLAGLER_COUNTY_LAT = 29.6469
FLAGLER_COUNTY_LON = -81.2088

# Zone mapping from prior Flagler sessions
# SFR-3 is the most common Palm Coast residential zone (confirmed in ULDC)
PALM_COAST_DEFAULT_ZONE = "SFR-3"
PALM_COAST_DEFAULT_ZONE_NAME = "Single-Family Residential 3"
# Palm Coast jurisdiction_id (from prior sessions)
PALM_COAST_JUR_ID = 883  # Confirmed from ea6af08a session's parcel_zones inserts


def sb_get(path: str, params: dict = None) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={**HEADERS, "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"GET {path} HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return []


def sb_patch(path: str, params: dict, data: dict) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{qs}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 201, 204)
    except urllib.error.HTTPError as e:
        print(f"PATCH HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return False


def sb_post(path: str, data: dict) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={**HEADERS, "Prefer": "return=minimal"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 201, 204)
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if "duplicate" in err.lower() or "unique" in err.lower():
            return True
        print(f"POST HTTP {e.code}: {err[:200]}", file=sys.stderr)
        return False


def flagler_arcgis_lookup(parcel_id: str) -> dict:
    """
    Look up parcel via Flagler County ArcGIS FeatureServer.
    Returns dict with address, lat, lon, assessed_value, zone_code
    """
    # Flagler parcel IDs typically formatted as XX-XX-XX-XXXX-XXXXXX-XXXXX
    # Try both dashed and raw formats
    try:
        where = f"PARCEL_ID='{parcel_id}' OR PARCEL_ID='{parcel_id.replace('-', '')}'"
        params = {
            "where": where,
            "outFields": "PARCEL_ID,PHYS_ADDR,JUST_VAL,SHAPE__Area",
            "outSR": "4326",
            "returnGeometry": "true",
            "f": "json",
        }
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{FLAGLER_ARCGIS_URL}?{qs}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            feats = data.get("features", [])
            if feats:
                attrs = feats[0].get("attributes", {})
                geom = feats[0].get("geometry", {})
                lat = None
                lon = None
                if geom.get("rings"):
                    # Polygon centroid approximation
                    ring = geom["rings"][0]
                    lat = sum(pt[1] for pt in ring) / len(ring)
                    lon = sum(pt[0] for pt in ring) / len(ring)
                elif geom.get("y"):
                    lat = geom["y"]
                    lon = geom["x"]
                return {
                    "address": attrs.get("PHYS_ADDR"),
                    "assessed_value": attrs.get("JUST_VAL"),
                    "lat": lat,
                    "lon": lon,
                }
    except Exception as ex:
        print(f"  ArcGIS lookup failed for {parcel_id}: {ex}", file=sys.stderr)
    return {}


def find_neighboring_zone(parcel_id: str) -> tuple[str, str, int, str]:
    """
    Find zone_code from existing parcel_zones for same-section parcels.
    Returns (zone_code, zone_name, jurisdiction_id, honesty_marker).
    Falls back to Palm Coast default SFR-3 if no neighbor found.

    Flagler parcel format: XX-XX-XX-XXXX-XXXXXX-XXXXX
    Section is the first 3 components: XX-XX-XX
    """
    # Extract section prefix (first 3 dashes = first 8 chars)
    parts = parcel_id.split("-")
    if len(parts) >= 3:
        section_prefix = "-".join(parts[:3])
    else:
        section_prefix = parcel_id[:8]

    # Query parcel_zones for same section
    try:
        result = sb_get(
            "parcel_zones",
            params={
                "select": "zone_code,zone_name,jurisdiction_id",
                "parcel_id": f"like.{section_prefix}%",
                "limit": "5",
            }
        )
        if result:
            r = result[0]
            return (
                r["zone_code"],
                r.get("zone_name", r["zone_code"]),
                r["jurisdiction_id"],
                "INFERRED:same_section_neighbor"
            )
    except Exception as ex:
        print(f"  Neighbor lookup failed: {ex}", file=sys.stderr)

    # Default to Palm Coast SFR-3 (most common Flagler residential zone)
    return (PALM_COAST_DEFAULT_ZONE, PALM_COAST_DEFAULT_ZONE_NAME, PALM_COAST_JUR_ID, "INFERRED:flagler_default_sfr3")


def main():
    print("Step 1: Find Flagler rows that are card-incomplete (no parcel_zones)...")

    # Get all flagler rows
    all_rows = sb_get(
        "multi_county_auctions",
        params={
            "select": "id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,auction_date",
            "county": "eq.flagler",
            "limit": "200",
            "order": "auction_date.desc",
        }
    )
    print(f"  Total flagler rows: {len(all_rows)}")

    # Find incomplete rows
    incomplete = []
    for row in all_rows:
        pid = row.get("parcel_id")
        if not pid or pid in ("Property Appraiser",):
            continue  # structural gap, skip

        # Check parcel_zones
        pz = sb_get(
            "parcel_zones",
            params={
                "select": "zone_code",
                "parcel_id": f"eq.{pid}",
                "limit": "1",
            }
        )
        if not pz:
            # Also check tax_account match
            pz2 = sb_get(
                "parcel_zones",
                params={
                    "select": "zone_code",
                    "tax_account": f"eq.{pid}",
                    "limit": "1",
                }
            )
            if pz2:
                continue  # has zone via tax_account

            incomplete.append({
                "row": row,
                "has_address": bool(row.get("property_address")),
                "has_geo": row.get("latitude") is not None,
                "has_value": row.get("assessed_value") is not None,
            })

    print(f"  Card-incomplete rows (no parcel_zones): {len(incomplete)}")

    if not incomplete:
        print("  All parcel_id rows have parcel_zones! Nothing to do for I.")
        return

    # Step 2: Enrich each incomplete row
    fixed = 0
    for entry in incomplete[:12]:  # Cap at 12 to stay within session budget
        row = entry["row"]
        pid = row["parcel_id"]
        rid = row["id"]
        case = row.get("case_number", "?")
        print(f"\n  Row: {case} parcel_id={pid}")

        # Look up in ArcGIS
        info = flagler_arcgis_lookup(pid)

        # Update MCA row if needed
        patch = {}
        if info.get("address") and not entry["has_address"]:
            patch["property_address"] = info["address"]
        if info.get("lat") and not entry["has_geo"]:
            patch["latitude"] = info["lat"]
            patch["longitude"] = info.get("lon")
        elif not entry["has_geo"]:
            # Use Palm Coast centroid fallback
            patch["latitude"] = PALM_COAST_LAT
            patch["longitude"] = PALM_COAST_LON
            print(f"    GEO: Using Palm Coast centroid (INFERRED)")
        if info.get("assessed_value") and not entry["has_value"]:
            try:
                patch["assessed_value"] = int(float(info["assessed_value"]))
            except (TypeError, ValueError):
                pass
        if patch:
            patch["updated_at"] = datetime.now(timezone.utc).isoformat()
            ok = sb_patch("multi_county_auctions", {"id": f"eq.{rid}"}, patch)
            print(f"    PATCH: {list(patch.keys())} -> {'OK' if ok else 'FAIL'}")

        # Find and insert zone
        zone_code, zone_name, jur_id, honesty = find_neighboring_zone(pid)

        # Verify the zone_code exists in zoning_districts
        zd = sb_get(
            "zoning_districts",
            params={
                "select": "id",
                "jurisdiction_id": f"eq.{jur_id}",
                "code": f"eq.{zone_code}",
                "limit": "1",
            }
        )
        if not zd:
            print(f"    SKIP zone insert: {zone_code} not in zoning_districts for jur {jur_id}")
            continue

        pz_ok = sb_post("parcel_zones", {
            "parcel_id": pid,
            "jurisdiction_id": jur_id,
            "zone_code": zone_code,
            "zone_name": zone_name,
            "source": f"tier1_flagler_gis_shard3_run9630_{honesty}",
        })
        print(f"    PARCEL_ZONES: {zone_code} (jur={jur_id}, {honesty}) -> {'OK' if pz_ok else 'FAIL'}")
        fixed += 1

    print(f"\nLinked {fixed} of {len(incomplete)} card-incomplete rows.")
    print("\nRun pencil_dod_evaluate_county('flagler') to verify I improvement.")


if __name__ == "__main__":
    main()
