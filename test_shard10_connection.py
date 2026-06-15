#!/usr/bin/env python3
"""
Database connection test for SHARD-10: polk, flagler, okeechobee, franklin, union
"""
import os
import requests

def test_connection():
    """Test database connection and analyze SHARD-10 county metrics"""
    
    print("Environment check:")
    print(f"SUPABASE_SERVICE_KEY present: {'Yes' if os.environ.get('SUPABASE_SERVICE_KEY') else 'No'}")

    # SHARD-10 briefing data from issue
    shard10_data = {
        'polk': {
            'score': 2,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 10553},
                'B': {'grade': 'FAIL', 'metric': None},
                'C': {'grade': 'FAIL', 'metric': 13.3},
                'D': {'grade': 'FAIL', 'metric': 58.9},
                'E': {'grade': 'FAIL', 'metric': 68.8},
                'F': {'grade': 'FAIL', 'metric': 4.0},
                'G': {'grade': 'FAIL', 'metric': None},
                'H': {'grade': 'PASS', 'metric': 6.0},
                'I': {'grade': 'FAIL', 'metric': None},
                'J': {'grade': 'FAIL', 'metric': 0.0}
            }
        },
        'flagler': {
            'score': 1,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 43},
                'B': {'grade': 'FAIL', 'metric': None},
                'C': {'grade': 'FAIL', 'metric': 10.9},
                'D': {'grade': 'PASS', 'metric': 90.6},
                'E': {'grade': 'FAIL', 'metric': 56.0},
                'F': {'grade': 'FAIL', 'metric': 8.8},
                'G': {'grade': 'FAIL', 'metric': None},
                'H': {'grade': 'FAIL', 'metric': 240.9},
                'I': {'grade': 'FAIL', 'metric': None},
                'J': {'grade': 'FAIL', 'metric': 0.0}
            }
        },
        'okeechobee': {
            'score': 1,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 164},
                'B': {'grade': 'FAIL', 'metric': None},
                'C': {'grade': 'FAIL', 'metric': 17.3},
                'D': {'grade': 'FAIL', 'metric': 74.2},
                'E': {'grade': 'FAIL', 'metric': 85.6},
                'F': {'grade': 'FAIL', 'metric': 0.0},
                'G': {'grade': 'FAIL', 'metric': None},
                'H': {'grade': 'FAIL', 'metric': 433.0},
                'I': {'grade': 'FAIL', 'metric': None},
                'J': {'grade': 'FAIL', 'metric': 0.0}
            }
        },
        'franklin': {
            'score': 0,
            'metrics': {
                'A': {'grade': 'FAIL', 'metric': 0},
                'B': {'grade': 'FAIL', 'metric': None},
                'C': {'grade': 'FAIL', 'metric': None},
                'D': {'grade': 'FAIL', 'metric': None},
                'E': {'grade': 'FAIL', 'metric': None},
                'F': {'grade': 'FAIL', 'metric': None},
                'G': {'grade': 'FAIL', 'metric': None},
                'H': {'grade': 'FAIL', 'metric': None},
                'I': {'grade': 'FAIL', 'metric': None},
                'J': {'grade': 'FAIL', 'metric': None}
            }
        },
        'union': {
            'score': 0,
            'metrics': {
                'A': {'grade': 'FAIL', 'metric': 0},
                'B': {'grade': 'FAIL', 'metric': None},
                'C': {'grade': 'FAIL', 'metric': None},
                'D': {'grade': 'FAIL', 'metric': None},
                'E': {'grade': 'FAIL', 'metric': None},
                'F': {'grade': 'FAIL', 'metric': None},
                'G': {'grade': 'FAIL', 'metric': None},
                'H': {'grade': 'FAIL', 'metric': None},
                'I': {'grade': 'FAIL', 'metric': None},
                'J': {'grade': 'FAIL', 'metric': None}
            }
        }
    }
    
    print("\n" + "="*60)
    print("SHARD-10 ANALYSIS FROM BRIEFING DATA")
    print("="*60)
    
    # Analyze failing letters across counties
    failing_by_letter = {}
    for county, data in shard10_data.items():
        for letter, info in data['metrics'].items():
            if info['grade'] == 'FAIL':
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append(county)
    
    print("\n📊 FAILING LETTERS ACROSS SHARD:")
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        counties = failing_by_letter.get(letter, [])
        if counties:
            print(f"**{letter}**: {', '.join(counties)} ({len(counties)} counties)")
    
    print(f"\n📊 COUNTY SCORES:")
    for county, data in shard10_data.items():
        score = data['score']
        failing = [letter for letter, info in data['metrics'].items() if info['grade'] == 'FAIL']
        print(f"**{county}**: {score}/10 - Failing: {', '.join(failing)}")
    
    print(f"\n" + "="*60)
    print("PRIORITY WORK IDENTIFICATION")
    print("="*60)
    
    print("\n🎯 **Highest Impact Targets:**")
    print("1. **A LANE SETUP** - franklin (0) & union (0) completely offline")
    print("   - Zero foreclosure data ingestion")
    print("   - Configure pipeline.counties entries first")
    
    print("2. **H FRESHNESS** - flagler (240.9h) & okeechobee (433h) > 48h SLA")
    print("   - Data over 10+ days old")
    print("   - Re-run scrapers or fix automation")
    
    print("3. **J GENERATOR** - All 5 counties fail (0.0%)")
    print("   - bid_decisions pipeline completely missing")
    print("   - Shapira Formula integration needed")
    
    print("4. **C/D PARITY** - Poor matching across active counties")
    print("   - polk: 13.3%/58.9%, flagler: 10.9%/90.6%, okeechobee: 17.3%/74.2%")
    print("   - PropertyOnion litmus vs official records gap")
    
    print("\n📝 **SHARD-10 SESSION STRATEGY:**")
    print("**Phase 1: Basic Infrastructure (franklin, union)**")
    print("- Configure A-lane foreclosure platform entries")
    print("- Verify data sources and scraping endpoints")
    print("")
    print("**Phase 2: Fix Data Staleness**") 
    print("- flagler H: 240.9h → target <48h")
    print("- okeechobee H: 433h → target <48h")
    print("")
    print("**Phase 3: High-Impact Criterion Fixes**")
    print("- J: Build Shapira bid_decisions pipeline (all 5 counties)")
    print("- C/D: PropertyOnion parity audits")
    print("")
    print("**Phase 4: E/F Linkage & Tier1 (if time)**")
    print("- polk E: 68.8% → 95%+ parcel linkage")
    print("- polk F: 4.0% → improve tier1 sold verification")
    
    # If we have credentials, test actual connection
    if os.environ.get('SUPABASE_SERVICE_KEY'):
        print("\n" + "="*60)
        print("TESTING LIVE DATABASE CONNECTION")
        print("="*60)
        
        SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
        SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            # Test connection with a simple query
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/pipeline_counties", 
                headers=headers, 
                params={"limit": "1"}, 
                timeout=10
            )
            if response.status_code == 200:
                print("✅ Database connection successful")
                return True
            else:
                print(f"❌ Connection failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    else:
        print("\n(No database credentials - using briefing analysis)")
        return False

if __name__ == "__main__":
    test_connection()