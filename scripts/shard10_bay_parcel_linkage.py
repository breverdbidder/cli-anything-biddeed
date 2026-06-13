#!/usr/bin/env python3
"""
SHARD-10 Bay County E-linkage Improvement
Close to passing at 81.3% (2396/2947) - need 99 more links for 85%+ pass

Strategy: Connect multi_county_auctions to parcels via Bay County GIS
Expected Impact: Bay county 1→2+ letters (E pass unlocks other improvements)

Usage:
  python scripts/shard10_bay_parcel_linkage.py
"""
import os
import sys
import requests
import json
import time
from datetime import datetime
from pathlib import Path

# Add the project root to Python path  
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def log(message, level="INFO"):
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] {level}: {message}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", 
        "Prefer": "resolution=merge-duplicates"
    }

def get_bay_auction_data():
    """Get Bay County auction data that needs parcel linkage"""
    log("📊 Fetching Bay County auction data for linkage analysis")
    
    try:
        # Get auctions missing parcel_id
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions", 
            headers=sb_headers(),
            params={
                "select": "case_number,property_address,property_city,property_zip,parcel_id",
                "county": "eq.bay",
                "parcel_id": "is.null",
                "limit": "500"  # Process in batches
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            log(f"✅ Found {len(data)} Bay auctions missing parcel_id")
            return data
        else:
            log(f"❌ Failed to fetch Bay auction data: {response.status_code}", "ERROR")
            return []
            
    except Exception as e:
        log(f"❌ Error fetching Bay auction data: {e}", "ERROR")
        return []

def discover_bay_gis_endpoints():
    """Discover Bay County GIS endpoints for parcel data"""
    log("🔍 Discovering Bay County GIS endpoints")
    
    # Known Bay County GIS patterns
    potential_endpoints = [
        "https://gis.baycountyfl.gov/arcgis/rest/services/",
        "https://baycountyfl.gov/arcgis/rest/services/", 
        "https://services.arcgis.com/bay/",
        "https://maps.baycountyfl.gov/arcgis/rest/services/"
    ]
    
    working_endpoints = []
    
    for endpoint in potential_endpoints:
        try:
            log(f"🌐 Testing endpoint: {endpoint}")
            response = requests.get(f"{endpoint}?f=json", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "services" in data:
                    log(f"✅ Working endpoint found: {endpoint}")
                    working_endpoints.append({
                        "base_url": endpoint,
                        "services": data.get("services", [])
                    })
                    
        except Exception as e:
            log(f"⚠️ Endpoint {endpoint} failed: {e}")
            continue
    
    return working_endpoints

def find_parcel_service(endpoints):
    """Find the parcel/property service in GIS endpoints"""
    log("🗺️ Looking for parcel/property services")
    
    for endpoint_info in endpoints:
        base_url = endpoint_info["base_url"]
        services = endpoint_info.get("services", [])
        
        for service in services:
            service_name = service.get("name", "").lower()
            if any(keyword in service_name for keyword in ["parcel", "property", "cadastral", "land"]):
                service_url = f"{base_url}{service['name']}/MapServer"
                
                try:
                    # Test the service
                    response = requests.get(f"{service_url}?f=json", timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        layers = data.get("layers", [])
                        
                        # Look for parcel layer
                        for layer in layers:
                            layer_name = layer.get("name", "").lower()
                            if "parcel" in layer_name:
                                log(f"✅ Found parcel layer: {service_url}/{layer['id']}")
                                return {
                                    "service_url": service_url,
                                    "layer_id": layer["id"],
                                    "layer_name": layer["name"]
                                }
                                
                except Exception as e:
                    log(f"⚠️ Service {service_url} failed: {e}")
                    continue
    
    return None

def link_parcels_via_address(auction_data, parcel_service):
    """Link auctions to parcels via address matching"""
    log("🔗 Linking auctions to parcels via address matching")
    
    if not parcel_service:
        log("❌ No parcel service available for linking", "ERROR")
        return []
    
    linked_parcels = []
    successful_links = 0
    
    for auction in auction_data:
        try:
            address = auction.get("property_address", "").strip()
            if not address:
                continue
                
            # Query parcel service by address
            query_url = f"{parcel_service['service_url']}/{parcel_service['layer_id']}/query"
            params = {
                "where": f"UPPER(ADDRESS) LIKE UPPER('%{address}%')",
                "outFields": "PARCEL_ID,ADDRESS,OWNER_NAME",
                "f": "json",
                "returnGeometry": "false"
            }
            
            response = requests.get(query_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                features = data.get("features", [])
                
                if features:
                    # Take best match (first result)
                    parcel_data = features[0]["attributes"]
                    parcel_id = parcel_data.get("PARCEL_ID")
                    
                    if parcel_id:
                        linked_parcels.append({
                            "case_number": auction["case_number"],
                            "parcel_id": parcel_id,
                            "match_type": "address",
                            "confidence": "medium"
                        })
                        successful_links += 1
                        
                        if successful_links % 10 == 0:
                            log(f"📊 Progress: {successful_links} parcels linked")
            
            # Rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            log(f"⚠️ Error linking auction {auction.get('case_number', 'unknown')}: {e}")
            continue
    
    log(f"✅ Successfully linked {successful_links} parcels")
    return linked_parcels

def update_parcel_linkages(linkages):
    """Update multi_county_auctions with new parcel_id linkages"""
    log(f"💾 Updating {len(linkages)} parcel linkages in database")
    
    if not linkages:
        log("⚠️ No linkages to update")
        return False
    
    successful_updates = 0
    
    try:
        # Batch update approach
        for linkage in linkages:
            case_number = linkage["case_number"]
            parcel_id = linkage["parcel_id"]
            
            # Update the auction record
            response = requests.patch(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=sb_headers(),
                params={"case_number": f"eq.{case_number}"},
                json={"parcel_id": parcel_id}
            )
            
            if response.status_code in (200, 204):
                successful_updates += 1
            else:
                log(f"⚠️ Failed to update {case_number}: {response.status_code}")
            
            # Rate limiting
            time.sleep(0.1)
        
        log(f"✅ Successfully updated {successful_updates}/{len(linkages)} linkages")
        return successful_updates > 0
        
    except Exception as e:
        log(f"❌ Error updating linkages: {e}", "ERROR")
        return False

def verify_improvement():
    """Verify the E letter improvement for Bay County"""
    log("🔍 Verifying Bay County E letter improvement")
    
    try:
        # This would call the evaluation function
        # For now, return framework status
        return {
            "county": "bay",
            "letter": "E",
            "verification_approach": "pencil_dod_evaluate_county('bay')",
            "status": "FRAMEWORK_READY",
            "note": "Requires database connection for actual verification"
        }
        
    except Exception as e:
        log(f"❌ Verification error: {e}", "ERROR")
        return {
            "county": "bay", 
            "letter": "E",
            "status": "ERROR",
            "error": str(e)
        }

def main():
    log("🎯 SHARD-10: Bay County E-linkage Improvement")
    log("Objective: 2396→2495+ parcel links (81.3%→85%+) for Letter E pass")
    
    results = {
        "bay_e_linkage": {
            "start_time": datetime.now().isoformat(),
            "objective": "Improve Bay County parcel linkage from 81.3% to 85%+", 
            "target": "99+ additional parcel links",
            "current_baseline": "2396/2947 linked"
        },
        "gis_discovery": {},
        "linkage_results": {},
        "verification": {},
        "summary": {}
    }
    
    # Phase 1: Discover GIS endpoints
    log("📡 Phase 1: GIS Endpoint Discovery")
    endpoints = discover_bay_gis_endpoints()
    results["gis_discovery"]["endpoints_found"] = len(endpoints)
    results["gis_discovery"]["endpoints"] = endpoints
    
    if not endpoints:
        log("❌ No working GIS endpoints found for Bay County", "ERROR") 
        results["summary"]["status"] = "BLOCKED"
        results["summary"]["blocker"] = "No accessible Bay County GIS endpoints"
        return results
    
    # Phase 2: Find parcel service
    log("🗺️ Phase 2: Parcel Service Discovery")
    parcel_service = find_parcel_service(endpoints)
    results["gis_discovery"]["parcel_service"] = parcel_service
    
    if not parcel_service:
        log("❌ No parcel service found in Bay County GIS", "ERROR")
        results["summary"]["status"] = "BLOCKED"
        results["summary"]["blocker"] = "No parcel service available"
        return results
    
    # Phase 3: Get auction data needing linkage
    log("📊 Phase 3: Auction Data Analysis")
    auction_data = get_bay_auction_data()
    results["linkage_results"]["auctions_to_link"] = len(auction_data)
    
    if not auction_data:
        log("✅ No auctions need parcel linkage (may already be at target)")
        results["summary"]["status"] = "SUCCESS"
        results["summary"]["note"] = "No additional linkages needed"
        return results
    
    # Phase 4: Execute parcel linking
    log("🔗 Phase 4: Parcel Linking Execution")
    linkages = link_parcels_via_address(auction_data, parcel_service)
    results["linkage_results"]["linkages_found"] = len(linkages)
    results["linkage_results"]["linkages"] = linkages
    
    # Phase 5: Update database
    if linkages:
        log("💾 Phase 5: Database Updates")
        update_success = update_parcel_linkages(linkages)
        results["linkage_results"]["update_success"] = update_success
        results["linkage_results"]["records_updated"] = len(linkages) if update_success else 0
    else:
        log("⚠️ No linkages found to update")
        results["linkage_results"]["update_success"] = False
        results["linkage_results"]["records_updated"] = 0
    
    # Phase 6: Verification
    log("🔍 Phase 6: E Letter Verification")
    verification = verify_improvement()
    results["verification"] = verification
    
    # Summary
    linkages_added = results["linkage_results"]["records_updated"]
    results["summary"] = {
        "end_time": datetime.now().isoformat(),
        "status": "SUCCESS" if linkages_added > 0 else "PARTIAL",
        "linkages_added": linkages_added,
        "target_progress": f"{linkages_added}/99 additional links needed",
        "e_letter_status": "Likely improved" if linkages_added > 50 else "Incremental improvement",
        "next_action": "Verify with pencil_dod_evaluate_county('bay')"
    }
    
    # Status report
    if linkages_added >= 99:
        log(f"🎉 TARGET ACHIEVED: {linkages_added} parcel linkages added")
        log("✅ Bay County E letter should now pass (85%+ threshold)")
    elif linkages_added > 0:
        log(f"📈 PROGRESS MADE: {linkages_added} parcel linkages added")
        log(f"🎯 Still need ~{99 - linkages_added} more links for guaranteed pass")
    else:
        log("⚠️ NO LINKAGES ADDED: Check GIS access or data availability")
    
    print("\n" + "="*60)
    print("BAY E-LINKAGE IMPROVEMENT RESULTS")
    print("="*60)
    print(f"Linkages Added: {linkages_added}")
    print(f"Target Progress: {linkages_added}/99")
    print(f"Status: {results['summary']['status']}")
    
    return results

if __name__ == "__main__":
    main()