import requests, json, time, sys

SB_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NDUzMjUyNiwiZXhwIjoyMDgwMTA4NTI2fQ.fL255mO0V8-rrU0Il3L41cIdQXUau-HRQXiamTqp9nE"
FEMA = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
sb_headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}

def query_fema_tile(west, south, east, north, offset=0):
    """Query FEMA for a small tile"""
    params = {
        "where": "1=1",
        "geometry": f"{west},{south},{east},{north}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "outSR": "4326",
        "outFields": "FLD_ZONE,ZONE_SUBTY,STATIC_BFE,DFIRM_ID",
        "returnGeometry": "true",
        "resultOffset": str(offset),
        "resultRecordCount": "2000",
        "f": "geojson"
    }
    r = requests.get(FEMA, params=params, timeout=120)
    return r.json() if r.text.strip() else {"features": []}

def load_county(name, west, south, east, north, tile_size=0.2):
    """Tile a county bbox and load all flood zones"""
    total = 0
    lat = south
    while lat < north:
        lon = west
        while lon < east:
            tile_w, tile_s = lon, lat
            tile_e, tile_n = min(lon + tile_size, east), min(lat + tile_size, north)
            
            offset = 0
            while True:
                try:
                    data = query_fema_tile(tile_w, tile_s, tile_e, tile_n, offset)
                    feats = data.get("features", [])
                    if not feats:
                        break
                    
                    rows = []
                    for f in feats:
                        p = f.get("properties", {})
                        g = f.get("geometry")
                        if g and g["type"] == "Polygon":
                            g = {"type": "MultiPolygon", "coordinates": [g["coordinates"]]}
                        rows.append({
                            "fld_zone": p.get("FLD_ZONE"),
                            "zone_subtype": p.get("ZONE_SUBTY"),
                            "bfe": p.get("STATIC_BFE"),
                            "dfirm_id": p.get("DFIRM_ID"),
                            "county": name.lower(),
                            "geom": json.dumps(g) if g else None
                        })
                    
                    resp = requests.post(f"{SB_URL}/rest/v1/flood_zones", headers=sb_headers, json=rows)
                    if resp.status_code in (200, 201):
                        total += len(rows)
                        sys.stdout.write(f"\r  {name}: {total} loaded (tile {tile_s:.1f},{tile_w:.1f})")
                        sys.stdout.flush()
                    else:
                        print(f"\n  ❌ Insert error: {resp.status_code} {resp.text[:100]}")
                    
                    if len(feats) < 2000:
                        break
                    offset += 2000
                    time.sleep(0.3)
                except Exception as e:
                    print(f"\n  ⚠️ Tile error: {e}")
                    break
            
            lon += tile_size
            time.sleep(0.2)
        lat += tile_size
    
    print(f"\n✅ {name}: {total} flood zones loaded")
    return total

# Load top 10 FL counties
counties = [
    ("BREVARD", -81.0, 27.8, -80.3, 28.6),
    ("ORANGE", -81.7, 28.3, -80.95, 28.8),
    ("DUVAL", -81.9, 30.1, -81.3, 30.6),
    ("HILLSBOROUGH", -82.8, 27.6, -82.05, 28.2),
    ("VOLUSIA", -81.7, 28.7, -80.8, 29.4),
]

grand_total = 0
target = sys.argv[1] if len(sys.argv) > 1 else "ALL"

for name, w, s, e, n in counties:
    if target != "ALL" and target != name:
        continue
    t = load_county(name, w, s, e, n)
    grand_total += t

print(f"\n🎉 Grand total: {grand_total} flood zones loaded")
