#!/usr/bin/env python3
"""
SHARD-7 County Discovery Script
Test and discover auction sources for Columbia, Madison, and Suwannee counties
"""
import urllib.request
import urllib.error
import json
import time
from datetime import datetime

# Test counties for SHARD-7
TEST_COUNTIES = {
    'columbia': [
        'https://columbia.realforeclose.com',
        'https://www.columbiaclerk.com/foreclosure',
        'https://www.columbiaclerk.com'
    ],
    'madison': [
        'https://madison.realforeclose.com', 
        'https://www.madisonclerk.com/foreclosure',
        'https://www.madisonclerk.com'
    ],
    'suwannee': [
        'https://suwannee.realforeclose.com',
        'https://www.suwanneeclerk.com/foreclosure', 
        'https://www.suwanneeclerk.com'
    ]
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (BidDeed-SHARD7-Discovery/1.0; contact: support@biddeed.ai)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def test_url(url):
    """Test if URL is accessible and return status info"""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.getcode()
            content_type = response.headers.get('content-type', '')
            content = response.read(1000).decode('utf-8', errors='ignore')  # Read first 1KB
            
            return {
                'url': url,
                'status': status,
                'accessible': True,
                'content_type': content_type,
                'has_auction_keywords': any(kw in content.lower() for kw in ['auction', 'foreclosure', 'sale', 'bid']),
                'content_sample': content[:200] if content else ''
            }
    except urllib.error.HTTPError as e:
        return {
            'url': url,
            'status': e.code,
            'accessible': False,
            'error': f'HTTP {e.code}',
            'has_auction_keywords': False
        }
    except Exception as e:
        return {
            'url': url,
            'status': 0,
            'accessible': False,
            'error': str(e),
            'has_auction_keywords': False
        }

def discover_county_sources():
    """Test all potential URLs for SHARD-7 counties"""
    results = {}
    
    print("=== SHARD-7 County Source Discovery ===")
    print(f"Testing {len(TEST_COUNTIES)} counties...")
    
    for county, urls in TEST_COUNTIES.items():
        print(f"\n[{county.upper()}] Testing {len(urls)} potential sources...")
        county_results = []
        
        for url in urls:
            print(f"  Testing: {url}")
            result = test_url(url)
            county_results.append(result)
            
            if result['accessible']:
                icon = "🔍" if result['has_auction_keywords'] else "✅"
                print(f"    {icon} {result['status']} - {result['content_type']}")
                if result['has_auction_keywords']:
                    print(f"    📋 Found auction keywords in content")
            else:
                print(f"    ❌ {result['error']}")
            
            time.sleep(2)  # Rate limiting
        
        results[county] = county_results
    
    return results

def analyze_results(results):
    """Analyze discovery results and recommend next steps"""
    recommendations = {}
    
    print("\n=== ANALYSIS & RECOMMENDATIONS ===")
    
    for county, county_results in results.items():
        accessible_urls = [r for r in county_results if r['accessible']]
        auction_urls = [r for r in county_results if r.get('has_auction_keywords', False)]
        
        print(f"\n[{county.upper()}]")
        print(f"  Accessible URLs: {len(accessible_urls)}/{len(county_results)}")
        print(f"  URLs with auction keywords: {len(auction_urls)}")
        
        if auction_urls:
            best_url = auction_urls[0]['url']
            platform = 'realforeclose' if 'realforeclose.com' in best_url else 'custom_clerk'
            recommendations[county] = {
                'status': 'READY_FOR_SCRAPING',
                'url': best_url,
                'platform': platform,
                'action': f'Add to COUNTY_SOURCES: {county}: ({platform}, {best_url})'
            }
            print(f"  ✅ RECOMMENDED: {best_url} (platform: {platform})")
        elif accessible_urls:
            recommendations[county] = {
                'status': 'NEEDS_INVESTIGATION', 
                'url': accessible_urls[0]['url'],
                'platform': 'unknown',
                'action': 'Manual inspection needed - site accessible but no clear auction content'
            }
            print(f"  🔍 INVESTIGATE: {accessible_urls[0]['url']} (accessible but unclear)")
        else:
            recommendations[county] = {
                'status': 'NO_ONLINE_SOURCE',
                'url': None,
                'platform': None,
                'action': 'Check for in-person auctions or alternative clerk websites'
            }
            print(f"  ❌ NO SOURCE: All tested URLs inaccessible")
    
    return recommendations

def generate_cairn_updates(recommendations):
    """Generate code snippets to add to cairn_multi_county_scraper.py"""
    updates = []
    
    print("\n=== CAIRN SCRAPER UPDATES ===")
    print("Add these lines to COUNTY_SOURCES in cairn_multi_county_scraper.py:")
    
    for county, rec in recommendations.items():
        if rec['status'] == 'READY_FOR_SCRAPING':
            line = f"    '{county}': ('{rec['platform']}', '{rec['url']}'),"
            updates.append(line)
            print(f"  {line}")
    
    if updates:
        print(f"\nTotal counties ready to add: {len(updates)}")
    else:
        print("  No counties ready for immediate scraping")
    
    return updates

if __name__ == "__main__":
    start_time = datetime.now()
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run discovery
    results = discover_county_sources()
    
    # Analyze and recommend
    recommendations = analyze_results(results)
    
    # Generate code updates
    cairn_updates = generate_cairn_updates(recommendations)
    
    # Save results
    output_data = {
        'discovery_timestamp': start_time.isoformat(),
        'raw_results': results,
        'recommendations': recommendations,
        'cairn_updates': cairn_updates
    }
    
    with open('shard7_discovery_results.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n=== SUMMARY ===")
    ready_count = sum(1 for r in recommendations.values() if r['status'] == 'READY_FOR_SCRAPING')
    investigate_count = sum(1 for r in recommendations.values() if r['status'] == 'NEEDS_INVESTIGATION')
    no_source_count = sum(1 for r in recommendations.values() if r['status'] == 'NO_ONLINE_SOURCE')
    
    print(f"Ready for scraping: {ready_count}")
    print(f"Need investigation: {investigate_count}")
    print(f"No online source: {no_source_count}")
    print(f"Results saved to: shard7_discovery_results.json")
    print(f"Duration: {datetime.now() - start_time}")