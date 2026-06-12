#!/usr/bin/env python3
"""
SHARD-19 G HIT LIST - Zone Standards Backfill
Per BREVARD SPRINT ORDER priority #3

DIAGNOSIS: Brevard G=48.9% (FAR binding constraint at 48.9%)
CONCRETE TARGETS per brief:
- Density gap: R-1AAA Melbourne 53,435; R-1AAA Titusville 22,252; R-1A Rockledge 17,085; 
  R-1B Titusville 9,855; R-1AAA West Melbourne 9,024
- FAR gap (binding): RU-2-15 Melbourne 5,601; R-3 Titusville 2,530; C-1 Melbourne 1,890

VALUES: Must come from ordinance text (zoning_gold_standard_vault or live municode) 
NO GUESSING - honesty markers required per brief

Usage:
  python scripts/shard19_g_hitlist.py
"""
import os
import requests
import json
import logging
from datetime import datetime
import re

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# G HIT LIST - Concrete targets from brief
DENSITY_TARGETS = [
    {'district': 'R-1AAA', 'jurisdiction': 'Melbourne', 'parcel_count': 53435},
    {'district': 'R-1AAA', 'jurisdiction': 'Titusville', 'parcel_count': 22252},
    {'district': 'R-1A', 'jurisdiction': 'Rockledge', 'parcel_count': 17085},
    {'district': 'R-1B', 'jurisdiction': 'Titusville', 'parcel_count': 9855},
    {'district': 'R-1AAA', 'jurisdiction': 'West Melbourne', 'parcel_count': 9024}
]

FAR_TARGETS = [
    {'district': 'RU-2-15', 'jurisdiction': 'Melbourne', 'parcel_count': 5601},
    {'district': 'R-3', 'jurisdiction': 'Titusville', 'parcel_count': 2530},
    {'district': 'C-1', 'jurisdiction': 'Melbourne', 'parcel_count': 1890}
]

def test_db_connection():
    """Test database connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Database connection successful")
            return True
        else:
            logger.error(f"❌ Connection failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def get_current_zone_standards():
    """Get current zone_standards to identify gaps"""
    try:
        response = requests.get(
            f"{BASE}/zone_standards",
            headers=HEADERS,
            params={
                "select": "district_code,jurisdiction,max_density_du_acre,max_far,parking_per_1000sf"
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get zone_standards: {response.status_code}")
            return None
        
        standards = response.json()
        
        # Index by district+jurisdiction
        standards_index = {}
        for standard in standards:
            key = f"{standard['district_code']}:{standard['jurisdiction']}"
            standards_index[key] = standard
        
        logger.info(f"📊 Current zone_standards: {len(standards)} records")
        return standards_index
        
    except Exception as e:
        logger.error(f"Error getting zone_standards: {e}")
        return None

def check_zoning_gold_standard_vault():
    """Check if we have ordinance text in zoning_gold_standard_vault"""
    try:
        response = requests.get(
            f"{BASE}/zoning_gold_standard_vault",
            headers=HEADERS,
            params={
                "county": "eq.brevard",
                "select": "jurisdiction,district_code,ordinance_text,source_url"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            vault_data = response.json()
            logger.info(f"📚 Zoning vault: {len(vault_data)} records for Brevard")
            return vault_data
        else:
            logger.warning(f"Zoning vault not accessible: {response.status_code}")
            return []
        
    except Exception as e:
        logger.warning(f"Zoning vault check failed: {e}")
        return []

def extract_density_from_ordinance(ordinance_text, district_code):
    """Extract density values from ordinance text with honesty markers"""
    if not ordinance_text:
        return None, "NO_ORDINANCE_TEXT"
    
    try:
        # Common density patterns in FL ordinances
        density_patterns = [
            r'maximum density.*?(\d+\.?\d*)\s*(?:units?|dwelling|du)?\s*per\s*acre',
            r'density.*?(?:shall not exceed|maximum of|up to)\s*(\d+\.?\d*)\s*(?:units?|dwelling|du)?\s*per\s*acre',
            r'(\d+\.?\d*)\s*(?:units?|dwelling|du)\s*per\s*acre\s*(?:maximum|max)',
            r'R-1AAA.*?(\d+\.?\d*)\s*(?:units?|dwelling|du)?\s*(?:per\s*acre|/acre)',
            r'Single.*?family.*?(\d+\.?\d*)\s*(?:units?|dwelling|du)?\s*per\s*acre'
        ]
        
        for pattern in density_patterns:
            matches = re.findall(pattern, ordinance_text, re.IGNORECASE | re.DOTALL)
            if matches:
                try:
                    density = float(matches[0])
                    logger.info(f"✅ Found density for {district_code}: {density} du/acre")
                    return density, "EXTRACTED_FROM_ORDINANCE"
                except ValueError:
                    continue
        
        return None, "PATTERN_NOT_FOUND"
        
    except Exception as e:
        logger.error(f"Error extracting density: {e}")
        return None, "EXTRACTION_ERROR"

def extract_far_from_ordinance(ordinance_text, district_code):
    """Extract FAR values from ordinance text with honesty markers"""
    if not ordinance_text:
        return None, "NO_ORDINANCE_TEXT"
    
    try:
        # Common FAR patterns in FL ordinances
        far_patterns = [
            r'floor area ratio.*?(?:shall not exceed|maximum of|up to)\s*(\d+\.?\d*)',
            r'FAR.*?(?:shall not exceed|maximum of|up to)\s*(\d+\.?\d*)',
            r'maximum.*?floor area ratio.*?(\d+\.?\d*)',
            r'building area.*?(?:shall not exceed|maximum of)\s*(\d+\.?\d*)\s*(?:times|x)',
            r'(\d+\.?\d*):1\s*floor area ratio'
        ]
        
        for pattern in far_patterns:
            matches = re.findall(pattern, ordinance_text, re.IGNORECASE | re.DOTALL)
            if matches:
                try:
                    far = float(matches[0])
                    logger.info(f"✅ Found FAR for {district_code}: {far}")
                    return far, "EXTRACTED_FROM_ORDINANCE"
                except ValueError:
                    continue
        
        return None, "PATTERN_NOT_FOUND"
        
    except Exception as e:
        logger.error(f"Error extracting FAR: {e}")
        return None, "EXTRACTION_ERROR"

def get_municode_ordinance(jurisdiction, district_code):
    """Fetch ordinance from live municode (placeholder - would need Firecrawl in real implementation)"""
    try:
        # This is a placeholder - in real implementation would use Firecrawl
        # to scrape library.municode.com/fl/{jurisdiction}/codes/land_development
        
        municode_urls = {
            'Melbourne': 'https://library.municode.com/fl/melbourne/codes/land_development_code',
            'Titusville': 'https://library.municode.com/fl/titusville/codes/zoning',
            'Rockledge': 'https://library.municode.com/fl/rockledge/codes/zoning',
            'West Melbourne': 'https://library.municode.com/fl/west_melbourne/codes/zoning'
        }
        
        base_url = municode_urls.get(jurisdiction)
        if not base_url:
            return None, "MUNICODE_URL_NOT_FOUND"
        
        # Simulate ordinance text (would be actual Firecrawl in production)
        logger.info(f"🌐 Would fetch from: {base_url} for {district_code}")
        
        # Return placeholder indicating this needs real implementation
        return None, "NEEDS_FIRECRAWL_IMPLEMENTATION"
        
    except Exception as e:
        logger.error(f"Error getting municode ordinance: {e}")
        return None, "MUNICODE_ERROR"

def create_zone_standard_with_honesty_marker(district_code, jurisdiction, density=None, far=None, source_info=""):
    """Create zone_standard record with honesty markers"""
    try:
        standard_data = {
            'district_code': district_code,
            'jurisdiction': jurisdiction,
            'county': 'brevard',
            'max_density_du_acre': density,
            'max_far': far,
            'parking_per_1000sf': None,  # Not extracting parking in this session
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'data_source': 'ordinance_extraction',
            'honesty_marker': source_info,
            'notes': f"Extracted from ordinance text: {source_info}"
        }
        
        response = requests.post(
            f"{BASE}/zone_standards",
            headers=HEADERS,
            json=standard_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Created zone_standard for {district_code}:{jurisdiction}")
            return True
        else:
            logger.error(f"Failed to create zone_standard: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error creating zone_standard: {e}")
        return False

def update_zone_standard_with_honesty_marker(district_code, jurisdiction, density=None, far=None, source_info=""):
    """Update existing zone_standard with honesty markers"""
    try:
        update_data = {}
        
        if density is not None:
            update_data['max_density_du_acre'] = density
        
        if far is not None:
            update_data['max_far'] = far
        
        if update_data:
            update_data.update({
                'updated_at': datetime.now().isoformat(),
                'honesty_marker': source_info,
                'notes': f"Updated from ordinance text: {source_info}"
            })
        
            response = requests.patch(
                f"{BASE}/zone_standards",
                headers=HEADERS,
                params={
                    "district_code": f"eq.{district_code}",
                    "jurisdiction": f"eq.{jurisdiction}"
                },
                json=update_data,
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info(f"✅ Updated zone_standard for {district_code}:{jurisdiction}")
                return True
            else:
                logger.error(f"Failed to update zone_standard: {response.status_code}")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"Error updating zone_standard: {e}")
        return False

def process_density_targets(vault_data, current_standards):
    """Process density gap targets"""
    print(f"\n🎯 Processing DENSITY targets...")
    
    density_fixed = 0
    
    for target in DENSITY_TARGETS:
        district = target['district']
        jurisdiction = target['jurisdiction']
        parcel_count = target['parcel_count']
        
        print(f"\n📋 Processing {district} in {jurisdiction} ({parcel_count:,} parcels)...")
        
        # Check if already has density
        key = f"{district}:{jurisdiction}"
        current = current_standards.get(key, {})
        
        if current.get('max_density_du_acre') is not None:
            print(f"   ✅ Already has density: {current['max_density_du_acre']} du/acre")
            continue
        
        # Look for ordinance text in vault
        ordinance_text = None
        source_info = ""
        
        for vault_record in vault_data:
            if (vault_record.get('jurisdiction') == jurisdiction and 
                vault_record.get('district_code') == district):
                ordinance_text = vault_record.get('ordinance_text')
                source_info = f"VAULT:{vault_record.get('source_url', '')}"
                break
        
        # Extract density
        density = None
        
        if ordinance_text:
            density, extraction_info = extract_density_from_ordinance(ordinance_text, district)
            source_info += f":{extraction_info}"
        else:
            # Try municode (placeholder)
            _, municode_info = get_municode_ordinance(jurisdiction, district)
            source_info = f"MUNICODE:{municode_info}"
        
        # Update/create standard if we found density
        if density is not None:
            if current:
                if update_zone_standard_with_honesty_marker(district, jurisdiction, density=density, source_info=source_info):
                    density_fixed += 1
            else:
                if create_zone_standard_with_honesty_marker(district, jurisdiction, density=density, source_info=source_info):
                    density_fixed += 1
        else:
            print(f"   ❌ Could not extract density - {source_info}")
    
    return density_fixed

def process_far_targets(vault_data, current_standards):
    """Process FAR gap targets (binding constraint)"""
    print(f"\n🎯 Processing FAR targets (BINDING CONSTRAINT)...")
    
    far_fixed = 0
    
    for target in FAR_TARGETS:
        district = target['district']
        jurisdiction = target['jurisdiction'] 
        parcel_count = target['parcel_count']
        
        print(f"\n📋 Processing {district} in {jurisdiction} ({parcel_count:,} parcels)...")
        
        # Check if already has FAR
        key = f"{district}:{jurisdiction}"
        current = current_standards.get(key, {})
        
        if current.get('max_far') is not None:
            print(f"   ✅ Already has FAR: {current['max_far']}")
            continue
        
        # Look for ordinance text in vault
        ordinance_text = None
        source_info = ""
        
        for vault_record in vault_data:
            if (vault_record.get('jurisdiction') == jurisdiction and 
                vault_record.get('district_code') == district):
                ordinance_text = vault_record.get('ordinance_text')
                source_info = f"VAULT:{vault_record.get('source_url', '')}"
                break
        
        # Extract FAR
        far = None
        
        if ordinance_text:
            far, extraction_info = extract_far_from_ordinance(ordinance_text, district)
            source_info += f":{extraction_info}"
        else:
            # Try municode (placeholder)
            _, municode_info = get_municode_ordinance(jurisdiction, district)
            source_info = f"MUNICODE:{municode_info}"
        
        # Update/create standard if we found FAR
        if far is not None:
            if current:
                if update_zone_standard_with_honesty_marker(district, jurisdiction, far=far, source_info=source_info):
                    far_fixed += 1
            else:
                if create_zone_standard_with_honesty_marker(district, jurisdiction, far=far, source_info=source_info):
                    far_fixed += 1
        else:
            print(f"   ❌ Could not extract FAR - {source_info}")
    
    return far_fixed

def main():
    """Main execution"""
    print("🏗️ SHARD-19 G HIT LIST - Zone Standards Backfill")
    print("Per BREVARD SPRINT ORDER priority #3")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    if not test_db_connection():
        return
    
    # Get current zone_standards
    current_standards = get_current_zone_standards()
    if current_standards is None:
        return
    
    # Check zoning vault for ordinance text
    vault_data = check_zoning_gold_standard_vault()
    
    print(f"\n📊 STARTING STATE:")
    print(f"   Existing zone_standards: {len(current_standards)} records")
    print(f"   Zoning vault records: {len(vault_data)} for Brevard")
    print(f"   Density targets: {len(DENSITY_TARGETS)} districts")
    print(f"   FAR targets (binding): {len(FAR_TARGETS)} districts")
    
    # Process targets
    density_fixed = process_density_targets(vault_data, current_standards)
    far_fixed = process_far_targets(vault_data, current_standards)
    
    # Summary
    print(f"\n{'='*70}")
    print("G HIT LIST RESULTS")
    print('='*70)
    print(f"📊 Density standards fixed: {density_fixed}/{len(DENSITY_TARGETS)}")
    print(f"📊 FAR standards fixed (binding): {far_fixed}/{len(FAR_TARGETS)}")
    
    total_fixed = density_fixed + far_fixed
    
    if total_fixed > 0:
        print(f"\n✅ SUCCESS: {total_fixed} zone_standards backfilled with ordinance values")
        print(f"📈 This should improve Brevard Letter G from 48.9%")
        print(f"🎯 FAR fixes are most critical (binding constraint at 48.9%)")
        
        print(f"\n🔍 HONESTY MARKERS:")
        print(f"   ✅ All values extracted from ordinance text")
        print(f"   ✅ Source tracking in honesty_marker field")
        print(f"   ✅ NO GUESSED VALUES per brief requirement")
        
        print(f"\n📋 NEXT STEPS:")
        print(f"1. Run pencil_dod_evaluate_county('brevard') to verify G improvement")
        print(f"2. Implement Firecrawl for live municode extraction")
        print(f"3. Expand zoning_gold_standard_vault with more ordinance text")
    else:
        print(f"⚠️  No standards fixed - need ordinance text in vault or Firecrawl")
        print(f"📋 REQUIREMENTS:")
        print(f"   1. Populate zoning_gold_standard_vault with ordinance text")
        print(f"   2. Implement Firecrawl for live municode scraping")
        print(f"   3. NO GUESSING - only ordinance-derived values allowed")
    
    print(f"\n⚡ G HIT LIST: COMPLETED")

if __name__ == "__main__":
    main()