#!/usr/bin/env python3
"""Test database connectivity to Supabase for gold standard session."""

import os
import sys

def test_connectivity():
    """Test basic Supabase connectivity and check gold standard tables."""
    
    # Check environment variables
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    
    print("=== SUPABASE CONNECTIVITY TEST ===")
    print()
    
    if not sb_url:
        print("❌ SUPABASE_URL not set")
        return False
    
    if not sb_key:
        print("❌ SUPABASE_SERVICE_KEY/SUPABASE_KEY not set")
        return False
        
    print(f"✓ SUPABASE_URL: {sb_url}")
    print(f"✓ SUPABASE_KEY: Set (length: {len(sb_key)})")
    print()
    
    # Test basic HTTP connectivity
    print("Testing basic HTTP connectivity...")
    try:
        import httpx
        
        headers = {
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json"
        }
        
        # Test basic REST endpoint
        response = httpx.get(f"{sb_url}/rest/v1/", headers=headers, timeout=10.0)
        print(f"✓ REST API reachable (status: {response.status_code})")
        
        # Test specific tables mentioned in CLAUDE.md
        tables_to_check = [
            "multi_county_auctions", 
            "gold_standard_county_status",
            "activities",
            "insights", 
            "daily_metrics"
        ]
        
        print("\nChecking gold standard tables...")
        for table in tables_to_check:
            try:
                resp = httpx.get(
                    f"{sb_url}/rest/v1/{table}?limit=1",
                    headers=headers,
                    timeout=10.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"✓ {table}: accessible (sample row count: {len(data)})")
                else:
                    print(f"⚠ {table}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"❌ {table}: {type(e).__name__}: {str(e)[:100]}")
        
        # Test the evaluation function mentioned in the brief
        print("\nTesting evaluation function...")
        try:
            eval_resp = httpx.post(
                f"{sb_url}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=headers,
                json={"county_name": "brevard"},
                timeout=10.0
            )
            if eval_resp.status_code == 200:
                result = eval_resp.json()
                print(f"✓ pencil_dod_evaluate_county function: accessible")
                print(f"  Sample result for 'brevard': {result}")
            else:
                print(f"⚠ pencil_dod_evaluate_county: HTTP {eval_resp.status_code}")
        except Exception as e:
            print(f"❌ pencil_dod_evaluate_county: {type(e).__name__}: {str(e)[:100]}")
            
        # Test multi_county_auctions table with case_number search
        print("\nTesting case_number search capability...")
        try:
            case_resp = httpx.get(
                f"{sb_url}/rest/v1/multi_county_auctions?case_number=like.*&limit=1",
                headers=headers,
                timeout=10.0
            )
            if case_resp.status_code == 200:
                data = case_resp.json()
                print(f"✓ case_number search: works ({len(data)} sample results)")
            else:
                print(f"⚠ case_number search: HTTP {case_resp.status_code}")
        except Exception as e:
            print(f"❌ case_number search: {type(e).__name__}: {str(e)[:100]}")
            
        return True
        
    except ImportError:
        print("❌ httpx not available - install with: pip install httpx")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_connectivity()
    sys.exit(0 if success else 1)