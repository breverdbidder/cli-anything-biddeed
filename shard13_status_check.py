#!/usr/bin/env python3
"""
SHARD-13 County Status Check for palm_beach, clay, okaloosa, gulf
"""
import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

print("=== Environment Check ===")
print(f"Python version: {sys.version}")

# Check for httpx first, fall back to urllib if needed
try:
    import httpx
    print("✅ httpx available")
    USE_HTTPX = True
except ImportError:
    print("⚠️  httpx not available, falling back to urllib")
    USE_HTTPX = False

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

# Try to read from GitHub secrets if not in environment
if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    print("Available env vars starting with SUPABASE:")
    for key in os.environ:
        if key.startswith("SUPABASE"):
            print(f"  {key}: {bool(os.environ[key])}")
    sys.exit(1)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def http_request(method, url, data=None):
    """Make HTTP request using either httpx or urllib"""
    headers = sb_headers()
    
    if USE_HTTPX:
        try:
            client = httpx.Client(timeout=60)
            if method == "GET":
                r = client.get(url, headers=headers)
            else:  # POST
                r = client.post(url, headers=headers, json=data)
            return r.status_code, r.text, r.json() if r.status_code == 200 else None
        except Exception as e:
            return 500, str(e), None
    else:
        try:
            # Use urllib
            req_data = json.dumps(data).encode('utf-8') if data else None
            request = urllib.request.Request(url, data=req_data, headers=headers, method=method)
            with urllib.request.urlopen(request, timeout=60) as response:
                response_text = response.read().decode('utf-8')
                try:
                    response_json = json.loads(response_text)
                except:
                    response_json = None
                return response.status, response_text, response_json
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8'), None
        except Exception as e:
            return 500, str(e), None

def test_connection():
    """Test basic connection to Supabase"""
    try:
        status, text, json_data = http_request("GET", f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1")
        print(f"Connection status: {status}")
        if status == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        status, text, result = http_request(
            "POST",
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            {"county_slug_arg": county_slug}
        )
        
        if status == 200 and result:
            print(f"✅ County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                score = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passed = letter_data.get('pass')
                    status_icon = "✅" if passed else "❌"
                    if passed:
                        score += 1
                    print(f"  {letter}: {status_icon} {metric}")
                print(f"  TOTAL: {score}/10")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {status} - {text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

if __name__ == "__main__":
    print("=== SHARD-13 Database Connectivity Test ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== SHARD-13 County Evaluations ===")
    shard13_counties = ['palm_beach', 'clay', 'okaloosa', 'gulf']
    
    results = {}
    for county in shard13_counties:
        print(f"\n--- {county} ---")
        result = evaluate_county_current(county)
        results[county] = result
    
    print("\n=== SHARD-13 SUMMARY ===")
    for county, data in results.items():
        if data:
            score = sum(1 for item in data if item.get('pass'))
            print(f"{county}: {score}/10")
        else:
            print(f"{county}: EVALUATION FAILED")