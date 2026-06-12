#!/usr/bin/env python3
"""
SHARD 19: Gold Standard Verification for BREVARD and DUVAL Counties
Run 19 autonomous session - verify current metrics and implement fixes per sprint order
"""
import os
import sys
import json
from datetime import datetime, timezone

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available - installing...")
    os.system("pip install httpx")
    import httpx

# Setup Supabase connection using environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    print("Expected: SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable")
    sys.exit(1)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        print(f"Connection status: {r.status_code}")
        if r.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function as specified in the issue
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ County evaluation for {county_slug}:")
            metrics = {}
            if isinstance(result, list) and len(result) > 0:
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    print(f"  {letter}: {status} {metric}")
                    metrics[letter] = {
                        'metric': metric,
                        'pass': letter_data.get('pass'),
                        'details': letter_data
                    }
            return metrics
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def run_sql_query(query, params=None):
    """Execute a raw SQL query via RPC"""
    try:
        client = httpx.Client(timeout=120)
        
        # Set statement timeout as mandated in the issue
        timeout_query = "SET statement_timeout = 0;"
        
        # Execute the timeout setting first
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/execute_sql",
            headers=sb_headers(),
            json={"query": timeout_query}
        )
        
        # Now execute the main query  
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/execute_sql",
            headers=sb_headers(),
            json={"query": query, "params": params or {}}
        )
        
        if r.status_code == 200:
            return r.json()
        else:
            print(f"❌ SQL query failed: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error executing SQL: {e}")
        return None

def analyze_sprint_priorities(county_metrics):
    """Analyze current metrics and determine sprint priorities per issue directives"""
    priorities = {}
    
    for county, metrics in county_metrics.items():
        county_priorities = []
        
        if county == 'brevard':
            # BREVARD Sprint Order: C/D root cause, J generator, G hit list, B reconciliation
            if metrics.get('C', {}).get('metric', 0) < 95:
                county_priorities.append(f"C: PropertyOnion coverage issue (current: {metrics.get('C', {}).get('metric', 'N/A')})")
            if metrics.get('D', {}).get('metric', 0) < 95:
                county_priorities.append(f"D: Parity matching (current: {metrics.get('D', {}).get('metric', 'N/A')})")
            if metrics.get('J', {}).get('metric', 0) < 95:
                county_priorities.append(f"J: Deal thesis generator (current: {metrics.get('J', {}).get('metric', 'N/A')})")
            if metrics.get('G', {}).get('metric', 0) < 95:
                county_priorities.append(f"G: Zoning density/FAR hit list (current: {metrics.get('G', {}).get('metric', 'N/A')})")
            if metrics.get('B', {}).get('metric', 0) > 105:
                county_priorities.append(f"B: ANOMALY reconciliation (current: {metrics.get('B', {}).get('metric', 'N/A')} > 105%)")
                
        elif county == 'duval':
            # DUVAL Sprint Order: G+I substrate, C/D root cause, J generator, B reconciliation
            if metrics.get('G', {}).get('metric') is None:
                county_priorities.append("G: Zoning substrate build (NULL - missing zoning data)")
            if metrics.get('I', {}).get('metric') is None:
                county_priorities.append("I: Property card substrate (NULL - missing zoning data)")
            if metrics.get('C', {}).get('metric', 0) < 95:
                county_priorities.append(f"C: PropertyOnion coverage issue (current: {metrics.get('C', {}).get('metric', 'N/A')})")
            if metrics.get('D', {}).get('metric', 0) < 95:
                county_priorities.append(f"D: Parity matching (current: {metrics.get('D', {}).get('metric', 'N/A')})")
            if metrics.get('J', {}).get('metric', 0) < 95:
                county_priorities.append(f"J: Deal thesis generator (current: {metrics.get('J', {}).get('metric', 'N/A')})")
            if metrics.get('B', {}).get('metric', 0) > 105:
                county_priorities.append(f"B: ANOMALY reconciliation (current: {metrics.get('B', {}).get('metric', 'N/A')} > 105%)")
        
        priorities[county] = county_priorities
        
    return priorities

def main():
    print("=== SHARD 19 Gold Standard Verification ===")
    print("ASSIGNED COUNTIES: brevard, duval")
    print("RUN 19: Autonomous 6-hour session")
    print()
    
    # Test database connection
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Current County Metrics (LIVE DATABASE VERIFICATION) ===")
    
    # Our assigned counties per the issue
    assigned_counties = ['brevard', 'duval']
    county_metrics = {}
    
    for county in assigned_counties:
        print(f"\n--- {county.upper()} ---")
        metrics = evaluate_county_current(county)
        if metrics:
            county_metrics[county] = metrics
        else:
            print(f"❌ Failed to retrieve metrics for {county}")
    
    print("\n=== SPRINT PRIORITY ANALYSIS ===")
    priorities = analyze_sprint_priorities(county_metrics)
    
    for county, county_priorities in priorities.items():
        print(f"\n{county.upper()} PRIORITIES:")
        if county_priorities:
            for i, priority in enumerate(county_priorities, 1):
                print(f"  {i}. {priority}")
        else:
            print("  ✅ All criteria passing or no issues identified")
    
    print(f"\n=== VERIFICATION TIMESTAMP ===")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()} UTC")
    print("Per HONESTY PROTOCOL: VERIFIED live database query results above")
    
    # Save results for session tracking
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "county_metrics": county_metrics,
        "sprint_priorities": priorities,
        "session": "shard19-run19"
    }
    
    with open("shard19_verification_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nResults saved to: shard19_verification_results.json")
    
    return county_metrics, priorities

if __name__ == "__main__":
    main()