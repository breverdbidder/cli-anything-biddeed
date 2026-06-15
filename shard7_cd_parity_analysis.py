#!/usr/bin/env python3
"""
SHARD-7 C/D Parity Root Cause Analysis and Fix
Counties: leon, clay, miami_dade, columbia, madison

Per CRITERION-PARALLEL PIVOT strategy:
- Fix C/D parity fleet-wide, not counties serially
- Target: VERIFIED 2026-06-12: frozen numerators while denominators grew
- Pre-authorized: adopt clerk/official-records as supplementary litmus source

Current metrics (from briefing):
- leon: C=12.7, D=51.0 
- clay: C=12.5, D=52.0
- miami_dade: C=19.3, D=48.7
- columbia: C=null, D=null (no data)
- madison: C=null, D=null (no data)

Root cause analysis:
1. PropertyOnion coverage gaps (proven pattern from other shards)
2. Need supplementary clerk/official records litmus
3. Backfill missing parity matches

Usage:
  python shard7_cd_parity_analysis.py
"""
import os
import sys
import json
from datetime import datetime, timezone

# Try to import HTTP client
try:
    import httpx
    HTTP_LIB = 'httpx'
except ImportError:
    try:
        import requests as httpx
        HTTP_LIB = 'requests'
    except ImportError:
        print("❌ No HTTP library available")
        sys.exit(1)

print(f"✅ Using {HTTP_LIB} for HTTP requests")

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

if not SUPABASE_KEY:
    print("⚠️ No SUPABASE_KEY found - will generate analysis only")
    SUPABASE_KEY = "dummy"

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# SHARD-7 target counties
SHARD7_COUNTIES = ['leon', 'clay', 'miami_dade', 'columbia', 'madison']

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def make_request(method, url, **kwargs):
    """Make HTTP request using available library"""
    if HTTP_LIB == 'httpx':
        client = httpx.Client(timeout=60)
        if method == 'GET':
            return client.get(url, **kwargs)
        elif method == 'POST':
            return client.post(url, **kwargs)
    else:  # requests
        import requests
        if method == 'GET':
            return requests.get(url, **kwargs)
        elif method == 'POST':
            return requests.post(url, **kwargs)

def evaluate_county_parity(county_slug):
    """Evaluate specific county C/D status using pencil_dod_evaluate_county"""
    log(f"📊 Evaluating {county_slug} C/D parity status")
    
    try:
        payload = {"county_slug_arg": county_slug}
        response = make_request(
            'POST',
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list):
                # Extract C and D letter metrics
                c_data = next((item for item in result if item.get('letter') == 'C'), None)
                d_data = next((item for item in result if item.get('letter') == 'D'), None)
                
                log(f"  {county_slug} C: {c_data.get('metric') if c_data else 'null'} {'✅' if c_data and c_data.get('pass') else '❌'}")
                log(f"  {county_slug} D: {d_data.get('metric') if d_data else 'null'} {'✅' if d_data and d_data.get('pass') else '❌'}")
                
                return {
                    'county': county_slug,
                    'c_metric': c_data.get('metric') if c_data else None,
                    'c_pass': c_data.get('pass', False) if c_data else False,
                    'd_metric': d_data.get('metric') if d_data else None,
                    'd_pass': d_data.get('pass', False) if d_data else False,
                    'raw_result': result
                }
            else:
                log(f"  {county_slug}: No evaluation data", "WARN")
                return None
        else:
            log(f"  {county_slug}: API error {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"  {county_slug}: Error - {e}", "ERROR")
        return None

def analyze_parity_sources(county_slug):
    """Analyze parity data sources for a county to identify gaps"""
    log(f"🔍 Analyzing parity sources for {county_slug}")
    
    # Query multi_county_auctions for this county to understand denominators
    try:
        response = make_request(
            'GET',
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": county_slug,
                "select": "count,source_platform,case_number",
                "limit": "1000"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            total_auctions = len(data)
            
            # Analyze source platforms
            source_counts = {}
            po_pattern_count = 0  # PropertyOnion pattern IDs
            
            for auction in data:
                source = auction.get('source_platform', 'unknown')
                case_num = auction.get('case_number', '')
                
                source_counts[source] = source_counts.get(source, 0) + 1
                
                # Check for PropertyOnion ID pattern (PO-xxxxxx)
                if case_num and case_num.startswith('PO-'):
                    po_pattern_count += 1
            
            log(f"  {county_slug} total auctions: {total_auctions}")
            for source, count in source_counts.items():
                log(f"    {source}: {count} ({count/total_auctions*100:.1f}%)")
            
            if po_pattern_count > 0:
                log(f"    PropertyOnion IDs: {po_pattern_count} ({po_pattern_count/total_auctions*100:.1f}%)")
                log(f"    🚨 DIAGNOSIS: PropertyOnion IDs cannot match clerk records - this explains C/D ceiling")
            
            return {
                'county': county_slug,
                'total_auctions': total_auctions,
                'source_counts': source_counts,
                'po_pattern_count': po_pattern_count,
                'po_percentage': po_pattern_count/total_auctions*100 if total_auctions > 0 else 0
            }
        else:
            log(f"  {county_slug}: Failed to get auction data", "ERROR")
            return None
            
    except Exception as e:
        log(f"  {county_slug}: Error analyzing sources - {e}", "ERROR")
        return None

def get_county_setup_status(county_slug):
    """Check if county is properly configured in pipeline.counties"""
    log(f"🔧 Checking {county_slug} pipeline configuration")
    
    try:
        response = make_request(
            'GET',
            f"{BASE}/fl_counties",
            headers=HEADERS,
            params={
                "name": f"eq.{county_slug.title()}",
                "select": "name,dor_number,total_parcels"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data:
                county_data = data[0]
                log(f"  {county_slug}: DOR#{county_data.get('dor_number')}, {county_data.get('total_parcels', 0)} parcels")
                return county_data
            else:
                log(f"  {county_slug}: Not found in fl_counties", "WARN")
                return None
        else:
            log(f"  {county_slug}: Failed to get county data", "ERROR")
            return None
            
    except Exception as e:
        log(f"  {county_slug}: Error checking config - {e}", "ERROR")
        return None

def generate_cd_fix_strategy(analysis_results):
    """Generate strategy to fix C/D parity based on analysis"""
    log("📋 Generating C/D parity fix strategy")
    
    strategy = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'counties_analyzed': len(analysis_results),
        'fixes_needed': [],
        'sql_migrations': [],
        'priority_order': []
    }
    
    for county, result in analysis_results.items():
        if result['evaluation']:
            c_metric = result['evaluation'].get('c_metric')
            d_metric = result['evaluation'].get('d_metric')
            
            # Determine fix needed
            fix_type = None
            if c_metric is None and d_metric is None:
                fix_type = 'initial_setup'
                priority = 1
            elif result['source_analysis'] and result['source_analysis']['po_percentage'] > 50:
                fix_type = 'clerk_records_supplement'  
                priority = 2
            elif c_metric and c_metric < 95:
                fix_type = 'parity_backfill'
                priority = 3
            
            if fix_type:
                strategy['fixes_needed'].append({
                    'county': county,
                    'fix_type': fix_type,
                    'priority': priority,
                    'current_c': c_metric,
                    'current_d': d_metric,
                    'po_percentage': result['source_analysis']['po_percentage'] if result['source_analysis'] else 0
                })
    
    # Sort by priority
    strategy['fixes_needed'].sort(key=lambda x: x['priority'])
    strategy['priority_order'] = [f['county'] for f in strategy['fixes_needed']]
    
    log(f"  Strategy generated for {len(strategy['fixes_needed'])} counties")
    log(f"  Priority order: {', '.join(strategy['priority_order'])}")
    
    return strategy

def main():
    """Main execution - analyze all SHARD-7 counties for C/D parity issues"""
    log("🎯 SHARD-7 C/D PARITY ROOT CAUSE ANALYSIS")
    log(f"Counties: {', '.join(SHARD7_COUNTIES)}")
    
    analysis_results = {}
    
    for county in SHARD7_COUNTIES:
        log(f"\n--- ANALYZING {county.upper()} ---")
        
        # Get current evaluation
        evaluation = evaluate_county_parity(county)
        
        # Analyze parity sources
        source_analysis = analyze_parity_sources(county)
        
        # Check county setup
        setup_status = get_county_setup_status(county)
        
        analysis_results[county] = {
            'evaluation': evaluation,
            'source_analysis': source_analysis,
            'setup_status': setup_status
        }
    
    # Generate fix strategy
    log(f"\n{'='*60}")
    strategy = generate_cd_fix_strategy(analysis_results)
    
    # Output strategy as JSON for next script
    strategy_file = "shard7_cd_strategy.json"
    with open(strategy_file, 'w') as f:
        json.dump(strategy, f, indent=2)
    
    log(f"📄 Strategy saved to {strategy_file}")
    
    # Summary
    log(f"\n📊 SHARD-7 C/D ANALYSIS SUMMARY")
    for county in SHARD7_COUNTIES:
        result = analysis_results[county]
        if result['evaluation']:
            c = result['evaluation'].get('c_metric', 'null')
            d = result['evaluation'].get('d_metric', 'null')
            po_pct = result['source_analysis']['po_percentage'] if result['source_analysis'] else 0
            log(f"  {county}: C={c} D={d} PO%={po_pct:.1f}")
        else:
            log(f"  {county}: No evaluation data")
    
    log(f"\n✅ Analysis complete. Next: implement fixes per strategy.")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)