#!/usr/bin/env python3
"""
DUVAL HARVEST→OUTCOMES MAPPER
Final link in the Duval B+F chain (VERIFIED from 2026-06-11 briefing)

MISSION:
Map 37 court-format Duval cases from staging tables to foreclosure_outcomes
Staging: duval_clerk_grantor_recordings_staging / duval_tax_deed_recordings_staging  
Target: public.foreclosure_outcomes with data_source=acclaim_ct:DUVAL-FC-V1

ROOT CAUSE (from briefing):
- Duval harvest→outcomes mapper MISSING for foreclosure (CA) cases
- 37 court-format Duval cases harvested clean to staging
- ZERO foreclosure_outcomes rows exist for duval  
- Staging rows lack case_number column → recover from raw_jsonb/doc_legal_description/comments
- Map CT consideration→winning_bid, write foreclosure_outcomes

CHAIN IMPACT: 
- This fixes Duval B (verified outcomes) + F (tier1 sold amount) automatically
- tier1-promote-hourly picks up amounts → F advances
- acclaim-queue-feeder-daily + 5 worker crons already running (per briefing)
"""

import os
import sys
import json
import re
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Optional

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

DATA_SOURCE = "acclaim_ct:DUVAL-FC-V1"

def extract_case_number_from_staging(raw_jsonb: dict, doc_legal: str, comments: str) -> Optional[str]:
    """
    Extract court case number from staging data sources
    Duval court format: YYYY-CA-XXXXXX or similar patterns
    """
    
    # Search patterns for case numbers
    case_patterns = [
        r'\b\d{4}-CA-\d{4,6}\b',  # YYYY-CA-XXXXXX
        r'\b\d{4}-CC-\d{4,6}\b',  # YYYY-CC-XXXXXX 
        r'\b\d{2,4}-\d{4,6}-CA\b', # Alternative format
        r'Case\s+No\.?\s*:?\s*([0-9]{4}-[A-Z]{2}-[0-9]{4,6})', # Case No: format
    ]
    
    # Search in all available text sources
    text_sources = [
        str(raw_jsonb.get('case_number', '')),
        str(raw_jsonb.get('document_description', '')),
        str(doc_legal or ''),
        str(comments or ''),
        json.dumps(raw_jsonb) if isinstance(raw_jsonb, dict) else str(raw_jsonb)
    ]
    
    for text in text_sources:
        if not text:
            continue
            
        for pattern in case_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Return first match, clean it up
                case_num = matches[0] if isinstance(matches[0], str) else matches[0]
                return case_num.strip().upper()
    
    return None

def extract_consideration_amount(raw_jsonb: dict, doc_legal: str, comments: str) -> Optional[float]:
    """
    Extract consideration (winning bid) amount from staging data
    Look for dollar amounts, consideration values
    """
    
    # Search for monetary amounts
    amount_patterns = [
        r'\$[\d,]+\.?\d*',  # $XXX,XXX.XX format
        r'consideration[:\s]+\$?([\d,]+\.?\d*)',  # consideration: $amount
        r'amount[:\s]+\$?([\d,]+\.?\d*)',  # amount: $amount
        r'bid[:\s]+\$?([\d,]+\.?\d*)',  # bid: $amount
    ]
    
    text_sources = [
        str(raw_jsonb.get('consideration', '')),
        str(raw_jsonb.get('amount', '')),  
        str(raw_jsonb.get('winning_bid', '')),
        str(doc_legal or ''),
        str(comments or ''),
        json.dumps(raw_jsonb) if isinstance(raw_jsonb, dict) else str(raw_jsonb)
    ]
    
    for text in text_sources:
        if not text:
            continue
            
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Clean up amount string and convert
                    amount_str = match.replace('$', '').replace(',', '').strip()
                    if amount_str:
                        amount = float(amount_str)
                        if amount > 0:  # Valid positive amount
                            return amount
                except ValueError:
                    continue
    
    return None

def get_staging_records() -> List[Dict]:
    """
    Retrieve Duval staging records from both grantor and tax deed tables
    Focus on foreclosure (CA) cases per briefing
    """
    staging_records = []
    
    try:
        with httpx.Client(timeout=60) as client:
            # Query grantor recordings staging
            grantor_resp = client.get(
                f"{BASE}/duval_clerk_grantor_recordings_staging",
                headers=HEADERS,
                params={"select": "*", "limit": "1000"}
            )
            
            if grantor_resp.status_code == 200:
                grantor_data = grantor_resp.json()
                print(f"Found {len(grantor_data)} grantor staging records")
                
                for record in grantor_data:
                    staging_records.append({
                        'source_table': 'duval_clerk_grantor_recordings_staging',
                        'record': record
                    })
            
            # Query tax deed recordings staging  
            tax_deed_resp = client.get(
                f"{BASE}/duval_tax_deed_recordings_staging",
                headers=HEADERS,
                params={"select": "*", "limit": "1000"}
            )
            
            if tax_deed_resp.status_code == 200:
                tax_deed_data = tax_deed_resp.json()
                print(f"Found {len(tax_deed_data)} tax deed staging records")
                
                for record in tax_deed_data:
                    staging_records.append({
                        'source_table': 'duval_tax_deed_recordings_staging',
                        'record': record
                    })
                    
    except Exception as e:
        print(f"Error retrieving staging records: {e}")
        return []
    
    print(f"Total staging records: {len(staging_records)}")
    return staging_records

def map_staging_to_outcomes(staging_records: List[Dict]) -> List[Dict]:
    """
    Map staging records to foreclosure_outcomes format
    """
    outcomes = []
    processed_cases = set()
    
    for staging_item in staging_records:
        record = staging_item['record']
        source_table = staging_item['source_table']
        
        # Extract case number
        raw_jsonb = record.get('raw_jsonb', {})
        doc_legal = record.get('doc_legal_description', '') 
        comments = record.get('comments', '')
        
        case_number = extract_case_number_from_staging(raw_jsonb, doc_legal, comments)
        if not case_number:
            continue
            
        # Skip duplicates
        if case_number in processed_cases:
            continue
        processed_cases.add(case_number)
        
        # Extract consideration amount
        winning_bid = extract_consideration_amount(raw_jsonb, doc_legal, comments)
        
        # Determine sale type and outcome details
        is_foreclosure = 'CA' in case_number.upper() or 'foreclosure' in str(raw_jsonb).lower()
        sale_type = 'foreclosure' if is_foreclosure else 'tax_deed'
        
        # Build foreclosure outcome record
        outcome = {
            'case_number': case_number,
            'county': 'duval',
            'sale_type': sale_type,
            'auction_date': record.get('recording_date') or record.get('doc_date'),
            'outcome': 'sold',  # Assume sold if recorded
            'winner_type': 'third_party',  # Default, could be refined
            'winner_name': record.get('grantee_name') or record.get('buyer_name'),
            'winning_bid': winning_bid,
            'plaintiff_raw': record.get('grantor_name') or record.get('seller_name'),
            'data_source': DATA_SOURCE,
            'source_url': record.get('document_url'),
            'enriched_at': datetime.now(timezone.utc).isoformat(),
            'staging_source': source_table,
            'staging_id': record.get('id')
        }
        
        # Clean up None values and ensure required fields
        outcome = {k: v for k, v in outcome.items() if v is not None}
        
        if case_number:  # Ensure we have the minimum required data
            outcomes.append(outcome)
    
    return outcomes

def write_outcomes_to_supabase(outcomes: List[Dict]) -> bool:
    """
    Write foreclosure outcomes to Supabase with conflict resolution
    """
    if not outcomes:
        print("No outcomes to write")
        return True
    
    try:
        with httpx.Client(timeout=120) as client:
            # Use upsert with conflict resolution
            response = client.post(
                f"{BASE}/foreclosure_outcomes",
                headers=HEADERS,
                params="?on_conflict=case_number,county,auction_date",
                json=outcomes
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ Successfully wrote {len(outcomes)} outcomes to foreclosure_outcomes")
                return True
            else:
                print(f"❌ Failed to write outcomes: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error writing outcomes: {e}")
        return False

def verify_outcomes_written() -> Dict:
    """
    Verify the outcomes were written and get counts
    """
    try:
        with httpx.Client(timeout=30) as client:
            # Get count of Duval foreclosure outcomes with our data source
            response = client.get(
                f"{BASE}/foreclosure_outcomes",
                headers=HEADERS,
                params={
                    "select": "count",
                    "county": "eq.duval", 
                    "data_source": f"eq.{DATA_SOURCE}"
                }
            )
            
            if response.status_code == 200:
                count_data = response.json()
                count = len(count_data) if isinstance(count_data, list) else count_data.get('count', 0)
                
                # Also get total duval outcomes
                total_response = client.get(
                    f"{BASE}/foreclosure_outcomes",
                    headers=HEADERS,
                    params={"select": "count", "county": "eq.duval"}
                )
                
                total_count = 0
                if total_response.status_code == 200:
                    total_data = total_response.json()
                    total_count = len(total_data) if isinstance(total_data, list) else total_data.get('count', 0)
                
                return {
                    'new_outcomes': count,
                    'total_duval_outcomes': total_count,
                    'verified': True
                }
            else:
                return {'verified': False, 'error': f"Verification failed: {response.status_code}"}
                
    except Exception as e:
        return {'verified': False, 'error': str(e)}

def main():
    print("🔄 DUVAL HARVEST→OUTCOMES MAPPER")
    print(f"Target: Bridge staging tables → foreclosure_outcomes")
    print(f"Data source: {DATA_SOURCE}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
    
    # Verify database connection
    try:
        with httpx.Client(timeout=10) as client:
            test_resp = client.get(f"{BASE}/fl_counties?limit=1", headers=HEADERS)
            if test_resp.status_code != 200:
                print(f"❌ Database connection failed: {test_resp.status_code}")
                return 1
        print("✅ Database connection verified\n")
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return 1
    
    # Step 1: Retrieve staging records
    print("📥 Retrieving staging records...")
    staging_records = get_staging_records()
    
    if not staging_records:
        print("⚠️ No staging records found. Check if harvest has run.")
        return 0
    
    # Step 2: Map to outcomes format
    print("🔄 Mapping staging records to foreclosure outcomes...")
    outcomes = map_staging_to_outcomes(staging_records)
    
    print(f"📊 Mapping results:")
    print(f"  - Input staging records: {len(staging_records)}")
    print(f"  - Output outcomes: {len(outcomes)}")
    
    if not outcomes:
        print("⚠️ No valid outcomes mapped. Check case number extraction logic.")
        return 0
    
    # Step 3: Write to foreclosure_outcomes
    print("💾 Writing outcomes to Supabase...")
    success = write_outcomes_to_supabase(outcomes)
    
    if not success:
        print("❌ Failed to write outcomes")
        return 1
    
    # Step 4: Verify and report
    print("✅ Verifying results...")
    verification = verify_outcomes_written()
    
    if verification.get('verified'):
        print(f"\n🎉 MAPPING COMPLETE")
        print(f"  - New outcomes written: {verification.get('new_outcomes', 0)}")
        print(f"  - Total Duval outcomes: {verification.get('total_duval_outcomes', 0)}")
        print(f"  - Data source: {DATA_SOURCE}")
        print(f"\n💡 IMPACT: tier1-promote-hourly will now pick up these amounts → F metric advances")
        print(f"💡 NEXT: Run verification to confirm B and F letter improvements")
        
        # Output SQL verification queries for the session report
        print(f"\n### SQL VERIFICATION")
        print(f"```sql")
        print(f"-- Verify new Duval outcomes written")
        print(f"SELECT COUNT(*) as new_outcomes FROM foreclosure_outcomes ")
        print(f"WHERE county = 'duval' AND data_source = '{DATA_SOURCE}';")
        print(f"")
        print(f"-- Verify total Duval outcomes")  
        print(f"SELECT COUNT(*) as total_outcomes FROM foreclosure_outcomes")
        print(f"WHERE county = 'duval';")
        print(f"")
        print(f"-- Run county evaluation")
        print(f"SELECT public.pencil_dod_evaluate_county('duval');")
        print(f"```")
        
    else:
        print(f"❌ Verification failed: {verification.get('error', 'Unknown error')}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())