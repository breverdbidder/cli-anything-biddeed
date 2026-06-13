#!/usr/bin/env python3
"""
Simple database connection test for SHARD-20
"""
import os
import requests

# Check environment
print("Environment check:")
print(f"SUPABASE_SERVICE_KEY present: {'Yes' if os.environ.get('SUPABASE_SERVICE_KEY') else 'No'}")

if not os.environ.get('SUPABASE_SERVICE_KEY'):
    print("No database credentials available. This is expected in Claude Code environment.")
    print("Proceeding with analysis based on the briefing data...")
    
    # Use the data from the briefing to analyze priorities
    briefing_data = {
        'charlotte': {
            'score': 3,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 249},
                'B': {'grade': 'FAIL', 'metric': None},
                'C': {'grade': 'FAIL', 'metric': 10.1},
                'D': {'grade': 'PASS', 'metric': 97.4},
                'E': {'grade': 'FAIL', 'metric': 43.8},
                'F': {'grade': 'FAIL', 'metric': 2.1},
                'G': {'grade': 'FAIL', 'metric': None},
                'H': {'grade': 'PASS', 'metric': 26.0},
                'I': {'grade': 'FAIL', 'metric': None},
                'J': {'grade': 'FAIL', 'metric': 0.0}
            }
        },
        'citrus': {
            'score': 3,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 1666},
                'B': {'grade': 'FAIL', 'metric': None},
                'C': {'grade': 'FAIL', 'metric': 9.5},
                'D': {'grade': 'FAIL', 'metric': 75.3},
                'E': {'grade': 'PASS', 'metric': 95.3},
                'F': {'grade': 'FAIL', 'metric': 6.1},
                'G': {'grade': 'FAIL', 'metric': None},
                'H': {'grade': 'PASS', 'metric': 13.6},
                'I': {'grade': 'FAIL', 'metric': None},
                'J': {'grade': 'FAIL', 'metric': 0.0}
            }
        },
        'broward': {
            'score': 2,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 10308},
                'B': {'grade': 'FAIL', 'metric': None},
                'C': {'grade': 'FAIL', 'metric': 19.4},
                'D': {'grade': 'FAIL', 'metric': 47.7},
                'E': {'grade': 'FAIL', 'metric': 20.6},
                'F': {'grade': 'FAIL', 'metric': 2.5},
                'G': {'grade': 'FAIL', 'metric': None},
                'H': {'grade': 'PASS', 'metric': 0.2},
                'I': {'grade': 'FAIL', 'metric': None},
                'J': {'grade': 'FAIL', 'metric': 0.0}
            }
        }
    }
    
    print("\n" + "="*60)
    print("SHARD-20 ANALYSIS FROM BRIEFING DATA")
    print("="*60)
    
    # Analyze failing letters across counties
    failing_by_letter = {}
    for county, data in briefing_data.items():
        for letter, info in data['metrics'].items():
            if info['grade'] == 'FAIL':
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append(county)
    
    # Priority order from briefing
    priority_letters = ['C', 'D', 'J', 'B', 'G', 'I', 'E', 'F']
    
    print("\n📊 FAILING LETTERS ACROSS SHARD:")
    for letter in priority_letters:
        counties = failing_by_letter.get(letter, [])
        if counties:
            print(f"**{letter}**: {', '.join(counties)} ({len(counties)} counties)")
    
    print(f"\n📊 COUNTY SCORES:")
    for county, data in briefing_data.items():
        score = data['score']
        failing = [letter for letter, info in data['metrics'].items() if info['grade'] == 'FAIL']
        print(f"**{county}**: {score}/10 - Failing: {', '.join(failing)}")
    
    print(f"\n" + "="*60)
    print("CRITERION-PARALLEL STRATEGY")
    print("="*60)
    
    print("\n🎯 **Priority Analysis:**")
    print("1. **J (0 counties pass)** - Build bid_decisions pipeline")
    print("   - All 3 counties fail: charlotte, citrus, broward") 
    print("   - Highest impact: fleet-wide fix needed")
    
    print("2. **B (0 counties pass)** - Fix verified outcomes")
    print("   - All 3 counties fail with null metrics")
    print("   - Root cause: independent outcome verification missing")
    
    print("3. **C/D (varying performance)** - Parity fixes") 
    print("   - C: all 3 fail (10.1%, 9.5%, 19.4%)")
    print("   - D: 2 fail (citrus 75.3%, broward 47.7%)")
    print("   - Property matching issues")
    
    print("4. **G/I (structural blockers)** - Zoning + property cards")
    print("   - All counties null metrics = infrastructure missing")
    
    print("\n📝 **Recommended Session Plan:**")
    print("1. **J GENERATOR** (highest leverage - 3 counties)")
    print("2. **B RECONCILIATION** (fleet-wide infrastructure)")  
    print("3. **C/D PARITY** (PropertyOnion vs official records)")
    print("4. **E LINKAGE** (parcel_id fixes for broward)")
    print("5. **G/I SUBSTRATE** (if time permits)")

else:
    # If credentials are available, test actual connection
    print("Testing database connection...")
    
    SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
    SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{SUPABASE_URL}/rest/v1/audit_log", headers=headers, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            print("✅ Database connection successful")
            print("Run the full verification script to get current metrics")
        else:
            print(f"❌ Connection failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Connection error: {e}")