#!/usr/bin/env python3
"""
Lee County SHARD-12 E+I backfill (dispatch 86e03369).
E: 5 auctions have property_address but no parcel_id -- resolve via Lee
   County ArcGIS FeatureServer address search.
I: 28 auctions already have a real STRAP parcel_id (+address/geo/value) but
   the parcel has no parcel_zones row (not zone-linked) -- query ArcGIS by
   STRAP for ZONING and insert parcel_zones. 2 more auctions have a STRAP
   but are missing geo/value too -- same ArcGIS query fills both.
Does NOT touch G directly; new zone codes are checked against existing
zoning_districts before insert (see main()).
"""
import os, json, time, urllib.parse, sys
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
LEE_ARCGIS = "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/Lee_County_Parcels/FeatureServer/0/query"
JURISDICTION_MAP = {
    "default": 630,
    "cape coral": 815,
    "bonita springs": 914,
    "fort myers beach": 912,
    "fort myers": 929,
    "sanibel": 942,
}

E_GAP_CASES = ["20-CA-005572", "24-CC-004249", "18-CC-004510", "25-CA-007100", "25-CA-003385"]
I_BUCKET1_STRAPS = [
    "20-44-25-P4-00600.0250", "32-44-25-P1-01100.1170", "35-44-24-P3-01501.0540",
    "02-45-24-P4-02335.0040", "35-44-24-P2-00903.0150", "25-46-22-T1-00600.0120",
    "21-43-24-C2-02414.0301", "34-43-25-09-00000.2600", "25-44-24-P3-02401.0120",
    "04-46-24-17-00080.0020", "08-44-22-02-00012.0090", "36-43-24-25-02000.00F0",
    "06-45-24-C4-00453.0570", "05-44-23-C3-04051.0660", "25-43-22-C3-05177.0340",
    "18-44-25-P2-01300.1360", "14-45-24-02-12310.0040", "10-44-24-05-0000C.0010",
    "07-43-25-00-00002.0150", "10-47-25-E4-10000.0260", "01-44-26-L1-06059.0140",
    "17-47-25-B4-0010A.0200", "20-44-24-C3-01150.0310", "34-44-23-C4-03200.0470",
    "27-43-24-01-0000A.0020", "06-44-24-C3-02031.0130", "34-46-22-T2-0080B.0140",
    "08-44-23-C2-04017.0130",
]
I_BUCKET2_STRAPS = ["02-46-23-02-0000D.0660", "18-43-24-C3-05714.0150"]

def log(msg, tag="INFO"):
    print(f"[{tag}] {msg}", flush=True)

def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def sb_post(path, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=body, headers={
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": prefer,
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def sb_patch(path, params, data):
    body = json.dumps(data).encode()
    url = f"{SUPABASE_URL}/rest/v1/{path}?{params}"
    req = urllib.request.Request(url, data=body, headers={
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": "return=minimal",
    }, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def normalize_strap(parcel_id: str) -> str:
    return parcel_id.replace("-", "").replace(".", "")

def query_arcgis_by_straps(straps):
    if not straps:
        return {}
    in_clause = ",".join(f"'{normalize_strap(s)}'" for s in straps)
    where = f"STRAP IN ({in_clause})"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 2000,
    })
    url = f"{LEE_ARCGIS}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "BidDeed-SHARD12"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    result = {}
    for feature in data.get("features", []):
        attrs = feature.get("attributes", {})
        strap = attrs.get("STRAP", "")
        if strap:
            result[strap] = attrs
    return result

def query_arcgis_by_address(siteaddr: str):
    parts = siteaddr.split(",")[0].strip().upper()
    where = f"SITEADDR LIKE '{parts}%'"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 5,
    })
    url = f"{LEE_ARCGIS}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "BidDeed-SHARD12"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        features = data.get("features", [])
        return features[0].get("attributes", {}) if features else None
    except Exception as e:
        log(f"address query error ({siteaddr}): {e}", "ERROR")
        return None

def get_jurisdiction_id(city: str) -> int:
    if not city:
        return JURISDICTION_MAP["default"]
    cl = city.strip().lower()
    for key, jid in JURISDICTION_MAP.items():
        if key != "default" and key in cl:
            return jid
    return JURISDICTION_MAP["default"]

def format_strap(s: str) -> str:
    if len(s) == 18:
        return f"{s[0:2]}-{s[2:4]}-{s[4:6]}-{s[6:8]}-{s[8:13]}.{s[13:18]}"
    return s

def main():
    log("=== Lee County SHARD-12 E+I backfill ===", "START")

    # ── E: resolve 5 address-only rows via ArcGIS address search ──────────
    rows = sb_get("multi_county_auctions",
                   "county=eq.lee&case_number=in.(" + ",".join(E_GAP_CASES) + ")"
                   "&select=id,case_number,property_address,parcel_id,latitude,longitude,assessed_value")
    e_resolved = 0
    for row in rows:
        addr = row.get("property_address") or ""
        addr_clean = addr.split(",")[0].strip().upper()
        if not addr_clean:
            log(f"  {row['case_number']}: no address, skip", "WARN")
            continue
        attrs = query_arcgis_by_address(addr_clean)
        if not attrs or not attrs.get("STRAP"):
            log(f"  {row['case_number']}: no ArcGIS match for '{addr_clean}'", "WARN")
            continue
        formatted = format_strap(attrs["STRAP"])
        patch = {"parcel_id": formatted}
        if attrs.get("LATITUDE") and not row.get("latitude"):
            patch["latitude"] = attrs["LATITUDE"]
            patch["longitude"] = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        if assessed and not row.get("assessed_value"):
            patch["assessed_value"] = assessed
        status, _ = sb_patch("multi_county_auctions", f"id=eq.{row['id']}", patch)
        if status in (200, 204):
            e_resolved += 1
            log(f"  {row['case_number']} -> parcel_id={formatted}", "VERIFIED")
        time.sleep(0.2)
    log(f"E resolved: {e_resolved}/{len(E_GAP_CASES)}", "RESULT")

    # ── I: query ArcGIS by STRAP for bucket1 (zone-link only) + bucket2 (zone+geo/val) ──
    all_straps = I_BUCKET1_STRAPS + I_BUCKET2_STRAPS
    arcgis_data = query_arcgis_by_straps(all_straps)
    log(f"ArcGIS returned {len(arcgis_data)}/{len(all_straps)} STRAP records", "VERIFIED")

    # existing zoning_districts codes per jurisdiction (to avoid introducing unmatched codes)
    existing_districts = sb_get("zoning_districts", "jurisdiction_id=in.(630,815,914,912,929,942)&select=jurisdiction_id,code")
    known_codes = {(d["jurisdiction_id"], d["code"]) for d in existing_districts}

    # map normalized (undashed) STRAP -> the ORIGINAL dashed parcel_id string
    # already used in multi_county_auctions, so parcel_zones.parcel_id matches
    # exactly (format_strap()'s fixed-width dash insertion is unreliable when
    # ArcGIS's STRAP field isn't exactly 18 chars -- verified live 2026-07-23:
    # it produced undashed parcel_ids that silently never matched MCA rows).
    norm_to_original = {normalize_strap(s): s for s in all_straps}

    pz_inserts = []
    skipped_unmatched = []
    for strap, attrs in arcgis_data.items():
        zoning = (attrs.get("ZONING") or "").strip()
        city = attrs.get("SITECITY", "")
        jid = get_jurisdiction_id(city)
        formatted = norm_to_original.get(strap, format_strap(strap))
        if zoning and (jid, zoning) not in known_codes:
            skipped_unmatched.append((formatted, jid, zoning))
            continue
        if zoning:
            pz_inserts.append({
                "parcel_id": formatted,
                "jurisdiction_id": jid,
                "zone_code": zoning,
                "zone_name": zoning,
                "source": "lee_arcgis_2026_shard12",
            })

    log(f"parcel_zones inserts staged (known zone codes only): {len(pz_inserts)}", "VERIFIED")
    if skipped_unmatched:
        log(f"SKIPPED (unmatched zone code, would risk G regression): {skipped_unmatched}", "WARN")

    CHUNK = 100
    pz_inserted = 0
    for i in range(0, len(pz_inserts), CHUNK):
        chunk = pz_inserts[i:i+CHUNK]
        status, resp = sb_post("parcel_zones", chunk, prefer="resolution=ignore-duplicates,return=minimal")
        if status in (200, 201):
            pz_inserted += len(chunk)
        else:
            log(f"parcel_zones insert failed ({status}): {resp[:200]}", "ERROR")
        time.sleep(0.2)
    log(f"parcel_zones inserted: {pz_inserted}", "RESULT")

    # geo/value patch for bucket2 (2 rows missing geo/val, and any bucket1 rows lacking it too)
    b_rows = sb_get("multi_county_auctions",
                     "county=eq.lee&parcel_id=in.(" + ",".join(I_BUCKET1_STRAPS + I_BUCKET2_STRAPS) + ")"
                     "&select=id,case_number,parcel_id,latitude,longitude,assessed_value,market_value")
    geo_updates = 0
    val_updates = 0
    for row in b_rows:
        strap_norm = normalize_strap(row["parcel_id"])
        attrs = arcgis_data.get(strap_norm)
        if not attrs:
            continue
        patch = {}
        if attrs.get("LATITUDE") and not row.get("latitude"):
            patch["latitude"] = attrs["LATITUDE"]
            patch["longitude"] = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        if assessed and not row.get("assessed_value") and not row.get("market_value"):
            patch["assessed_value"] = assessed
        if patch:
            status, _ = sb_patch("multi_county_auctions", f"id=eq.{row['id']}", patch)
            if status in (200, 204):
                if "latitude" in patch:
                    geo_updates += 1
                if "assessed_value" in patch:
                    val_updates += 1
        time.sleep(0.1)
    log(f"geo updates: {geo_updates}, value updates: {val_updates}", "RESULT")

    log("=== Summary ===", "RESULT")
    log(f"E resolved: {e_resolved}/{len(E_GAP_CASES)}", "VERIFIED")
    log(f"I parcel_zones inserted: {pz_inserted} (skipped unmatched: {len(skipped_unmatched)})", "VERIFIED")
    log(f"I geo/value backfilled: geo={geo_updates} val={val_updates}", "VERIFIED")
    log("Run pencil_dod_evaluate_county('lee') to verify E+I movement", "NEXT")

if __name__ == "__main__":
    main()
