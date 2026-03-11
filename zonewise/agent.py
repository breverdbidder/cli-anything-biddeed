#!/usr/bin/env python3
"""
cli_anything.zoning — Universal FL county zoning agent.

5-stage pipeline for ANY Florida county:
  1. DISCOVER — Probe county GIS + AGOL for zoning/FLU layers
  2. DOWNLOAD — Parcels + zoning polygons + municipal sources
  3. CROSSREF — Build TaxAcct→PARCEL_ID lookup (solves ID mismatch)
  4. MATCH    — STRtree spatial join + municipal overlay
  5. PERSIST  — Priority upsert: municipal > county zoning > FLU > USE_CODE

Usage:
  python -m zoning.agent conquer brevard
  python -m zoning.agent conquer orange
  python -m zoning.agent discover palm_beach
  python -m zoning.agent status brevard
"""
import httpx, json, os, sys, time, argparse, re
from datetime import datetime, timezone
from pathlib import Path

try:
    from shapely.geometry import shape, Point
    from shapely import STRtree
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

CONFIG_DIR = Path(__file__).parent / "county_configs"
CONFIG_DIR.mkdir(exist_ok=True)

# Common FL county GIS patterns
GIS_PATTERNS = [
    "https://gis.{county}fl.gov/gissrv/rest/services",
    "https://gis.{county}fl.gov/arcgis/rest/services",
    "https://maps.{county}fl.gov/arcgis/rest/services",
    "https://gis.{county}.gov/arcgis/rest/services",
    "https://gis.{county}county.gov/arcgis/rest/services",
    "https://gis.{county}countyfl.gov/arcgis/rest/services",
    "https://maps.{county}.gov/arcgis/rest/services",
]

# Known county GIS endpoints (discovered)
KNOWN_ENDPOINTS = {
    "brevard": {
        "gis_base": "https://gis.brevardfl.gov/gissrv/rest/services",
        "zoning_layer": "Planning_Development/Zoning_WKID2881/MapServer/0",
        "zoning_field": "ZONING",
        "flu_layer": "Planning_Development/FLU_WKID2881/MapServer/0",
        "flu_field": "FLU",
        "parcel_layer": "Base_Map/Parcel_New_WKID2881/MapServer/5",
        "parcel_id_field": "PARCEL_ID",
        "taxacct_field": "TaxAcct",
        "city_field": "CITY",
        "usecode_field": "USE_CODE",
        "usecode_desc_field": "USE_CODE_DESCRIPTION",
        "native_crs": 2881,
        "municipal_agol": [
            {"jurisdiction": "satellite_beach",
             "url": "https://services5.arcgis.com/6oVY31bK6DOd0VbR/arcgis/rest/services/Zoning/FeatureServer/0",
             "pid_field": "PID", "zone_field": "Zoning"},
            {"jurisdiction": "cocoa_beach",
             "url": "https://services5.arcgis.com/U4PMgBw5XA2nmleg/arcgis/rest/services/CBParcelsMaster2021/FeatureServer/0",
             "pid_field": "Name", "zone_field": "Zoning"},
            {"jurisdiction": "malabar",
             "url": "https://services6.arcgis.com/UteZaUNFn6dZLkez/arcgis/rest/services/TownOfMalabar_LandUse_Zoning/FeatureServer/0",
             "pid_field": "Name", "zone_field": "Current_Zoning"},
            {"jurisdiction": "west_melbourne",
             "url": "https://cwm-gis.westmelbourne.org/server/rest/services/Hosted/Zoning_View/FeatureServer/0",
             "pid_field": "name", "zone_field": "zoningnew"},
        ],
        "municipal_taxacct": [
            # Melbourne, Cocoa, Rockledge use TaxAcct in AGOL → need cross-ref
            {"jurisdiction": "melbourne", "owner": "GISAdmn",
             "url": "https://services5.arcgis.com/lh4CRjtBYJAJEZaP/arcgis/rest/services",
             "taxacct_field": "TaxAcct", "zone_field": "Zoning"},
        ],
    }
}

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Agent)"})

# ═══════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_headers(prefer="resolution=merge-duplicates"):
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": prefer}

def sb_upsert(rows, table="zoning_assignments"):
    h = sb_headers()
    ok = err = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = c.post(f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=parcel_id",
                      headers=h, json=batch)
        if resp.status_code in (200, 201, 204): ok += len(batch)
        else: err += len(batch)
        time.sleep(0.3)
    return ok, err

def sb_count(county):
    h = sb_headers(prefer="count=exact")
    r = c.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.{county}",
              headers=h)
    cr = r.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

def load_config(county):
    """Load county config — known endpoints or discovered."""
    if county in KNOWN_ENDPOINTS:
        return KNOWN_ENDPOINTS[county]
    config_path = CONFIG_DIR / f"{county}.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return None

def save_config(county, config):
    config_path = CONFIG_DIR / f"{county}.json"
    config_path.write_text(json.dumps(config, indent=2))

def gis_query(url, params, max_pages=None):
    """Paginated GIS query. Yields features."""
    offset = 0
    page = 0
    while True:
        p = {**params, "resultOffset": offset, "f": "json"}
        r = c.get(f"{url}/query", params=p)
        data = r.json()
        feats = data.get("features", [])
        if not feats: break
        yield from feats
        offset += len(feats)
        page += 1
        if max_pages and page >= max_pages: break
        if not data.get("exceededTransferLimit") and len(feats) < int(params.get("resultRecordCount", 2000)):
            break
        time.sleep(1)

# ═══════════════════════════════════════════════════════════════
# STAGE 1: DISCOVER
# ═══════════════════════════════════════════════════════════════

def discover(county):
    """Probe for county GIS endpoints and AGOL municipal sources."""
    telegram(f"🔍 DISCOVER: {county.upper()}")
    config = load_config(county) or {}
    
    # 1. Probe county GIS
    if not config.get("gis_base"):
        telegram("  Probing county GIS patterns...")
        for pattern in GIS_PATTERNS:
            url = pattern.format(county=county.replace("_", ""))
            try:
                r = c.get(f"{url}?f=json", timeout=5)
                if r.status_code == 200:
                    d = r.json()
                    if d.get("services") or d.get("folders"):
                        config["gis_base"] = url
                        telegram(f"  🎯 GIS: {url}")
                        break
            except: pass
    
    if not config.get("gis_base"):
        telegram(f"  ❌ No county GIS found for {county}")
        return config
    
    # 2. Find zoning + parcel layers
    base = config["gis_base"]
    telegram("  Scanning for zoning/parcel layers...")
    
    # Check all folders
    try:
        r = c.get(f"{base}?f=json")
        d = r.json()
        folders = d.get("folders", [])
        services = d.get("services", [])
        
        all_services = list(services)
        for folder in folders:
            try:
                r2 = c.get(f"{base}/{folder}?f=json")
                all_services.extend(r2.json().get("services", []))
            except: pass
        
        for svc in all_services:
            name = svc.get("name", "").lower()
            stype = svc.get("type", "")
            if stype != "MapServer": continue
            
            if any(kw in name for kw in ["zon", "land_use", "flu", "future"]):
                # Probe layers
                svc_url = f"{base}/{svc['name']}/MapServer"
                try:
                    r3 = c.get(f"{svc_url}?f=json")
                    for layer in r3.json().get("layers", []):
                        lname = layer["name"].lower()
                        lid = layer["id"]
                        if "zon" in lname and "flood" not in lname:
                            r4 = c.get(f"{svc_url}/{lid}?f=json")
                            fields = [f["name"] for f in r4.json().get("fields", [])
                                     if any(kw in f["name"].upper() for kw in ["ZONE", "ZON"])]
                            if fields:
                                config["zoning_layer"] = f"{svc['name']}/MapServer/{lid}"
                                config["zoning_field"] = fields[0]
                                cnt = c.get(f"{svc_url}/{lid}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}).json().get("count", 0)
                                telegram(f"  🎯 Zoning: {svc['name']}/{lid} ({cnt} polygons, field: {fields[0]})")
                        elif "flu" in lname or "future" in lname:
                            r4 = c.get(f"{svc_url}/{lid}?f=json")
                            fields = [f["name"] for f in r4.json().get("fields", [])
                                     if any(kw in f["name"].upper() for kw in ["FLU", "LAND"])]
                            if fields:
                                config["flu_layer"] = f"{svc['name']}/MapServer/{lid}"
                                config["flu_field"] = fields[0]
                                telegram(f"  🎯 FLU: {svc['name']}/{lid} (field: {fields[0]})")
            
            elif "parcel" in name:
                svc_url = f"{base}/{svc['name']}/MapServer"
                try:
                    r3 = c.get(f"{svc_url}?f=json")
                    for layer in r3.json().get("layers", []):
                        r4 = c.get(f"{svc_url}/{layer['id']}?f=json")
                        d4 = r4.json()
                        field_names = [f["name"] for f in d4.get("fields", [])]
                        pid = next((f for f in field_names if "PARCEL" in f.upper() and "ID" in f.upper()), None)
                        tax = next((f for f in field_names if "TAX" in f.upper() and "ACCT" in f.upper()), None)
                        city = next((f for f in field_names if f.upper() == "CITY"), None)
                        use = next((f for f in field_names if f.upper() == "USE_CODE"), None)
                        if pid:
                            config["parcel_layer"] = f"{svc['name']}/MapServer/{layer['id']}"
                            config["parcel_id_field"] = pid
                            if tax: config["taxacct_field"] = tax
                            if city: config["city_field"] = city
                            if use: config["usecode_field"] = use
                            cnt = c.get(f"{svc_url}/{layer['id']}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}).json().get("count", 0)
                            telegram(f"  🎯 Parcels: {svc['name']}/{layer['id']} ({cnt} features, PID: {pid})")
                            break
                except: pass
    except Exception as e:
        telegram(f"  Error scanning: {e}")
    
    # 3. AGOL municipal search
    telegram("  Scanning AGOL for municipal zoning...")
    config.setdefault("municipal_agol", [])
    
    try:
        r = c.get("https://www.arcgis.com/sharing/rest/search", params={
            "q": f"{county} florida zoning", "f": "json", "num": 20
        })
        for item in r.json().get("results", []):
            if "Feature" in item.get("type", "") and item.get("url"):
                title = item.get("title", "")
                if "zon" in title.lower():
                    telegram(f"  📡 AGOL: {title[:50]} | {item.get('owner','')}")
    except: pass
    
    save_config(county, config)
    telegram(f"  Config saved: {len(config)} keys")
    return config

# ═══════════════════════════════════════════════════════════════
# STAGE 3: CROSSREF (TaxAcct → PARCEL_ID)
# ═══════════════════════════════════════════════════════════════

def build_crossref(config, county):
    """Build TaxAcct→PARCEL_ID lookup from county GIS."""
    base = config["gis_base"]
    layer = config["parcel_layer"]
    pid_f = config["parcel_id_field"]
    tax_f = config.get("taxacct_field")
    
    if not tax_f:
        telegram("  ⚠️ No TaxAcct field — crossref not needed")
        return {}
    
    telegram(f"  Building TaxAcct→PARCEL_ID crossref...")
    xref = {}
    url = f"{base}/{layer}"
    for feat in gis_query(url, {"where": "1=1", "outFields": f"{pid_f},{tax_f}",
                                 "returnGeometry": "false", "resultRecordCount": "2000"}):
        a = feat.get("attributes", {})
        pid = (str(a.get(pid_f, "")) or "").strip()
        tax = a.get(tax_f)
        if pid and tax:
            xref[str(tax)] = pid
    
    telegram(f"  Crossref built: {len(xref):,} TaxAcct→PID mappings")
    return xref

# ═══════════════════════════════════════════════════════════════
# STAGE 4: SPATIAL JOIN
# ═══════════════════════════════════════════════════════════════

def spatial_join(config, county):
    """STRtree spatial join: parcels × zoning polygons."""
    if not HAS_SHAPELY:
        telegram("  ❌ Shapely not installed — pip install shapely")
        return []
    
    base = config["gis_base"]
    zoning_url = f"{base}/{config['zoning_layer']}"
    parcel_url = f"{base}/{config['parcel_layer']}"
    zone_field = config["zoning_field"]
    pid_field = config["parcel_id_field"]
    city_field = config.get("city_field", "CITY")
    
    # Download zoning polygons
    telegram("  Downloading zoning polygons...")
    polys = []
    for feat in gis_query(zoning_url, {"where": "1=1", "outFields": zone_field,
                                        "returnGeometry": "true", "resultRecordCount": "1000"}):
        try:
            geom = feat.get("geometry", {})
            if not geom or "rings" not in geom: continue
            code = feat["attributes"].get(zone_field, "")
            if not code: continue
            poly = shape({"type": "Polygon", "coordinates": geom["rings"]})
            if poly.is_valid and not poly.is_empty:
                polys.append((poly, str(code).strip()))
        except: pass
    
    telegram(f"  {len(polys)} polygons loaded, building STRtree...")
    tree = STRtree([p[0] for p in polys])
    
    # Download parcels with geometry
    telegram("  Downloading parcels with geometry...")
    rows = []
    total = 0
    for feat in gis_query(parcel_url, {"where": "1=1", "outFields": f"{pid_field},{city_field}",
                                        "returnGeometry": "true",
                                        "resultRecordCount": "2000"}):
        pid = (feat["attributes"].get(pid_field) or "").strip()
        city = (feat["attributes"].get(city_field) or "").strip()
        if not pid: continue
        total += 1
        
        rings = feat.get("geometry", {}).get("rings", [])
        if not rings: continue
        ring = rings[0]
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        pt = Point(cx, cy)
        
        hits = tree.query(pt)
        for idx in hits:
            poly, code = polys[idx]
            if poly.contains(pt):
                rows.append({
                    "parcel_id": pid,
                    "zone_code": code,
                    "jurisdiction": city.lower().replace(" ", "_") if city else "unincorporated",
                    "county": county,
                })
                break
        
        if total % 50000 == 0:
            telegram(f"  {total:,} parcels, {len(rows):,} matched")
    
    telegram(f"  Spatial join: {len(rows):,} / {total:,} ({len(rows)/max(total,1)*100:.0f}%)")
    return rows

# ═══════════════════════════════════════════════════════════════
# STAGE 2+5: MUNICIPAL AGOL DOWNLOAD + PERSIST
# ═══════════════════════════════════════════════════════════════

def download_municipal(config, county):
    """Download zoning from all known municipal AGOL sources."""
    sources = config.get("municipal_agol", [])
    if not sources:
        telegram("  No municipal AGOL sources configured")
        return []
    
    all_rows = []
    for src in sources:
        juris = src["jurisdiction"]
        url = src["url"]
        pid_f = src["pid_field"]
        zone_f = src["zone_field"]
        
        telegram(f"  Downloading {juris}...")
        records = []
        for feat in gis_query(url, {"where": f"{zone_f} IS NOT NULL",
                                     "outFields": f"{pid_f},{zone_f}",
                                     "returnGeometry": "false",
                                     "resultRecordCount": "2000"}):
            a = feat.get("attributes", {})
            pid = (str(a.get(pid_f, "")) or "").strip()
            zone = (str(a.get(zone_f, "")) or "").strip()
            if pid and zone:
                records.append({"parcel_id": pid, "zone_code": zone,
                               "jurisdiction": juris, "county": county})
        
        # Dedup
        seen = {}
        for r in records: seen[r["parcel_id"]] = r
        records = list(seen.values())
        telegram(f"    {juris}: {len(records):,} records")
        all_rows.extend(records)
    
    return all_rows

def fill_usecode(config, county):
    """Fill remaining parcels with USE_CODE as fallback."""
    base = config["gis_base"]
    layer = config["parcel_layer"]
    pid_f = config["parcel_id_field"]
    use_f = config.get("usecode_field")
    use_desc_f = config.get("usecode_desc_field")
    city_f = config.get("city_field", "CITY")
    tax_f = config.get("taxacct_field")
    
    if not use_f and not use_desc_f:
        telegram("  ⚠️ No USE_CODE field — skipping fallback")
        return []
    
    fields = f"{pid_f},{city_f}"
    if use_f: fields += f",{use_f}"
    if use_desc_f: fields += f",{use_desc_f}"
    if tax_f: fields += f",{tax_f}"
    
    telegram("  Downloading USE_CODE fallback...")
    seen = {}
    for feat in gis_query(f"{base}/{layer}", {"where": "1=1", "outFields": fields,
                                               "returnGeometry": "false",
                                               "resultRecordCount": "2000"}):
        a = feat.get("attributes", {})
        pid = (str(a.get(pid_f, "")) or "").strip()
        if not pid or pid in seen: continue
        
        use_desc = (str(a.get(use_desc_f, "")) or "").strip() if use_desc_f else ""
        use_code = (str(a.get(use_f, "")) or "").strip() if use_f else ""
        city = (str(a.get(city_f, "")) or "").strip()
        tax = a.get(tax_f) if tax_f else None
        
        zone_val = use_desc if use_desc else (f"USE:{use_code}" if use_code else "UNCLASSIFIED")
        
        row = {
            "parcel_id": pid,
            "zone_code": zone_val,
            "jurisdiction": city.lower().replace(" ", "_") if city else "unincorporated",
            "county": county,
        }
        
        # Photo URL from TaxAcct
        if tax:
            prefix = str(tax)[:2]
            row["photo_url"] = f"https://www.bcpao.us/photos/{prefix}/{tax}011.jpg"
        
        seen[pid] = row
    
    telegram(f"  USE_CODE fallback: {len(seen):,} parcels")
    return list(seen.values())

# ═══════════════════════════════════════════════════════════════
# MAIN: CONQUER
# ═══════════════════════════════════════════════════════════════

def conquer(county):
    """Full pipeline: discover → spatial join → municipal → usecode → persist."""
    start = time.time()
    telegram(f"🏔️ CONQUER: {county.upper()}\n")
    
    # Load or discover config
    config = load_config(county)
    if not config:
        config = discover(county)
    
    if not config.get("gis_base"):
        telegram(f"❌ Cannot conquer {county} — no GIS endpoint found")
        return
    
    current = sb_count(county)
    telegram(f"  Current Supabase: {current:,} records for {county}")
    
    # Step 1: USE_CODE base layer (every parcel gets at least this)
    telegram("\n🏔️ STEP 1: USE_CODE base layer")
    usecode_rows = fill_usecode(config, county)
    if usecode_rows:
        ok, err = sb_upsert(usecode_rows)
        telegram(f"  Base layer: {ok:,} ok, {err:,} err")
    
    # Step 2: County zoning spatial join (overwrites USE_CODE where polygon exists)
    if config.get("zoning_layer") and HAS_SHAPELY:
        telegram("\n🏔️ STEP 2: County zoning spatial join")
        zoning_rows = spatial_join(config, county)
        if zoning_rows:
            ok, err = sb_upsert(zoning_rows)
            telegram(f"  County zoning: {ok:,} ok, {err:,} err")
    
    # Step 3: Municipal AGOL (highest priority — overwrites everything)
    if config.get("municipal_agol"):
        telegram("\n🏔️ STEP 3: Municipal AGOL zoning")
        municipal_rows = download_municipal(config, county)
        if municipal_rows:
            ok, err = sb_upsert(municipal_rows)
            telegram(f"  Municipal: {ok:,} ok, {err:,} err")
    
    # Final count
    final = sb_count(county)
    elapsed = int(time.time() - start)
    
    telegram(f"""
🏔️ CONQUER {county.upper()} COMPLETE

📈 Supabase: {final:,} records
⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

def status(county):
    """Show current data status for a county."""
    total = sb_count(county)
    telegram(f"📊 {county.upper()}: {total:,} records in Supabase")

# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ZoneWise — Universal FL county zoning agent")
    parser.add_argument("command", choices=["conquer", "discover", "status", "crossref"],
                       help="Action to perform")
    parser.add_argument("county", help="FL county name (e.g., brevard, orange, palm_beach)")
    args = parser.parse_args()
    
    county = args.county.lower().replace(" ", "_")
    
    if args.command == "discover":
        discover(county)
    elif args.command == "conquer":
        conquer(county)
    elif args.command == "status":
        status(county)
    elif args.command == "crossref":
        config = load_config(county)
        if config:
            xref = build_crossref(config, county)
            print(f"Crossref: {len(xref):,} mappings")
        else:
            print(f"No config for {county} — run discover first")

if __name__ == "__main__":
    main()
