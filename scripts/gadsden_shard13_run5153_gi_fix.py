#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-13 — gadsden G+I fix (run 5153)
dispatch_id: 47974994-0d84-4a27-a865-6429cab3303d

STRATEGY:
1. Verify current state (E=21/23, G=null, I=0%)
2. E: Try "Live Oak" address search for 25000942CA (Woods)
   - Search fl_parcels phy_addr1 ILIKE '*LIVE OAK*' co_no=30
   - If unique WOODS match: write parcel_id
   - Try also: 2021 as street number + various street name patterns
3. G+I: Query ARPCmaps (Apalachee Regional Planning Council) FeatureServer
   for gadsden parcels with real coordinates.
   Known ARPC endpoints from prior session:
   - Havana Zoning: services8.arcgis.com/N3lCn6dEKCL6LidU/arcgis/rest/services/Havana_Zoning_Districts_WFL1/FeatureServer
   - Also try Quincy Zoning at same org (N3lCn6dEKCL6LidU)
   - Also try gadsdencountyfl ArcGIS hub directly
   
   For parcels with real lat/lon, do spatial query to find zone_code.
   Insert: parcel_zones rows + any needed zoning_districts.

4. Verify: pencil_dod_evaluate_county('gadsden') — confirm G and I moved.
5. Ultraloop audit row.

HONESTY MARKERS:
- VERIFIED: fl_parcels data used for unique owner/address matches
- INFERRED: zone codes from spatial join (confidence noted)
- BLANK > WRONG: ambiguous matches are skipped

Usage: python3 scripts/gadsden_shard13_run5153_gi_fix.py [--dry-run]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
COUNTY = "gadsden"
DISPATCH_ID = "47974994-0d84-4a27-a865-6429cab3303d"
DRY_RUN = "--dry-run" in sys.argv


def ts() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table: str, params: str = "") -> List[Dict]:
    url = f"{BASE}/{table}{'?' + params if params else ''}{'&' if params else '?'}limit=1000"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=none",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  GET {table} HTTP {e.code}: {e.read().decode()[:200]}")
        return []
    except Exception as e:
        log(f"  GET {table} ERROR: {e}")
        return []


def sb_rpc(func: str, params: Dict) -> Dict:
    body = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/{func}", data=body,
        headers={**HEADERS, "Prefer": ""},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  RPC {func} HTTP {e.code}: {e.read().decode()[:300]}")
        return {}
    except Exception as e:
        log(f"  RPC {func} ERROR: {e}")
        return {}


def sb_post(table: str, data, prefer: str = "resolution=merge-duplicates,return=minimal") -> Tuple[int, str]:
    if isinstance(data, dict):
        data = [data]
    if not data:
        return 200, "no-op"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}/{table}", data=body,
        headers={**HEADERS, "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_patch(table: str, filters: str, data: Dict) -> Tuple[int, str]:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={**HEADERS, "Prefer": "return=representation"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def http_get_json(url: str, timeout: int = 15) -> Optional[Dict]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"    HTTP {e.code} for {url[:80]}")
        return None
    except Exception as e:
        log(f"    ERROR {e} for {url[:80]}")
        return None


def evaluate() -> Dict:
    return sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})


if not SUPABASE_KEY:
    log("FATAL: No Supabase key in environment")
    sys.exit(1)

log("=" * 70)
log(f"GADSDEN SHARD-13 RUN 5153 G+I+E FIX — {ts()}")
log(f"DRY_RUN={DRY_RUN}")
log("=" * 70)

# ── Step 1: Before eval ────────────────────────────────────────────────────
log("\n=== STEP 1: BEFORE EVALUATION ===")
before_eval = evaluate()
log(f"BEFORE: {json.dumps(before_eval, indent=2)}")

# ── Step 2: Get current MCA rows ───────────────────────────────────────────
log("\n=== STEP 2: MCA ROW AUDIT ===")
mca_rows = sb_get(
    "multi_county_auctions",
    "county=eq.gadsden&select=id,case_number,parcel_id,sale_type,property_address,latitude,longitude,last_seen_at&limit=50"
)
log(f"  Total gadsden rows: {len(mca_rows)}")
linked = [r for r in mca_rows if r.get("parcel_id")]
unlinked = [r for r in mca_rows if not r.get("parcel_id")]
log(f"  Linked: {len(linked)}, Unlinked: {len(unlinked)}")
for r in unlinked:
    log(f"    UNLINKED: {r['case_number']} | {r['sale_type']} | addr='{r['property_address']}'")

# Verify coordinates are real (not all-same placeholder)
coords_set = set((r.get("latitude"), r.get("longitude")) for r in mca_rows)
log(f"  Distinct lat/lon pairs: {len(coords_set)} (expect ~21 distinct after 20260718m fix)")

# ── Step 3: E fix — try Live Oak manufactured home address search ──────────
log("\n=== STEP 3: E FIX — Live Oak / Woods angle ===")
# Prior sessions found Woods at "2021 Live Oak Manufactured Home"
# Try: search fl_parcels for phy_addr1 ILIKE '*LIVE OAK*' in co_no=30
live_oak_q = urllib.parse.quote("*LIVE OAK*")
lo_parcels = sb_get("fl_parcels", f"phy_addr1=ilike.{live_oak_q}&co_no=eq.30&select=parcel_id,own_name,phy_addr1,phy_city,jv,dor_uc,centroid_lat,centroid_lng&limit=20")
log(f"  fl_parcels LIVE OAK in phy_addr1, co_no=30: {len(lo_parcels)} rows")
for p in lo_parcels:
    log(f"    {p['parcel_id']} | {p['own_name']} | {p['phy_addr1']}, {p['phy_city']} | dor_uc={p.get('dor_uc')}")

# Also try "2021" as street number
addr_2021_q = urllib.parse.quote("2021*")
p2021 = sb_get("fl_parcels", f"phy_addr1=ilike.{addr_2021_q}&co_no=eq.30&own_name=ilike.*WOODS*&select=parcel_id,own_name,phy_addr1,phy_city,jv,dor_uc,centroid_lat,centroid_lng&limit=10")
log(f"  fl_parcels '2021*' AND 'WOODS' co_no=30: {len(p2021)} rows")
for p in p2021:
    log(f"    {p['parcel_id']} | {p['own_name']} | {p['phy_addr1']}, {p['phy_city']} | dor_uc={p.get('dor_uc')}")

# Try own_addr1 ILIKE '*LIVE OAK*' (mailing address might contain manufactured home park name)
lo_own_q = urllib.parse.quote("*LIVE OAK*")
lo_own_parcels = sb_get("fl_parcels", f"own_addr1=ilike.{lo_own_q}&co_no=eq.30&select=parcel_id,own_name,own_addr1,phy_addr1,phy_city,jv&limit=10")
log(f"  fl_parcels LIVE OAK in own_addr1, co_no=30: {len(lo_own_parcels)} rows")
for p in lo_own_parcels:
    log(f"    {p['parcel_id']} | {p['own_name']} | own_addr={p.get('own_addr1')} | phy={p['phy_addr1']}, {p['phy_city']}")

# Check if there's a mobile home park parcel ID with "LIVE OAK" in phy_city or adjacent field
lo_city_q = urllib.parse.quote("*LIVE OAK*")
lo_city_parcels = sb_get("fl_parcels", f"phy_city=ilike.{lo_city_q}&co_no=eq.30&select=parcel_id,own_name,phy_addr1,phy_city&limit=10")
log(f"  fl_parcels LIVE OAK in phy_city, co_no=30: {len(lo_city_parcels)} rows")

# E assessment:
woods_match = None
if len(lo_parcels) == 1 and "WOODS" in (lo_parcels[0].get("own_name") or "").upper():
    woods_match = lo_parcels[0]
    log(f"  UNIQUE LIVE OAK + WOODS match: {woods_match['parcel_id']}")
elif len(p2021) == 1:
    woods_match = p2021[0]
    log(f"  UNIQUE 2021 + WOODS match: {woods_match['parcel_id']}")
else:
    log(f"  No unique E match for 25000942CA (Woods). Remaining candidates too ambiguous or zero.")

if woods_match and not DRY_RUN:
    woods_mca = sb_get("multi_county_auctions", "county=eq.gadsden&case_number=eq.25000942CA&select=id,parcel_id&limit=2")
    if woods_mca and woods_mca[0]["parcel_id"] is None:
        payload = {
            "parcel_id": woods_match["parcel_id"],
            "assessed_value_source": "fl_parcels_jv_verified_live_oak_address_match",
            "latitude": woods_match.get("centroid_lat"),
            "longitude": woods_match.get("centroid_lng"),
        }
        if woods_match.get("jv"):
            payload["assessed_value"] = woods_match["jv"]
        if woods_match.get("phy_addr1"):
            payload["property_address"] = f"{woods_match['phy_addr1']}, {woods_match.get('phy_city', '')}, FL"
        s, r = sb_patch("multi_county_auctions", f"id=eq.{woods_mca[0]['id']}", payload)
        log(f"  PATCH 25000942CA: HTTP {s}")
        if s not in (200, 204):
            log(f"  ERROR: {r[:200]}")

# ── Step 4: G+I fix — ARPCmaps ArcGIS probe ───────────────────────────────
log("\n=== STEP 4: G+I FIX — ARPCmaps ArcGIS FeatureServer probe ===")
# Known org from prior session: N3lCn6dEKCL6LidU (Apalachee Regional Planning Council)
# Prior session confirmed: Havana Zoning Districts at FeatureServer layer 5
# Try: look for all ARPC services that might include Quincy + Gadsden County zoning

ARPC_ORG = "N3lCn6dEKCL6LidU"
arpc_base = f"https://services8.arcgis.com/{ARPC_ORG}/arcgis/rest/services"

# List all services to find zoning-related ones
log(f"  Probing {arpc_base}?f=json")
services = http_get_json(f"{arpc_base}?f=json", timeout=20)
if services:
    svc_names = [s.get("name", "") for s in services.get("services", [])]
    log(f"  ARPC services ({len(svc_names)}): {svc_names[:20]}")
    zoning_svcs = [s for s in services.get("services", []) if "zon" in s.get("name", "").lower() or "gadsden" in s.get("name", "").lower() or "quincy" in s.get("name", "").lower()]
    log(f"  Zoning-relevant services: {zoning_svcs}")
else:
    log("  Could not list ARPC services")
    zoning_svcs = []

# Try the known Havana endpoint first to confirm it's still up
havana_fs_url = f"https://services8.arcgis.com/{ARPC_ORG}/arcgis/rest/services/Havana_Zoning_Districts_WFL1/FeatureServer"
havana_info = http_get_json(f"{havana_fs_url}?f=json", timeout=15)
if havana_info:
    log(f"  Havana FeatureServer: UP — layers: {[l.get('name') for l in havana_info.get('layers', [])]}")
else:
    log("  Havana FeatureServer: DOWN or unreachable")

# Try to find Quincy zoning at ARPC
quincy_urls = [
    f"https://services8.arcgis.com/{ARPC_ORG}/arcgis/rest/services/Quincy_Zoning_Districts_WFL1/FeatureServer",
    f"https://services8.arcgis.com/{ARPC_ORG}/arcgis/rest/services/QuincyZoningDistricts/FeatureServer",
    f"https://services8.arcgis.com/{ARPC_ORG}/arcgis/rest/services/Quincy_Zoning/FeatureServer",
    f"https://services8.arcgis.com/{ARPC_ORG}/arcgis/rest/services/Gadsden_Zoning/FeatureServer",
    f"https://services8.arcgis.com/{ARPC_ORG}/arcgis/rest/services/Gadsden_County_Zoning/FeatureServer",
]
working_zoning_fs = None
for url in quincy_urls:
    info = http_get_json(f"{url}?f=json", timeout=10)
    if info and "layers" in info:
        log(f"  FOUND zoning FeatureServer: {url}")
        log(f"    Layers: {[l.get('name') for l in info.get('layers', [])]}")
        working_zoning_fs = url
        break
    else:
        log(f"  Not found: {url.split('/')[-2]}")
    time.sleep(0.5)

# Get jurisdictions for Gadsden
jurs = sb_get("jurisdictions", "county=ilike.*Gadsden*&select=id,name,county,co_no,state&limit=20")
log(f"\n  Gadsden jurisdictions in DB: {len(jurs)}")
jur_by_name = {}
for j in jurs:
    log(f"    id={j['id']} name={j['name']}")
    jur_by_name[j["name"].lower()] = j["id"]

# Get linked MCA rows with real (non-centroid) coordinates for zoning lookup
linked_with_coords = [
    r for r in mca_rows
    if r.get("parcel_id") and r.get("latitude") and r.get("longitude")
    and not (abs(r["latitude"] - 30.5768) < 0.001 and abs(r["longitude"] + 84.5875) < 0.001)
]
linked_centroid_only = [
    r for r in mca_rows
    if r.get("parcel_id") and r.get("latitude")
    and (abs(r["latitude"] - 30.5768) < 0.001 and abs(r["longitude"] + 84.5875) < 0.001)
]
log(f"\n  Rows with real (non-placeholder) coordinates: {len(linked_with_coords)}")
log(f"  Rows still on county centroid: {len(linked_centroid_only)}")

# Check existing parcel_zones for gadsden
existing_pz_ids = set()
if linked:
    for r in linked:
        pid = r["parcel_id"]
        if pid:
            pid_q = urllib.parse.quote(pid)
            pz_check = sb_get("parcel_zones", f"parcel_id=eq.{pid_q}&select=parcel_id,zone_code,jurisdiction_id&limit=5")
            if pz_check:
                existing_pz_ids.add(pid)
                log(f"  parcel_zones exists for {pid}: {pz_check}")

log(f"\n  Parcels already in parcel_zones: {len(existing_pz_ids)}")
parcels_needing_zones = [r for r in linked_with_coords if r.get("parcel_id") not in existing_pz_ids]
log(f"  Parcels needing zone lookup: {len(parcels_needing_zones)}")

# ── Step 5: Spatial zone lookup via ArcGIS ─────────────────────────────────
log("\n=== STEP 5: SPATIAL ZONE LOOKUP ===")
# Strategy: for each parcel with real coordinates, query ARPCmaps or
# Gadsden county GIS for zoning. Use point-in-polygon via ArcGIS REST query.

# Known working Havana endpoint from prior session (layer 1 = ZoningDistricts polygon)
havana_zone_layer = f"https://services8.arcgis.com/{ARPC_ORG}/arcgis/rest/services/Havana_Zoning_Districts_WFL1/FeatureServer/1"
quincy_zone_layer = None
if working_zoning_fs:
    quincy_zone_layer = f"{working_zoning_fs}/1"

# Build map of parcel addresses to municipality
# Based on original bootstrap data:
# Quincy: 25000148CA (208 S. Love St), 25000126CA (121 Lantern Ln, Havana), etc.
# Chattahoochee: 23000820CA (924 Bethel St), 25000484CA (211 N. Oak Rd)
# Havana: 25000126CA (121 Lantern Ln), 25000943CA (1726 Kemp Rd), 25000896CA (540 Old Federal Rd)

# Map each MCA row to its likely municipality for jurisdiction_id lookup
ADDR_TO_CITY = {
    "25000942CA": "county",    # "2021 Live Oak Manufactured Home" — unincorporated
    "25000827CA": "county",    # "Lot 19 of Old Federal Ranch" — unincorporated (Havana area)
    "23000820CA": "chattahoochee",
    "25000896CA": "quincy",    # "540 Old Federal Rd, Quincy"
    "25000580CA": "quincy",    # "511 Hopkins Landing Rd, Quincy"
    "25000484CA": "chattahoochee",  # "211 N. Oak Rd, Chattahoochee"
    "24000687CA": "quincy",    # "4164 Mount Pleasant Rd, Quincy"
    "25000901CA": "county",    # "Section 26, Township 2 North" — unincorporated
    "25000696CA": "county",    # "Section 3, Township 3 North" — unincorporated
    "25000545CA": "county",    # "4 Parcels, Gadsden County" — unincorporated
    "25000148CA": "quincy",    # "208 S. Love St, Quincy"
    "25000742CA": "county",    # "Lot 35, Block A of Tobacco Rd" — Midway/unincorporated
    "25000126CA": "havana",    # "121 Lantern Ln, Havana"
    "25000121CA": "quincy",    # "310 Holly Circle, Quincy"
    "25000943CA": "havana",    # "1726 Kemp Rd, Havana"
    "24000726CA": "quincy",    # "121 Squirrel Ln, Quincy"
    "26000007TDC": "chattahoochee",  # "520 Pearl St, Chattahoochee"
    "26000008TDC": "havana",         # "301 John Yawn Place, Havana"
    "26000009TDC": "quincy",         # "2320 Pavillion Dr, Quincy"
    "26000010TDC": "quincy",         # "614 Williams St, Quincy"
    "26000011TDC": "quincy",         # "226 Carver St, Quincy"
    "26000012TDC": "quincy",         # "876 Union Chapel Rd, Quincy"
    "26000013TDC": "county",         # "3090 Lakeview Point Rd, Quincy" area — likely unincorporated
}

# Quincy parcels: 9 total rows. Try ARPCmaps for Quincy or use ordnance-derived zone for all.
# Since the ARPCmaps probe above will tell us if Quincy zoning layer exists,
# let's try the direct approach: query for each Quincy parcel via a known Quincy ArcGIS layer.

# Check the Gadsden County open data hub (ArcHub)
gadsden_hub_urls = [
    "https://arcgis.gadsdencountyfl.gov/arcgis/rest/services",
    "https://gis.gadsdencountyfl.gov/arcgis/rest/services",
    "https://maps.gadsdencountyfl.gov/arcgis/rest/services",
    "https://hub.arcgis.com/datasets/gadsden",
]

log("\n  Probing Gadsden County ArcGIS endpoints:")
for hub_url in gadsden_hub_urls[:3]:
    result = http_get_json(f"{hub_url}?f=json", timeout=10)
    if result and ("services" in result or "folders" in result):
        log(f"  ACCESSIBLE: {hub_url}")
        folders = result.get("folders", [])
        services = [s.get("name") for s in result.get("services", [])]
        log(f"    Folders: {folders}, Services: {services[:10]}")
    else:
        log(f"  INACCESSIBLE: {hub_url}")
    time.sleep(0.5)

# For the I/G fix, we need parcel_zones. If ArcGIS is inaccessible,
# we can still assign zones based on the municipality from address + the
# dominant residential zone for each municipality. This is not ghost-success
# if we're assigning the CORRECT zoning district code for that address.
# 
# BUT: we must not fabricate zone codes. If we don't have a verified source,
# we should not write parcel_zones at all (BLANK > WRONG).
# 
# The key question is: can we get a working ArcGIS endpoint for zone lookups?

# Try the city of Quincy directly
quincy_direct_urls = [
    "https://maps.cityofquincy.com/arcgis/rest/services",
    "https://cityofquincy.com/arcgis/rest/services",
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services",  # FL statewide
    "https://services1.arcgis.com/CY1LXxl9zlJeBuiP/arcgis/rest/services",  # FCIT FL
]
log("\n  Probing Quincy direct ArcGIS:")
for q_url in quincy_direct_urls:
    result = http_get_json(f"{q_url}?f=json", timeout=10)
    if result and ("services" in result or "folders" in result):
        log(f"  ACCESSIBLE: {q_url}")
        svcs = [s.get("name") for s in result.get("services", [])]
        log(f"    Services: {svcs[:10]}")
        break
    time.sleep(0.3)

# Try ArcGIS Hub open data for Gadsden
hub_data_url = "https://opendata.arcgis.com/api/v3/datasets?q=gadsden+zoning&f=json"
hub_result = http_get_json(hub_data_url, timeout=15)
if hub_result:
    results = hub_result.get("data", [])
    log(f"  ArcGIS Hub gadsden+zoning results: {len(results)}")
    for r in results[:5]:
        log(f"    {r.get('id')} | {r.get('attributes', {}).get('name')} | {r.get('attributes', {}).get('url')}")

# ── Step 6: Quincy property appraiser or GIS via BCPAO-style approach ─────
log("\n=== STEP 6: FL GIO parcel zone_code check ===")
# FL GIO fl_parcels might have zone_code for Quincy parcels
sample_quincy_parcels = [
    r["parcel_id"] for r in mca_rows
    if r.get("parcel_id") and ADDR_TO_CITY.get(r["case_number"]) == "quincy"
]
log(f"  Quincy parcel_ids: {sample_quincy_parcels[:5]}")
if sample_quincy_parcels:
    pid_q = urllib.parse.quote(sample_quincy_parcels[0])
    fl_parcel = sb_get("fl_parcels", f"parcel_id=eq.{pid_q}&co_no=eq.30&select=parcel_id,zone_code,muni,phy_addr1,phy_city,jv,centroid_lat,centroid_lng&limit=5")
    log(f"  fl_parcels sample Quincy row: {fl_parcel}")
    if fl_parcel:
        log(f"    zone_code={fl_parcel[0].get('zone_code')}, muni={fl_parcel[0].get('muni')}")

# Check all linked gadsden parcels for fl_parcels zone_code availability
log("\n  Checking fl_parcels.zone_code for all gadsden linked parcels:")
zoned_parcels = []  # parcels with zone_code from fl_parcels
for row in linked:
    pid = row.get("parcel_id")
    if not pid:
        continue
    pid_q = urllib.parse.quote(pid)
    fl_row = sb_get("fl_parcels", f"parcel_id=eq.{pid_q}&co_no=eq.30&select=parcel_id,zone_code,muni,centroid_lat,centroid_lng&limit=2")
    if fl_row:
        zc = fl_row[0].get("zone_code")
        muni = fl_row[0].get("muni")
        log(f"    {pid} | zone_code={zc} | muni={muni}")
        if zc and zc.strip():
            zoned_parcels.append({
                "parcel_id": pid,
                "zone_code": zc.strip(),
                "muni": muni,
                "case_number": row["case_number"],
                "centroid_lat": fl_row[0].get("centroid_lat"),
                "centroid_lng": fl_row[0].get("centroid_lng"),
            })
    time.sleep(0.1)

log(f"\n  fl_parcels.zone_code available for {len(zoned_parcels)} gadsden parcels")
if zoned_parcels:
    for z in zoned_parcels:
        log(f"    {z['parcel_id']} | zone_code={z['zone_code']} | muni={z['muni']}")

# ── Step 7: Write parcel_zones if fl_parcels has zone_code ────────────────
log("\n=== STEP 7: INSERT parcel_zones FROM fl_parcels.zone_code ===")
new_pz_rows = []
if zoned_parcels:
    for z in zoned_parcels:
        if z["parcel_id"] in existing_pz_ids:
            log(f"  SKIP: {z['parcel_id']} already has parcel_zones row")
            continue

        # Determine jurisdiction_id from municipality name
        muni_lower = (z.get("muni") or "").lower()
        city_key = ADDR_TO_CITY.get(z["case_number"], "county")
        jur_id = jur_by_name.get(city_key) or jur_by_name.get(muni_lower)

        if not jur_id:
            log(f"  SKIP: {z['parcel_id']} — no jurisdiction_id for muni={z.get('muni')} city_key={city_key}")
            continue

        new_pz_rows.append({
            "parcel_id": z["parcel_id"],
            "jurisdiction_id": jur_id,
            "zone_code": z["zone_code"],
            "zone_name": z["zone_code"],
            "source": f"fl_parcels_zone_code:gadsden:shard13_run5153",
        })

    if new_pz_rows:
        log(f"  Inserting {len(new_pz_rows)} parcel_zones rows from fl_parcels.zone_code")
        if not DRY_RUN:
            s, r = sb_post("parcel_zones", new_pz_rows, "resolution=merge-duplicates,return=minimal")
            log(f"  INSERT parcel_zones: HTTP {s}")
            if s >= 300:
                log(f"  ERROR: {r[:300]}")
        else:
            log("  DRY RUN — no write")
    else:
        log("  No new parcel_zones rows to insert (all filtered or no zone_code found)")
else:
    log("  No fl_parcels.zone_code available for gadsden parcels — G/I cannot be fixed via this route")

# ── Step 8: After eval ────────────────────────────────────────────────────
log("\n=== STEP 8: AFTER EVALUATION ===")
after_eval = evaluate()
log(f"AFTER: {json.dumps(after_eval, indent=2)}")

# ── Step 9: Ultraloop audit ───────────────────────────────────────────────
log("\n=== STEP 9: ULTRALOOP AUDIT ===")
audit_rows = []
for letter in "ABCDEFGHIJ":
    before = before_eval.get(letter, {})
    after = after_eval.get(letter, {})
    survived = after.get("pass", False)
    claim = f"letter_{letter}_metric={after.get('metric')}_pass={after.get('pass')}"
    audit_rows.append({
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": COUNTY,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": json.dumps({
            "before": before,
            "after": after,
            "evidence": "live pencil_dod_evaluate_county() before+after, shard13 run5153",
        }),
        "survived": survived,
    })

if not DRY_RUN:
    s2, _ = sb_post("gold_standard_ultraloop_audit", audit_rows, "resolution=merge-duplicates,return=minimal")
    log(f"  INSERT ultraloop_audit ({len(audit_rows)} rows): HTTP {s2}")

# Summary
log("\n=== SESSION SUMMARY ===")
before_score = sum(1 for l in "ABCDEFGHIJ" if before_eval.get(l, {}).get("pass"))
after_score = sum(1 for l in "ABCDEFGHIJ" if after_eval.get(l, {}).get("pass"))
log(f"  BEFORE: {before_score}/10")
log(f"  AFTER:  {after_score}/10")

print("\n### SQL VERIFICATION — GADSDEN")
print(f"Timestamp: {ts()}")
print(f"dispatch_id: {DISPATCH_ID}")
print(f"BEFORE pencil_dod_evaluate_county('gadsden'):")
print(json.dumps(before_eval, indent=2))
print(f"\nAFTER pencil_dod_evaluate_county('gadsden'):")
print(json.dumps(after_eval, indent=2))
print(f"\nScore: {before_score}/10 → {after_score}/10")
print(f"new parcel_zones rows attempted: {len(new_pz_rows)}")
