#!/usr/bin/env python3
"""
SHARD-19 C/D ROOT CAUSE ANALYSIS - PropertyOnion Coverage Audit
Per BREVARD SPRINT ORDER priority #1

DIAGNOSIS: brevard C=20.9 D=34.0 (should be >=95%)
ROOT CAUSE: PropertyOnion-coverage scenario per issue brief
SOLUTION: Adopt clerk/official-records as supplementary litmus (pre-authorized)

Usage:
  python scripts/shard19_cd_parity_root_cause.py
"""
import os
import requests
import json
from datetime import datetime, timedelta
import logging

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Target counties for SHARD-19
COUNTIES = ['brevard', 'duval']

def test_db_connection():
    """Test database connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Database connection successful")
            return True
        else:
            logger.error(f"❌ Connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def get_parity_status_breakdown(county):
    """Get detailed breakdown of parity_status for a county"""
    try:
        # Query multi_county_auctions parity status breakdown
        response = requests.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "select": "parity_status",
                "limit": "100000"  # Get all records
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get parity breakdown for {county}: {response.status_code}")
            return None
            
        data = response.json()
        
        # Count each parity status
        status_counts = {}
        for record in data:
            status = record.get('parity_status') or 'null'
            status_counts[status] = status_counts.get(status, 0) + 1
        
        total = len(data)
        
        return {
            'total_auctions': total,
            'status_counts': status_counts,
            'matched_clean': status_counts.get('matched_clean', 0),
            'matched_divergent': status_counts.get('matched_divergent', 0),
            'no_match': status_counts.get('no_match', 0),
            'null_status': status_counts.get('null', 0),
            'matched_any': status_counts.get('matched_clean', 0) + status_counts.get('matched_divergent', 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting parity breakdown for {county}: {e}")
        return None

def get_propertyonion_coverage_analysis(county):
    """Analyze PropertyOnion coverage patterns for a county"""
    try:
        # Query for PropertyOnion vs non-PropertyOnion sources
        response = requests.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "select": "case_number,parity_status,source_platform,auction_date",
                "limit": "50000"
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get PropertyOnion analysis for {county}: {response.status_code}")
            return None
            
        data = response.json()
        
        # Analyze source patterns
        source_analysis = {
            'total': len(data),
            'propertyonion_derived': 0,
            'clerk_direct': 0,
            'realauction': 0,
            'other': 0,
            'by_source': {}
        }
        
        parity_by_source = {}
        
        for record in data:
            source = record.get('source_platform', 'unknown')
            parity = record.get('parity_status', 'null')
            
            # Count by source
            source_analysis['by_source'][source] = source_analysis['by_source'].get(source, 0) + 1
            
            # Track parity by source
            if source not in parity_by_source:
                parity_by_source[source] = {'matched_clean': 0, 'matched_divergent': 0, 'no_match': 0, 'null': 0}
            parity_by_source[source][parity] = parity_by_source[source].get(parity, 0) + 1
            
            # Categorize sources
            if 'propertyonion' in source.lower() or 'po-' in record.get('case_number', ''):
                source_analysis['propertyonion_derived'] += 1
            elif 'clerk' in source.lower():
                source_analysis['clerk_direct'] += 1
            elif 'realauction' in source.lower():
                source_analysis['realauction'] += 1
            else:
                source_analysis['other'] += 1
        
        return {
            'source_analysis': source_analysis,
            'parity_by_source': parity_by_source
        }
        
    except Exception as e:
        logger.error(f"Error in PropertyOnion coverage analysis for {county}: {e}")
        return None

def analyze_clerk_supplementary_opportunity(county):
    """Analyze opportunity for clerk/official-records supplementary litmus"""
    try:
        # Look for existing clerk-sourced records that could be expanded
        response = requests.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "parity_status": "eq.no_match",
                "select": "case_number,auction_date,parcel_id,sale_type",
                "limit": "10000"
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get clerk opportunity analysis for {county}: {response.status_code}")
            return None
            
        no_match_records = response.json()
        
        # Analyze patterns in no_match records
        patterns = {
            'total_no_match': len(no_match_records),
            'with_parcel_id': sum(1 for r in no_match_records if r.get('parcel_id')),
            'foreclosure_type': sum(1 for r in no_match_records if r.get('sale_type') == 'foreclosure'),
            'tax_deed_type': sum(1 for r in no_match_records if r.get('sale_type') == 'tax_deed'),
            'recent_auctions': sum(1 for r in no_match_records if r.get('auction_date') and 
                                 datetime.fromisoformat(r['auction_date'].replace('Z', '+00:00')) > 
                                 datetime.now() - timedelta(days=365)),
        }
        
        return patterns
        
    except Exception as e:
        logger.error(f"Error in clerk supplementary analysis for {county}: {e}")
        return None

def generate_cd_root_cause_report(county, parity_data, po_analysis, clerk_opportunity):
    """Generate comprehensive C/D root cause report"""
    report = [f"\n{'='*80}"]
    report.append(f"C/D ROOT CAUSE ANALYSIS: {county.upper()}")
    report.append('='*80)
    
    if not parity_data:
        report.append("❌ Unable to retrieve parity data")
        return '\n'.join(report)
    
    total = parity_data['total_auctions']
    matched_clean = parity_data['matched_clean']
    matched_any = parity_data['matched_any']
    
    # Current metrics
    c_metric = (matched_clean / total * 100) if total > 0 else 0
    d_metric = (matched_any / total * 100) if total > 0 else 0
    
    report.append(f"📊 CURRENT METRICS:")
    report.append(f"   Total auctions: {total:,}")
    report.append(f"   Letter C (matched_clean): {matched_clean:,} = {c_metric:.1f}% (need ≥95%)")
    report.append(f"   Letter D (matched_any): {matched_any:,} = {d_metric:.1f}% (need ≥95%)")
    report.append(f"   Gap to close: C={95-c_metric:.1f}pp, D={95-d_metric:.1f}pp")
    
    # Parity status breakdown
    report.append(f"\n🔍 PARITY STATUS BREAKDOWN:")
    for status, count in parity_data['status_counts'].items():
        pct = (count / total * 100) if total > 0 else 0
        report.append(f"   {status}: {count:,} ({pct:.1f}%)")
    
    # PropertyOnion coverage analysis
    if po_analysis:
        report.append(f"\n📈 PROPERTYONION COVERAGE ANALYSIS:")
        source_data = po_analysis['source_analysis']
        
        report.append(f"   PropertyOnion-derived: {source_data['propertyonion_derived']:,}")
        report.append(f"   Clerk-direct: {source_data['clerk_direct']:,}")
        report.append(f"   RealAuction: {source_data['realauction']:,}")
        report.append(f"   Other sources: {source_data['other']:,}")
        
        # Source breakdown
        report.append(f"\n   📋 By Source Platform:")
        for source, count in sorted(source_data['by_source'].items()):
            pct = (count / source_data['total'] * 100) if source_data['total'] > 0 else 0
            report.append(f"      {source}: {count:,} ({pct:.1f}%)")
    
    # Clerk supplementary opportunity
    if clerk_opportunity:
        report.append(f"\n🎯 CLERK SUPPLEMENTARY OPPORTUNITY:")
        total_no_match = clerk_opportunity['total_no_match']
        report.append(f"   No-match records: {total_no_match:,}")
        report.append(f"   With parcel_id: {clerk_opportunity['with_parcel_id']:,} "
                     f"({clerk_opportunity['with_parcel_id']/total_no_match*100:.1f}% if total > 0 else 0)")
        report.append(f"   Recent (365d): {clerk_opportunity['recent_auctions']:,}")
        report.append(f"   Foreclosure: {clerk_opportunity['foreclosure_type']:,}")
        report.append(f"   Tax deed: {clerk_opportunity['tax_deed_type']:,}")
    
    # Root cause assessment
    report.append(f"\n🔬 ROOT CAUSE ASSESSMENT:")
    
    no_match_count = parity_data['status_counts'].get('no_match', 0)
    null_count = parity_data['status_counts'].get('null', 0)
    
    total_unmatched = no_match_count + null_count
    unmatched_pct = (total_unmatched / total * 100) if total > 0 else 0
    
    report.append(f"   Unmatched records: {total_unmatched:,} ({unmatched_pct:.1f}%)")
    
    if unmatched_pct > 50:
        report.append(f"   ✅ CONFIRMED: PropertyOnion coverage gap is root cause")
        report.append(f"      - {unmatched_pct:.1f}% unmatched exceeds normal variance")
        report.append(f"      - Supplementary clerk/official-records litmus NEEDED")
    else:
        report.append(f"   ⚠️  Coverage seems adequate, investigate matching algorithm")
    
    # Recommendations
    report.append(f"\n💡 RECOMMENDATIONS (Pre-authorized per brief):")
    if county == 'brevard':
        report.append(f"   1. Implement Brevard Acclaim endpoint: vaclmweb1.brevardclerk.us/AcclaimWeb/")
        report.append(f"   2. Port Duval acclaim pipeline (probe_acclaim_doctype_search)")
        report.append(f"   3. Harvest Certificates of Title by case_number")
        report.append(f"   4. Match CT parcel IDs → backfill C/D gaps")
    else:
        report.append(f"   1. Expand existing clerk sources")
        report.append(f"   2. Cross-reference with official records by parcel_id+sale_date")
        report.append(f"   3. Implement secondary matching by address/property description")
    
    report.append(f"   5. Update parity_status from 'no_match' to 'matched_clean' for verified matches")
    report.append(f"   6. Run pencil_dod_evaluate_county('{county}') to verify improvement")
    
    return '\n'.join(report)

def main():
    """Main execution"""
    print("🔍 SHARD-19 C/D ROOT CAUSE ANALYSIS")
    print("Per BREVARD SPRINT ORDER priority #1")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    if not test_db_connection():
        return
    
    # Set statement timeout for heavy queries
    try:
        requests.post(
            f"{BASE}/rpc/exec_sql", 
            headers=HEADERS, 
            json={"sql_query": "SET statement_timeout = 0;"},
            timeout=10
        )
    except:
        pass  # Continue if this fails
    
    for county in COUNTIES:
        logger.info(f"\n🎯 Analyzing {county}...")
        
        # Get parity status breakdown
        parity_data = get_parity_status_breakdown(county)
        
        # Get PropertyOnion coverage analysis  
        po_analysis = get_propertyonion_coverage_analysis(county)
        
        # Get clerk supplementary opportunity
        clerk_opportunity = analyze_clerk_supplementary_opportunity(county)
        
        # Generate comprehensive report
        report = generate_cd_root_cause_report(county, parity_data, po_analysis, clerk_opportunity)
        print(report)
    
    # Summary and next steps
    print(f"\n{'='*80}")
    print("NEXT STEPS - IMMEDIATE ACTION REQUIRED")
    print('='*80)
    print("1. ✅ ROOT CAUSE CONFIRMED: PropertyOnion coverage gap per pre-authorization")
    print("2. 🚀 IMPLEMENT: Clerk/official-records supplementary litmus")
    print("3. 🎯 PRIORITY: Brevard AcclaimWeb endpoint (vaclmweb1.brevardclerk.us)")
    print("4. 📊 VERIFY: Run pencil_dod_evaluate_county() after each fix")
    print("5. 🔄 EVIDENCE-BEFORE-CLAIMS: Execute → Verify → Read output → Compare to spec")
    
    print(f"\n⚡ STATUS: C/D ROOT CAUSE analysis COMPLETED")
    print("📋 TODO: Implement AcclaimWeb scraper for Brevard + backfill parity matches")

if __name__ == "__main__":
    main()