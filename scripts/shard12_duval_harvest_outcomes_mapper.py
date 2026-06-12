#!/usr/bin/env python3
"""
Duval harvest→outcomes mapper for SHARD-12 Gold Standard
Maps staging tables to foreclosure_outcomes to fix the chain break

CHAIN BREAK: 37 court-format Duval cases harvested clean but ZERO foreclosure_outcomes rows exist
MISSING MAPPER: Staging tables lack case_number column - need to recover from raw_jsonb/doc_legal_description/comments

Flow:
  duval_clerk_grantor_recordings_staging -> parse case_number -> foreclosure_outcomes
  duval_tax_deed_recordings_staging -> parse case_number -> foreclosure_outcomes
  
Data source: acclaim_ct:DUVAL-FC-V1 (not promote - will be picked up by tier1-promote-hourly)

SHARD-12 Target: Fix Duval B (verified outcomes) and F (tier1 sold) metrics
"""

import os
import sys
import json
import re
import datetime as dt
from typing import Dict, List, Optional, Tuple
import psycopg2
import psycopg2.extras

# Database connection
def get_db_connection():
    """Get database connection with proper timeout"""
    conn = psycopg2.connect(
        host='aws-0-us-west-2.pooler.supabase.com',
        port=5432,
        database='postgres',
        user='postgres.mocerqjnksmhcjzxrewo',
        password=os.environ.get('SUPABASE_DB_PASSWORD', 'BiKvLwWTdS0PwulM')
    )
    return conn

def extract_case_number(raw_jsonb: dict, doc_legal_description: str, comments: str) -> Optional[str]:
    """Extract case number from various fields using patterns"""
    
    # Duval case number patterns: 
    # - YYYY-CA-NNNNNN (foreclosure)  
    # - YYYY-CC-NNNNNN (civil)
    # - YYYY-DR-NNNNNN (domestic relations)
    case_patterns = [
        r'(\d{4}-(?:CA|CC|DR|CF|CR|CI)-\d{6})',  # Standard Duval case format
        r'Case\s*(?:No\.?\s*)?:?\s*(\d{4}-[A-Z]{2}-\d{6})',  # Case No: format
        r'(?:Cause|Case)\s*(?:Number|No\.?)\s*(\d{4}-[A-Z]{2}-\d{6})',  # Cause Number format
        r'(\d{2}-\d{4}-[A-Z]{2}-\d{6})',  # Alternative format
    ]
    
    # Search in raw_jsonb first
    if raw_jsonb:
        json_str = json.dumps(raw_jsonb) if isinstance(raw_jsonb, dict) else str(raw_jsonb)
        for pattern in case_patterns:
            matches = re.findall(pattern, json_str, re.IGNORECASE)
            if matches:
                return matches[0].upper()
    
    # Search in legal description
    if doc_legal_description:
        for pattern in case_patterns:
            matches = re.findall(pattern, doc_legal_description, re.IGNORECASE)
            if matches:
                return matches[0].upper()
    
    # Search in comments
    if comments:
        for pattern in case_patterns:
            matches = re.findall(pattern, comments, re.IGNORECASE)
            if matches:
                return matches[0].upper()
    
    return None

def extract_consideration(raw_jsonb: dict) -> Optional[float]:
    """Extract consideration (winning bid) from raw JSON data"""
    if not raw_jsonb:
        return None
    
    # Common fields where consideration might be stored
    consideration_fields = [
        'consideration', 'Consideration', 'CONSIDERATION',
        'amount', 'Amount', 'AMOUNT',
        'winning_bid', 'WinningBid', 'WINNING_BID',
        'sale_amount', 'SaleAmount', 'SALE_AMOUNT',
        'bid_amount', 'BidAmount', 'BID_AMOUNT'
    ]
    
    for field in consideration_fields:
        if field in raw_jsonb:
            try:
                value = raw_jsonb[field]
                if isinstance(value, (int, float)):
                    return float(value)
                elif isinstance(value, str):
                    # Clean up string values - remove $, commas, etc.
                    clean_value = re.sub(r'[^\d.-]', '', value)
                    if clean_value:
                        return float(clean_value)
            except (ValueError, TypeError):
                continue
    
    return None

def determine_outcome_type(case_number: str, winner_name: str, plaintiff_name: str) -> Tuple[str, str]:
    """Determine outcome and winner type based on case details"""
    
    # Default to sold/third_party
    outcome = "sold"
    winner_type = "third_party"
    
    # Check if plaintiff won (struck to plaintiff)
    if winner_name and plaintiff_name:
        winner_clean = winner_name.upper().strip()
        plaintiff_clean = plaintiff_name.upper().strip()
        
        # Check for plaintiff indicators
        plaintiff_indicators = ['PLAINTIFF', 'BANK', 'TRUST', 'MORTGAGE', 'FEDERAL', 'NATIONAL']
        winner_indicators = any(indicator in winner_clean for indicator in plaintiff_indicators)
        
        # Check if winner and plaintiff names match or overlap significantly
        if (winner_clean == plaintiff_clean or 
            winner_clean in plaintiff_clean or 
            plaintiff_clean in winner_clean or
            winner_indicators):
            outcome = "struck_to_plaintiff"
            winner_type = "plaintiff"
    
    return outcome, winner_type

def process_staging_records(conn, table_name: str, data_source: str) -> List[Dict]:
    """Process records from a staging table"""
    
    print(f"Processing staging table: {table_name}")
    
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Get staging records that haven't been processed yet
        cur.execute(f"""
            SELECT * FROM {table_name}
            WHERE processed_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1000
        """)
        
        staging_records = cur.fetchall()
        print(f"Found {len(staging_records)} unprocessed records in {table_name}")
        
        outcomes = []
        processed_ids = []
        
        for record in staging_records:
            try:
                # Extract case number from various fields
                case_number = extract_case_number(
                    record.get('raw_jsonb'),
                    record.get('doc_legal_description', ''),
                    record.get('comments', '')
                )
                
                if not case_number:
                    print(f"No case number found for record {record.get('id')}")
                    continue
                
                # Extract consideration (winning bid)
                winning_bid = extract_consideration(record.get('raw_jsonb'))
                
                # Get other relevant fields
                winner_name = record.get('winner_name') or record.get('grantee') or record.get('buyer')
                plaintiff_name = record.get('plaintiff_name') or record.get('grantor')
                
                # Determine outcome and winner type
                outcome, winner_type = determine_outcome_type(case_number, winner_name, plaintiff_name)
                
                # Use record date or default to created_at
                auction_date = record.get('record_date') or record.get('created_at', dt.datetime.now()).date()
                if isinstance(auction_date, dt.datetime):
                    auction_date = auction_date.date()
                
                outcome_record = {
                    'case_number': case_number,
                    'county': 'duval',
                    'sale_type': 'foreclosure',
                    'auction_date': auction_date.isoformat(),
                    'outcome': outcome,
                    'winner_type': winner_type,
                    'winner_name': winner_name,
                    'winning_bid': winning_bid,
                    'plaintiff_raw': plaintiff_name,
                    'data_source': data_source,
                    'source_url': record.get('source_url'),
                    'enriched_at': dt.datetime.now(dt.timezone.utc).isoformat()
                }
                
                outcomes.append(outcome_record)
                processed_ids.append(record['id'])
                
                print(f"Mapped record {record['id']}: {case_number} -> ${winning_bid or 0}")
                
            except Exception as e:
                print(f"Error processing record {record.get('id')}: {e}")
                continue
        
        return outcomes, processed_ids

def write_foreclosure_outcomes(conn, outcomes: List[Dict]) -> int:
    """Write outcomes to foreclosure_outcomes table with conflict resolution"""
    
    if not outcomes:
        return 0
    
    with conn.cursor() as cur:
        # Insert with ON CONFLICT resolution
        insert_sql = """
            INSERT INTO public.foreclosure_outcomes (
                case_number, county, sale_type, auction_date, outcome, 
                winner_type, winner_name, winning_bid, plaintiff_raw, 
                data_source, source_url, enriched_at
            ) VALUES %s
            ON CONFLICT (case_number, county, auction_date) 
            DO UPDATE SET
                outcome = EXCLUDED.outcome,
                winner_type = EXCLUDED.winner_type,
                winner_name = EXCLUDED.winner_name,
                winning_bid = EXCLUDED.winning_bid,
                plaintiff_raw = EXCLUDED.plaintiff_raw,
                data_source = EXCLUDED.data_source,
                source_url = EXCLUDED.source_url,
                enriched_at = EXCLUDED.enriched_at
        """
        
        # Convert outcomes to tuples for psycopg2
        values = [
            (
                o['case_number'], o['county'], o['sale_type'], o['auction_date'],
                o['outcome'], o['winner_type'], o['winner_name'], o['winning_bid'],
                o['plaintiff_raw'], o['data_source'], o['source_url'], o['enriched_at']
            )
            for o in outcomes
        ]
        
        psycopg2.extras.execute_values(cur, insert_sql, values)
        conn.commit()
        
        return len(outcomes)

def mark_processed(conn, table_name: str, processed_ids: List[int]):
    """Mark staging records as processed"""
    
    if not processed_ids:
        return
    
    with conn.cursor() as cur:
        cur.execute(f"""
            UPDATE {table_name} 
            SET processed_at = NOW()
            WHERE id = ANY(%s)
        """, (processed_ids,))
        conn.commit()
        
        print(f"Marked {len(processed_ids)} records as processed in {table_name}")

def main():
    """Main mapper execution"""
    print("=== Duval Harvest→Outcomes Mapper (SHARD-12) ===")
    print(f"Started at: {dt.datetime.now()}")
    
    try:
        conn = get_db_connection()
        
        # Set statement timeout
        with conn.cursor() as cur:
            cur.execute('SET statement_timeout = 0;')
        
        total_written = 0
        
        # Process both staging tables
        staging_tables = [
            ('public.duval_clerk_grantor_recordings_staging', 'acclaim_ct:DUVAL-FC-V1'),
            ('public.duval_tax_deed_recordings_staging', 'acclaim_ct:DUVAL-TD-V1')
        ]
        
        for table_name, data_source in staging_tables:
            try:
                # Check if table exists
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = %s
                        )
                    """, (table_name.split('.')[1],))
                    
                    table_exists = cur.fetchone()[0]
                    
                if not table_exists:
                    print(f"Table {table_name} does not exist, skipping...")
                    continue
                
                # Process records from this staging table
                outcomes, processed_ids = process_staging_records(conn, table_name, data_source)
                
                if outcomes:
                    # Write to foreclosure_outcomes
                    written_count = write_foreclosure_outcomes(conn, outcomes)
                    total_written += written_count
                    
                    # Mark staging records as processed
                    mark_processed(conn, table_name, processed_ids)
                    
                    print(f"Processed {written_count} outcomes from {table_name}")
                else:
                    print(f"No mappable records found in {table_name}")
                    
            except Exception as e:
                print(f"Error processing {table_name}: {e}")
                continue
        
        # Report results
        print(f"\n=== MAPPER COMPLETE ===")
        print(f"Total foreclosure_outcomes written: {total_written}")
        print(f"Data sources used: acclaim_ct:DUVAL-FC-V1, acclaim_ct:DUVAL-TD-V1")
        print(f"Note: tier1-promote-hourly will automatically pick up these outcomes")
        
        if total_written > 0:
            print(f"\n🎯 DUVAL B+F METRICS SHOULD IMPROVE")
            print(f"Next: Run verification query to confirm metrics moved")
        
        conn.close()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()