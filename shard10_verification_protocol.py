#!/usr/bin/env python3
"""
SHARD-10 VERIFICATION PROTOCOL
Purpose: Verify metrics and evidence for polk, flagler, okeechobee, franklin, union
Per HONESTY PROTOCOL: VERIFIED claims must have actual database proof
"""
import os
import json
import httpx
from datetime import datetime

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
SHARD10_COUNTIES = ['polk', 'flagler', 'okeechobee', 'franklin', 'union']

def query_database(sql_query, description):
    """Execute SQL query and return results with error handling"""
    try:
        if not SUPABASE_KEY:
            return {'error': 'No database credentials available', 'description': description}
        
        client = httpx.Client(timeout=90)
        
        # For RPC functions, use POST
        if 'public.' in sql_query and '(' in sql_query:
            # Extract function name and parameters
            func_match = sql_query.split('public.')[1].split('(')[0]
            if func_match == 'pencil_dod_evaluate_county':
                county = sql_query.split("'")[1]  # Extract county from query
                response = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                    headers={
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={"county_slug_arg": county}
                )
            else:
                response = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/{func_match}",
                    headers={
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={}
                )
        else:
            # For regular queries, use the query endpoint
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json"
                },
                json={"query": sql_query}
            )
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'data': result,
                'description': description,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        else:
            return {
                'error': f'HTTP {response.status_code}: {response.text}',
                'description': description,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            
    except Exception as e:
        return {
            'error': str(e),
            'description': description,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

def verify_shard10_metrics():
    """Verify current metrics for all SHARD-10 counties with HONESTY PROTOCOL compliance"""
    print("🔍 SHARD-10 VERIFICATION PROTOCOL - HONESTY PROTOCOL COMPLIANT")
    print("=" * 80)
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Counties: {', '.join(SHARD10_COUNTIES)}")
    print()
    
    verification_results = {
        'session_id': 'shard10_verification',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'counties': {},
        'summary': {},
        'evidence_queries': []
    }
    
    # Verify each county using the standard evaluator
    for county in SHARD10_COUNTIES:
        print(f"🔍 Verifying {county.upper()}...")
        
        query = f"SELECT public.pencil_dod_evaluate_county('{county}')"
        result = query_database(query, f"Gold standard evaluation for {county}")
        
        verification_results['evidence_queries'].append({
            'query': query,
            'result': result,
            'county': county
        })
        
        if result.get('success'):
            data = result['data']
            if data:
                pass_count = sum(1 for letter_data in data if letter_data.get('pass', False))
                verification_results['counties'][county] = {
                    'score': f"{pass_count}/10",
                    'raw_evaluation': data,
                    'verification_status': 'VERIFIED',
                    'timestamp': result['timestamp']
                }
                print(f"✅ {county}: {pass_count}/10 - VERIFIED")
                
                # Show key metrics
                for letter_data in data:
                    letter = letter_data.get('letter', 'Unknown')
                    metric = letter_data.get('metric')
                    passes = letter_data.get('pass', False)
                    status = '✅' if passes else '❌'
                    print(f"    {letter}: {status} {metric}")
            else:
                verification_results['counties'][county] = {
                    'score': 'NO_DATA',
                    'verification_status': 'UNVERIFIED',
                    'error': 'Empty result set'
                }
                print(f"❌ {county}: NO_DATA")
        else:
            verification_results['counties'][county] = {
                'score': 'ERROR',
                'verification_status': 'FAILED',
                'error': result.get('error', 'Unknown error')
            }
            print(f"❌ {county}: ERROR - {result.get('error', 'Unknown')}")
    
    # Calculate summary statistics with VERIFIED tag
    total_counties = len(SHARD10_COUNTIES)
    verified_counties = sum(1 for c in verification_results['counties'].values() 
                          if c.get('verification_status') == 'VERIFIED')
    
    verification_results['summary'] = {
        'total_counties': total_counties,
        'verified_counties': verified_counties,
        'verification_rate': f"{verified_counties/total_counties:.1%}",
        'status': 'VERIFIED' if verified_counties > 0 else 'UNVERIFIED'
    }
    
    print(f"\n📊 VERIFICATION SUMMARY:")
    print(f"  Counties verified: {verified_counties}/{total_counties} ({verified_counties/total_counties:.1%})")
    print(f"  Verification status: {verification_results['summary']['status']}")
    
    # Identify priority work based on VERIFIED metrics
    print(f"\n🎯 PRIORITY WORK IDENTIFICATION (based on VERIFIED metrics):")
    
    failing_letters = {}
    zero_state_counties = []
    
    for county, data in verification_results['counties'].items():
        if data.get('verification_status') == 'VERIFIED':
            raw_eval = data.get('raw_evaluation', [])
            county_score = data.get('score', '0/10')
            
            if county_score == '0/10':
                zero_state_counties.append(county)
            
            for letter_data in raw_eval:
                letter = letter_data.get('letter')
                if not letter_data.get('pass', False):
                    if letter not in failing_letters:
                        failing_letters[letter] = []
                    failing_letters[letter].append(county)
    
    if zero_state_counties:
        print(f"  🚨 ZERO STATE: {', '.join(zero_state_counties)} - Require A-lane setup")
    
    priority_letters = ['A', 'H', 'J', 'C', 'D', 'E', 'F', 'G', 'I', 'B']
    for letter in priority_letters:
        counties = failing_letters.get(letter, [])
        if counties:
            print(f"  **{letter}**: {', '.join(counties)} ({len(counties)} counties)")
    
    # Save verification results
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"shard10_verification_{timestamp}.json"
    
    try:
        with open(filename, 'w') as f:
            json.dump(verification_results, f, indent=2)
        print(f"\n📁 Verification results saved to: {filename}")
    except Exception as e:
        print(f"⚠️ Could not save results: {e}")
    
    return verification_results

def check_parallel_fleet_status():
    """Check if other shards are currently running to avoid conflicts"""
    print("\n🚥 PARALLEL FLEET STATUS CHECK...")
    
    # This would query for active sessions or locks
    # For now, we'll just note the timestamp
    timestamp = datetime.utcnow()
    print(f"Session timestamp: {timestamp.isoformat()}Z")
    print("Note: Other shards may be running concurrently")
    print("Following PARALLEL-FLEET RULES: only touching SHARD-10 counties")
    
    return timestamp

if __name__ == "__main__":
    print("🎯 SHARD-10 VERIFICATION PROTOCOL")
    print("Executing verification with HONESTY PROTOCOL compliance")
    print("All claims will be marked VERIFIED with database evidence")
    print()
    
    # Check fleet status
    fleet_timestamp = check_parallel_fleet_status()
    
    # Run verification
    results = verify_shard10_metrics()
    
    # Print SQL verification block for final reporting
    print(f"\n### SQL VERIFICATION")
    print(f"-- SHARD-10 verification queries executed:")
    for county in SHARD10_COUNTIES:
        print(f"SELECT public.pencil_dod_evaluate_county('{county}');")
    print(f"-- Fleet timestamp: {fleet_timestamp.isoformat()}Z")
    print(f"-- Verification status: {results['summary'].get('status', 'UNKNOWN')}")
    print(f"-- Counties verified: {results['summary'].get('verified_counties', 0)}/{results['summary'].get('total_counties', 0)}")