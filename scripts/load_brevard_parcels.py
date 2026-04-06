#!/usr/bin/env python3
"""Extract Brevard parcels from FL DOR Cadastral FeatureServer → Supabase zw_parcels"""
import requests, json, time, os, sys

# Config
BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TG_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

FIELDS = "OBJECTID,PARCEL_ID,PARCELNO,DOR_UC,JV,AV_SD,TV_SD,LND_VAL,NCONST_VAL,TOT_LVG_AR,LND_SQFOOT,ACT_YR_BLT,EFF_YR_BLT,IMP_QUAL,CONST_CLAS,NO_BULDNG,NO_RES_UNT,OWN_NAME,OWN_ADDR1,OWN_CITY,OWN_STATE,OWN_ZIPCD,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,S_LEGAL,TWN,RNG,SEC,NBRHD_CD,TAX_AUTH_C,SALE_PRC1,SALE_YR1,SALE_MO1,ALT_KEY,LND_UNTS_C,NO_LND_UNT,SPEC_FEAT_,DISTR_CD"
WHERE = "PARCELNO LIKE '05%'"
BATCH = 2000

def tg(msg):
    if TG_BOT and TG_CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage",
                data={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        except: pass

def map_to_zw_parcels(rec):
    """Map FL DOR Cadastral fields → zw_parcels schema"""
    parcel_id = rec.get("PARCEL_ID") or rec.get("PARCELNO", "")
    addr = rec.get("PHY_ADDR1", "") or ""
    city = rec.get("PHY_CITY", "") or ""
    zipcode = rec.get("PHY_ZIPCD", "") or ""
    
    return {
        "county": "Brevard",
        "parcel_id": parcel_id.strip() if parcel_id else None,
        "address": f"{addr}, {city}, FL {zipcode}".strip(", ") if addr else None,
        "owner_name": (rec.get("OWN_NAME") or "").strip() or None,
        "owner_address": (rec.get("OWN_ADDR1") or "").strip() or None,
        "owner_city": (rec.get("OWN_CITY") or "").strip() or None,
        "owner_state": (rec.get("OWN_STATE") or "").strip() or None,
        "owner_zip": (rec.get("OWN_ZIPCD") or "").strip() or None,
        "just_value": int(rec["JV"]) if rec.get("JV") else None,
        "assessed_value": int(rec["AV_SD"]) if rec.get("AV_SD") else None,
        "taxable_value": int(rec["TV_SD"]) if rec.get("TV_SD") else None,
        "land_value": int(rec["LND_VAL"]) if rec.get("LND_VAL") else None,
        "improvement_value": int(rec["NCONST_VAL"]) if rec.get("NCONST_VAL") else None,
        "total_living_area": int(rec["TOT_LVG_AR"]) if rec.get("TOT_LVG_AR") else None,
        "land_sqft": float(rec["LND_SQFOOT"]) if rec.get("LND_SQFOOT") else None,
        "year_built": int(rec["ACT_YR_BLT"]) if rec.get("ACT_YR_BLT") and rec["ACT_YR_BLT"] > 0 else None,
        "effective_year_built": int(rec["EFF_YR_BLT"]) if rec.get("EFF_YR_BLT") and rec["EFF_YR_BLT"] > 0 else None,
        "building_count": int(rec["NO_BULDNG"]) if rec.get("NO_BULDNG") else None,
        "unit_count": int(rec["NO_RES_UNT"]) if rec.get("NO_RES_UNT") else None,
        "dor_use_code": str(rec["DOR_UC"]).zfill(3) if rec.get("DOR_UC") is not None else None,
        "construction_class": (rec.get("CONST_CLAS") or "").strip() or None,
        "quality": (rec.get("IMP_QUAL") or "").strip() or None,
        "township": (rec.get("TWN") or "").strip() or None,
        "range_": (rec.get("RNG") or "").strip() or None,
        "section": (rec.get("SEC") or "").strip() or None,
        "neighborhood": (rec.get("NBRHD_CD") or "").strip() or None,
        "tax_district": (rec.get("TAX_AUTH_C") or "").strip() or None,
        "legal_desc": (rec.get("S_LEGAL") or "").strip()[:500] if rec.get("S_LEGAL") else None,
        "last_sale_price": int(rec["SALE_PRC1"]) if rec.get("SALE_PRC1") and rec["SALE_PRC1"] > 0 else None,
        "last_sale_year": int(rec["SALE_YR1"]) if rec.get("SALE_YR1") and rec["SALE_YR1"] > 0 else None,
        "last_sale_month": int(rec["SALE_MO1"]) if rec.get("SALE_MO1") and rec["SALE_MO1"] > 0 else None,
        "alt_key": (rec.get("ALT_KEY") or "").strip() or None,
        "source": "FL_DOR_CADASTRAL_2025",
        "data_year": 2025,
    }

def upsert_batch(records):
    """Upsert batch to Supabase zw_parcels"""
    if not SUPABASE_KEY:
        print("  No SUPABASE_SERVICE_KEY, skipping upsert")
        return False
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    # Upsert in chunks of 500
    for i in range(0, len(records), 500):
        chunk = records[i:i+500]
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/zw_parcels",
            headers=headers,
            json=chunk,
            timeout=60
        )
        if r.status_code not in [200, 201]:
            print(f"  Supabase error ({r.status_code}): {r.text[:200]}")
            return False
    return True

# ─── MAIN ───
print(f"=== Brevard Parcel Load ===")
print(f"Source: FL DOR Cadastral 2025 FeatureServer")
print(f"Target: zw_parcels (Supabase)")

tg("🏗️ *Brevard Parcel Load* starting\nSource: FL DOR Cadastral (153K parcels)\nTarget: zw_parcels")

all_records = []
last_oid = 0
errors = 0
total_upserted = 0

while errors < 5:
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
            errors += 1
            time.sleep(5)
            continue
        
        data = r.json()
        if "error" in data:
            print(f"  API error: {data['error'].get('message','?')}")
            errors += 1
            time.sleep(5)
            continue
        
        features = data.get("features", [])
        if not features:
            print(f"  No more features at OID>{last_oid}")
            break
        
        errors = 0  # Reset on success
        mapped = [map_to_zw_parcels(f["attributes"]) for f in features]
        mapped = [m for m in mapped if m["parcel_id"]]  # Skip null parcel_ids
        all_records.extend(mapped)
        last_oid = features[-1]["attributes"]["OBJECTID"]
        
        # Upsert every 10K records
        if len(all_records) >= 10000:
            print(f"  Upserting {len(all_records):,} records to Supabase...")
            if upsert_batch(all_records):
                total_upserted += len(all_records)
                print(f"  ✅ {total_upserted:,} total upserted")
            all_records = []
        
        if total_upserted % 20000 < BATCH:
            print(f"  Progress: {total_upserted + len(all_records):,} (OID={last_oid})")
        
        time.sleep(0.5)
        
    except requests.exceptions.Timeout:
        print(f"  Timeout at OID>{last_oid}")
        errors += 1
        time.sleep(10)
    except Exception as e:
        print(f"  Error: {e}")
        errors += 1
        time.sleep(5)

# Final upsert
if all_records:
    print(f"  Final upsert: {len(all_records):,} records...")
    if upsert_batch(all_records):
        total_upserted += len(all_records)

print(f"\n=== COMPLETE ===")
print(f"Total extracted & upserted: {total_upserted:,}")

tg(f"✅ *Brevard Parcel Load COMPLETE*\n{total_upserted:,} parcels loaded into zw_parcels\nSource: FL DOR Cadastral 2025")
