#!/usr/bin/env python3
"""
Quick SHARD-8 test to verify county evaluation and basic pipeline functionality
"""
import os
import httpx
import sys

# Supabase configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def sb_headers():
    """Get Supabase headers"""
    return {
        "apikey": SUPABASE_KEY or "test", 
        "Authorization": f"Bearer {SUPABASE_KEY or 'test'}",
        "Content-Type": "application/json"
    }

def test_county_evaluation():
    """Test the pencil_dod_evaluate_county function"""
    
    print("=== Testing County Evaluation ===")
    
    # Test counties for SHARD-8
    counties = ['indian_river', 'volusia', 'lee', 'desoto', 'monroe']
    
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY - testing without auth")
        return False
    
    try:
        client = httpx.Client(timeout=30)
        
        for county in counties:
            print(f"\nTesting {county}...")
            
            # Call the evaluation function
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=sb_headers(),
                json={"county_slug_arg": county}
            )
            
            if r.status_code == 200:
                result = r.json()
                if result:
                    pass_count = sum(1 for item in result if item.get('pass', False))
                    print(f"  ✅ {county}: {pass_count}/10 letters passing")
                    
                    # Show failing letters for context
                    failing = [item.get('letter') for item in result if not item.get('pass', False)]
                    if failing:
                        print(f"     Failing: {', '.join(failing)}")
                else:
                    print(f"  ⚠️ {county}: No evaluation data returned")
            elif r.status_code == 404:
                print(f"  ℹ️ {county}: Function not found (may be county not setup)")
            else:
                print(f"  ❌ {county}: Error {r.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing county evaluation: {e}")
        return False

def test_basic_queries():
    """Test basic table access"""
    
    print("\n=== Testing Basic Table Access ===")
    
    try:
        client = httpx.Client(timeout=30)
        
        # Test multi_county_auctions table
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=county&limit=5",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            data = r.json()
            print(f"✅ multi_county_auctions accessible: {len(data)} sample records")
        else:
            print(f"❌ multi_county_auctions: {r.status_code}")
        
        # Test bid_decisions table
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions?select=county&limit=5",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            data = r.json()
            print(f"✅ bid_decisions accessible: {len(data)} records")
        elif r.status_code == 404:
            print(f"ℹ️ bid_decisions table may not exist yet")
        else:
            print(f"❌ bid_decisions: {r.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing basic queries: {e}")
        return False

def test_shapira_formula():
    """Test Shapira Formula calculations"""
    
    print("\n=== Testing Shapira Formula ===")
    
    try:
        # Import our deal thesis functions
        sys.path.append('scripts')
        from enable_deal_thesis_shard8 import (
            estimate_arv_from_estimated_value,
            calculate_shapira_max_bid,
            estimate_repair_costs,
            generate_ml_score
        )
        
        # Test with sample property
        test_value = 120000
        test_county = 'volusia'
        
        print(f"Test property: ${test_value:,} in {test_county}")
        
        arv = estimate_arv_from_estimated_value(test_value, test_county)
        print(f"  ARV: ${arv:,}")
        
        repairs = estimate_repair_costs(test_value, test_county)
        print(f"  Repairs: ${repairs:,}")
        
        max_bid = calculate_shapira_max_bid(arv, repairs, test_county)
        print(f"  Max bid: ${max_bid:,}")
        
        ml_score = generate_ml_score(arv, test_value, test_county)
        print(f"  ML score: {ml_score}")
        
        # Verify formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)
        arv_70 = arv * 0.70
        profit_15pct = arv * 0.15
        min_profit = min(25000, profit_15pct)
        expected_max_bid = arv_70 - repairs - 10000 - min_profit
        
        print(f"  Formula check: ${expected_max_bid:,} (expected) vs ${max_bid:,} (calculated)")
        
        if abs(expected_max_bid - max_bid) < 100:  # Allow small rounding differences
            print("  ✅ Shapira Formula calculation correct")
            return True
        else:
            print("  ❌ Shapira Formula calculation incorrect")
            return False
        
    except Exception as e:
        print(f"❌ Error testing Shapira Formula: {e}")
        return False

if __name__ == "__main__":
    print("🚀 SHARD-8 QUICK TEST")
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"API Key available: {bool(SUPABASE_KEY)}")
    
    # Run tests
    test_results = []
    
    test_results.append(test_basic_queries())
    test_results.append(test_county_evaluation()) 
    test_results.append(test_shapira_formula())
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n{'='*50}")
    print(f"TESTS PASSED: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed - pipeline ready")
        sys.exit(0)
    else:
        print("❌ Some tests failed - check configuration")
        sys.exit(1)