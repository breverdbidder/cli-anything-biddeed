#!/usr/bin/env python3
"""
cli_anything.municipal — Municipal Portal Intelligence Agent

Discovers and scrapes ALL data layers from city ArcGIS Enterprise portals.
Not just zoning — permits, code enforcement, liens, utilities, assessments.

5-squad architecture:
  RECON    — Discover portal endpoints for any FL municipality
  ZONING   — Zoning districts + FLU (existing zonewise agent)
  PERMITS  — Building permits, inspections, certificates of occupancy
  CODE_ENF — Code enforcement cases, violations, demolition orders
  LIENS    — Utility liens, special assessments, delinquencies

Usage:
  python municipal/agent.py recon palm_bay
  python municipal/agent.py conquer palm_bay --all
  python municipal/agent.py conquer palm_bay --squad permits
  python municipal/agent.py inventory brevard
"""
import httpx, json, os, sys, time, argparse, re
from datetime import datetime, timezone
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

CONFIG_DIR = Path(__file__).parent / "portal_configs"
CONFIG_DIR.mkdir(exist_ok=True)

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (BidDeed.AI Municipal Intelligence)"})

# ═══════════════════════════════════════════════════════════════
# SQUAD DEFINITIONS — what to look for in each portal
# ═══════════════════════════════════════════════════════════════

SQUADS = {
    "zoning": {
        "folder_keywords": ["growth", "planning", "zoning", "development", "community"],
        "layer_keywords": ["zoning", "zone", "flu", "future land", "land use", "comp_plan", "compplan"],
        "exclude_keywords": ["flood", "fema", "school", "fire", "wind"],
        "priority_fields": ["ZONING", "ZONE_ALL", "ZONE", "FLU", "COMP_PLAN", "COMPPLAN", "LAND_USE"],
        "table": "zoning_assignments",
        "description": "Zoning districts and future land use",
    },
    "permits": {
        "folder_keywords": ["building", "permit", "ims", "development", "construction"],
        "layer_keywords": ["permit", "building permit", "construction", "inspection", "certificate",
                          "occupancy", "demolition", "mechanical", "electrical", "plumbing", "roofing"],
        "exclude_keywords": ["parking permit", "event permit"],
        "priority_fields": ["PERMIT_NUM", "PERMIT_NO", "PERMIT_TYPE", "STATUS", "ISSUE_DATE",
                           "FINAL_DATE", "CONTRACTOR", "WORK_DESC", "VALUATION", "PARCEL"],
        "table": "municipal_permits",
        "description": "Building permits, inspections, CO status",
    },
    "code_enforcement": {
        "folder_keywords": ["code", "enforcement", "compliance", "violation", "building"],
        "layer_keywords": ["code enforcement", "violation", "complaint", "condemned", "demolition",
                          "nuisance", "abatement", "lien", "unsafe", "boarded"],
        "exclude_keywords": ["zip code", "area code"],
        "priority_fields": ["CASE_NUM", "CASE_NO", "VIOLATION", "STATUS", "CASE_TYPE",
                           "OPEN_DATE", "CLOSE_DATE", "LIEN_AMOUNT", "PARCEL", "ADDRESS"],
        "table": "code_enforcement",
        "description": "Code violations, city liens, demolition orders",
    },
    "utilities": {
        "folder_keywords": ["utility", "utilities", "water", "sewer", "stormwater", "public_works"],
        "layer_keywords": ["water", "sewer", "utility", "stormwater", "reclaim", "assessment",
                          "connection", "availability", "delinquent", "shutoff", "service"],
        "exclude_keywords": ["manhole", "valve", "pipe", "main", "hydrant", "pump", "lift"],
        "priority_fields": ["WATER", "SEWER", "ASSESSMENT", "STATUS", "ACCOUNT", "DELINQUENT",
                           "PARCEL", "ADDRESS", "AMOUNT"],
        "table": "utility_data",
        "description": "Water/sewer availability, utility liens, special assessments",
    },
    "addresses": {
        "folder_keywords": ["common", "base", "address", "building"],
        "layer_keywords": ["address", "site address", "address point"],
        "exclude_keywords": ["mail address"],
        "priority_fields": ["PARCELID", "PARCEL_ID", "SITEADDR", "ADDRESS", "HOUSENO",
                           "STREET", "CITY", "ZIP", "UNIT"],
        "table": "address_points",
        "description": "Address points with parcel cross-reference",
    },
}

# Known municipal portals (discovered via web search/AGOL)
KNOWN_PORTALS = {
    "palm_bay": {
        "base_urls": [
            "https://gis.palmbayflorida.org/arcgis/rest/services",
        ],
        "portal_url": "https://gis.palmbayflorida.org/portal",
        "county": "brevard",
    },
    "west_melbourne": {
        "base_urls": [
            "https://cwm-gis.westmelbourne.org/server/rest/services",
        ],
        "portal_url": "https://cwm-gis.westmelbourne.org/portal",
        "county": "brevard",
    },
    "titusville": {
        "base_urls": [
            "https://www.titusville.com/arcgis/rest/services",
        ],
        "county": "brevard",
    },
    "satellite_beach": {
        "agol_owner": "sskinner@satellitebeach.gov",
        "agol_org": "6oVY31bK6DOd0VbR",
        "county": "brevard",
    },
    "cocoa_beach": {
        "agol_owner": "sryancb",
        "agol_org": "U4PMgBw5XA2nmleg",
        "county": "brevard",
    },
}

# URL patterns to probe for unknown municipalities
PORTAL_PATTERNS = [
    "https://gis.{city}.org/arcgis/rest/services",
    "https://gis.{city}.com/arcgis/rest/services",
    "https://gis.{city}.gov/arcgis/rest/services",
    "https://gis.cityof{city}.org/arcgis/rest/services",
    "https://gis.cityof{city}.com/arcgis/rest/services",
    "https://gis.{city}fl.gov/arcgis/rest/services",
    "https://gis.{city}florida.org/arcgis/rest/services",
    "https://www.{city}.org/arcgis/rest/services",
    "https://www.{city}.com/arcgis/rest/services",
    "https://www.{city}fl.gov/arcgis/rest/services",
    "https://{city}-gis.{city}.org/server/rest/services",
    "https://cwm-gis.{city}.org/server/rest/services",
    "https://gis.townof{city}.org/arcgis/rest/services",
    "https://maps.{city}.org/arcgis/rest/services",
    "https://maps.{city}fl.gov/arcgis/rest/services",
]

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

def sb_upsert(rows, table="zoning_assignments"):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    ok = err = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = c.post(f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=parcel_id",
                      headers=h, json=batch)
        if resp.status_code in (200, 201, 204): ok += len(batch)
        else: err += len(batch)
        time.sleep(0.3)
    return ok, err

def gis_query(url, params):
    """Paginated GIS query. Yields features."""
    offset = 0
    while True:
        p = {**params, "resultOffset": str(offset), "f": "json"}
        try:
            r = c.get(f"{url}/query", params=p, timeout=30)
            data = r.json()
        except:
            break
        feats = data.get("features", [])
        if not feats: break
        yield from feats
        offset += len(feats)
        if not data.get("exceededTransferLimit") and len(feats) < int(params.get("resultRecordCount", 1000)):
            break
        time.sleep(1)

def probe_layer(url):
    """Get layer metadata: name, fields, count, geometry type."""
    try:
        r = c.get(f"{url}?f=json", timeout=15)
        if r.status_code != 200: return None
        d = r.json()
        
        count_r = c.get(f"{url}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}, timeout=15)
        count = count_r.json().get("count", 0)
        
        return {
            "url": url,
            "name": d.get("name", "?"),
            "fields": [f["name"] for f in d.get("fields", [])],
            "field_details": {f["name"]: {"alias": f.get("alias",""), "type": f.get("type","")} 
                            for f in d.get("fields", [])},
            "geometry": d.get("geometryType", ""),
            "count": count,
            "max_record_count": d.get("maxRecordCount", 1000),
        }
    except:
        return None

def classify_layer(layer_info, squad_name):
    """Score how well a layer matches a squad's mission."""
    squad = SQUADS[squad_name]
    name = layer_info["name"].lower()
    fields = " ".join(layer_info["fields"]).upper()
    
    # Exclude check
    if any(kw in name for kw in squad["exclude_keywords"]):
        return 0
    
    score = 0
    # Name match
    if any(kw in name for kw in squad["layer_keywords"]):
        score += 50
    
    # Field match
    for pf in squad["priority_fields"]:
        if pf in fields:
            score += 10
    
    # Count bonus (more data = more useful)
    if layer_info["count"] > 1000: score += 5
    if layer_info["count"] > 10000: score += 10
    
    return score

# ═══════════════════════════════════════════════════════════════
# RECON SQUAD — Discover everything in a portal
# ═══════════════════════════════════════════════════════════════

def recon(municipality):
    """Full portal reconnaissance — discover every accessible layer."""
    city = municipality.lower().replace(" ", "_")
    city_clean = city.replace("_", "")
    telegram(f"🔍 RECON: {municipality.upper()}\n")
    
    config = KNOWN_PORTALS.get(city, {})
    base_urls = config.get("base_urls", [])
    
    # If unknown, probe URL patterns
    if not base_urls:
        telegram("  Probing URL patterns...")
        for pattern in PORTAL_PATTERNS:
            url = pattern.format(city=city_clean)
            try:
                r = c.get(f"{url}?f=json", timeout=5)
                if r.status_code == 200:
                    d = r.json()
                    if d.get("services") or d.get("folders"):
                        base_urls.append(url)
                        telegram(f"  🎯 FOUND: {url}")
                        break
            except: pass
    
    if not base_urls:
        # Try AGOL
        telegram("  Probing AGOL...")
        try:
            r = c.get("https://www.arcgis.com/sharing/rest/search", params={
                "q": f'"{municipality.replace("_"," ")}" florida', "f": "json", "num": 20
            })
            for item in r.json().get("results", []):
                if item.get("url") and "Feature" in item.get("type", ""):
                    telegram(f"  📡 AGOL: {item['title'][:50]} | {item.get('owner','')}")
        except: pass
    
    # Scan all services and folders
    portal_inventory = {"municipality": city, "services": [], "layers": [], "squads": {}}
    
    for base_url in base_urls:
        telegram(f"\n  Scanning: {base_url}")
        try:
            r = c.get(f"{base_url}?f=json", timeout=15)
            d = r.json()
            
            # Process root services + all folders
            all_services = []
            for svc in d.get("services", []):
                all_services.append(svc)
            for folder in d.get("folders", []):
                telegram(f"  📁 {folder}")
                try:
                    r2 = c.get(f"{base_url}/{folder}?f=json", timeout=10)
                    for svc in r2.json().get("services", []):
                        all_services.append(svc)
                except: pass
            
            # Probe each service for layers
            for svc in all_services:
                sname = svc.get("name", "")
                stype = svc.get("type", "")
                if stype not in ("MapServer", "FeatureServer"): continue
                
                svc_url = f"{base_url}/{sname}/{stype}"
                try:
                    r3 = c.get(f"{svc_url}?f=json", timeout=10)
                    d3 = r3.json()
                    
                    for layer in d3.get("layers", []):
                        lid = layer["id"]
                        layer_url = f"{svc_url}/{lid}"
                        info = probe_layer(layer_url)
                        if not info or info["count"] == 0: continue
                        
                        info["service"] = sname
                        info["service_type"] = stype
                        portal_inventory["layers"].append(info)
                        
                        # Classify by squad
                        for squad_name in SQUADS:
                            score = classify_layer(info, squad_name)
                            if score > 20:
                                portal_inventory["squads"].setdefault(squad_name, [])
                                portal_inventory["squads"][squad_name].append({
                                    "url": layer_url,
                                    "name": info["name"],
                                    "count": info["count"],
                                    "score": score,
                                    "fields": info["fields"],
                                })
                    
                    time.sleep(0.5)
                except: pass
        except Exception as e:
            telegram(f"  Error: {e}")
    
    # Report
    telegram(f"\n{'='*50}")
    telegram(f"📋 PORTAL INVENTORY: {municipality.upper()}")
    telegram(f"  Total layers: {len(portal_inventory['layers'])}")
    telegram(f"  Total features: {sum(l['count'] for l in portal_inventory['layers']):,}")
    
    for squad_name, layers in portal_inventory["squads"].items():
        squad = SQUADS[squad_name]
        layers.sort(key=lambda x: x["score"], reverse=True)
        telegram(f"\n  🎖️ {squad_name.upper()} SQUAD — {squad['description']}")
        for l in layers[:5]:
            telegram(f"    [{l['score']:3}] {l['name']} ({l['count']:,} features)")
    
    # Squads with no matches
    empty = [s for s in SQUADS if s not in portal_inventory["squads"]]
    if empty:
        telegram(f"\n  ❌ No data found for: {', '.join(empty)}")
    
    # Save config
    config_path = CONFIG_DIR / f"{city}.json"
    config_path.write_text(json.dumps(portal_inventory, indent=2, default=str))
    telegram(f"\n  Config saved: {config_path}")
    
    return portal_inventory

# ═══════════════════════════════════════════════════════════════
# CONQUER — Download and persist squad data
# ═══════════════════════════════════════════════════════════════

def conquer_squad(municipality, squad_name, inventory=None):
    """Download all data for a specific squad from a municipality."""
    city = municipality.lower().replace(" ", "_")
    
    if not inventory:
        config_path = CONFIG_DIR / f"{city}.json"
        if config_path.exists():
            inventory = json.loads(config_path.read_text())
        else:
            telegram(f"  No inventory for {city} — running recon first...")
            inventory = recon(municipality)
    
    squad_layers = inventory.get("squads", {}).get(squad_name, [])
    if not squad_layers:
        telegram(f"  ❌ No {squad_name} layers found for {municipality}")
        return 0
    
    squad = SQUADS[squad_name]
    telegram(f"\n  🎖️ CONQUERING {squad_name.upper()} — {len(squad_layers)} layers")
    
    total_downloaded = 0
    for layer in squad_layers[:3]:  # Top 3 by score
        url = layer["url"]
        telegram(f"    Downloading: {layer['name']} ({layer['count']:,} features)")
        
        # Determine output fields
        fields = layer.get("fields", [])
        out_fields = ",".join(fields[:15])  # Cap at 15 fields
        
        records = []
        for feat in gis_query(url, {"where": "1=1", "outFields": out_fields,
                                     "returnGeometry": "false", "resultRecordCount": "1000"}):
            records.append(feat.get("attributes", {}))
        
        telegram(f"    Downloaded: {len(records):,} records")
        total_downloaded += len(records)
        
        # TODO: Transform and persist to squad-specific Supabase table
        # For now, save to local JSON
        out_path = CONFIG_DIR / f"{city}_{squad_name}_{layer['name'].replace(' ','_')}.json"
        with open(out_path, "w") as f:
            json.dump(records[:100], f, indent=2, default=str)  # Sample for now
    
    return total_downloaded

def conquer(municipality, squad_filter=None):
    """Full conquest — all squads or specific one."""
    start = time.time()
    city = municipality.lower().replace(" ", "_")
    telegram(f"🏔️ CONQUER: {municipality.upper()}")
    
    # Load or create inventory
    config_path = CONFIG_DIR / f"{city}.json"
    if config_path.exists():
        inventory = json.loads(config_path.read_text())
    else:
        inventory = recon(municipality)
    
    squads_to_run = [squad_filter] if squad_filter else list(SQUADS.keys())
    
    for squad_name in squads_to_run:
        if squad_name in inventory.get("squads", {}):
            conquer_squad(municipality, squad_name, inventory)
    
    elapsed = int(time.time() - start)
    telegram(f"\n🏔️ CONQUEST COMPLETE: {municipality.upper()}")
    telegram(f"⏱️ Duration: {elapsed//60}m {elapsed%60}s")
    telegram(f"💰 Cost: $0")

# ═══════════════════════════════════════════════════════════════
# INVENTORY — Show all known portals for a county
# ═══════════════════════════════════════════════════════════════

def inventory_county(county):
    """List all known municipal portals for a county."""
    telegram(f"📋 MUNICIPAL PORTALS: {county.upper()}\n")
    
    for city, config in KNOWN_PORTALS.items():
        if config.get("county") == county:
            base = config.get("base_urls", ["AGOL"])[0] if config.get("base_urls") else "AGOL"
            telegram(f"  {city:25} {base[:60]}")
    
    # Check for saved configs
    for config_path in CONFIG_DIR.glob("*.json"):
        city = config_path.stem
        try:
            data = json.loads(config_path.read_text())
            layer_count = len(data.get("layers", []))
            squad_count = len(data.get("squads", {}))
            telegram(f"  {city:25} {layer_count} layers, {squad_count} squads (cached)")
        except: pass

# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Municipal Portal Intelligence Agent")
    parser.add_argument("command", choices=["recon", "conquer", "inventory"],
                       help="Action to perform")
    parser.add_argument("target", help="Municipality name or county name (for inventory)")
    parser.add_argument("--squad", choices=list(SQUADS.keys()), default=None,
                       help="Specific squad to deploy (default: all)")
    parser.add_argument("--all", action="store_true", help="Run all squads")
    args = parser.parse_args()
    
    if args.command == "recon":
        recon(args.target)
    elif args.command == "conquer":
        conquer(args.target, args.squad)
    elif args.command == "inventory":
        inventory_county(args.target)

if __name__ == "__main__":
    main()
