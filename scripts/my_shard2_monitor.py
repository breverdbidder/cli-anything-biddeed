#!/usr/bin/env python3
"""
MY SHARD-2 MONITORING AND HEALTH CHECK
Monitors pipeline health and provides diagnostic information
For charlotte, polk, hendry, st_lucie, holmes counties

Usage:
  python scripts/my_shard2_monitor.py --health-check
  python scripts/my_shard2_monitor.py --pipeline-status
  python scripts/my_shard2_monitor.py --data-quality-audit
"""
import httpx
import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

MY_TARGET_COUNTIES = ['charlotte', 'polk', 'hendry', 'st_lucie', 'holmes']

client = httpx.Client(timeout=30, follow_redirects=True)

def supabase_get(table: str, params: Dict = None) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def test_database_connectivity() -> Dict:
    """Test basic database connectivity"""
    logger.info("Testing database connectivity...")
    
    try:
        if not SUPABASE_KEY:
            return {
                'connected': False,
                'error': 'SUPABASE_KEY not available',
                'details': f'Environment variables: {[k for k in os.environ.keys() if "SUPABASE" in k]}'
            }
        
        # Test basic table access
        response = client.get(f"{BASE}/multi_county_auctions?limit=1", headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            return {
                'connected': True,
                'status_code': response.status_code,
                'database_url': SUPABASE_URL,
                'test_timestamp': datetime.now().isoformat()
            }
        else:
            return {
                'connected': False,
                'status_code': response.status_code,
                'error': response.text[:200]
            }
            
    except Exception as e:
        return {
            'connected': False,
            'error': str(e)
        }

def get_county_auction_counts() -> Dict[str, int]:
    """Get auction counts for each county"""
    logger.info("Getting auction counts per county...")
    
    counts = {}
    for county in MY_TARGET_COUNTIES:
        try:
            auctions = supabase_get('multi_county_auctions', {
                'select': 'count',
                'county': f'eq.{county}'
            })
            
            if auctions and isinstance(auctions, list) and len(auctions) > 0:
                counts[county] = auctions[0].get('count', 0)
            else:
                # Fallback to actual count
                auctions = supabase_get('multi_county_auctions', {
                    'county': f'eq.{county}',
                    'limit': '1000'
                })
                counts[county] = len(auctions)
                
        except Exception as e:
            logger.error(f"Error counting auctions for {county}: {e}")
            counts[county] = 0
    
    return counts

def get_verified_outcomes_stats() -> Dict[str, Dict]:
    """Get verified outcomes statistics"""
    logger.info("Analyzing verified outcomes coverage...")
    
    stats = {}
    for county in MY_TARGET_COUNTIES:
        try:
            # Count foreclosure outcomes
            foreclosure_outcomes = supabase_get('foreclosure_outcomes', {
                'select': 'count',
                'county_slug': f'eq.{county}',
                'data_source': 'not.ilike.*propertyonion*'  # Independent sources only
            })
            
            # Count tax deed outcomes
            tax_deed_outcomes = supabase_get('tax_deed_outcomes', {
                'select': 'count', 
                'county_slug': f'eq.{county}',
                'data_source': 'not.ilike.*propertyonion*'  # Independent sources only
            })
            
            fc_count = 0
            td_count = 0
            
            if foreclosure_outcomes and foreclosure_outcomes[0]:
                fc_count = foreclosure_outcomes[0].get('count', 0)
            if tax_deed_outcomes and tax_deed_outcomes[0]:
                td_count = tax_deed_outcomes[0].get('count', 0)
            
            stats[county] = {
                'foreclosure_outcomes': fc_count,
                'tax_deed_outcomes': td_count,
                'total_verified': fc_count + td_count
            }
            
        except Exception as e:
            logger.error(f"Error getting outcomes stats for {county}: {e}")
            stats[county] = {
                'foreclosure_outcomes': 0,
                'tax_deed_outcomes': 0,
                'total_verified': 0,
                'error': str(e)
            }
    
    return stats

def get_property_completeness_stats() -> Dict[str, Dict]:
    """Get property card completeness statistics"""
    logger.info("Analyzing property card completeness...")
    
    stats = {}
    for county in MY_TARGET_COUNTIES:
        try:
            # Get total auctions
            total_auctions = supabase_get('multi_county_auctions', {
                'select': 'count',
                'county': f'eq.{county}'
            })
            
            # Get auctions with complete property data
            complete_properties = supabase_get('multi_county_auctions', {
                'select': 'count',
                'county': f'eq.{county}',
                'property_address': 'not.is.null',
                'latitude': 'not.is.null',
                'longitude': 'not.is.null',
                'assessed_value': 'not.is.null'
            })
            
            total = 0
            complete = 0
            
            if total_auctions and total_auctions[0]:
                total = total_auctions[0].get('count', 0)
            if complete_properties and complete_properties[0]:
                complete = complete_properties[0].get('count', 0)
            
            completion_pct = (complete / total * 100) if total > 0 else 0
            
            stats[county] = {
                'total_auctions': total,
                'complete_properties': complete,
                'completion_percentage': round(completion_pct, 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting property stats for {county}: {e}")
            stats[county] = {
                'total_auctions': 0,
                'complete_properties': 0,
                'completion_percentage': 0,
                'error': str(e)
            }
    
    return stats

def get_deal_thesis_stats() -> Dict[str, Dict]:
    """Get deal thesis completion statistics"""
    logger.info("Analyzing deal thesis completion...")
    
    stats = {}
    for county in MY_TARGET_COUNTIES:
        try:
            # Count total auctions
            total_auctions = supabase_get('multi_county_auctions', {
                'select': 'count',
                'county': f'eq.{county}'
            })
            
            # Count bid decisions
            bid_decisions = supabase_get('bid_decisions', {
                'select': 'count',
                'county_slug': f'eq.{county}'
            })
            
            total = 0
            decisions = 0
            
            if total_auctions and total_auctions[0]:
                total = total_auctions[0].get('count', 0)
            if bid_decisions and bid_decisions[0]:
                decisions = bid_decisions[0].get('count', 0)
            
            completion_pct = (decisions / total * 100) if total > 0 else 0
            
            stats[county] = {
                'total_auctions': total,
                'bid_decisions': decisions,
                'completion_percentage': round(completion_pct, 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting deal thesis stats for {county}: {e}")
            stats[county] = {
                'total_auctions': 0,
                'bid_decisions': 0,
                'completion_percentage': 0,
                'error': str(e)
            }
    
    return stats

def evaluate_all_counties() -> Dict[str, Dict]:
    """Run pencil_dod_evaluate_county for all counties"""
    logger.info("Running county evaluations...")
    
    evaluations = {}
    for county in MY_TARGET_COUNTIES:
        try:
            # Try multiple parameter formats
            evaluation = None
            for param_name in ["county_name", "county_slug_arg", "county_slug"]:
                response = client.post(
                    f"{BASE}/rpc/pencil_dod_evaluate_county",
                    headers=HEADERS,
                    json={param_name: county},
                    timeout=60
                )
                
                if response.status_code == 200:
                    evaluation = response.json()
                    break
            
            if evaluation:
                # Count passing grades
                passing = 0
                if isinstance(evaluation, dict):
                    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                        grade_field = f"grade_{letter.lower()}"
                        if evaluation.get(grade_field) == 'PASS':
                            passing += 1
                
                evaluations[county] = {
                    'evaluation_success': True,
                    'passing_letters': passing,
                    'total_score': f"{passing}/10",
                    'raw_evaluation': evaluation
                }
            else:
                evaluations[county] = {
                    'evaluation_success': False,
                    'error': 'All parameter formats failed'
                }
                
        except Exception as e:
            logger.error(f"Error evaluating {county}: {e}")
            evaluations[county] = {
                'evaluation_success': False,
                'error': str(e)
            }
    
    return evaluations

def generate_health_report() -> Dict:
    """Generate comprehensive health report"""
    logger.info("Generating comprehensive health report...")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'database': test_database_connectivity(),
        'auction_counts': get_county_auction_counts(),
        'verified_outcomes': get_verified_outcomes_stats(),
        'property_completeness': get_property_completeness_stats(),
        'deal_thesis': get_deal_thesis_stats(),
        'county_evaluations': evaluate_all_counties()
    }
    
    return report

def print_health_summary(report: Dict):
    """Print formatted health summary"""
    print("\n" + "="*80)
    print("MY SHARD-2 PIPELINE HEALTH REPORT")
    print("="*80)
    
    # Database status
    db = report['database']
    db_status = "✅ Connected" if db.get('connected') else "❌ Disconnected"
    print(f"Database: {db_status}")
    if not db.get('connected'):
        print(f"  Error: {db.get('error', 'Unknown')}")
    
    print(f"\n{'County':<12} {'Auctions':<10} {'Verified':<10} {'Property':<10} {'Deals':<10} {'Score':<8}")
    print("-" * 70)
    
    for county in MY_TARGET_COUNTIES:
        auctions = report['auction_counts'].get(county, 0)
        verified = report['verified_outcomes'].get(county, {}).get('total_verified', 0)
        property_pct = report['property_completeness'].get(county, {}).get('completion_percentage', 0)
        deal_pct = report['deal_thesis'].get(county, {}).get('completion_percentage', 0)
        
        evaluation = report['county_evaluations'].get(county, {})
        score = evaluation.get('total_score', 'N/A')
        
        print(f"{county:<12} {auctions:<10} {verified:<10} {property_pct:>8.1f}% {deal_pct:>8.1f}% {score:<8}")
    
    # Overall statistics
    total_auctions = sum(report['auction_counts'].values())
    total_verified = sum(vo.get('total_verified', 0) for vo in report['verified_outcomes'].values())
    
    print(f"\n📊 TOTALS:")
    print(f"Total Auctions: {total_auctions:,}")
    print(f"Total Verified Outcomes: {total_verified:,}")
    
    # Letter B, I, J focus
    print(f"\n🎯 CRITICAL LETTERS (B, I, J) STATUS:")
    for county in MY_TARGET_COUNTIES:
        evaluation = report['county_evaluations'].get(county, {})
        if evaluation.get('evaluation_success'):
            raw_eval = evaluation.get('raw_evaluation', {})
            b_grade = raw_eval.get('grade_b', 'UNKNOWN')
            i_grade = raw_eval.get('grade_i', 'UNKNOWN')
            j_grade = raw_eval.get('grade_j', 'UNKNOWN')
            
            b_icon = "✅" if b_grade == 'PASS' else "❌"
            i_icon = "✅" if i_grade == 'PASS' else "❌"
            j_icon = "✅" if j_grade == 'PASS' else "❌"
            
            print(f"{county:<12} B:{b_icon} I:{i_icon} J:{j_icon}")

def run_data_quality_audit() -> Dict:
    """Run data quality audit"""
    logger.info("Running data quality audit...")
    
    audit_results = {}
    
    for county in MY_TARGET_COUNTIES:
        logger.info(f"Auditing {county}...")
        
        try:
            # Check for duplicate case numbers
            duplicates = supabase_get('multi_county_auctions', {
                'select': 'case_number',
                'county': f'eq.{county}',
                'limit': '1000'
            })
            
            case_numbers = [a['case_number'] for a in duplicates if a['case_number']]
            duplicate_count = len(case_numbers) - len(set(case_numbers))
            
            # Check data source diversity
            sources = supabase_get('multi_county_auctions', {
                'select': 'data_source',
                'county': f'eq.{county}',
                'limit': '1000'
            })
            
            unique_sources = set(s['data_source'] for s in sources if s['data_source'])
            
            audit_results[county] = {
                'total_records': len(duplicates),
                'duplicate_case_numbers': duplicate_count,
                'unique_data_sources': len(unique_sources),
                'data_sources': list(unique_sources)
            }
            
        except Exception as e:
            logger.error(f"Audit error for {county}: {e}")
            audit_results[county] = {'error': str(e)}
    
    return audit_results

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="MY SHARD-2 Pipeline Monitoring")
    parser.add_argument('--health-check', action='store_true', help='Run full health check')
    parser.add_argument('--pipeline-status', action='store_true', help='Check pipeline status only')
    parser.add_argument('--data-quality-audit', action='store_true', help='Run data quality audit')
    parser.add_argument('--county', choices=MY_TARGET_COUNTIES, help='Focus on specific county')
    parser.add_argument('--json-output', action='store_true', help='Output results as JSON')
    
    args = parser.parse_args()
    
    logger.info("🔍 MY SHARD-2 PIPELINE MONITORING")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    if args.health_check:
        report = generate_health_report()
        
        if args.json_output:
            print(json.dumps(report, indent=2))
        else:
            print_health_summary(report)
    
    elif args.pipeline_status:
        db_status = test_database_connectivity()
        auction_counts = get_county_auction_counts()
        evaluations = evaluate_all_counties()
        
        print("\n📊 PIPELINE STATUS")
        print(f"Database: {'✅' if db_status.get('connected') else '❌'}")
        
        for county in MY_TARGET_COUNTIES:
            count = auction_counts.get(county, 0)
            eval_result = evaluations.get(county, {})
            score = eval_result.get('total_score', 'N/A')
            print(f"{county}: {count} auctions, {score} score")
    
    elif args.data_quality_audit:
        audit_results = run_data_quality_audit()
        
        if args.json_output:
            print(json.dumps(audit_results, indent=2))
        else:
            print("\n🔍 DATA QUALITY AUDIT")
            for county, results in audit_results.items():
                if 'error' in results:
                    print(f"{county}: ❌ {results['error']}")
                else:
                    print(f"{county}:")
                    print(f"  Records: {results['total_records']}")
                    print(f"  Duplicates: {results['duplicate_case_numbers']}")
                    print(f"  Data Sources: {results['unique_data_sources']}")
    
    else:
        # Default: quick status
        db_status = test_database_connectivity()
        if db_status.get('connected'):
            print("✅ Database connected")
            auction_counts = get_county_auction_counts()
            total = sum(auction_counts.values())
            print(f"📊 Total auctions: {total:,}")
            print("Use --health-check for full report")
        else:
            print("❌ Database connection failed")
            print(f"Error: {db_status.get('error')}")

if __name__ == "__main__":
    main()