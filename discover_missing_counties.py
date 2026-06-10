#!/usr/bin/env python3
"""
Discover foreclosure URLs for bradford, glades, levy counties
These are missing from COUNTY_SOURCES in cairn_multi_county_scraper.py
"""
import httpx

missing_counties = ['bradford', 'glades', 'levy']

# Standard foreclosure URL patterns for Florida counties
url_patterns = [
    'https://{}.realforeclose.com',
    'https://www.{}clerk.com/foreclosure', 
    'https://www.{}countyclerk.com/foreclosure',
    'https://{}clerkofcourt.com/foreclosure',
    'https://{}clerk.org/foreclosure',
]

def test_url(url, county):
    """Test if a foreclosure URL is valid"""
    try:
        client = httpx.Client(timeout=10)
        r = client.get(url, follow_redirects=True)
        print(f"{county}: {url} -> {r.status_code} ({len(r.text)} bytes)")
        if r.status_code == 200 and 'foreclosure' in r.text.lower():
            return True
        return False
    except Exception as e:
        print(f"{county}: {url} -> ERROR: {e}")
        return False

print("=== Discovering foreclosure URLs for missing counties ===")

for county in missing_counties:
    print(f"\n--- {county.upper()} ---")
    found_url = None
    
    for pattern in url_patterns:
        url = pattern.format(county)
        if test_url(url, county):
            found_url = url
            break
    
    if found_url:
        print(f"✅ FOUND: {county} -> {found_url}")
        print(f"    '{county}': ('realforeclose', '{found_url}'),")
    else:
        print(f"❌ NO VALID URL FOUND for {county}")

print("\n=== Summary ===")
print("Add these lines to COUNTY_SOURCES in cairn_multi_county_scraper.py")