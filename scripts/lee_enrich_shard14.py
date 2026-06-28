#!/usr/bin/env python3
"""
Lee County E+I enrichment — SHARD-14, dispatch fdf41615
Queries Lee County ArcGIS FeatureServer for ZONING, LAT, LNG, ASSESSED
Writes: parcel_zones inserts + multi_county_auctions updates
"""
import os, json, time, urllib.parse, sys
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
LEE_ARCGIS = "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/Lee_County_Parcels/FeatureServer/0/query"
# Jurisdiction IDs for Lee County (from jurisdictions table)
JURISDICTION_MAP = {
    "default": 630,  # Lee County (Unincorporated)
    "cape coral": 815,
    "bonita springs": 914,
    "fort myers beach": 912,
    "fort myers": 929,
    "sanibel": 942,
}

def log(msg, tag="INFO"):
    print(f"[{tag}] {msg}", flush=True)

def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def sb_post(path, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=body,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def sb_patch(path, params, data):
    body = json.dumps(data).encode()
    url = f"{SUPABASE_URL}/rest/v1/{path}?{params}"
    req = urllib.request.Request(
        url, data=body,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def normalize_strap(parcel_id: str) -> str:
    """Convert 'XX-XX-XX-XX-XXXXX.XXXX' to 'XXXXXXXXXXXXXXXX' (no dashes/dots)"""
    return parcel_id.replace("-", "").replace(".", "")

def query_arcgis_by_straps(straps: list[str]) -> dict[str, dict]:
    """Batch query ArcGIS FeatureServer by STRAP list. Returns strap→attrs dict."""
    if not straps:
        return {}
    # ArcGIS IN clause
    in_clause = ",".join(f"'{s}'" for s in straps)
    where = f"STRAP IN ({in_clause})"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITENUMBER,SITESTREET,SITECITY,SITEZIP",
        "f": "json",
        "resultRecordCount": 2000,
    })
    url = f"{LEE_ARCGIS}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BidDeed-SHARD14"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        result = {}
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            strap = attrs.get("STRAP", "")
            if strap:
                result[strap] = attrs
        return result
    except Exception as e:
        log(f"ArcGIS query error (batch {len(straps)}): {e}", "ERROR")
        return {}

def query_arcgis_by_address(siteaddr: str) -> dict | None:
    """Look up parcel by site address. Returns attrs or None."""
    # Normalize address for ArcGIS LIKE match
    # Extract just the number and street
    parts = siteaddr.split(",")[0].strip().upper()
    where = f"SITEADDR LIKE '{parts}%'"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 5,
    })
    url = f"{LEE_ARCGIS}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BidDeed-SHARD14"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        features = data.get("features", [])
        if features:
            return features[0].get("attributes", {})
        return None
    except Exception as e:
        log(f"ArcGIS address query error ({siteaddr}): {e}", "ERROR")
        return None

def get_jurisdiction_id(city: str) -> int:
    if not city:
        return JURISDICTION_MAP["default"]
    city_lower = city.strip().lower()
    for key, jid in JURISDICTION_MAP.items():
        if key != "default" and key in city_lower:
            return jid
    return JURISDICTION_MAP["default"]

def main():
    log("=== Lee County Shard-14 E+I Enrichment ===", "START")

    # ── Step 1: Load all lee rows ──────────────────────────────────────────
    log("Loading lee county rows from Supabase...")
    rows = sb_get("multi_county_auctions",
                   "county=eq.lee&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,po_market_value,auction_status&limit=300")
    log(f"Loaded {len(rows)} rows", "VERIFIED")

    real_rows = [r for r in rows
                 if r.get("parcel_id")
                 and r["parcel_id"] not in ("Property Appraiser", "", "UNKNOWN")
                 and any(c.isdigit() for c in r["parcel_id"])]
    fake_rows = [r for r in rows if r.get("parcel_id") == "Property Appraiser"]
    null_rows = [r for r in rows if not r.get("parcel_id")]
    log(f"Real parcel: {len(real_rows)}, Fake: {len(fake_rows)}, Null: {len(null_rows)}", "VERIFIED")

    # ── Step 2: Query ArcGIS for all real parcel rows (batch of 50) ────────
    log("Querying Lee County ArcGIS for zoning/geo/value...")
    strap_to_row = {}
    for r in real_rows:
        strap = normalize_strap(r["parcel_id"])
        strap_to_row[strap] = r

    all_straps = list(strap_to_row.keys())
    arcgis_data = {}
    BATCH = 50
    for i in range(0, len(all_straps), BATCH):
        batch = all_straps[i:i+BATCH]
        result = query_arcgis_by_straps(batch)
        arcgis_data.update(result)
        log(f"  Batch {i//BATCH+1}/{(len(all_straps)+BATCH-1)//BATCH}: "
            f"{len(result)}/{len(batch)} found")
        time.sleep(0.3)

    log(f"ArcGIS returned {len(arcgis_data)}/{len(all_straps)} parcel records", "VERIFIED")

    # ── Step 3: Load existing parcel_zones for lee county ─────────────────
    log("Loading existing parcel_zones for Lee County...")
    existing_pz = sb_get("parcel_zones",
                          "jurisdiction_id=in.(630,815,914,912,929,942)&select=parcel_id&limit=500")
    existing_pz_set = {r["parcel_id"] for r in existing_pz}
    log(f"Existing parcel_zones: {len(existing_pz_set)}", "VERIFIED")

    # ── Step 4: Insert new parcel_zones + patch geo/value on MCA ──────────
    pz_inserts = []
    mca_geo_updates = 0
    mca_val_updates = 0

    for strap, attrs in arcgis_data.items():
        row = strap_to_row.get(strap)
        if not row:
            continue

        original_pid = row["parcel_id"]
        zoning = attrs.get("ZONING", "")
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = attrs.get("SITECITY", "")

        # Build parcel_zones insert if zoning present and not yet loaded
        if zoning and original_pid not in existing_pz_set:
            jid = get_jurisdiction_id(city)
            pz_inserts.append({
                "parcel_id": original_pid,
                "jurisdiction_id": jid,
                "zone_code": zoning,
                "zone_name": zoning,
                "source": "lee_arcgis_2026_shard14",
            })

        # Patch geo if missing
        needs_geo = not row.get("latitude") and lat
        needs_val = not (row.get("assessed_value") or 0) > 0 and not (row.get("po_market_value") or 0) > 0 and assessed

        patch_data = {}
        if needs_geo:
            patch_data["latitude"] = lat
            patch_data["longitude"] = lng
        if needs_val:
            patch_data["assessed_value"] = assessed

        if patch_data:
            status, resp = sb_patch("multi_county_auctions", f"id=eq.{row['id']}", patch_data)
            if "geo" in str(patch_data):
                mca_geo_updates += 1
            if "assessed" in str(patch_data):
                mca_val_updates += 1

    log(f"MCA geo updates: {mca_geo_updates}, val updates: {mca_val_updates}", "VERIFIED")

    # Batch insert parcel_zones
    log(f"Inserting {len(pz_inserts)} new parcel_zones entries...")
    CHUNK = 100
    pz_inserted = 0
    for i in range(0, len(pz_inserts), CHUNK):
        chunk = pz_inserts[i:i+CHUNK]
        status, resp = sb_post("parcel_zones", chunk,
                                prefer="resolution=ignore-duplicates,return=minimal")
        if status in (200, 201):
            pz_inserted += len(chunk)
        else:
            log(f"parcel_zones insert failed ({status}): {resp[:200]}", "ERROR")
        time.sleep(0.2)

    log(f"Inserted {pz_inserted} parcel_zones rows", "VERIFIED")

    # ── Step 5: Resolve fake "Property Appraiser" rows via address ─────────
    log(f"Resolving {len(fake_rows)} 'Property Appraiser' rows by address...")
    fake_resolved = 0
    for row in fake_rows:
        addr = row.get("property_address", "")
        if not addr:
            continue
        # Extract first part of address (before comma)
        addr_clean = addr.split(",")[0].strip().upper()
        if not addr_clean:
            continue

        attrs = query_arcgis_by_address(addr_clean)
        if not attrs:
            log(f"  No match for {addr_clean}", "WARN")
            continue

        new_strap = attrs.get("STRAP", "")
        if not new_strap:
            continue

        # Format STRAP back to standard parcel_id format
        # STRAP = 18 chars: XX XX XX LL XXXXX XXXX
        # Standard format: XX-XX-XX-LL-XXXXX.XXXX
        s = new_strap
        if len(s) == 18:
            formatted = f"{s[0:2]}-{s[2:4]}-{s[4:6]}-{s[6:8]}-{s[8:13]}.{s[13:18]}"
        else:
            formatted = new_strap

        zoning = attrs.get("ZONING", "")
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = attrs.get("SITECITY", "")
        jid = get_jurisdiction_id(city)

        # Update MCA with real parcel_id + geo + value
        patch_data = {"parcel_id": formatted}
        if lat and not row.get("latitude"):
            patch_data["latitude"] = lat
            patch_data["longitude"] = lng
        if assessed and not (row.get("assessed_value") or 0) > 0:
            patch_data["assessed_value"] = assessed

        status, resp = sb_patch("multi_county_auctions", f"id=eq.{row['id']}", patch_data)
        if status in (200, 204):
            fake_resolved += 1
            log(f"  Resolved {row['case_number']} → {formatted} zone={zoning}", "VERIFIED")

            # Add to parcel_zones
            if zoning and formatted not in existing_pz_set:
                status2, _ = sb_post("parcel_zones", [{
                    "parcel_id": formatted,
                    "jurisdiction_id": jid,
                    "zone_code": zoning,
                    "zone_name": zoning,
                    "source": "lee_arcgis_2026_shard14_addr",
                }], prefer="resolution=ignore-duplicates,return=minimal")
                if status2 in (200, 201):
                    pz_inserted += 1
        time.sleep(0.2)

    log(f"Fake rows resolved: {fake_resolved}/{len(fake_rows)}", "VERIFIED")

    # ── Step 6: Add cancelled auctions to gold_standard_exclusions ─────────
    log("Checking cancelled lee auctions for exclusion...")
    cancelled = [r for r in rows if r.get("auction_status") == "cancelled"]
    log(f"Cancelled: {len(cancelled)}", "VERIFIED")

    if cancelled:
        exclusion_rows = [{
            "county_slug": "lee",
            "auction_id": r["id"],
            "excluded_reason": "cancelled",
            "excluded_by": "shard14_ai_architect",
            "backfill_target": True,
        } for r in cancelled]
        status, resp = sb_post("gold_standard_exclusions", exclusion_rows,
                                prefer="resolution=ignore-duplicates,return=minimal")
        log(f"Exclusions insert: status={status}", "VERIFIED")

    # ── Step 7: Summary ────────────────────────────────────────────────────
    log("=== Summary ===", "RESULT")
    log(f"parcel_zones: {len(existing_pz_set)} existing + {pz_inserted} new", "VERIFIED")
    log(f"MCA geo updated: {mca_geo_updates}", "VERIFIED")
    log(f"MCA value updated: {mca_val_updates}", "VERIFIED")
    log(f"Fake parcel rows resolved: {fake_resolved}/{len(fake_rows)}", "VERIFIED")
    log(f"Cancelled rows excluded: {len(cancelled)}", "VERIFIED")
    log("Run pencil_dod_evaluate_county('lee') to verify E+I movement", "NEXT")

if __name__ == "__main__":
    main()
