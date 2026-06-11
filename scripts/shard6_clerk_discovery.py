#!/usr/bin/env python3
"""
SHARD-6 Clerk Endpoint Discovery
Research official records systems for highlands, sumter, jackson, calhoun, liberty

Identifies:
- Official clerk websites
- AcclaimWeb endpoints (if available)
- Alternative official records portals
- Document search capabilities for Letter B verification
"""
import sys
import time
import httpx
from urllib.parse import urljoin
from dataclasses import dataclass
from typing import List, Dict, Optional

# Install httpx if not available
try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

@dataclass
class ClerkEndpoint:
    county: str
    co_no: int
    name: str
    base_url: str
    records_portal: Optional[str] = None
    acclaim_web: Optional[str] = None
    search_capability: Optional[str] = None
    doc_types: List[str] = None
    status: str = "unknown"
    notes: str = ""

def test_endpoint(url: str, timeout: int = 10) -> tuple[int, str]:
    """Test if an endpoint is accessible"""
    try:
        client = httpx.Client(timeout=timeout, follow_redirects=True)
        response = client.get(url)
        client.close()
        return response.status_code, response.headers.get('server', '')
    except Exception as e:
        return 0, str(e)

def check_acclaim_web(base_url: str) -> Optional[str]:
    """Check if county uses AcclaimWeb system"""
    acclaim_paths = [
        "/AcclaimWeb/",
        "/acclaimweb/",
        "/acclaim/",
        "/Acclaim/",
        "/records/acclaim/"
    ]
    
    for path in acclaim_paths:
        url = urljoin(base_url, path)
        status, _ = test_endpoint(url)
        if status == 200:
            return url
    return None

def discover_records_portal(base_url: str) -> Optional[str]:
    """Discover official records portal URL"""
    portal_paths = [
        "/records/",
        "/official-records/",
        "/public-records/",
        "/Records/",
        "/OfficialRecords/",
        "/PublicRecords/",
        "/clerk-records/",
        "/documents/"
    ]
    
    for path in portal_paths:
        url = urljoin(base_url, path)
        status, _ = test_endpoint(url)
        if status == 200:
            return url
    return None

def discover_county_clerk_endpoints() -> List[ClerkEndpoint]:
    """Discover clerk endpoints for SHARD-6 counties"""
    
    # Based on FL county naming patterns and known clerk URL schemes
    counties = [
        ClerkEndpoint(
            county="highlands",
            co_no=38,
            name="Highlands County Clerk",
            base_url="https://www.highlandsclerk.org"
        ),
        ClerkEndpoint(
            county="sumter",
            co_no=70,
            name="Sumter County Clerk",
            base_url="https://www.sumtercountyfl.gov/clerk"
        ),
        ClerkEndpoint(
            county="jackson",
            co_no=42,
            name="Jackson County Clerk",
            base_url="https://www.jacksoncountyclerk.com"
        ),
        ClerkEndpoint(
            county="calhoun", 
            co_no=17,
            name="Calhoun County Clerk",
            base_url="https://www.calhounclerk.com"
        ),
        ClerkEndpoint(
            county="liberty",
            co_no=49,
            name="Liberty County Clerk",
            base_url="https://www.libertyclerk.com"
        )
    ]
    
    # Alternative URL patterns to try
    alt_patterns = [
        "https://{county}clerk.com",
        "https://www.{county}clerk.com", 
        "https://{county}.realforeclose.com",
        "https://www.{county}countyfl.gov",
        "https://www.{county}county.org",
        "https://{county}county.gov",
        "https://clerk.{county}county.gov"
    ]
    
    print("🔍 Discovering SHARD-6 clerk endpoints...")
    
    for endpoint in counties:
        print(f"\n--- {endpoint.county.upper()} COUNTY ---")
        
        # Test primary URL
        print(f"Testing primary: {endpoint.base_url}")
        status, server = test_endpoint(endpoint.base_url)
        
        if status == 200:
            endpoint.status = "accessible"
            print(f"✅ Primary URL accessible (status: {status})")
            
            # Check for AcclaimWeb
            acclaim_url = check_acclaim_web(endpoint.base_url)
            if acclaim_url:
                endpoint.acclaim_web = acclaim_url
                print(f"✅ AcclaimWeb found: {acclaim_url}")
            else:
                print("❌ No AcclaimWeb detected")
            
            # Check for records portal
            records_url = discover_records_portal(endpoint.base_url)
            if records_url:
                endpoint.records_portal = records_url
                print(f"✅ Records portal found: {records_url}")
            else:
                print("⚠️ No obvious records portal found")
                
        else:
            print(f"❌ Primary URL failed (status: {status})")
            endpoint.status = "failed"
            
            # Try alternative URL patterns
            print("Trying alternative patterns...")
            for pattern in alt_patterns:
                alt_url = pattern.format(county=endpoint.county)
                alt_status, _ = test_endpoint(alt_url)
                
                if alt_status == 200:
                    endpoint.base_url = alt_url
                    endpoint.status = "alternative_found"
                    print(f"✅ Alternative found: {alt_url}")
                    
                    # Recheck for AcclaimWeb and records
                    acclaim_url = check_acclaim_web(alt_url)
                    if acclaim_url:
                        endpoint.acclaim_web = acclaim_url
                        print(f"✅ AcclaimWeb found: {acclaim_url}")
                    
                    records_url = discover_records_portal(alt_url)
                    if records_url:
                        endpoint.records_portal = records_url
                        print(f"✅ Records portal found: {records_url}")
                    break
            else:
                print("❌ No accessible alternatives found")
        
        # Brief pause between counties
        time.sleep(1)
    
    return counties

def analyze_capabilities(endpoints: List[ClerkEndpoint]) -> Dict:
    """Analyze discovered endpoints for Letter B capability"""
    
    analysis = {
        "total_counties": len(endpoints),
        "accessible_counties": 0,
        "acclaim_web_counties": 0,
        "records_portal_counties": 0,
        "letter_b_ready": [],
        "needs_manual_research": [],
        "implementation_strategy": {}
    }
    
    for endpoint in endpoints:
        if endpoint.status in ["accessible", "alternative_found"]:
            analysis["accessible_counties"] += 1
            
            if endpoint.acclaim_web:
                analysis["acclaim_web_counties"] += 1
                analysis["letter_b_ready"].append({
                    "county": endpoint.county,
                    "strategy": "acclaim_web_scraping",
                    "endpoint": endpoint.acclaim_web,
                    "estimated_complexity": "low",
                    "pattern": "brevard_acclaim_pattern"
                })
                
            elif endpoint.records_portal:
                analysis["records_portal_counties"] += 1
                analysis["letter_b_ready"].append({
                    "county": endpoint.county,
                    "strategy": "portal_scraping", 
                    "endpoint": endpoint.records_portal,
                    "estimated_complexity": "medium",
                    "pattern": "custom_portal_scraper"
                })
                
            else:
                analysis["needs_manual_research"].append({
                    "county": endpoint.county,
                    "base_url": endpoint.base_url,
                    "next_steps": "manual_site_exploration"
                })
        else:
            analysis["needs_manual_research"].append({
                "county": endpoint.county,
                "issue": "no_accessible_endpoint",
                "next_steps": "contact_clerk_office"
            })
    
    return analysis

def generate_implementation_plan(analysis: Dict) -> str:
    """Generate Letter B implementation plan"""
    
    plan = []
    plan.append("="*60)
    plan.append("SHARD-6 LETTER B IMPLEMENTATION PLAN")
    plan.append("="*60)
    
    plan.append(f"\nSUMMARY:")
    plan.append(f"- Total counties: {analysis['total_counties']}")
    plan.append(f"- Accessible endpoints: {analysis['accessible_counties']}")
    plan.append(f"- AcclaimWeb counties: {analysis['acclaim_web_counties']}")
    plan.append(f"- Portal counties: {analysis['records_portal_counties']}")
    
    if analysis["letter_b_ready"]:
        plan.append(f"\nREADY FOR IMPLEMENTATION:")
        for county_plan in analysis["letter_b_ready"]:
            county = county_plan["county"]
            strategy = county_plan["strategy"]
            endpoint = county_plan["endpoint"]
            complexity = county_plan["estimated_complexity"]
            
            plan.append(f"  {county.upper()}:")
            plan.append(f"    Strategy: {strategy}")
            plan.append(f"    Endpoint: {endpoint}")
            plan.append(f"    Complexity: {complexity}")
    
    if analysis["needs_manual_research"]:
        plan.append(f"\nNEEDS MANUAL RESEARCH:")
        for item in analysis["needs_manual_research"]:
            county = item["county"]
            next_steps = item["next_steps"]
            
            plan.append(f"  {county.upper()}: {next_steps}")
    
    plan.append(f"\nNEXT ACTIONS:")
    plan.append(f"1. Implement AcclaimWeb scrapers first (lowest complexity)")
    plan.append(f"2. Build custom portal scrapers for non-Acclaim counties")
    plan.append(f"3. Manual research for inaccessible endpoints")
    plan.append(f"4. Wire scrapers to cron/GHA executors")
    plan.append(f"5. Test with recent case numbers and verify outcomes")
    
    return "\n".join(plan)

def main():
    """Main discovery execution"""
    print("🚀 SHARD-6 CLERK ENDPOINT DISCOVERY")
    print("Researching official records systems for Letter B verification")
    
    # Discover endpoints
    endpoints = discover_county_clerk_endpoints()
    
    # Analyze capabilities  
    analysis = analyze_capabilities(endpoints)
    
    # Generate plan
    plan = generate_implementation_plan(analysis)
    
    print("\n" + plan)
    
    # Output JSON summary for use by implementation scripts
    import json
    summary = {
        "discovery_timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "endpoints": [
            {
                "county": ep.county,
                "co_no": ep.co_no,
                "base_url": ep.base_url,
                "acclaim_web": ep.acclaim_web,
                "records_portal": ep.records_portal,
                "status": ep.status
            }
            for ep in endpoints
        ],
        "analysis": analysis
    }
    
    with open("shard6_clerk_discovery.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ Discovery complete. Results saved to shard6_clerk_discovery.json")
    
    return len(analysis["letter_b_ready"]) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)