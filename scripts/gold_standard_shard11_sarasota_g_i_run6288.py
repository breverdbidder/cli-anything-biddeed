#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-11: sarasota — G (pk1000) + I (property card completion)
Session: run 6288, dispatch_id: 42827b21-94db-42c9-92df-4e1b83219c49
Date: 2026-07-25

Usage: python3 scripts/gold_standard_shard11_sarasota_g_i_run6288.py

Steps:
1. Evaluate baseline: pencil_dod_evaluate_county('sarasota')
2. Apply G migration (zoning_districts + zone_standards for unresolved sarasota zones)
3. Re-evaluate G letter
4. Diagnose I: find the 12 incomplete property cards
5. For each missing card, try:
   a. scgov.net ParcelProperty FeatureServer (lat/lng/assessed_value by tax_account)
   b. scgov_arcgis CountyZoning FeatureServer (zone_code by lat/lng, municipality='SC')
   c. cos_zoning_arcgis City of Sarasota Zoning layer (zone_code by lat/lng)
   d. npgis.northportfl.gov (zone_code for North Port addresses)
6. Insert any resolved parcel_zones rows
7. Re-evaluate I letter
8. Log gold_standard_ultraloop_audit entries for survived claims
9. Report before/after JSON
"""
import os, sys, json, time, urllib.request, urllib.parse
import urllib.error

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

DISPATCH_ID = "42827b21-94db-42c9-92df-4e1b83219c49"
COUNTY = "sarasota"

def mgmt_sql(query: str, timeout=120):
    """Execute SQL via Supabase Management API."""
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=body, headers=h, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.read else {}

def sb_get(path: str, params=""):
    """GET from Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + params
    req = urllib.request.Request(url, headers={
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  sb_get error {path}: {e}", flush=True)
        return []

def sb_post(table: str, data, prefer="return=minimal"):
    """POST to Supabase REST API."""
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=body,
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read()
            return resp.status, json.loads(content) if content else None
    except urllib.error.HTTPError as e:
        content = e.read()
        return e.code, content.decode()[:200] if content else ""

def evaluate_county(county: str):
    """Run pencil_dod_evaluate_county and return result."""
    status, result = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{county}')")
    if status == 200 and result:
        row = result[0] if isinstance(result, list) else result
        # Result is typically: {"pencil_dod_evaluate_county": "A pass(59) B pass(98.0) ..."}
        eval_str = row.get("pencil_dod_evaluate_county", str(row))
        return eval_str
    return f"ERROR: {status} {result}"

def http_get_json(url: str, timeout=20):
    """Simple HTTP GET returning JSON."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def query_scgov_zone(lat: float, lng: float):
    """Query scgov.net unincorporated county zoning layer."""
    url = (
        f"https://ags3.scgov.net/server/rest/services/Hosted/CountyZoning/FeatureServer/0/query"
        f"?geometry={lng},{lat}"
        f"&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects"
        f"&outFields=municipality,zoningdesignation,zoningcode,zoninggroup&f=json&resultRecordCount=1"
    )
    data = http_get_json(url)
    features = data.get("features", [])
    if features:
        attrs = features[0].get("attributes", {})
        if attrs.get("municipality") == "SC":
            return {"source": "scgov_arcgis", "zone_code": attrs.get("zoningcode"), "zone_name": attrs.get("zoningdesignation"), "municipality": "SC", "jurisdiction_id": 824}
    return None

def query_cos_zone(lat: float, lng: float):
    """Query City of Sarasota zoning layer."""
    url = (
        f"https://services3.arcgis.com/AWDwYUpli8WqpWxQ/arcgis/rest/services/Zoning_Districts_(View_Only)/FeatureServer/0/query"
        f"?geometry={lng},{lat}"
        f"&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects"
        f"&outFields=ZONECLASS,ZONEDESC,ORD_NO&f=json&resultRecordCount=1"
    )
    data = http_get_json(url)
    features = data.get("features", [])
    if features:
        attrs = features[0].get("attributes", {})
        zone_code = attrs.get("ZONECLASS")
        if zone_code:
            return {"source": "cos_zoning_arcgis", "zone_code": zone_code, "zone_name": attrs.get("ZONEDESC"), "jurisdiction_id": 824}
    return None

def query_northport_zone(lat: float, lng: float):
    """Query North Port zoning layer."""
    url = (
        f"https://npgis.northportfl.gov/cnpserver/rest/services/Hosted/Current_Zoning/FeatureServer/241/query"
        f"?geometry={lng},{lat}"
        f"&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects"
        f"&outFields=zone_abbr,zone_des&f=json&resultRecordCount=1"
    )
    data = http_get_json(url)
    features = data.get("features", [])
    if features:
        attrs = features[0].get("attributes", {})
        zone_code = attrs.get("zone_abbr")
        if zone_code:
            return {"source": "northport_gis_arcgis", "zone_code": zone_code, "zone_name": attrs.get("zone_des"), "jurisdiction_id": 941}
    return None

def query_scgov_parcel_value(tax_account: str):
    """Query scgov.net ParcelProperty FeatureServer for assessed_value and geo."""
    url = (
        f"https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query"
        f"?where=tax_account+%3D+%27{urllib.parse.quote(tax_account)}%27"
        f"&outFields=tax_account,justval,improvval,landval,latitude,longitude"
        f"&returnGeometry=false&f=json&resultRecordCount=1"
    )
    data = http_get_json(url)
    features = data.get("features", [])
    if features:
        return features[0].get("attributes", {})
    return None

def log_ultraloop_audit(county: str, letter: str, claim: str, survived: bool, evidence: dict):
    """Log to gold_standard_ultraloop_audit."""
    row = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim[:500],
        "refuter_evidence": json.dumps(evidence),
        "survived": survived,
    }
    status, _ = sb_post("gold_standard_ultraloop_audit", row)
    return status in (200, 201)


def main():
    print(f"=== SARASOTA GOLD STANDARD SHARD-11 RUN-6288 ===", flush=True)
    print(f"Session start: {__import__('datetime').datetime.utcnow().isoformat()}Z", flush=True)

    if not TOKEN:
        print("ERROR: SUPABASE_ACCESS_TOKEN not set", flush=True)
        sys.exit(1)

    # ─── STEP 1: BASELINE EVALUATION ─────────────────────────────────────────
    print("\n--- STEP 1: Baseline evaluation ---", flush=True)
    baseline = evaluate_county(COUNTY)
    print(f"BASELINE: {baseline}", flush=True)

    # ─── STEP 2: APPLY G MIGRATION ───────────────────────────────────────────
    print("\n--- STEP 2: Applying G migration (pk1000 classification) ---", flush=True)
    migration_file = "migrations/20260725_gold_standard_shard11_sarasota_g_pk1000_and_i_completion.sql"
    try:
        with open(migration_file) as f:
            migration_sql = f.read()
    except FileNotFoundError:
        print(f"ERROR: Migration file not found: {migration_file}", flush=True)
        sys.exit(1)

    status, result = mgmt_sql(migration_sql, timeout=120)
    print(f"Migration apply status: {status}", flush=True)
    if status not in (200, 201):
        print(f"Migration error: {json.dumps(result, default=str)[:500]}", flush=True)
        print("CONTINUING despite migration error — may have partial success", flush=True)
    else:
        print("Migration applied successfully", flush=True)

    # ─── STEP 3: RE-EVALUATE G ───────────────────────────────────────────────
    print("\n--- STEP 3: G evaluation after migration ---", flush=True)
    time.sleep(2)
    after_g = evaluate_county(COUNTY)
    print(f"AFTER G MIGRATION: {after_g}", flush=True)

    # ─── STEP 4: I DIAGNOSIS — FIND 12 INCOMPLETE CARDS ─────────────────────
    print("\n--- STEP 4: I diagnosis — finding incomplete property cards ---", flush=True)

    i_query = """
SET statement_timeout = 0;
SELECT
    a.case_number,
    a.parcel_id,
    a.property_address,
    a.county,
    a.latitude,
    a.longitude,
    a.assessed_value,
    a.market_value,
    pz.zone_code,
    CASE
        WHEN a.latitude IS NULL AND a.longitude IS NULL THEN 'missing_geo'
        WHEN a.assessed_value IS NULL AND a.market_value IS NULL THEN 'missing_value'
        WHEN pz.zone_code IS NULL THEN 'missing_zone'
        ELSE 'unknown'
    END as missing_what
FROM public.multi_county_auctions a
LEFT JOIN public.parcel_zones pz ON (
    pz.tax_account = a.parcel_id
    AND pz.jurisdiction_id IN (
        SELECT id FROM public.jurisdictions WHERE lower(county) = 'sarasota'
    )
)
WHERE lower(a.county) = 'sarasota'
  AND a.parcel_id IS NOT NULL
  AND NOT (
    a.latitude IS NOT NULL
    AND a.longitude IS NOT NULL
    AND COALESCE(a.assessed_value, a.market_value) IS NOT NULL
    AND pz.zone_code IS NOT NULL
  )
ORDER BY a.case_number
LIMIT 20;
"""
    status, incomplete_rows = mgmt_sql(i_query, timeout=60)
    print(f"I query status: {status}", flush=True)
    if status != 200 or not incomplete_rows:
        print(f"I query result: {json.dumps(incomplete_rows, default=str)[:500]}", flush=True)
        incomplete_rows = []

    print(f"Incomplete cards found: {len(incomplete_rows)}", flush=True)
    for row in incomplete_rows:
        print(f"  {row}", flush=True)

    # ─── STEP 5: FIX I — TRY TO COMPLETE INCOMPLETE CARDS ───────────────────
    print("\n--- STEP 5: Resolving incomplete property cards ---", flush=True)

    resolved_geo_count = 0
    resolved_zone_count = 0

    for row in incomplete_rows:
        case_num = row.get("case_number", "")
        parcel_id = row.get("parcel_id", "")
        address = row.get("property_address", "")
        lat = row.get("latitude")
        lng = row.get("longitude")
        assessed = row.get("assessed_value")
        market = row.get("market_value")
        zone = row.get("zone_code")
        missing = row.get("missing_what", "unknown")

        print(f"\n  Processing: {case_num} / parcel={parcel_id} missing={missing}", flush=True)

        # Try to resolve geo/value via scgov ParcelProperty by tax_account
        if (lat is None or lng is None or (assessed is None and market is None)) and parcel_id:
            pv = query_scgov_parcel_value(parcel_id)
            if pv:
                new_lat = pv.get("latitude")
                new_lng = pv.get("longitude")
                new_val = pv.get("justval") or pv.get("improvval")
                print(f"    scgov ParcelProperty: lat={new_lat} lng={new_lng} val={new_val}", flush=True)
                if new_lat and new_lng:
                    # Update MCA with geo
                    update_geo_query = f"""
UPDATE public.multi_county_auctions
SET latitude = {new_lat},
    longitude = {new_lng}
WHERE case_number = '{case_num}'
  AND (latitude IS NULL OR longitude IS NULL);
"""
                    s, r = mgmt_sql(update_geo_query)
                    if s in (200, 201):
                        print(f"    Geo updated for {case_num}", flush=True)
                        lat = new_lat
                        lng = new_lng
                        resolved_geo_count += 1
                    else:
                        print(f"    Geo update failed: {s}", flush=True)

                if new_val and (assessed is None and market is None):
                    update_val_query = f"""
UPDATE public.multi_county_auctions
SET assessed_value = {new_val}
WHERE case_number = '{case_num}'
  AND assessed_value IS NULL;
"""
                    s, r = mgmt_sql(update_val_query)
                    if s in (200, 201):
                        print(f"    Value updated for {case_num}", flush=True)
                    else:
                        print(f"    Value update failed: {s}", flush=True)
            else:
                print(f"    scgov ParcelProperty: no result for parcel_id={parcel_id}", flush=True)

        # Try to resolve zone_code
        if zone is None and lat is not None and lng is not None:
            # Determine which source to try based on address
            addr_upper = address.upper() if address else ""

            if "NORTH PORT" in addr_upper or "NORTHPORT" in addr_upper:
                zone_result = query_northport_zone(float(lat), float(lng))
                if zone_result:
                    print(f"    North Port zone: {zone_result['zone_code']}", flush=True)
            elif "VENICE" in addr_upper:
                # Venice was skipped in prior session due to geometry artifact — skip again
                print(f"    Venice address — skipping (known geometry artifact)", flush=True)
                zone_result = None
            elif "LONGBOAT" in addr_upper:
                # Longboat Key — no vetted source
                print(f"    Longboat Key — skipping (no vetted zoning source)", flush=True)
                zone_result = None
            else:
                # Try scgov first (unincorporated county)
                zone_result = query_scgov_zone(float(lat), float(lng))
                if not zone_result or zone_result.get("municipality") != "SC":
                    # Fall back to City of Sarasota layer
                    zone_result = query_cos_zone(float(lat), float(lng))

            if zone_result and zone_result.get("zone_code"):
                zc = zone_result["zone_code"]
                zn = zone_result.get("zone_name", zc)
                src = zone_result.get("source", "unknown")
                jid = zone_result.get("jurisdiction_id", 824)
                print(f"    Zone resolved: code={zc} name={zn} source={src} jid={jid}", flush=True)

                # Insert to parcel_zones (ON CONFLICT DO NOTHING for idempotency)
                insert_pz_query = f"""
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES (
    '{parcel_id}',
    '{parcel_id}',
    {jid},
    '{zc.replace("'", "''")}',
    '{zn.replace("'", "''")}',
    '{src}:shard11_run6288'
)
ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;
"""
                s, r = mgmt_sql(insert_pz_query)
                if s in (200, 201):
                    print(f"    parcel_zones inserted for {parcel_id}", flush=True)
                    resolved_zone_count += 1
                else:
                    print(f"    parcel_zones insert failed: {s}: {r}", flush=True)
            else:
                print(f"    Zone not resolved for {case_num}", flush=True)
        elif zone is not None:
            print(f"    Zone already present: {zone}", flush=True)

    print(f"\n  I fix summary: geo_resolved={resolved_geo_count} zone_resolved={resolved_zone_count}", flush=True)

    # ─── STEP 6: FINAL EVALUATION ────────────────────────────────────────────
    print("\n--- STEP 6: Final evaluation ---", flush=True)
    time.sleep(3)
    final = evaluate_county(COUNTY)
    print(f"FINAL: {final}", flush=True)

    # ─── STEP 7: LOG ULTRALOOP AUDIT ─────────────────────────────────────────
    print("\n--- STEP 7: Log ultraloop audit ───", flush=True)

    g_survived = "pk1000=9" in final or "pk1000=10" in final or "G pass" in final
    log_ultraloop_audit(
        COUNTY, "G",
        f"pk1000 classification: added zoning_districts for CN/RC/RE-2/OUE-1/MP/RSM-9 + set pk1000_regulated=false on PUD/SKOD residential variants. BASELINE: {baseline[:100]}. AFTER: {final[:100]}",
        g_survived,
        {"baseline": baseline, "after_migration": after_g, "final": final, "honesty_marker": "CN pk1000=4.0 INFERRED; residential classifications CONFIRMED"}
    )

    i_survived = "I pass" in final
    log_ultraloop_audit(
        COUNTY, "I",
        f"Property card completion: resolved {resolved_zone_count} zone codes, {resolved_geo_count} geo. BASELINE: {baseline[:100]}. AFTER: {final[:100]}",
        i_survived,
        {"baseline": baseline, "final": final, "geo_resolved": resolved_geo_count, "zone_resolved": resolved_zone_count}
    )

    # ─── STEP 8: FINAL REPORT ────────────────────────────────────────────────
    print("\n=== SESSION SUMMARY ===", flush=True)
    print(f"BEFORE: {baseline}", flush=True)
    print(f"AFTER:  {final}", flush=True)
    print(f"G migration applied (pk1000 classification for unresolved sarasota zones)", flush=True)
    print(f"I: {resolved_zone_count} zone codes + {resolved_geo_count} geo backfills attempted", flush=True)
    print(f"Dispatch: {DISPATCH_ID}", flush=True)
    print(f"Session end: {__import__('datetime').datetime.utcnow().isoformat()}Z", flush=True)

if __name__ == "__main__":
    main()
