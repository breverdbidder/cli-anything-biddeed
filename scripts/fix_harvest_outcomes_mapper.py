#!/usr/bin/env python3
"""
Fix harvest→outcomes mapper for foreclosure (CA) cases
 
Based on issue description:
"37 court-format Duval cases harvested clean (docs in duval_clerk_grantor_recordings_staging / 
duval_tax_deed_recordings_staging) but ZERO foreclosure_outcomes rows exist for duval. 
Staging rows lack case_number column — recover it from raw_jsonb / doc_legal_description / comments, 
map CT consideration→winning_bid, write foreclosure_outcomes with data_source=acclaim_ct:DUVAL-FC-V1"

This script builds the missing mapper to extract case_numbers from staging tables 
and populate foreclosure_outcomes.
"""
import os
import sys
import json
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any

try:
    import httpx
except ImportError:
    print("ERROR: httpx not available. Install with: pip install httpx")
    sys.exit(1)

# Setup Supabase connection
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY environment variable required")
    sys.exit(1)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def extract_case_number(raw_jsonb: Optional[Dict], doc_legal_description: Optional[str], comments: Optional[str]) -> Optional[str]:
    """
    Extract case_number from various staging data fields.
    Look for patterns like: 05-2024-CA-012345, 2024-CA-012345, etc.
    """
    # Check all potential sources
    sources = []
    if raw_jsonb:
        sources.append(json.dumps(raw_jsonb))
    if doc_legal_description:
        sources.append(doc_legal_description)
    if comments:
        sources.append(comments)
    
    # Common foreclosure case number patterns
    patterns = [
        r'\b(\d{2}-\d{4}-(?:CA|CC)-\d+)\b',  # 05-2024-CA-012345
        r'\b(\d{4}-(?:CA|CC)-\d+)\b',        # 2024-CA-012345  
        r'\b(\d{2}-\d{4}-(?:FC|FORE)-\d+)\b', # Some counties use FC
        r'\bCase\s*(?:No\.?|Number)?\s*:?\s*([A-Z0-9-]+)\b',  # Case No: ...
        r'\b(?:CA|CC)\s*(\d{2}-\d{4}-\d+)\b', # CA 05-2024-12345
    ]
    
    for source in sources:
        for pattern in patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                return match.group(1).upper()
    
    return None

def extract_consideration_amount(raw_jsonb: Optional[Dict], doc_legal_description: Optional[str]) -> Optional[float]:
    """
    Extract consideration amount (winning bid) from staging data.
    Look for patterns like: $123,456.78, consideration: 150000, etc.
    """
    sources = []
    if raw_jsonb:
        # Look for consideration field directly
        if 'consideration' in raw_jsonb:
            try:
                return float(str(raw_jsonb['consideration']).replace(',', '').replace('$', ''))
            except (ValueError, TypeError):
                pass
        sources.append(json.dumps(raw_jsonb))
    if doc_legal_description:
        sources.append(doc_legal_description)
    
    # Money patterns
    patterns = [
        r'\$?([\d,]+\.?\d*)\s*consideration',
        r'consideration[:\s]+\$?([\d,]+\.?\d*)',
        r'amount[:\s]+\$?([\d,]+\.?\d*)',
        r'bid[:\s]+\$?([\d,]+\.?\d*)',
        r'\$([0-9,]+(?:\.\d{2})?)\b',
    ]
    
    for source in sources:
        for pattern in patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                try:
                    amount = float(match.group(1).replace(',', ''))
                    if amount > 0:  # Sanity check
                        return amount
                except (ValueError, TypeError):
                    continue
    
    return None

def get_staging_records():
    """
    Get staging records that need case_number extraction.
    Based on issue description, check duval_clerk_grantor_recordings_staging and 
    duval_tax_deed_recordings_staging tables.
    """
    client = httpx.Client(timeout=60)
    
    # Try to get staging records from potential table names
    table_names = [
        'duval_clerk_grantor_recordings_staging',
        'duval_tax_deed_recordings_staging', 
        'duval_clerk_recordings_staging',
        'acclaim_staging',
        'brevard_fc_acclaim_raw'  # From the existing script
    ]
    
    all_records = []
    
    for table_name in table_names:
        try:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/{table_name}?select=*&limit=100",
                headers=sb_headers()
            )
            if r.status_code == 200:
                records = r.json()
                print(f"✅ Found {len(records)} records in {table_name}")
                all_records.extend([(table_name, record) for record in records])
            elif r.status_code == 404:
                print(f"⚠️  Table {table_name} not found")
            else:
                print(f"❌ Error accessing {table_name}: {r.status_code}")
        except Exception as e:
            print(f"❌ Exception accessing {table_name}: {e}")
    
    return all_records

def process_staging_to_outcomes():
    """
    Main function to process staging records and populate foreclosure_outcomes.
    """
    print("=== Harvest→Outcomes Mapper - Duval Foreclosure Cases ===")
    
    # Get staging records
    staging_records = get_staging_records()
    if not staging_records:
        print("❌ No staging records found to process")
        return
    
    # Process each staging record
    client = httpx.Client(timeout=60)
    processed = 0
    created_outcomes = 0
    
    for table_name, record in staging_records:
        print(f"\n--- Processing record from {table_name} ---")
        print(f"Record keys: {list(record.keys())}")
        
        # Extract case number
        raw_jsonb = record.get('raw_jsonb') or record.get('rec')
        doc_legal = record.get('doc_legal_description') or record.get('legal')
        comments = record.get('comments') or record.get('note')
        
        case_number = extract_case_number(raw_jsonb, doc_legal, comments)
        if not case_number:
            print(f"⚠️  Could not extract case_number from record")
            continue
            
        print(f"✅ Extracted case_number: {case_number}")
        
        # Extract consideration amount
        consideration = extract_consideration_amount(raw_jsonb, doc_legal)
        print(f"💰 Extracted consideration: ${consideration or 0}")
        
        # Extract other relevant fields
        rec_date = record.get('rec_date') or record.get('auction_date')
        winner = record.get('winner') or record.get('buyer') or record.get('grantee')
        grantor = record.get('grantor') or record.get('plaintiff_raw')
        
        # Create foreclosure_outcome record
        outcome_record = {
            "county_slug": "duval",
            "case_number": case_number,
            "auction_date": rec_date or datetime.now().date().isoformat(),
            "sale_status": "sold" if consideration and consideration > 0 else "unknown",
            "sale_amount": consideration,
            "buyer_name": winner,
            "buyer_type": "third_party" if winner else None,
            "plaintiff": grantor,
            "data_source": "acclaim_ct:DUVAL-FC-V1",
            "source_url": f"duval_staging_{table_name}",
            "confidence_level": "verified",
            "notes": f"Extracted from {table_name} staging table",
        }
        
        # Remove None values
        outcome_record = {k: v for k, v in outcome_record.items() if v is not None}
        
        print(f"📝 Creating outcome record: {outcome_record}")
        
        # Insert into foreclosure_outcomes table
        try:
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes?on_conflict=county_slug,case_number,auction_date",
                headers={**sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=outcome_record
            )
            
            if r.status_code in [200, 201, 204]:
                print(f"✅ Created foreclosure_outcome for case {case_number}")
                created_outcomes += 1
            else:
                print(f"❌ Failed to create outcome: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"❌ Exception creating outcome: {e}")
        
        processed += 1
        
        # Limit processing for safety
        if processed >= 50:
            print(f"⚠️  Processed {processed} records, stopping for safety")
            break
    
    print(f"\n=== Summary ===")
    print(f"Processed: {processed} staging records")
    print(f"Created: {created_outcomes} foreclosure_outcomes")
    
    return created_outcomes

if __name__ == "__main__":
    result = process_staging_to_outcomes()
    if result > 0:
        print(f"\n✅ SUCCESS: Created {result} foreclosure outcome records")
    else:
        print(f"\n❌ No outcome records were created")