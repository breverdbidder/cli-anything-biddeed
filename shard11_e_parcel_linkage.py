#!/usr/bin/env python3
"""
SHARD-11 E-LANE: Parcel Linkage Implementation
High-leverage fix for counties: putnam (17.9%), gilchrist (42.9%), orange (72.2%)

Per issue brief: "E: link parcel_id via the county property appraiser ArcGIS FeatureServer 
(Brevard/BCPAO pipeline is the reference implementation)"

Target: E >=95% parcel linkage for gold standard compliance

Counties and property appraiser endpoints:
- putnam: Putnam County Property Appraiser - putnam.flparc.com
- gilchrist: Gilchrist County Property Appraiser - gilchrist.flparc.com  
- orange: Orange County Property Appraiser - ocpaweb.ocpafl.org

Usage:
  python shard11_e_parcel_linkage.py
"""
import os
import sys
import json
import httpx
import logging
import asyncio
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-11 counties with parcel linkage gaps
TARGET_COUNTIES = {
    'putnam': {
        'current_linkage': 17.9,
        'appraiser_url': 'https://putnam.flparc.com',
        'arcgis_discovery': 'https://maps.putnamcountyfl.gov/arcgis/rest/services',
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN', 'STRAP'],
        'priority': 1  # Lowest current linkage
    },
    'gilchrist': {
        'current_linkage': 42.9,
        'appraiser_url': 'https://gilchrist.flparc.com',
        'arcgis_discovery': None,  # Need to discover
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN'],
        'priority': 2
    },
    'orange': {
        'current_linkage': 72.2,
        'appraiser_url': 'https://ocpaweb.ocpafl.org', 
        'arcgis_discovery': 'https://ocgis4.ocfl.net/arcgis/rest/services',
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN', 'FOLIO'],
        'priority': 3  # Highest current linkage - optimize existing
    }
}

# Evidence collection for Honesty Protocol
linkage_evidence = []

def log_evidence(action, result, status="VERIFIED"):
    """Collect VERIFIED evidence per Honesty Protocol"""
    evidence = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "result": result,
        "status": status
    }
    linkage_evidence.append(evidence)
    return evidence

class ParcelLinkageExecutor:
    def __init__(self):
        self.session_id = f"shard11_e_linkage_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.client = httpx.AsyncClient(timeout=60)
        self.discovered_services = {}
        self.linkage_results = {}
        
    async def test_connection(self):
        """Test Supabase connection with VERIFIED evidence"""
        try:
            response = await self.client.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"})
            if response.status_code == 200:
                log_evidence("Connection test", {"status": "success", "code": 200})
                logger.info("✅ VERIFIED: Supabase connection successful")
                return True
            else:
                log_evidence("Connection test", {"status": "failed", "code": response.status_code})
                logger.error(f"❌ VERIFIED: Connection failed {response.status_code}")
                return False
        except Exception as e:
            log_evidence("Connection test", {"status": "error", "error": str(e)})
            logger.error(f"❌ VERIFIED: Connection error {e}")
            return False
    
    async def get_county_baseline(self, county):
        """Get current parcel linkage baseline - VERIFIED evidence"""
        try:
            # Get current evaluation
            payload = {"county_name": county}
            response = await self.client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                e_metric = result.get('metric_e')
                
                evidence = log_evidence(
                    f"Baseline E metric for {county}",
                    {"metric_e": e_metric, "total_score": result.get('total_score')},
                    "VERIFIED"
                )
                
                logger.info(f"✅ VERIFIED: {county} baseline E={e_metric}%")
                return e_metric, result
            else:
                log_evidence(
                    f"Baseline query for {county}",
                    {"error": f"HTTP {response.status_code}"},
                    "VERIFIED"
                )
                return None, None
                
        except Exception as e:
            log_evidence(
                f"Baseline query for {county}",
                {"error": str(e)},
                "VERIFIED" 
            )
            logger.error(f"❌ Error getting {county} baseline: {e}")
            return None, None
    
    async def discover_arcgis_service(self, county):
        """Discover ArcGIS property service for county - INFERRED from discovery"""
        config = TARGET_COUNTIES.get(county, {})
        discovery_url = config.get('arcgis_discovery')
        
        if not discovery_url:
            logger.info(f"🔍 INFERRED: No ArcGIS discovery URL for {county} - trying appraiser URL")
            return None
            
        try:
            # Get services list
            services_url = f"{discovery_url}?f=json"
            response = await self.client.get(services_url)
            
            if response.status_code != 200:
                log_evidence(
                    f"ArcGIS discovery for {county}",
                    {"error": f"HTTP {response.status_code}", "url": services_url},
                    "INFERRED"
                )
                return None
            
            services_data = response.json()
            
            # Look for property/parcel services
            property_keywords = ['property', 'parcel', 'cadastral', 'ownership', 'appraiser', 'tax']
            
            for service in services_data.get('services', []):
                service_name = service.get('name', '').lower()
                service_type = service.get('type', '')
                
                if service_type == 'MapServer':
                    for keyword in property_keywords:
                        if keyword in service_name:
                            service_url = f"{discovery_url}/{service['name']}/MapServer"
                            
                            # Test the service
                            test_response = await self.client.get(f"{service_url}?f=json")
                            if test_response.status_code == 200:
                                self.discovered_services[county] = service_url
                                
                                log_evidence(
                                    f"ArcGIS service discovery for {county}",
                                    {"service_url": service_url, "service_name": service['name']},
                                    "INFERRED"
                                )
                                
                                logger.info(f"✅ INFERRED: Found {county} property service: {service_url}")
                                return service_url
            
            log_evidence(
                f"ArcGIS service discovery for {county}",
                {"status": "no_property_service_found", "services_checked": len(services_data.get('services', []))},
                "INFERRED"
            )
            return None
            
        except Exception as e:
            log_evidence(
                f"ArcGIS service discovery for {county}",
                {"error": str(e)},
                "INFERRED"
            )
            logger.error(f"❌ Error discovering {county} ArcGIS service: {e}")
            return None
    
    async def get_unlinked_properties(self, county, limit=500):
        """Get properties without parcel_id - VERIFIED evidence"""
        try:
            params = {
                'county_name': f'eq.{county}',
                'parcel_id': 'is.null',
                'limit': limit,
                'select': 'id,address,case_number,county_name,sale_date,status',
                'order': 'sale_date.desc'
            }
            
            response = await self.client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params=params)
            
            if response.status_code == 200:
                properties = response.json()
                
                log_evidence(
                    f"Unlinked properties query for {county}",
                    {"count": len(properties), "limit": limit},
                    "VERIFIED"
                )
                
                logger.info(f"✅ VERIFIED: {county} has {len(properties)} unlinked properties")
                return properties
            else:
                log_evidence(
                    f"Unlinked properties query for {county}",
                    {"error": f"HTTP {response.status_code}"},
                    "VERIFIED"
                )
                return []
                
        except Exception as e:
            log_evidence(
                f"Unlinked properties query for {county}",
                {"error": str(e)},
                "VERIFIED"
            )
            logger.error(f"❌ Error getting unlinked properties for {county}: {e}")
            return []
    
    def normalize_address(self, address):
        """Normalize address for better matching - INFERRED heuristics"""
        if not address:
            return ""
            
        # Clean and normalize
        clean = address.strip().upper()
        
        # Common abbreviation expansions
        clean = re.sub(r'\bAVE\b', 'AVENUE', clean)
        clean = re.sub(r'\bST\b', 'STREET', clean) 
        clean = re.sub(r'\bDR\b', 'DRIVE', clean)
        clean = re.sub(r'\bRD\b', 'ROAD', clean)
        clean = re.sub(r'\bLN\b', 'LANE', clean)
        clean = re.sub(r'\bCT\b', 'COURT', clean)
        clean = re.sub(r'\bPL\b', 'PLACE', clean)
        clean = re.sub(r'\bBLVD\b', 'BOULEVARD', clean)
        
        # Remove extra spaces
        clean = re.sub(r'\s+', ' ', clean)
        
        return clean
    
    async def search_parcel_by_address(self, county, property_record, service_url):
        """Search for parcel ID using address - INFERRED from fuzzy matching"""
        address = property_record.get('address', '')
        if not address:
            return None
            
        normalized_address = self.normalize_address(address)
        
        # Try multiple address variants
        search_variants = [
            normalized_address,
            address.strip().upper(),
            # Remove unit numbers
            re.sub(r'\s+(APT|UNIT|#)\s*\w+', '', normalized_address),
        ]
        
        for variant in search_variants:
            if not variant:
                continue
                
            try:
                # Query the feature service (assuming layer 0 is property layer)
                query_url = f"{service_url}/0/query"
                params = {
                    'where': f"ADDRESS LIKE '%{variant.replace(' ', '%')}%' OR SITUS LIKE '%{variant.replace(' ', '%')}%'",
                    'outFields': 'PARCEL_ID,PARCELNO,PIN,STRAP,FOLIO,ADDRESS,SITUS',
                    'f': 'json',
                    'returnGeometry': 'false',
                    'maxRecordCount': 5
                }
                
                response = await self.client.get(query_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    features = data.get('features', [])
                    
                    if features:
                        # Take first match - could be improved with fuzzy scoring
                        feature = features[0]
                        attributes = feature.get('attributes', {})
                        
                        # Find the parcel ID field
                        config = TARGET_COUNTIES.get(county, {})
                        search_fields = config.get('search_fields', ['PARCEL_ID'])
                        
                        for field in search_fields:
                            parcel_id = attributes.get(field)
                            if parcel_id:
                                logger.info(f"📍 INFERRED: Found parcel {parcel_id} for {address} in {county}")
                                return parcel_id
                        
                        logger.info(f"⚠️ INFERRED: Found feature but no parcel ID field for {address} in {county}")
                        return None
                        
            except Exception as e:
                logger.warning(f"⚠️ Error searching {variant} in {county}: {e}")
                continue
        
        return None
    
    async def update_parcel_linkage(self, property_id, parcel_id):
        """Update property with discovered parcel_id - VERIFIED evidence"""
        try:
            update_data = {"parcel_id": parcel_id}
            
            response = await self.client.patch(
                f"{BASE}/multi_county_auctions",
                headers=HEADERS,
                params={"id": f"eq.{property_id}"},
                json=update_data
            )
            
            if response.status_code in [200, 204]:
                log_evidence(
                    f"Parcel linkage update for property {property_id}",
                    {"parcel_id": parcel_id, "status": "success"},
                    "VERIFIED"
                )
                return True
            else:
                log_evidence(
                    f"Parcel linkage update for property {property_id}",
                    {"error": f"HTTP {response.status_code}", "parcel_id": parcel_id},
                    "VERIFIED"
                )
                return False
                
        except Exception as e:
            log_evidence(
                f"Parcel linkage update for property {property_id}",
                {"error": str(e), "parcel_id": parcel_id},
                "VERIFIED"
            )
            logger.error(f"❌ Error updating property {property_id}: {e}")
            return False
    
    async def execute_county_linkage(self, county):
        """Execute parcel linkage for a specific county"""
        logger.info(f"🚀 Starting parcel linkage for {county}")
        
        # Get baseline
        baseline_metric, baseline_eval = await self.get_county_baseline(county)
        
        # Discover ArcGIS service
        service_url = await self.discover_arcgis_service(county)
        if not service_url:
            logger.warning(f"⚠️ No ArcGIS service found for {county} - skipping automated linkage")
            return {"status": "NO_SERVICE", "baseline": baseline_metric}
        
        # Get unlinked properties
        unlinked = await self.get_unlinked_properties(county, limit=100)  # Start small for testing
        
        if not unlinked:
            logger.info(f"✅ {county} has no unlinked properties to process")
            return {"status": "NO_UNLINKED", "baseline": baseline_metric}
        
        logger.info(f"🔗 Processing {len(unlinked)} unlinked properties for {county}")
        
        # Process properties
        linked_count = 0
        processed_count = 0
        
        for prop in unlinked[:20]:  # Limit for testing - can scale up
            processed_count += 1
            prop_id = prop.get('id')
            address = prop.get('address', '')
            
            if not address:
                continue
                
            # Search for parcel ID
            parcel_id = await self.search_parcel_by_address(county, prop, service_url)
            
            if parcel_id:
                # Update the property
                success = await self.update_parcel_linkage(prop_id, parcel_id)
                if success:
                    linked_count += 1
                    logger.info(f"✅ Linked property {prop_id} to parcel {parcel_id}")
                    
            # Rate limiting
            await asyncio.sleep(0.1)
        
        # Get updated baseline
        updated_metric, updated_eval = await self.get_county_baseline(county)
        
        result = {
            "status": "COMPLETED",
            "baseline_metric": baseline_metric,
            "updated_metric": updated_metric,
            "improvement": (updated_metric - baseline_metric) if (baseline_metric and updated_metric) else None,
            "processed_count": processed_count,
            "linked_count": linked_count,
            "success_rate": (linked_count / processed_count) if processed_count > 0 else 0,
            "service_url": service_url
        }
        
        self.linkage_results[county] = result
        logger.info(f"🎯 {county} linkage complete: {linked_count}/{processed_count} linked")
        
        return result
    
    async def run_linkage_campaign(self):
        """Execute parcel linkage for all SHARD-11 target counties"""
        logger.info("🚀 SHARD-11 E-LANE Parcel Linkage Campaign Starting")
        
        if not await self.test_connection():
            logger.error("❌ Campaign aborted - no database connection")
            return {"status": "FAILED", "reason": "NO_CONNECTION"}
        
        # Sort counties by priority (lowest linkage first)
        sorted_counties = sorted(TARGET_COUNTIES.keys(), key=lambda c: TARGET_COUNTIES[c]['priority'])
        
        campaign_results = {
            "session_id": self.session_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "target_counties": sorted_counties,
            "county_results": {},
            "verification_evidence": linkage_evidence,
            "status": "IN_PROGRESS"
        }
        
        for county in sorted_counties:
            logger.info(f"📍 Processing {county}...")
            result = await self.execute_county_linkage(county)
            campaign_results["county_results"][county] = result
            
            # Log progress
            baseline = result.get("baseline_metric")
            updated = result.get("updated_metric") 
            improvement = result.get("improvement")
            
            if improvement:
                logger.info(f"✅ {county}: {baseline}% → {updated}% (+{improvement:.1f}%)")
            else:
                logger.info(f"📊 {county}: baseline {baseline}%")
        
        campaign_results.update({
            "end_time": datetime.now(timezone.utc).isoformat(),
            "status": "COMPLETED",
            "verification_evidence": linkage_evidence
        })
        
        await self.client.aclose()
        return campaign_results

async def main():
    """Main entry point for SHARD-11 parcel linkage"""
    executor = ParcelLinkageExecutor()
    results = await executor.run_linkage_campaign()
    
    # Save results
    results_file = f"/tmp/shard11_parcel_linkage_results_{executor.session_id}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print("SHARD-11 E-LANE PARCEL LINKAGE COMPLETE")
    print(f"{'='*60}")
    print(f"Session ID: {results['session_id']}")
    print(f"Counties: {', '.join(results['target_counties'])}")
    print(f"Evidence items: {len(results['verification_evidence'])}")
    
    print(f"\nResults per county:")
    for county, result in results.get('county_results', {}).items():
        status = result.get('status')
        baseline = result.get('baseline_metric')
        updated = result.get('updated_metric')
        linked = result.get('linked_count', 0)
        
        if status == "COMPLETED" and updated is not None:
            improvement = updated - baseline if baseline else 0
            print(f"- {county}: {baseline}% → {updated}% (+{improvement:.1f}%) - {linked} properties linked")
        else:
            print(f"- {county}: {status} - baseline {baseline}%")
    
    print(f"\nResults saved to: {results_file}")
    return results

if __name__ == "__main__":
    results = asyncio.run(main())