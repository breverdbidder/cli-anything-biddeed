#!/usr/bin/env python3
"""Extract Brevard parcels from FL DOR Cadastral FeatureServer → Supabase zw_parcels"""
import requests, json, time, os, sys

BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TG_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

FIELDS = ",".join([
    "OBJECTID","PARCEL_ID","PARCELNO","DOR_UC","PA_UC",
    "JV","AV_SD","TV_SD","LND_VAL","NCONST_VAL",
    "TOT_LVG_AR","LND_SQFOOT","NO_LND_UNT","LND_UNTS_C",
    "ACT_YR_BLT","EFF_YR_BLT","IMP_QUAL","CONST_CLAS",
    "NO_BULDNG","NO_RES_UNT",
    "OWN_NAME","OWN_ADDR1","OWN_ADDR2","OWN_CITY","OWN_STATE","OWN_ZIPCD",
    "PHY_ADDR1","PHY_ADDR2","PHY_CITY","PHY_ZIPCD",
    "S_LEGAL","TWN","RNG","SEC","NBRHD_CD","TAX_AUTH_C",
    "SALE_PRC1","SALE_YR1","SALE_MO1","OR_BOOK1","OR_PAGE1",
    "SALE_PRC2","SALE_YR2","SALE_MO2",
    "ALT_KEY","SPEC_FEAT_","DISTR_CD","CENSUS_BK",
    "JV_HMSTD","AV_HMSTD"
])
WHERE = "CO_NO=15"
BATCH = 2000

def tg(msg):
    if TG_BOT and TG_CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage",
                data={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        except: pass

def safe_int(v):
    try: return int(v) if v and v != 0 else None
    except: return None

def safe_str(v):
    if v is None: return None
    s = str(v).strip()
    return s if s else None

def map_to_zw(rec):
    """Map FL DOR Cadastral → zw_parcels (existing 77-col schema)"""
    pid = safe_str(rec.get("PARCEL_ID")) or safe_str(rec.get("PARCELNO"))
    if not pid: return None
    
    addr = safe_str(rec.get("PHY_ADDR1")) or ""
    city = safe_str(rec.get("PHY_CITY")) or ""
    zipcd = safe_str(rec.get("PHY_ZIPCD")) or ""
    
    # Build clean PIN (remove dashes/spaces)
    pin_clean = pid.replace("-","").replace(" ","").replace(".","")
    
    sale_yr = safe_int(rec.get("SALE_YR1"))
    sale_mo = safe_int(rec.get("SALE_MO1"))
    sale_date = None
    if sale_yr and sale_yr > 1900 and sale_mo and 1 <= sale_mo <= 12:
        sale_date = f"{sale_yr}-{sale_mo:02d}-01"
    
    return {
        "co_no": 15,
        "county": "BREVARD",
        "pin": pid,
        "pin_clean": pin_clean,
        "altkey": safe_str(rec.get("ALT_KEY")),
        "luse_code": str(rec.get("DOR_UC","")).zfill(3) if rec.get("DOR_UC") is not None else None,
        "site_addr": addr,
        "site_city": city,
        "site_zip": zipcd,
        "owner_name": safe_str(rec.get("OWN_NAME")),
        "owner_addr1": safe_str(rec.get("OWN_ADDR1")),
        "owner_addr2": safe_str(rec.get("OWN_ADDR2")),
        "owner_city": safe_str(rec.get("OWN_CITY")),
        "owner_state": safe_str(rec.get("OWN_STATE")),
        "owner_zip": safe_str(rec.get("OWN_ZIPCD")),
        "val_market": safe_int(rec.get("JV")),
        "val_assessed": safe_int(rec.get("AV_SD")),
        "val_taxable": safe_int(rec.get("TV_SD")),
        "val_land": safe_int(rec.get("LND_VAL")),
        "val_building": safe_int(rec.get("NCONST_VAL")),
        "sqft_heated": safe_int(rec.get("TOT_LVG_AR")),
        "year_built": safe_int(rec.get("ACT_YR_BLT")) if rec.get("ACT_YR_BLT") and rec["ACT_YR_BLT"] > 0 else None,
        "year_built_eff": safe_int(rec.get("EFF_YR_BLT")) if rec.get("EFF_YR_BLT") and rec["EFF_YR_BLT"] > 0 else None,
        "num_buildings": safe_int(rec.get("NO_BULDNG")),
        "sale_price": safe_int(rec.get("SALE_PRC1")) if rec.get("SALE_PRC1") and rec["SALE_PRC1"] > 0 else None,
        "sale_date": sale_date,
        "sale_book": safe_str(rec.get("OR_BOOK1")),
        "sale_page": safe_str(rec.get("OR_PAGE1")),
        "data_source": "FL_DOR_CADASTRAL_2025",
        "extracted_at": "2026-04-06",
    }

def upsert_batch(records):
    """Upsert to zw_parcels on (co_no, pin)"""
    if not SUPABASE_KEY:
        print("  WARN: No SUPABASE_SERVICE_KEY")
        return 0
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    ok = 0
    for i in range(0, len(records), 500):
        chunk = records[i:i+500]
        try:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/zw_parcels",
                headers=headers, json=chunk, timeout=60
            )
            if r.status_code in [200, 201]:
                ok += len(chunk)
            else:
                print(f"  Supabase {r.status_code}: {r.text[:200]}")
                # Try smaller chunks on error
                for rec in chunk:
                    try:
                        r2 = requests.post(
                            f"{SUPABASE_URL}/rest/v1/zw_parcels",
                            headers=headers, json=[rec], timeout=30
                        )
                        if r2.status_code in [200, 201]:
                            ok += 1
                    except: pass
        except Exception as e:
            print(f"  Upsert error: {e}")
    return ok

# ─── MAIN ───
print("=" * 60)
print("BREVARD PARCEL LOAD")
print("Source: FL DOR Statewide Cadastral 2025 FeatureServer")
print("Target: zw_parcels (Supabase)")
print("Expected: ~153,000 parcels")
print("=" * 60)

tg("🏗️ *Brevard Parcel Load* starting\nSource: FL DOR Cadastral (153K parcels)\nTarget: zw_parcels")

total_fetched = 0
total_upserted = 0
last_oid = 0
errors = 0
buffer = []
start_time = time.time()

while errors < 10:
    try:
        r = requests.get(BASE, params={
            "where": f"{WHERE} AND OBJECTID>{last_oid}",
            "outFields": FIELDS,
            "returnGeometry": "false",
            "resultRecordCount": BATCH,
            "orderByFields": "OBJECTID ASC",
            "f": "json"
        }, timeout=90)
        
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} at OID>{last_oid}")
            errors += 1; time.sleep(5); continue
        
        data = r.json()
        if "error" in data:
            print(f"  API error: {data['error'].get('message','?')}")
            errors += 1; time.sleep(5); continue
        
        features = data.get("features", [])
        if not features:
            print(f"  Done at OID>{last_oid}")
            break
        
        errors = 0
        mapped = [map_to_zw(f["attributes"]) for f in features]
        mapped = [m for m in mapped if m]
        buffer.extend(mapped)
        total_fetched += len(features)
        last_oid = features[-1]["attributes"]["OBJECTID"]
        
        # Upsert every 5K records
        if len(buffer) >= 5000:
            n = upsert_batch(buffer)
            total_upserted += n
            elapsed = time.time() - start_time
            rate = total_fetched / elapsed * 60
            print(f"  {total_fetched:>7,} fetched | {total_upserted:>7,} upserted | {rate:.0f}/min | OID={last_oid}")
            buffer = []
        
        time.sleep(0.3)
        
    except requests.exceptions.Timeout:
        print(f"  Timeout OID>{last_oid}"); errors += 1; time.sleep(10)
    except Exception as e:
        print(f"  Error: {e}"); errors += 1; time.sleep(5)

# Final flush
if buffer:
    n = upsert_batch(buffer)
    total_upserted += n

elapsed = time.time() - start_time
print(f"\n{'=' * 60}")
print(f"COMPLETE in {elapsed/60:.1f} minutes")
print(f"Fetched:  {total_fetched:,}")
print(f"Upserted: {total_upserted:,}")
print(f"{'=' * 60}")

tg(f"✅ *Brevard Parcel Load COMPLETE*\n{total_upserted:,} parcels → zw_parcels\nTime: {elapsed/60:.1f}min\nSource: FL DOR Cadastral 2025")
