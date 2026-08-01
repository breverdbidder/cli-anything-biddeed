#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-4 (st_lucie): E+I parcel linkage fix
dispatch_id: 74c00f71-da5f-4b6a-9b1c-57192bde0725
Session: architect-20260801T160000

CONTEXT:
- Prior session (8198896f, 2026-07-27) removed 7 ghost parcel_ids, honest 8/10
- Brief (loop 7963, 2026-08-01): E=94.1% (parcel_linked=112/119), I=94.1% (card_complete=112/119)
- 7 rows still have NULL parcel_id. Need 114/119 (95.0%) → need to fix 2+ more.

METHOD:
1. Baseline: pencil_dod_evaluate_county('st_lucie')
2. Find all st_lucie rows with NULL parcel_id
3. For each: try St Lucie PA ArcGIS search by address (SiteAddress LIKE)
4. Geocode via US Census Bureau geocoder (free, no key)
5. Backfill market_value from PA ArcGIS if found
6. Zoning via county/city ArcGIS layers
7. Update parcel_zones so v_zoning_gold_standard_card picks them up (I)
8. Re-evaluate and verify

HONESTY MARKERS:
- parcel_id lookups: VERIFIED if found via live PA ArcGIS query
- lat/lon: VERIFIED if from Census geocoder; INFERRED if using property centroid from PA
- market_value: VERIFIED if from PA ArcGIS JustMarketValue
- zoning: VERIFIED if from county/city ArcGIS; INFERRED if spatial point-in-polygon
"""
from __future__ import annotations
import json, os, sys, time, urllib.request, urllib.error, urllib.parse

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
DISPATCH_ID = "74c00f71-da5f-4b6a-9b1c-57192bde0725"
COUNTY = "st_lucie"

if not SB_KEY:
    print("ERROR: SUPABASE_KEY / SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SB_URL}/rest/v1"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}
JURISDICTIONS = {"unincorporated": 1400, "fort_pierce": 971, "port_st_lucie": 953}
PA_URL = "https://map.paslc.gov/arcgis/rest/services/PROD/SLCPA_PublicParcels/MapServer/0"
UNINC_ZONING_URL = "https://slcgis.stlucieco.gov/hosting/rest/services/LandUse/Zoning/MapServer/0"
FTPIERCE_ZONING_URL = "https://slcgis.stlucieco.gov/hosting/rest/services/LandUse/ForttPierceZoningFLU/MapServer/0"
PSL_ZONING_URL = "https://services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/Zoning/FeatureServer/1"


def ts() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table: str, params: str = "") -> list:
    url = f"{BASE}/{table}{'?' + params if params else '?limit=500'}"
    if "limit=" not in url:
        url += "&limit=500"
    req = urllib.request.Request(url, headers={**HEADERS})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  GET {table} ERROR {e.code}: {e.read().decode()[:200]}")
        return []


def sb_patch(table: str, filters: str, data: dict) -> tuple:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body,
                                  headers={**HEADERS, "Prefer": "return=minimal"},
                                  method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_post(table: str, rows: list, prefer="return=representation") -> tuple:
    if not rows:
        return 200, "no-op"
    url = f"{BASE}/{table}"
    body = json.dumps(rows).encode()
    req = urllib.request.Request(url, data=body,
                                  headers={**HEADERS, "Prefer": prefer},
                                  method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def evaluate(county: str) -> dict:
    url = f"{BASE}/rpc/pencil_dod_evaluate_county"
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  evaluate ERROR: {e}")
        return {}


def arcgis_query(base_url: str, where: str, out_fields: str = "*",
                 geometry_params: dict = None, return_count_only: bool = False) -> dict:
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
    }
    if geometry_params:
        params.update(geometry_params)
    if return_count_only:
        params["returnCountOnly"] = "true"
    url = base_url + "/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  ArcGIS query error ({base_url}): {e}")
        return {}


def dashify(pid: str) -> str:
    """Convert 15-digit undashed parcel ID to dashed format ####-###-####-###-#"""
    if len(pid) == 15:
        return f"{pid[0:4]}-{pid[4:7]}-{pid[7:11]}-{pid[11:14]}-{pid[14:15]}"
    return pid


def search_pa_by_address(address: str) -> dict | None:
    """Search St Lucie PA ArcGIS by SiteAddress and return parcel attributes."""
    if not address:
        return None
    addr_upper = address.upper().split(",")[0].strip()
    addr_cleaned = addr_upper.replace("'", "''")
    where = f"SiteAddress LIKE '{addr_cleaned}%'"
    res = arcgis_query(PA_URL, where,
                       "ParcelID,AccountNumber,SiteAddress,JustMarketValue,LandValue")
    feats = res.get("features", [])
    if feats:
        return feats[0]["attributes"]
    addr_short = " ".join(addr_upper.split()[:3]) if len(addr_upper.split()) > 3 else addr_upper
    addr_short_clean = addr_short.replace("'", "''")
    where2 = f"SiteAddress LIKE '{addr_short_clean}%'"
    res2 = arcgis_query(PA_URL, where2,
                        "ParcelID,AccountNumber,SiteAddress,JustMarketValue,LandValue")
    feats2 = res2.get("features", [])
    if feats2:
        return feats2[0]["attributes"]
    return None


def search_pa_by_parcel(parcel_id: str) -> dict | None:
    """Search St Lucie PA ArcGIS by dashed ParcelID."""
    dashed = dashify(parcel_id)
    where = f"ParcelID = '{dashed}'"
    res = arcgis_query(PA_URL, where,
                       "ParcelID,AccountNumber,SiteAddress,JustMarketValue,LandValue")
    feats = res.get("features", [])
    if feats:
        return feats[0]["attributes"]
    return None


def census_geocode(address: str) -> tuple | None:
    """Geocode using US Census Bureau (free, no key)."""
    params = {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + \
          urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read())
        matches = res.get("result", {}).get("addressMatches", [])
        if matches:
            c = matches[0]["coordinates"]
            return c["y"], c["x"]
    except Exception as e:
        log(f"  Census geocode error: {e}")
    return None


def get_zoning(parcel_id: str, lat: float, lon: float) -> tuple | None:
    """Try to get zone_code from county/city ArcGIS layers.
    Returns (zone_code, zone_name, jurisdiction_id, source_tag) or None.
    """
    if parcel_id:
        res = arcgis_query(UNINC_ZONING_URL, f"Parcel_num = '{parcel_id}'",
                           "Parcel_num,Zoned")
        feats = res.get("features", [])
        if feats:
            a = feats[0]["attributes"]
            return (a.get("Zoned"), None, JURISDICTIONS["unincorporated"],
                    "arcgis_live_uninc")

        res = arcgis_query(FTPIERCE_ZONING_URL, f"Parcel_Num = '{parcel_id}'",
                           "Parcel_Num,Zoning,ZoningDesc")
        feats = res.get("features", [])
        if feats:
            a = feats[0]["attributes"]
            return (a.get("Zoning"), a.get("ZoningDesc"), JURISDICTIONS["fort_pierce"],
                    "arcgis_live_fort_pierce")

    if lat and lon:
        geometry_params = {
            "geometry": json.dumps({"x": lon, "y": lat,
                                     "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        }
        res = arcgis_query(PSL_ZONING_URL, "1=1", "ZOLEGEND,ZONING,ZO_ID",
                           geometry_params)
        feats = res.get("features", [])
        if feats:
            a = feats[0]["attributes"]
            return (a.get("ZOLEGEND"), a.get("ZONING"), JURISDICTIONS["port_st_lucie"],
                    "arcgis_live_psl_spatial")

    return None


# ── Phase 0: Baseline ────────────────────────────────────────────────────────
log("=== PHASE 0: BASELINE ===")
before = evaluate(COUNTY)
log(f"BEFORE: {json.dumps(before)}")

e_before = before.get("E", {})
i_before = before.get("I", {})
log(f"E: pass={e_before.get('pass')} metric={e_before.get('metric')} detail={e_before.get('detail')}")
log(f"I: pass={i_before.get('pass')} metric={i_before.get('metric')} detail={i_before.get('detail')}")

total_auctions = before.get("auctions_total", 0)
log(f"Total auctions: {total_auctions}")

# ── Phase 1: Find unlinked rows ──────────────────────────────────────────────
log("=== PHASE 1: FIND UNLINKED ROWS ===")
unlinked_rows = sb_get("multi_county_auctions",
    f"county=eq.{COUNTY}&parcel_id=is.null&select=id,case_number,property_address,auction_date,auction_status,source_url")
log(f"Unlinked rows (parcel_id=NULL): {len(unlinked_rows)}")

for r in unlinked_rows:
    log(f"  case={r.get('case_number')} addr={r.get('property_address')!r} "
        f"date={r.get('auction_date')} src={r.get('source_url', '')[:80] if r.get('source_url') else 'NONE'}")

# ── Phase 2: PA ArcGIS lookup for each unlinked row ──────────────────────────
log("=== PHASE 2: PA ARCGIS ADDRESS LOOKUP ===")
fixed_parcel = {}  # case_number -> {parcel_id, market_value, site_address}

for row in unlinked_rows:
    case = row.get("case_number")
    addr = row.get("property_address", "")
    log(f"  Trying PA lookup for {case} addr={addr!r}")

    if not addr or "St. Lucie County FL" in str(addr) or "shard" in str(addr).lower():
        log(f"  {case}: placeholder/missing address, skipping PA lookup")
        continue

    pa_hit = search_pa_by_address(addr)
    if pa_hit and pa_hit.get("ParcelID"):
        raw_pid = pa_hit["ParcelID"].replace("-", "")
        log(f"  {case}: PA FOUND ParcelID={pa_hit['ParcelID']} (undashed={raw_pid}) "
            f"JMV={pa_hit.get('JustMarketValue')} SiteAddress={pa_hit.get('SiteAddress')!r}")
        fixed_parcel[case] = {
            "parcel_id": raw_pid,
            "market_value": pa_hit.get("JustMarketValue"),
            "site_address": pa_hit.get("SiteAddress"),
        }
    else:
        log(f"  {case}: PA no match for address {addr!r}")
    time.sleep(0.5)

log(f"PA matches found: {len(fixed_parcel)}")

# ── Phase 3: Geocode found parcels + missing ones ────────────────────────────
log("=== PHASE 3: GEOCODE ===")
geocoded = {}  # case_number -> (lat, lon)

for row in unlinked_rows:
    case = row.get("case_number")
    addr = row.get("property_address", "")
    if not addr or "St. Lucie County FL" in str(addr):
        continue
    fl_addr = addr
    if "FL" not in fl_addr.upper():
        fl_addr = fl_addr + ", FL"
    coords = census_geocode(fl_addr)
    if coords:
        geocoded[case] = coords
        log(f"  {case}: geocoded lat={coords[0]:.6f} lon={coords[1]:.6f}")
    else:
        log(f"  {case}: geocode failed")
    time.sleep(0.3)

# ── Phase 4: Get market values for PA-found parcels if not in PA result ───────
log("=== PHASE 4: MARKET VALUE BACKFILL FROM PA ARCGIS ===")
for case, pdata in fixed_parcel.items():
    if pdata.get("market_value") is None:
        pid = pdata["parcel_id"]
        pa_hit = search_pa_by_parcel(pid)
        if pa_hit and pa_hit.get("JustMarketValue") is not None:
            pdata["market_value"] = pa_hit["JustMarketValue"]
            log(f"  {case}: market_value={pa_hit['JustMarketValue']} from direct PA lookup")
    time.sleep(0.3)

# ── Phase 5: Write parcel_ids to multi_county_auctions ───────────────────────
log("=== PHASE 5: UPDATE PARCEL_IDS ===")
today = time.strftime("%Y%m%d", time.gmtime())
updated_cases = []
for case, pdata in fixed_parcel.items():
    pid = pdata["parcel_id"]
    update_data = {
        "parcel_id": pid,
        "parity_status": "matched_clean",
        "parity_source": f"pa_arcgis_live_{today}",
        "parity_checked_at": ts(),
    }
    if pdata.get("market_value") is not None:
        update_data["market_value"] = pdata["market_value"]
    if pdata.get("market_value") is not None:
        update_data["assessed_value"] = pdata["market_value"]

    case_enc = urllib.parse.quote(case)
    status, body = sb_patch("multi_county_auctions",
                             f"county=eq.{COUNTY}&case_number=eq.{case_enc}",
                             update_data)
    log(f"  PATCH {case} parcel_id={pid}: HTTP {status}")
    if status < 300:
        updated_cases.append(case)
    else:
        log(f"    ERROR body: {body[:200]}")

time.sleep(1)

# Write geocoordinates for found rows
log("=== PHASE 5b: UPDATE LAT/LON FOR FIXED ROWS ===")
for case, coords in geocoded.items():
    lat, lon = coords
    case_enc = urllib.parse.quote(case)
    status, _ = sb_patch("multi_county_auctions",
                          f"county=eq.{COUNTY}&case_number=eq.{case_enc}&latitude=is.null",
                          {"latitude": lat, "longitude": lon})
    log(f"  PATCH lat/lon {case}: HTTP {status}")
time.sleep(1)

# ── Phase 6: Also backfill market value for rows with parcel_id but no value ──
log("=== PHASE 6: BACKFILL MARKET VALUE FOR LINKED ROWS WITHOUT VALUE ===")
rows_no_value = sb_get("multi_county_auctions",
    f"county=eq.{COUNTY}&parcel_id=not.is.null&assessed_value=is.null&select=id,case_number,parcel_id")
log(f"Rows with parcel_id but no assessed_value: {len(rows_no_value)}")

value_filled = 0
for row in rows_no_value[:20]:
    pid = row.get("parcel_id", "")
    if not pid:
        continue
    pa_hit = search_pa_by_parcel(pid)
    if pa_hit and pa_hit.get("JustMarketValue") is not None:
        case = row.get("case_number")
        case_enc = urllib.parse.quote(case)
        status, _ = sb_patch("multi_county_auctions",
                              f"county=eq.{COUNTY}&case_number=eq.{case_enc}",
                              {"assessed_value": pa_hit["JustMarketValue"],
                               "market_value": pa_hit["JustMarketValue"]})
        if status < 300:
            value_filled += 1
        log(f"  PATCH value {case}: JMV={pa_hit['JustMarketValue']} HTTP {status}")
    time.sleep(0.3)
log(f"Values filled: {value_filled}")
time.sleep(1)

# ── Phase 7: Insert parcel_zones for new linked parcels ──────────────────────
log("=== PHASE 7: PARCEL_ZONES FOR NEW LINKED PARCELS ===")
zones_inserted = 0
for case, pdata in fixed_parcel.items():
    if case not in updated_cases:
        continue
    pid = pdata["parcel_id"]
    coords = geocoded.get(case)
    lat = coords[0] if coords else None
    lon = coords[1] if coords else None

    zoning = get_zoning(pid, lat, lon)
    if zoning:
        zone_code, zone_name, jur_id, source_tag = zoning
        log(f"  {case}: zoning={zone_code} zone_name={zone_name} jur={jur_id} src={source_tag}")
        status, body = sb_post("parcel_zones", [{
            "parcel_id": pid,
            "jurisdiction_id": jur_id,
            "zone_code": zone_code,
            "zone_name": zone_name,
            "source": f"{source_tag}_{today}",
        }], "resolution=merge-duplicates,return=minimal")
        if status < 300:
            zones_inserted += 1
            log(f"  parcel_zones INSERT {pid}: HTTP {status}")
        else:
            log(f"  parcel_zones INSERT {pid}: HTTP {status} BODY={body[:200]}")
    else:
        log(f"  {case}: NO ZONING found for pid={pid} lat={lat} lon={lon}")
    time.sleep(0.3)

log(f"Zoning rows inserted: {zones_inserted}")
time.sleep(1)

# Also check for existing linked rows missing from parcel_zones (I criterion gap)
log("=== PHASE 7b: CHECK EXISTING LINKED ROWS WITHOUT ZONING ===")
all_linked = sb_get("multi_county_auctions",
    f"county=eq.{COUNTY}&parcel_id=not.is.null&select=case_number,parcel_id,latitude,longitude")
log(f"All linked rows: {len(all_linked)}")

existing_zones = sb_get("parcel_zones",
    f"parcel_id=in.({','.join(repr(r['parcel_id']) for r in all_linked[:100] if r.get('parcel_id'))})&select=parcel_id")
existing_pids = {r["parcel_id"] for r in existing_zones}
log(f"Parcel_zones existing for st_lucie parcels: {len(existing_pids)}")

missing_zone_rows = [r for r in all_linked if r.get("parcel_id") and r["parcel_id"] not in existing_pids]
log(f"Linked rows missing from parcel_zones: {len(missing_zone_rows)}")

zones_backfilled = 0
for row in missing_zone_rows[:30]:
    pid = row.get("parcel_id")
    lat = row.get("latitude")
    lon = row.get("longitude")
    if not pid:
        continue
    zoning = get_zoning(pid, lat, lon)
    if zoning:
        zone_code, zone_name, jur_id, source_tag = zoning
        status, body = sb_post("parcel_zones", [{
            "parcel_id": pid,
            "jurisdiction_id": jur_id,
            "zone_code": zone_code,
            "zone_name": zone_name,
            "source": f"{source_tag}_{today}",
        }], "resolution=merge-duplicates,return=minimal")
        if status < 300:
            zones_backfilled += 1
    time.sleep(0.3)

log(f"Additional zones backfilled: {zones_backfilled}")
time.sleep(1)

# ── Phase 8: Re-evaluate ─────────────────────────────────────────────────────
log("=== PHASE 8: RE-EVALUATE ===")
after = evaluate(COUNTY)
log(f"AFTER: {json.dumps(after)}")

e_after = after.get("E", {})
i_after = after.get("I", {})
log(f"E: pass={e_after.get('pass')} metric={e_after.get('metric')} detail={e_after.get('detail')}")
log(f"I: pass={i_after.get('pass')} metric={i_after.get('metric')} detail={i_after.get('detail')}")

# ── Phase 9: Ultraloop audit ─────────────────────────────────────────────────
log("=== PHASE 9: ULTRALOOP AUDIT ===")
letters_passing = [l for l in "ABCDEFGHIJ" if after.get(l, {}).get("pass")]
letters_failing = [l for l in "ABCDEFGHIJ" if not after.get(l, {}).get("pass")]

audit_rows = []
for letter in "ABCDEFGHIJ":
    ldata = after.get(letter, {})
    is_pass = ldata.get("pass", False)
    metric = ldata.get("metric")
    claim = f"letter_{letter}_metric={metric}_pass={is_pass}"
    refuter = {"evaluator_output": ldata, "evidence": "live pencil_dod_evaluate_county()"}
    audit_rows.append({
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": COUNTY,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": json.dumps(refuter),
        "survived": is_pass,
    })

s, r = sb_post("gold_standard_ultraloop_audit", audit_rows,
               "resolution=merge-duplicates,return=minimal")
log(f"Ultraloop audit INSERT: HTTP {s}")

# ── Phase 10: Session close-out to gold_standard_campaign ────────────────────
log("=== PHASE 10: SESSION CLOSE-OUT ===")
criteria_passed = {l: bool(after.get(l, {}).get("pass")) for l in "ABCDEFGHIJ"}
score = len(letters_passing)

closeout_data = {
    "criteria_passed": json.dumps(criteria_passed),
    "criteria_total": 10,
    "exit_reason": "certified" if score == 10 else "timeout",
    "session_end_at": ts(),
}

# Find the campaign row for this dispatch
campaign_rows = sb_get("gold_standard_campaign",
    f"dispatch_id=eq.{DISPATCH_ID}&select=id")
if campaign_rows:
    cid = campaign_rows[0]["id"]
    s, body = sb_patch("gold_standard_campaign", f"id=eq.{cid}", closeout_data)
    log(f"Campaign close-out (id={cid}): HTTP {s}")
else:
    s, body = sb_post("gold_standard_campaign", [{
        "dispatch_id": DISPATCH_ID,
        "county_slug": COUNTY,
        **closeout_data,
    }], "resolution=merge-duplicates,return=minimal")
    log(f"Campaign close-out INSERT: HTTP {s}")

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n### SQL VERIFICATION — ST_LUCIE — {ts()}")
print(f"dispatch_id: {DISPATCH_ID}")
print()
print("BEFORE:")
print(json.dumps(before, indent=2))
print()
print("AFTER:")
print(json.dumps(after, indent=2))
print()
print(f"Score: {score}/10")
print(f"PASSING: {letters_passing}")
print(f"FAILING: {letters_failing}")
print()
print(f"PA matches found: {len(fixed_parcel)} of {len(unlinked_rows)} unlinked rows")
print(f"Cases updated: {updated_cases}")
print(f"Zones inserted: {zones_inserted}")
print(f"Zones backfilled: {zones_backfilled}")

if score == 10:
    print(f"\nGOLD STANDARD ACHIEVED: {COUNTY}")
elif "E" in letters_failing or "I" in letters_failing:
    print(f"\nE/I still failing — may need manual review of remaining {len(unlinked_rows) - len(updated_cases)} unlinked rows")
