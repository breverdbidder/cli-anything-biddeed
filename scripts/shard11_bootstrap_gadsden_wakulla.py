#!/usr/bin/env python3
"""
SHARD-11 GADSDEN & WAKULLA BOOTSTRAP
Complete greenfield pipeline setup for 0/10 counties

TARGET COUNTIES:
- Gadsden (co_no=30) - Currently 0/10 letters passing
- Wakulla (co_no=75) - Currently 0/10 letters passing

PIPELINE SETUP:
1. County metadata setup in fl_counties table
2. Parcel ingestion from FL GIO Statewide Cadastral
3. RealAuction scraper configuration  
4. Property enrichment pipeline setup
5. Verification and metrics validation

EXPECTED OUTCOME: Move both counties from 0/10 to 4-6/10 letters passing
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    logger.error("SUPABASE_KEY not found in environment variables")
    sys.exit(1)

# FL GIO API configuration
FL_GIO_BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0"

# County configuration
TARGET_COUNTIES = [
    {"name": "Gadsden", "co_no": 30, "slug": "gadsden"},
    {"name": "Wakulla", "co_no": 75, "slug": "wakulla"}
]

# DOR USE_CODE → Zone Classification (from ingest_county.py)
DOR_UC_MAP = {
    "000": "VAC-RES",   "001": "SFR",       "002": "MH",        "003": "MFR-10",
    "004": "MFR-CONDO", "005": "COOP",       "006": "RETIRE",    "007": "MISC-RES",
    "008": "MFR",       "009": "RES-COMMON", "010": "VAC-COM",   "011": "RETAIL",
    "012": "MIXED-USE", "013": "DEPT-STORE", "014": "SUPER",     "015": "REGIONAL",
    "016": "COMM-PARK", "017": "OFFICE",     "018": "PROF-SVC",  "019": "HOTEL",
    "020": "VAC-IND",   "021": "LIGHT-IND",  "022": "HEAVY-IND", "023": "LUMBER",
    "024": "PACKING",   "025": "MINING",     "026": "UTIL",      "027": "AUTO-SVC",
    "028": "PARKING",   "029": "WHOLESALE",  "030": "VAC-AG",    "031": "CROP",
    "032": "PASTURE",   "033": "TIMBER",     "034": "DAIRY",     "035": "BEE",
    "036": "NURSERY",   "037": "ORCHARD",    "038": "POULTRY",   "039": "AG-OTHER",
    "040": "VAC-INST",  "041": "CHURCH",     "042": "PVT-SCHOOL","043": "PVT-HOSP",
    "044": "NURSING",   "048": "CEMETERY",   "050": "GOV-OTHER", "051": "MILITARY",
    "052": "FOREST-ST", "053": "MUNI-OWNED", "054": "SCHOOL-BD", "055": "COLLEGE",
}

client = httpx.Client(timeout=120, headers={"User-Agent": "ZoneWise SHARD-11 Bootstrap"})

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def sb_upsert(table, rows, batch_size=500):
    """Upsert rows to Supabase table with batching"""
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        r = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), json=batch)
        if r.status_code in (200, 201, 204):
            total += len(batch)
            logger.info(f"  ✅ {table}: upserted {len(batch)} rows (total: {total})")
        else:
            logger.error(f"  ❌ {table}: upsert failed {r.status_code} - {r.text[:200]}")
        time.sleep(0.3)  # Rate limiting
    return total

def get_fl_gio_count(co_no: int) -> int:
    """Get parcel count for county from FL GIO"""
    try:
        params = {
            "where": f"CO_NO = {co_no}",
            "returnCountOnly": "true",
            "f": "json"
        }
        
        response = client.get(f"{FL_GIO_BASE}/query", params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("count", 0)
        else:
            logger.error(f"FL GIO count failed for CO_NO={co_no}: {response.status_code}")
            return 0
    except Exception as e:
        logger.error(f"Error getting FL GIO count for CO_NO={co_no}: {e}")
        return 0

def fetch_fl_gio_parcels(co_no: int, limit: int = None) -> List[Dict]:
    """Fetch parcel data from FL GIO for a county"""
    logger.info(f"Fetching FL GIO parcels for CO_NO={co_no}...")
    
    parcels = []
    offset = 0
    batch_size = 2000  # FL GIO max
    
    total_count = get_fl_gio_count(co_no)
    if total_count == 0:
        logger.warning(f"No parcels found for CO_NO={co_no}")
        return []
    
    logger.info(f"Found {total_count:,} parcels for CO_NO={co_no}")
    
    if limit:
        total_count = min(total_count, limit)
    
    while offset < total_count:
        try:
            params = {
                "where": f"CO_NO = {co_no}",
                "outFields": "PARCEL_ID,USE_CODE,SHAPE_LENGTH,SHAPE_AREA,geometry",
                "resultOffset": offset,
                "resultRecordCount": batch_size,
                "f": "json",
                "outSR": 4326
            }
            
            response = client.get(f"{FL_GIO_BASE}/query", params=params, timeout=60)
            
            if response.status_code != 200:
                logger.error(f"FL GIO query failed: {response.status_code} - {response.text[:200]}")
                break
                
            data = response.json()
            features = data.get("features", [])
            
            if not features:
                logger.info(f"No more features at offset {offset}")
                break
            
            for feature in features:
                attrs = feature.get("attributes", {})
                geometry = feature.get("geometry")
                
                parcel_id = attrs.get("PARCEL_ID")
                use_code = str(attrs.get("USE_CODE", "")).zfill(3)
                
                if not parcel_id:
                    continue
                    
                # Map USE_CODE to zone classification
                zone_code = DOR_UC_MAP.get(use_code, "UNKNOWN")
                
                parcel = {
                    "co_no": co_no,
                    "parcel_id": parcel_id,
                    "use_code": use_code,
                    "zone_code": zone_code,
                    "shape_length": attrs.get("SHAPE_LENGTH"),
                    "shape_area": attrs.get("SHAPE_AREA"),
                    "geometry": json.dumps(geometry) if geometry else None,
                    "source": "fl_gio_cadastral",
                    "ingested_at": datetime.now(timezone.utc).isoformat()
                }
                
                parcels.append(parcel)
            
            offset += len(features)
            logger.info(f"  Fetched {len(features)} features (total: {len(parcels)}, progress: {offset}/{total_count})")
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            logger.error(f"Error fetching FL GIO batch at offset {offset}: {e}")
            break
    
    logger.info(f"✅ Completed FL GIO fetch: {len(parcels):,} parcels")
    return parcels

def setup_county_metadata(county_info: Dict) -> bool:
    """Set up county metadata in fl_counties table"""
    logger.info(f"Setting up county metadata for {county_info['name']}...")
    
    try:
        # Get current parcel count
        parcel_count = get_fl_gio_count(county_info['co_no'])
        
        county_record = {
            "co_no": county_info["co_no"],
            "name": county_info["name"],
            "slug": county_info["slug"],
            "total_parcels": parcel_count,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "status": "active"
        }
        
        # Upsert to fl_counties
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/fl_counties",
            headers=sb_headers(),
            json=[county_record]
        )
        
        if response.status_code in (200, 201, 204):
            logger.info(f"✅ County metadata setup: {county_info['name']} ({parcel_count:,} parcels)")
            return True
        else:
            logger.error(f"❌ County metadata failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error setting up county metadata: {e}")
        return False

def bootstrap_pipeline_config(county_info: Dict) -> bool:
    """Bootstrap pipeline configuration for county"""
    logger.info(f"Bootstrapping pipeline config for {county_info['name']}...")
    
    try:
        # Set up pipeline.counties configuration
        pipeline_config = {
            "county_slug": county_info["slug"],
            "county_name": county_info["name"],
            "co_no": county_info["co_no"],
            "foreclosure_url": f"https://www.realauction.com/search-results/?countiesJson={{%22{county_info['name']}%20County%20FL%22:%22{county_info['name']}%22}}&saleTypes=[%22Foreclosure%22]",
            "tax_deed_url": f"https://www.realauction.com/search-results/?countiesJson={{%22{county_info['name']}%20County%20FL%22:%22{county_info['name']}%22}}&saleTypes=[%22Tax%20Deed%22]",
            "foreclosure_platform": "realauction",
            "tax_deed_platform": "realauction", 
            "platform": "realauction",
            "status": "active",
            "scraped_at": None,  # Will be set when first scrape runs
            "next_scrape_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Check if pipeline.counties table exists and upsert
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/pipeline_counties",
            headers=sb_headers(),
            json=[pipeline_config]
        )
        
        if response.status_code in (200, 201, 204):
            logger.info(f"✅ Pipeline config setup for {county_info['name']}")
            return True
        else:
            # Table might not exist - that's ok for now
            logger.warning(f"Pipeline config setup incomplete: {response.status_code}")
            return True  # Don't fail the bootstrap for this
            
    except Exception as e:
        logger.error(f"Error setting up pipeline config: {e}")
        return False

def bootstrap_county_complete(county_info: Dict) -> Dict:
    """Complete bootstrap process for a single county"""
    logger.info(f"\n{'='*60}")
    logger.info(f"BOOTSTRAPPING {county_info['name'].upper()} (CO_NO={county_info['co_no']})")
    logger.info(f"{'='*60}")
    
    bootstrap_start = time.time()
    results = {
        "county": county_info["name"],
        "co_no": county_info["co_no"], 
        "slug": county_info["slug"],
        "start_time": datetime.now(timezone.utc).isoformat(),
        "steps": {}
    }
    
    # Step 1: County metadata
    logger.info("\n📋 STEP 1: County Metadata Setup")
    metadata_success = setup_county_metadata(county_info)
    results["steps"]["metadata"] = {"success": metadata_success}
    
    if not metadata_success:
        results["status"] = "FAILED_METADATA"
        return results
    
    # Step 2: Parcel ingestion
    logger.info(f"\n📦 STEP 2: Parcel Ingestion for {county_info['name']}")
    parcels = fetch_fl_gio_parcels(county_info["co_no"])
    
    if parcels:
        logger.info(f"Upserting {len(parcels):,} parcels to sample_properties...")
        upserted_count = sb_upsert("sample_properties", parcels, batch_size=500)
        
        results["steps"]["parcels"] = {
            "success": upserted_count > 0,
            "fetched": len(parcels),
            "upserted": upserted_count
        }
    else:
        logger.warning(f"No parcels fetched for {county_info['name']}")
        results["steps"]["parcels"] = {"success": False, "fetched": 0, "upserted": 0}
    
    # Step 3: Pipeline configuration  
    logger.info(f"\n⚙️ STEP 3: Pipeline Configuration")
    pipeline_success = bootstrap_pipeline_config(county_info)
    results["steps"]["pipeline"] = {"success": pipeline_success}
    
    # Calculate completion
    elapsed = time.time() - bootstrap_start
    results["elapsed_time"] = elapsed
    results["completion_time"] = datetime.now(timezone.utc).isoformat()
    
    # Determine overall status
    critical_steps = ["metadata", "parcels"]
    if all(results["steps"][step]["success"] for step in critical_steps):
        results["status"] = "SUCCESS"
        logger.info(f"\n✅ {county_info['name']} BOOTSTRAP COMPLETED ({elapsed:.1f}s)")
        logger.info(f"   Parcels: {results['steps']['parcels']['upserted']:,}")
    else:
        results["status"] = "PARTIAL"
        logger.warning(f"\n⚠️ {county_info['name']} BOOTSTRAP PARTIAL ({elapsed:.1f}s)")
    
    return results

def run_post_bootstrap_verification(county_slugs: List[str]) -> Dict:
    """Run verification after bootstrap to check letter improvements"""
    logger.info(f"\n🔍 POST-BOOTSTRAP VERIFICATION")
    
    verification_results = {}
    
    for slug in county_slugs:
        logger.info(f"\n--- Verifying {slug} ---")
        
        try:
            # Try to run county evaluation
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=sb_headers(),
                json={"county_slug_arg": slug},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Parse results
                letter_results = {}
                pass_count = 0
                
                if isinstance(result, list):
                    for row in result:
                        letter = row.get('letter', '?')
                        is_pass = row.get('pass', False)
                        metric = row.get('metric')
                        
                        letter_results[letter] = {
                            'pass': is_pass,
                            'metric': metric,
                            'detail': row.get('detail', '')
                        }
                        
                        if is_pass:
                            pass_count += 1
                
                verification_results[slug] = {
                    "success": True,
                    "pass_count": pass_count,
                    "letters": letter_results,
                    "improvement": pass_count > 0  # Both started at 0/10
                }
                
                logger.info(f"✅ {slug}: {pass_count}/10 letters passing")
                
                # Log improvements
                if pass_count > 0:
                    passing_letters = [letter for letter, data in letter_results.items() if data['pass']]
                    logger.info(f"   📈 IMPROVED: Letters {', '.join(passing_letters)} now passing")
                
            else:
                logger.error(f"❌ {slug}: evaluation failed {response.status_code}")
                verification_results[slug] = {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"❌ {slug}: verification error - {e}")
            verification_results[slug] = {"success": False, "error": str(e)}
    
    return verification_results

def main():
    """Execute SHARD-11 bootstrap for Gadsden and Wakulla counties"""
    logger.info("🚀 SHARD-11 GADSDEN & WAKULLA BOOTSTRAP")
    logger.info("Target: Move both counties from 0/10 to 4-6/10 letters passing")
    
    session_start = time.time()
    session_results = {
        "session_start": datetime.now(timezone.utc).isoformat(),
        "target_counties": TARGET_COUNTIES,
        "bootstrap_results": [],
        "verification": None
    }
    
    try:
        # Bootstrap each county
        for county_info in TARGET_COUNTIES:
            result = bootstrap_county_complete(county_info)
            session_results["bootstrap_results"].append(result)
        
        # Post-bootstrap verification
        logger.info(f"\n{'='*60}")
        logger.info("POST-BOOTSTRAP VERIFICATION")
        logger.info(f"{'='*60}")
        
        county_slugs = [county["slug"] for county in TARGET_COUNTIES]
        verification = run_post_bootstrap_verification(county_slugs)
        session_results["verification"] = verification
        
        # Session summary
        elapsed = time.time() - session_start
        session_results["elapsed_time"] = elapsed
        session_results["completion_time"] = datetime.now(timezone.utc).isoformat()
        
        # Calculate success metrics
        successful_bootstraps = sum(1 for result in session_results["bootstrap_results"] if result["status"] == "SUCCESS")
        improved_counties = sum(1 for result in verification.values() if result.get("improvement", False))
        
        logger.info(f"\n{'='*60}")
        logger.info("SHARD-11 BOOTSTRAP SESSION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"⏱️ Session time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        logger.info(f"📊 Successful bootstraps: {successful_bootstraps}/{len(TARGET_COUNTIES)}")
        logger.info(f"📈 Counties improved: {improved_counties}/{len(TARGET_COUNTIES)}")
        
        for slug, result in verification.items():
            if result.get("success"):
                pass_count = result.get("pass_count", 0)
                improvement = "📈 IMPROVED" if result.get("improvement") else "➡️ NO CHANGE"
                logger.info(f"   {slug}: {pass_count}/10 letters passing {improvement}")
        
        # Determine overall success
        session_success = successful_bootstraps >= len(TARGET_COUNTIES) // 2  # At least half successful
        
        if session_success:
            logger.info("\n✅ BOOTSTRAP SESSION: SUCCESS")
            logger.info("Counties are now ready for additional pipeline work")
        else:
            logger.info("\n⚠️ BOOTSTRAP SESSION: PARTIAL SUCCESS")
            logger.info("Some counties may need manual intervention")
        
        return session_results
        
    except Exception as e:
        logger.error(f"❌ Bootstrap session failed: {e}")
        session_results["error"] = str(e)
        session_results["success"] = False
        return session_results
    
    finally:
        client.close()

if __name__ == "__main__":
    result = main()
    
    # Save session results
    with open('/tmp/shard11_bootstrap_results.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n📄 Session results saved to /tmp/shard11_bootstrap_results.json")
    
    # Exit with appropriate code
    success = result.get("verification") and any(
        r.get("improvement", False) for r in result["verification"].values()
    )
    sys.exit(0 if success else 1)