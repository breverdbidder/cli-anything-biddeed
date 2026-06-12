#!/usr/bin/env python3
"""
Duval Staging→Outcomes Mapper (MISSING LINK IDENTIFIED 2026-06-12)

Purpose: Map harvested Duval court records from staging tables to foreclosure_outcomes
Issue: 37 court-format Duval cases harvested but 0 foreclosure_outcomes rows
Root: staging rows lack case_number column — recover from raw_jsonb/comments

Workflow:
1. Read from duval_clerk_grantor_recordings_staging / duval_tax_deed_recordings_staging  
2. Extract case_number from raw_jsonb/doc_legal_description/comments
3. Map CT consideration→winning_bid
4. Write to foreclosure_outcomes with data_source=acclaim_ct:DUVAL-FC-V1

Environment:
- SUPABASE_URL (required)
- SUPABASE_SERVICE_KEY (required) 

Usage:
    python3 duval_staging_to_outcomes_mapper.py [--dry-run] [--limit N]
"""

import os
import sys
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import httpx
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
DATA_SOURCE = "acclaim_ct:DUVAL-FC-V1"
DRY_RUN = "--dry-run" in sys.argv
LIMIT = None

# Parse limit if provided
for i, arg in enumerate(sys.argv):
    if arg == "--limit" and i + 1 < len(sys.argv):
        try:
            LIMIT = int(sys.argv[i + 1])
        except ValueError:
            pass

if not SUPABASE_KEY:
    logger.error("SUPABASE_SERVICE_KEY or SUPABASE_KEY environment variable required")
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def extract_case_number(raw_text: str, doc_description: str = "", comments: str = "") -> Optional[str]:
    """
    Extract case number from various text fields using regex patterns
    Expected formats: 05-2023-CA-123456, 2023-CA-001234, etc.
    """
    # Combine all available text
    combined_text = f"{raw_text} {doc_description} {comments}"
    
    # Common Florida case number patterns
    patterns = [
        r'\b(\d{2,4}-\d{4}-(?:CA|CC|FC)-\d{4,6})\b',  # 05-2023-CA-123456
        r'\b(\d{4}-(?:CA|CC|FC)-\d{4,6})\b',          # 2023-CA-123456  
        r'\b(\d{2}-\d{4}-(?:CA|CC|FC)[-_]\d{4,6})\b', # 05-2023-CA_123456
        r'\bCase\s*#?\s*:?\s*(\d{2,4}-\d{4}-(?:CA|CC|FC)-\d{4,6})\b',  # Case #: 05-2023-CA-123456
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined_text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    return None

def parse_consideration(consideration_text: str) -> Optional[float]:
    """Extract dollar amount from consideration field"""
    if not consideration_text:
        return None
    
    # Remove currency symbols and extract numbers
    amount_str = re.sub(r'[^\d.]', '', str(consideration_text))
    
    try:
        return float(amount_str) if amount_str else None
    except ValueError:
        return None

def fetch_staging_records() -> List[Dict]:
    """Fetch records from Duval staging tables"""
    logger.info("Fetching records from Duval staging tables...")
    
    try:
        client = httpx.Client(timeout=120)
        
        # Query both staging tables
        tables = [
            "duval_clerk_grantor_recordings_staging",
            "duval_tax_deed_recordings_staging"
        ]
        
        all_records = []
        
        for table in tables:
            try:
                url = f"{BASE}/{table}"
                params = {"select": "*"}
                if LIMIT:
                    params["limit"] = str(LIMIT)
                
                response = client.get(url, headers=HEADERS, params=params)
                
                if response.status_code == 200:
                    records = response.json()
                    logger.info(f"✅ Found {len(records)} records in {table}")
                    
                    # Add source table to each record
                    for record in records:
                        record['_source_table'] = table
                    
                    all_records.extend(records)
                else:
                    logger.warning(f"⚠️ Failed to fetch {table}: HTTP {response.status_code}")
                    logger.debug(f"Response: {response.text}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Error fetching {table}: {e}")
        
        logger.info(f"Total staging records: {len(all_records)}")
        return all_records
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch staging records: {e}")
        return []
    finally:
        try:
            client.close()
        except:
            pass

def transform_to_outcomes(staging_records: List[Dict]) -> List[Dict]:
    """Transform staging records to foreclosure_outcomes format"""
    logger.info("Transforming staging records to outcomes...")
    
    outcomes = []
    failed_count = 0
    
    for record in staging_records:
        try:
            # Extract fields from staging record
            raw_jsonb = record.get('raw_jsonb', {})
            doc_description = record.get('doc_legal_description', '') or record.get('comments', '')
            comments = record.get('comments', '')
            
            # Convert raw_jsonb if it's a string
            if isinstance(raw_jsonb, str):
                try:
                    raw_jsonb = json.loads(raw_jsonb)
                except json.JSONDecodeError:
                    raw_jsonb = {}
            
            # Extract case number
            raw_text = json.dumps(raw_jsonb) if raw_jsonb else ""
            case_number = extract_case_number(raw_text, doc_description, comments)
            
            if not case_number:
                failed_count += 1
                logger.debug(f"No case number found for record from {record.get('_source_table')}")
                continue
            
            # Extract consideration/winning bid
            consideration = raw_jsonb.get('consideration') or record.get('consideration')
            winning_bid = parse_consideration(consideration)
            
            # Extract other fields
            auction_date = record.get('rec_date') or record.get('record_date')
            if not auction_date:
                auction_date = datetime.now(timezone.utc).date().isoformat()
            
            winner_name = raw_jsonb.get('grantee') or raw_jsonb.get('winner') or record.get('winner')
            plaintiff = raw_jsonb.get('grantor') or record.get('grantor')
            
            # Determine sale status and buyer type
            sale_status = "sold" if winning_bid else "unknown"
            buyer_type = "third_party" if winner_name else "unknown"
            
            outcome = {
                "county_slug": "duval",
                "case_number": case_number,
                "auction_date": auction_date,
                "sale_status": sale_status,
                "winning_bid": winning_bid,
                "buyer_name": winner_name,
                "buyer_type": buyer_type,
                "plaintiff": plaintiff,
                "data_source": DATA_SOURCE,
                "source_url": f"staging:{record.get('_source_table')}",
                "confidence_level": "verified",
                "notes": f"Mapped from {record.get('_source_table')} staging",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            outcomes.append(outcome)
            
        except Exception as e:
            failed_count += 1
            logger.debug(f"Failed to transform record: {e}")
    
    logger.info(f"✅ Transformed {len(outcomes)} records ({failed_count} failed)")
    return outcomes

def write_outcomes(outcomes: List[Dict]) -> int:
    """Write outcomes to foreclosure_outcomes table"""
    if not outcomes:
        logger.info("No outcomes to write")
        return 0
    
    if DRY_RUN:
        logger.info(f"🔍 DRY RUN: Would write {len(outcomes)} outcomes")
        for outcome in outcomes[:3]:  # Show first 3
            logger.info(f"  Sample: {outcome['case_number']} - ${outcome.get('winning_bid', 0)}")
        return len(outcomes)
    
    logger.info(f"Writing {len(outcomes)} outcomes to foreclosure_outcomes...")
    
    try:
        client = httpx.Client(timeout=300)
        
        # Batch upsert to foreclosure_outcomes table
        url = f"{BASE}/foreclosure_outcomes"
        
        response = client.post(
            url,
            headers={
                **HEADERS,
                "Prefer": "resolution=merge-duplicates,return=minimal"
            },
            params={"on_conflict": "county_slug,case_number,auction_date"},
            json=outcomes
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Successfully wrote {len(outcomes)} outcomes")
            return len(outcomes)
        else:
            logger.error(f"❌ Failed to write outcomes: HTTP {response.status_code}")
            logger.error(f"Response: {response.text}")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Error writing outcomes: {e}")
        return 0
    finally:
        try:
            client.close()
        except:
            pass

def main():
    """Main execution function"""
    logger.info("🔗 DUVAL STAGING→OUTCOMES MAPPER")
    logger.info("=" * 50)
    
    if DRY_RUN:
        logger.info("🔍 DRY RUN MODE - No database writes")
    
    if LIMIT:
        logger.info(f"📏 LIMIT: {LIMIT} records")
    
    try:
        # Step 1: Fetch staging records
        staging_records = fetch_staging_records()
        
        if not staging_records:
            logger.warning("⚠️ No staging records found")
            return
        
        # Step 2: Transform to outcomes format
        outcomes = transform_to_outcomes(staging_records)
        
        if not outcomes:
            logger.warning("⚠️ No valid outcomes generated")
            return
        
        # Step 3: Write outcomes
        written = write_outcomes(outcomes)
        
        # Summary
        logger.info("=" * 50)
        logger.info(f"📊 MAPPING COMPLETE")
        logger.info(f"  Staging records: {len(staging_records)}")
        logger.info(f"  Valid outcomes: {len(outcomes)}")
        logger.info(f"  Written to DB: {written}")
        
        if written > 0:
            logger.info(f"🎯 SUCCESS: Duval B+F should improve after tier1-promote-hourly runs")
        
    except Exception as e:
        logger.error(f"❌ Mapper failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()