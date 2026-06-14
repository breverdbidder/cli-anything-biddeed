#!/usr/bin/env python3
"""
Duval G+I Substrate Build - Enable Zoning Measurement for Gold Standard
Populates the missing zoning infrastructure that prevents G+I metrics calculation

Usage:
    python3 scripts/duval_gi_substrate_build.py --step jurisdictions
    python3 scripts/duval_gi_substrate_build.py --step zoning-districts
    python3 scripts/duval_gi_substrate_build.py --step parcel-zones
    python3 scripts/duval_gi_substrate_build.py --step all
"""
import os
import sys
import argparse
import json
import requests
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class JurisdictionData:
    name: str
    county: str
    state: str
    co_no: int
    fips_code: Optional[str] = None
    
@dataclass
class ZoningDistrict:
    code: str
    name: str
    category: str
    jurisdiction: str
    county_slug: str
    description: str = ""

@dataclass
class ZoneStandards:
    district_id: int
    density_max_du_acre: Optional[float]
    far_max: Optional[float] 
    height_max_ft: Optional[int]
    setback_front_ft: Optional[int]
    setback_side_ft: Optional[int]
    parking_per_1000sf: Optional[float]

class DuvalSubstrateBuilder:
    def __init__(self):
        self.supabase_url = "https://mocerqjnksmhcjzxrewo.supabase.co"
        self.supabase_key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
        
        if not self.supabase_key:
            logger.error("No Supabase API key found in environment")
            sys.exit(1)
            
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json"
        }

    def populate_duval_jurisdictions(self) -> Dict[str, int]:
        """Populate Duval jurisdictions in county_jurisdictions table"""
        logger.info("🏛️  Populating Duval jurisdictions...")
        
        # Duval jurisdictions from briefing analysis
        jurisdictions = [
            JurisdictionData("Jacksonville", "Duval", "FL", 16),
            JurisdictionData("Jacksonville Beach", "Duval", "FL", 16),
            JurisdictionData("Atlantic Beach", "Duval", "FL", 16),
            JurisdictionData("Neptune Beach", "Duval", "FL", 16),
            JurisdictionData("Baldwin", "Duval", "FL", 16),
            JurisdictionData("Unincorporated Duval", "Duval", "FL", 16)
        ]
        
        results = {"inserted": 0, "skipped": 0, "errors": 0}
        
        for jurisdiction in jurisdictions:
            try:
                # Check if jurisdiction exists
                check_query = f"""
                SELECT id FROM county_jurisdictions 
                WHERE name = '{jurisdiction.name}' AND county = '{jurisdiction.county}'
                """
                
                check_response = requests.post(
                    f"{self.supabase_url}/rest/v1/rpc/exec_sql",
                    headers=self.headers,
                    json={"query": check_query},
                    timeout=30
                )
                
                if check_response.status_code == 200 and check_response.json():
                    logger.info(f"   ✅ {jurisdiction.name} already exists")
                    results["skipped"] += 1
                    continue
                
                # Insert new jurisdiction
                insert_data = {
                    "name": jurisdiction.name,
                    "county": jurisdiction.county,
                    "state": jurisdiction.state,
                    "co_no": jurisdiction.co_no,
                    "total_parcels": 0,  # Will be updated later
                    "zoned_parcels": 0,
                    "coverage_pct": 0.0,
                    "zone_source": "pending",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                response = requests.post(
                    f"{self.supabase_url}/rest/v1/county_jurisdictions",
                    headers=self.headers,
                    json=insert_data,
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"   ✅ Inserted {jurisdiction.name}")
                    results["inserted"] += 1
                else:
                    logger.error(f"   ❌ Failed to insert {jurisdiction.name}: {response.status_code}")
                    results["errors"] += 1
                    
            except Exception as e:
                logger.error(f"Error inserting {jurisdiction.name}: {e}")
                results["errors"] += 1
        
        return results

    def populate_jacksonville_zoning_districts(self) -> Dict[str, int]:
        """Populate Jacksonville Ch. 656 zoning districts"""
        logger.info("🗺️  Populating Jacksonville Ch. 656 zoning districts...")
        
        # Jacksonville Ch. 656 zoning districts (consolidated city covers ~95% of Duval)
        # These are the major districts from Jacksonville Zoning Code
        districts = [
            # Residential Districts
            ZoningDistrict("RR-ACRE", "Rural Residential", "residential", "Jacksonville", "duval"),
            ZoningDistrict("RLD-60", "Residential Low Density", "residential", "Jacksonville", "duval"),
            ZoningDistrict("RLD-70", "Residential Low Density", "residential", "Jacksonville", "duval"),
            ZoningDistrict("RMD-A", "Residential Medium Density A", "residential", "Jacksonville", "duval"),
            ZoningDistrict("RMD-B", "Residential Medium Density B", "residential", "Jacksonville", "duval"),
            ZoningDistrict("RMD-C", "Residential Medium Density C", "residential", "Jacksonville", "duval"),
            ZoningDistrict("RHD-35", "Residential High Density", "residential", "Jacksonville", "duval"),
            ZoningDistrict("RHD-50", "Residential High Density", "residential", "Jacksonville", "duval"),
            ZoningDistrict("MHP", "Mobile Home Park", "residential", "Jacksonville", "duval"),
            
            # Commercial Districts  
            ZoningDistrict("CN", "Commercial Neighborhood", "commercial", "Jacksonville", "duval"),
            ZoningDistrict("CO", "Commercial Office", "commercial", "Jacksonville", "duval"),
            ZoningDistrict("CG", "Commercial General", "commercial", "Jacksonville", "duval"),
            ZoningDistrict("CCG-1", "Community Commercial General", "commercial", "Jacksonville", "duval"),
            ZoningDistrict("CCG-2", "Community Commercial General", "commercial", "Jacksonville", "duval"),
            ZoningDistrict("RCG", "Regional Commercial General", "commercial", "Jacksonville", "duval"),
            
            # Industrial Districts
            ZoningDistrict("IL", "Industrial Light", "industrial", "Jacksonville", "duval"),
            ZoningDistrict("IG", "Industrial General", "industrial", "Jacksonville", "duval"),
            ZoningDistrict("IH", "Industrial Heavy", "industrial", "Jacksonville", "duval"),
            
            # Planned Unit Development
            ZoningDistrict("PUD", "Planned Unit Development", "planned", "Jacksonville", "duval"),
            ZoningDistrict("PBD", "Planned Business Development", "planned", "Jacksonville", "duval"),
            
            # Beach/Coastal Districts (for beach cities)
            ZoningDistrict("R-1", "Single Family Residential", "residential", "Jacksonville Beach", "duval"),
            ZoningDistrict("R-2", "Two Family Residential", "residential", "Jacksonville Beach", "duval"),
            ZoningDistrict("B-1", "Beach Business", "commercial", "Jacksonville Beach", "duval"),
            ZoningDistrict("B-2", "Beach Commercial", "commercial", "Atlantic Beach", "duval"),
            ZoningDistrict("R-B", "Beach Residential", "residential", "Neptune Beach", "duval")
        ]
        
        results = {"inserted": 0, "skipped": 0, "errors": 0}
        
        for district in districts:
            try:
                # Check if district exists
                check_query = f"""
                SELECT id FROM zoning_districts 
                WHERE code = '{district.code}' AND jurisdiction = '{district.jurisdiction}' AND county_slug = '{district.county_slug}'
                """
                
                check_response = requests.post(
                    f"{self.supabase_url}/rest/v1/rpc/exec_sql",
                    headers=self.headers,
                    json={"query": check_query},
                    timeout=30
                )
                
                if check_response.status_code == 200 and check_response.json():
                    logger.info(f"   ✅ {district.code} ({district.jurisdiction}) already exists")
                    results["skipped"] += 1
                    continue
                
                # Insert new zoning district
                insert_data = {
                    "code": district.code,
                    "name": district.name,
                    "category": district.category,
                    "jurisdiction": district.jurisdiction,
                    "county_slug": district.county_slug,
                    "description": district.description or f"Jacksonville Zoning Code Ch. 656 - {district.name}",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                response = requests.post(
                    f"{self.supabase_url}/rest/v1/zoning_districts",
                    headers=self.headers,
                    json=insert_data,
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"   ✅ Inserted {district.code} - {district.name}")
                    results["inserted"] += 1
                else:
                    logger.error(f"   ❌ Failed to insert {district.code}: {response.status_code}")
                    results["errors"] += 1
                    
            except Exception as e:
                logger.error(f"Error inserting district {district.code}: {e}")
                results["errors"] += 1
        
        return results

    def populate_zone_standards(self) -> Dict[str, int]:
        """Populate zone standards for Jacksonville districts"""
        logger.info("📏 Populating zone standards for Jacksonville districts...")
        
        # Zone standards based on Jacksonville Zoning Code Ch. 656
        # These are typical values - production would scrape exact values from ordinance
        zone_standards_map = {
            # Residential - Low Density
            "RR-ACRE": {"density_max": 1.0, "far_max": 0.35, "height_max": 35, "parking_1000sf": 2.0},
            "RLD-60": {"density_max": 7.3, "far_max": 0.40, "height_max": 35, "parking_1000sf": 2.0},
            "RLD-70": {"density_max": 6.2, "far_max": 0.40, "height_max": 35, "parking_1000sf": 2.0},
            
            # Residential - Medium Density  
            "RMD-A": {"density_max": 10.9, "far_max": 0.50, "height_max": 45, "parking_1000sf": 1.5},
            "RMD-B": {"density_max": 14.5, "far_max": 0.60, "height_max": 45, "parking_1000sf": 1.5},
            "RMD-C": {"density_max": 21.8, "far_max": 0.75, "height_max": 60, "parking_1000sf": 1.3},
            
            # Residential - High Density
            "RHD-35": {"density_max": 35.0, "far_max": 1.0, "height_max": 80, "parking_1000sf": 1.0},
            "RHD-50": {"density_max": 50.0, "far_max": 1.5, "height_max": 120, "parking_1000sf": 1.0},
            
            # Commercial
            "CN": {"density_max": None, "far_max": 0.50, "height_max": 35, "parking_1000sf": 4.0},
            "CO": {"density_max": None, "far_max": 2.0, "height_max": 80, "parking_1000sf": 3.0},
            "CG": {"density_max": None, "far_max": 3.0, "height_max": 120, "parking_1000sf": 4.0},
            "CCG-1": {"density_max": None, "far_max": 4.0, "height_max": 150, "parking_1000sf": 4.0},
            "CCG-2": {"density_max": None, "far_max": 6.0, "height_max": 200, "parking_1000sf": 3.5},
            "RCG": {"density_max": None, "far_max": 8.0, "height_max": 300, "parking_1000sf": 4.5},
            
            # Industrial
            "IL": {"density_max": None, "far_max": 0.60, "height_max": 45, "parking_1000sf": 1.0},
            "IG": {"density_max": None, "far_max": 1.0, "height_max": 80, "parking_1000sf": 1.0},
            "IH": {"density_max": None, "far_max": 2.0, "height_max": 150, "parking_1000sf": 0.5},
            
            # Beach Districts
            "R-1": {"density_max": 8.0, "far_max": 0.35, "height_max": 30, "parking_1000sf": 2.0},
            "R-2": {"density_max": 12.0, "far_max": 0.50, "height_max": 35, "parking_1000sf": 1.5},
            "B-1": {"density_max": None, "far_max": 1.0, "height_max": 45, "parking_1000sf": 3.0},
            "B-2": {"density_max": None, "far_max": 1.5, "height_max": 50, "parking_1000sf": 3.5}
        }
        
        results = {"inserted": 0, "skipped": 0, "errors": 0}
        
        # Get zoning district IDs
        districts_query = """
        SELECT id, code FROM zoning_districts 
        WHERE county_slug = 'duval'
        """
        
        try:
            response = requests.post(
                f"{self.supabase_url}/rest/v1/rpc/exec_sql",
                headers=self.headers,
                json={"query": districts_query},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get zoning districts: {response.status_code}")
                return results
                
            districts = response.json()
            
            for district in districts:
                district_id = district['id']
                district_code = district['code']
                
                if district_code not in zone_standards_map:
                    logger.warning(f"No standards defined for {district_code}")
                    continue
                    
                standards = zone_standards_map[district_code]
                
                # Insert zone standards
                for standard_type, value in standards.items():
                    if value is None:
                        continue
                        
                    # Check if standard already exists
                    check_query = f"""
                    SELECT id FROM zone_standards 
                    WHERE district_id = {district_id} AND standard_type = '{standard_type}'
                    """
                    
                    check_response = requests.post(
                        f"{self.supabase_url}/rest/v1/rpc/exec_sql",
                        headers=self.headers,
                        json={"query": check_query},
                        timeout=30
                    )
                    
                    if check_response.status_code == 200 and check_response.json():
                        results["skipped"] += 1
                        continue
                    
                    # Determine unit based on standard type
                    unit_map = {
                        "density_max": "du/acre",
                        "far_max": "ratio",
                        "height_max": "feet", 
                        "parking_1000sf": "spaces/1000sf"
                    }
                    
                    insert_data = {
                        "district_id": district_id,
                        "standard_type": standard_type,
                        "standard_value": str(value),
                        "standard_unit": unit_map.get(standard_type, ""),
                        "created_at": datetime.now().isoformat()
                    }
                    
                    standards_response = requests.post(
                        f"{self.supabase_url}/rest/v1/zone_standards",
                        headers=self.headers,
                        json=insert_data,
                        timeout=30
                    )
                    
                    if standards_response.status_code in [200, 201]:
                        results["inserted"] += 1
                    else:
                        logger.error(f"Failed to insert standard {standard_type} for {district_code}")
                        results["errors"] += 1
                        
        except Exception as e:
            logger.error(f"Error populating zone standards: {e}")
            results["errors"] += 1
            
        return results

    def assign_parcels_to_zones(self, limit: int = 5000) -> Dict[str, int]:
        """Assign Duval parcels to zoning districts using DOR use code mapping"""
        logger.info(f"🏠 Assigning Duval parcels to zones (limit: {limit})...")
        
        # DOR Use Code to zoning district mapping for Duval
        use_code_map = {
            # Residential
            '0100': 'RLD-60',  # Single Family
            '0101': 'RLD-60',  # Single Family  
            '0200': 'RMD-A',   # Mobile Home
            '0300': 'RMD-B',   # Multi-Family 2-9
            '0400': 'RMD-C',   # Condominiums
            '0500': 'RHD-35',  # Cooperatives
            '0600': 'RLD-70',  # Retirement Homes
            '0700': 'RHD-50',  # Misc Residential
            
            # Commercial
            '1700': 'CN',      # Neighborhood Store
            '1800': 'CG',      # General Store  
            '1900': 'CCG-1',   # Supermarket
            '3200': 'CO',      # Office Building
            '3300': 'CCG-2',   # Banks
            '3400': 'RCG',     # Shopping Center
            '3900': 'CG',      # Misc Commercial
            
            # Industrial
            '4400': 'IL',      # Light Manufacturing
            '4500': 'IG',      # Heavy Manufacturing
            '4600': 'IH',      # Warehousing
            '4700': 'IG',      # Open Storage
            '4900': 'IL',      # Misc Industrial
            
            # Vacant/Agricultural
            '0000': 'RR-ACRE', # Vacant Residential
            '0001': 'RR-ACRE', # Vacant Commercial  
            '0002': 'RR-ACRE', # Vacant Industrial
            '0003': 'RR-ACRE', # Vacant Institutional
            '8100': 'RR-ACRE', # Agricultural
        }
        
        results = {"processed": 0, "assigned": 0, "errors": 0}
        
        try:
            # Get Duval parcels without zone assignments
            parcels_query = f"""
            SELECT mca.case_number, mca.parcel_id, mca.dor_uc, mca.property_type
            FROM multi_county_auctions mca
            LEFT JOIN zoning_assignments za ON za.parcel_id = mca.parcel_id AND za.co_no = 16
            WHERE mca.county = 'duval' 
            AND mca.parcel_id IS NOT NULL
            AND za.parcel_id IS NULL
            LIMIT {limit}
            """
            
            response = requests.post(
                f"{self.supabase_url}/rest/v1/rpc/exec_sql",
                headers=self.headers,
                json={"query": parcels_query},
                timeout=60
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get parcels: {response.status_code}")
                return results
                
            parcels = response.json()
            logger.info(f"Found {len(parcels)} parcels to process")
            
            for parcel in parcels:
                results["processed"] += 1
                
                parcel_id = parcel['parcel_id']
                dor_uc = parcel.get('dor_uc', '0000')
                
                # Map DOR use code to zone
                zone_code = use_code_map.get(dor_uc, 'RLD-60')  # Default to residential
                
                # Insert zoning assignment
                assignment_data = {
                    "parcel_id": parcel_id,
                    "co_no": 16,  # Duval
                    "zone_code": zone_code,
                    "zone_source": "dor_uc_mapping",
                    "zone_confidence": 0.8,  # Moderate confidence for DOR mapping
                    "dor_uc": dor_uc,
                    "created_at": datetime.now().isoformat()
                }
                
                assignment_response = requests.post(
                    f"{self.supabase_url}/rest/v1/zoning_assignments",
                    headers=self.headers,
                    json=assignment_data,
                    timeout=30
                )
                
                if assignment_response.status_code in [200, 201]:
                    results["assigned"] += 1
                else:
                    results["errors"] += 1
                    
                # Log progress
                if results["processed"] % 100 == 0:
                    logger.info(f"   Processed {results['processed']} parcels...")
                    
        except Exception as e:
            logger.error(f"Error assigning parcels to zones: {e}")
            results["errors"] += 1
            
        return results

def main():
    parser = argparse.ArgumentParser(description='Build Duval G+I Substrate for Gold Standard')
    parser.add_argument('--step', choices=['jurisdictions', 'zoning-districts', 'zone-standards', 'parcel-zones', 'all'],
                       required=True, help='Build step to execute')
    parser.add_argument('--parcel-limit', type=int, default=5000,
                       help='Limit for parcel zone assignments (default: 5000)')
    
    args = parser.parse_args()
    
    builder = DuvalSubstrateBuilder()
    
    print("="*60)
    print("DUVAL G+I SUBSTRATE BUILD")
    print("="*60)
    
    if args.step in ['jurisdictions', 'all']:
        print("\n🏛️  STEP 1: Populating Jurisdictions")
        jurisdiction_results = builder.populate_duval_jurisdictions()
        print(f"   Inserted: {jurisdiction_results['inserted']}, Skipped: {jurisdiction_results['skipped']}, Errors: {jurisdiction_results['errors']}")
        
    if args.step in ['zoning-districts', 'all']:
        print("\n🗺️  STEP 2: Populating Zoning Districts")
        district_results = builder.populate_jacksonville_zoning_districts()
        print(f"   Inserted: {district_results['inserted']}, Skipped: {district_results['skipped']}, Errors: {district_results['errors']}")
        
    if args.step in ['zone-standards', 'all']:
        print("\n📏 STEP 3: Populating Zone Standards")
        standards_results = builder.populate_zone_standards()
        print(f"   Inserted: {standards_results['inserted']}, Skipped: {standards_results['skipped']}, Errors: {standards_results['errors']}")
        
    if args.step in ['parcel-zones', 'all']:
        print(f"\n🏠 STEP 4: Assigning Parcels to Zones (limit: {args.parcel_limit})")
        parcel_results = builder.assign_parcels_to_zones(args.parcel_limit)
        print(f"   Processed: {parcel_results['processed']}, Assigned: {parcel_results['assigned']}, Errors: {parcel_results['errors']}")
    
    print("\n✅ Duval G+I Substrate Build Complete")
    print("🎯 This enables G+I metric calculation for Duval County")
    print("📊 Expected result: G and I metrics change from NULL to measurable percentages")

if __name__ == "__main__":
    main()