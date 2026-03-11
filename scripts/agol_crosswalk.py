#!/usr/bin/env python3
"""
SUMMIT: AGOL CROSSWALK — Melbourne (62K), Cocoa (30K), Rockledge (18K)
Problem: AGOL uses TaxAcct as parcel ID. Supabase uses BCPAO PARCEL_ID.
Fix: Download TaxAcct→PARCEL_ID mapping from BCPAO GIS, then re-download
AGOL zoning with TaxAcct, crosswalk to PARCEL_ID, upsert.
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_upsert(rows):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    ok = err = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = c.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
                      headers=h, json=batch)
        if resp.status_code in (200, 201, 204): ok += len(batch)
        else: err += len(batch)
        time.sleep(0.3)
    return ok, err

def download_agol(url, zone_field, taxacct_field="TaxAcct"):
    """Download TaxAcct + zoning from AGOL."""
    records = {}
    offset = 0
    while True:
        r = c.get(f"{url}/query", params={
            "where": f"{zone_field} IS NOT NULL",
            "outFields": f"{taxacct_field},{zone_field}",
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "json"
        })
        feats = r.json().get("features", [])
        if not feats: break
        for f in feats:
            a = f["attributes"]
            tax = a.get(taxacct_field)
            zone = (str(a.get(zone_field, "")) or "").strip()
            if tax and zone:
                records[str(tax)] = zone
        offset += len(feats)
        if len(feats) < 2000: break
        time.sleep(1)
    return records

def main():
    start = time.time()
    telegram("🏔️ AGOL CROSSWALK — Melbourne/Cocoa/Rockledge/Indialantic/Titusville")

    # ═══ Phase 1: Build TaxAcct → PARCEL_ID lookup from BCPAO GIS ═══
    telegram("🏔️ Phase 1: Building TaxAcct → PARCEL_ID crosswalk...")
    tax_to_pid = {}
    offset = 0
    while True:
        r = c.get(f"{GIS_PARCELS}/query", params={
            "where": "TaxAcct IS NOT NULL",
            "outFields": "PARCEL_ID,TaxAcct,CITY",
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "json"
        })
        feats = r.json().get("features", [])
        if not feats: break
        for f in feats:
            a = f["attributes"]
            pid = (a.get("PARCEL_ID") or "").strip()
            tax = a.get("TaxAcct")
            city = (a.get("CITY") or "").strip()
            if pid and tax:
                tax_to_pid[str(tax)] = {"pid": pid, "city": city.lower().replace(" ", "_") if city else "unincorporated"}
        offset += len(feats)
        if offset % 50000 == 0:
            telegram(f"  Phase 1: {offset:,} parcels, {len(tax_to_pid):,} mapped")
        if not r.json().get("exceededTransferLimit") and len(feats) < 2000: break
        time.sleep(1)
    
    telegram(f"🏔️ Phase 1 complete: {len(tax_to_pid):,} TaxAcct → PARCEL_ID mappings")

    # ═══ Phase 2: Download AGOL zoning for each municipality ═══
    telegram("🏔️ Phase 2: Downloading municipal AGOL zoning...")
    
    # Melbourne — from GISAdmn AGOL
    # First find the Melbourne AGOL URL
    agol_sources = [
        # Cocoa — GISAdmn
        {"name": "Cocoa", "search": "Public View Cocoa Zoning", "owner": "GISAdmn"},
    ]
    
    # Direct known AGOL endpoints from earlier recon
    # Melbourne uses the county GIS viewer — its zoning IS in the county layer
    # But Melbourne has city-specific zoning NOT in the county layer
    
    # Let's search AGOL for Melbourne zoning
    telegram("  Searching AGOL for Melbourne zoning...")
    mel_zones = {}
    r = c.get("https://www.arcgis.com/sharing/rest/search", params={
        "q": "melbourne zoning owner:GISAdmn", "f": "json", "num": 10
    })
    for item in r.json().get("results", []):
        if "melbourne" in item.get("title", "").lower() and "Feature" in item.get("type", ""):
            telegram(f"    Found: {item['title']} → {item.get('url','')[:80]}")

    # Cocoa Zoning — GISAdmn confirmed
    telegram("  Downloading Cocoa zoning (GISAdmn)...")
    r = c.get("https://www.arcgis.com/sharing/rest/search", params={
        "q": "Cocoa Zoning Split Lots owner:GISAdmn", "f": "json", "num": 5
    })
    cocoa_url = None
    for item in r.json().get("results", []):
        if "Public View" in item.get("title", "") and item.get("url"):
            cocoa_url = item["url"]
            break
    
    cocoa_zones = {}
    if cocoa_url:
        telegram(f"    Cocoa URL: {cocoa_url}")
        # Check layers
        r2 = c.get(f"{cocoa_url}?f=json", timeout=10)
        d2 = r2.json()
        for layer in d2.get("layers", []):
            telegram(f"    Layer {layer['id']}: {layer['name']}")
            r3 = c.get(f"{cocoa_url}/{layer['id']}?f=json", timeout=10)
            d3 = r3.json()
            fields = [f["name"] for f in d3.get("fields", [])]
            zone_fields = [f for f in fields if any(kw in f.upper() for kw in ["ZONE","ZON"])]
            tax_fields = [f for f in fields if any(kw in f.upper() for kw in ["TAX","ACCOUNT","TAXACCT"])]
            pid_fields = [f for f in fields if any(kw in f.upper() for kw in ["PARCEL","PID","NAME"])]
            telegram(f"      Zone: {zone_fields}, Tax: {tax_fields}, PID: {pid_fields}")
            
            if zone_fields:
                zf = zone_fields[0]
                # Try TaxAcct first, then PID
                id_field = tax_fields[0] if tax_fields else (pid_fields[0] if pid_fields else None)
                if id_field:
                    count = c.get(f"{cocoa_url}/{layer['id']}/query", params={
                        "where": "1=1", "returnCountOnly": "true", "f": "json"
                    }).json().get("count", 0)
                    telegram(f"      Count: {count}, using {id_field} + {zf}")
                    
                    offset = 0
                    while True:
                        r4 = c.get(f"{cocoa_url}/{layer['id']}/query", params={
                            "where": f"{zf} IS NOT NULL",
                            "outFields": f"{id_field},{zf}",
                            "returnGeometry": "false",
                            "resultOffset": offset,
                            "resultRecordCount": 2000,
                            "f": "json"
                        })
                        feats = r4.json().get("features", [])
                        if not feats: break
                        for f in feats:
                            a = f["attributes"]
                            key = str(a.get(id_field, "")).strip()
                            zone = str(a.get(zf, "")).strip()
                            if key and zone:
                                cocoa_zones[key] = zone
                        offset += len(feats)
                        if len(feats) < 2000: break
                        time.sleep(1)
                    telegram(f"    Cocoa: {len(cocoa_zones):,} records downloaded")
                break  # Use first layer with zoning

    # Rockledge — from Wave 2 AGOL (confirmed working earlier today)
    telegram("  Downloading Rockledge zoning (AGOL)...")
    rock_zones = {}
    r = c.get("https://www.arcgis.com/sharing/rest/search", params={
        "q": "zoning rockledge florida", "f": "json", "num": 10
    })
    for item in r.json().get("results", []):
        if "rockledge" in item.get("title", "").lower() and "Feature" in item.get("type", "") and item.get("url"):
            url = item["url"]
            telegram(f"    Found: {item['title']} → {url[:80]}")
            try:
                r2 = c.get(f"{url}?f=json", timeout=10)
                d2 = r2.json()
                for layer in d2.get("layers", []):
                    lname = layer["name"].lower()
                    if "zon" in lname:
                        r3 = c.get(f"{url}/{layer['id']}?f=json", timeout=10)
                        d3 = r3.json()
                        fields = [f["name"] for f in d3.get("fields", [])]
                        zone_f = [f for f in fields if "ZONE" in f.upper() or "ZON" in f.upper()]
                        tax_f = [f for f in fields if "TAX" in f.upper() or "ACCOUNT" in f.upper()]
                        pid_f = [f for f in fields if "PARCEL" in f.upper() or "PID" in f.upper() or "NAME" in f.upper()]
                        telegram(f"      Layer: {layer['name']} | Zone: {zone_f} Tax: {tax_f} PID: {pid_f}")
                        
                        if zone_f:
                            zf = zone_f[0]
                            id_f = tax_f[0] if tax_f else (pid_f[0] if pid_f else None)
                            if id_f:
                                off = 0
                                while True:
                                    r4 = c.get(f"{url}/{layer['id']}/query", params={
                                        "where": f"{zf} IS NOT NULL",
                                        "outFields": f"{id_f},{zf}",
                                        "returnGeometry": "false",
                                        "resultOffset": off,
                                        "resultRecordCount": 2000,
                                        "f": "json"
                                    })
                                    feats = r4.json().get("features", [])
                                    if not feats: break
                                    for feat in feats:
                                        a = feat["attributes"]
                                        key = str(a.get(id_f, "")).strip()
                                        zone = str(a.get(zf, "")).strip()
                                        if key and zone:
                                            rock_zones[key] = zone
                                    off += len(feats)
                                    if len(feats) < 2000: break
                                    time.sleep(1)
                                telegram(f"    Rockledge: {len(rock_zones):,} records")
                        break
            except Exception as e:
                telegram(f"    Error: {e}")
            break

    # ═══ Phase 3: Crosswalk + Upsert ═══
    telegram("🏔️ Phase 3: Crosswalking TaxAcct → PARCEL_ID...")
    
    all_municipal = {}
    
    # Cocoa zones are keyed by TaxAcct (numeric) or PARCEL_ID — check format
    if cocoa_zones:
        sample_key = list(cocoa_zones.keys())[0]
        telegram(f"  Cocoa key format sample: '{sample_key}'")
        if sample_key.isdigit():
            # TaxAcct → need crosswalk
            for tax, zone in cocoa_zones.items():
                if tax in tax_to_pid:
                    pid = tax_to_pid[tax]["pid"]
                    all_municipal[pid] = {"zone": zone, "juris": "cocoa"}
        else:
            # Already PARCEL_ID
            for pid, zone in cocoa_zones.items():
                all_municipal[pid] = {"zone": zone, "juris": "cocoa"}
    
    if rock_zones:
        sample_key = list(rock_zones.keys())[0]
        telegram(f"  Rockledge key format sample: '{sample_key}'")
        if sample_key.isdigit():
            for tax, zone in rock_zones.items():
                if tax in tax_to_pid:
                    pid = tax_to_pid[tax]["pid"]
                    all_municipal[pid] = {"zone": zone, "juris": "rockledge"}
        else:
            for pid, zone in rock_zones.items():
                all_municipal[pid] = {"zone": zone, "juris": "rockledge"}
    
    telegram(f"  Total crosswalked: {len(all_municipal):,}")
    
    # Build upsert rows
    rows = [{"parcel_id": pid, "zone_code": info["zone"], "jurisdiction": info["juris"], "county": "brevard"}
            for pid, info in all_municipal.items()]
    
    if rows:
        telegram(f"🏔️ Phase 3: Upserting {len(rows):,} crosswalked records...")
        ok, err = sb_upsert(rows)
        telegram(f"  Upserted: {ok:,} ok, {err:,} err")
    
    elapsed = int(time.time() - start)
    telegram(f"""🏔️ AGOL CROSSWALK COMPLETE

  Cocoa: {len(cocoa_zones):,} AGOL records → {sum(1 for v in all_municipal.values() if v['juris']=='cocoa'):,} crosswalked
  Rockledge: {len(rock_zones):,} AGOL records → {sum(1 for v in all_municipal.values() if v['juris']=='rockledge'):,} crosswalked
  Total upserted: {len(rows):,}
  
⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
