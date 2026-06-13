#!/usr/bin/env python3
"""
SHARD-3 Harvest→Outcomes Mapper
Missing link identified in CHAIN BREAK (2026-06-11): map staging records to foreclosure_outcomes

This script processes staging records from AcclaimWeb harvests and writes complete
foreclosure_outcomes records with proper case_number extraction and data_source attribution.

Handles both Brevard and Duval staging records per the CHAIN BREAK directive.
"""
import os
import sys
import json
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import httpx
except ImportError:
    print("❌ httpx not available - required for Supabase access")
    sys.exit(1)

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ SUPABASE_SERVICE_KEY environment variable required")
    sys.exit(1)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def extract_case_number_from_staging(staging_record):
    """
    Extract case_number from staging record fields per CHAIN BREAK directive.
    Order: raw_jsonb > doc_legal_description > comments > fallback patterns
    """
    record = staging_record
    
    # Try raw_jsonb first if it exists
    if 'raw_jsonb' in record and record['raw_jsonb']:
        try:
            raw_data = json.loads(record['raw_jsonb']) if isinstance(record['raw_jsonb'], str) else record['raw_jsonb']
            
            # Look for CaseNumber in raw data
            if 'CaseNumber' in raw_data and raw_data['CaseNumber']:
                case_num = str(raw_data['CaseNumber']).strip()
                if case_num and not case_num.startswith('PO-'):
                    return case_num
                    
            # Look for case number patterns in other raw fields
            for field in ['InstrumentNumber', 'DocumentNumber', 'BookPage']:
                if field in raw_data and raw_data[field]:
                    val = str(raw_data[field]).strip()
                    if re.match(r'\d{2}-\d{4}-[A-Z]{2}-\d+', val):  # Brevard format
                        return val
                        
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Try doc_legal_description
    if 'doc_legal_description' in record and record['doc_legal_description']:
        legal_desc = str(record['doc_legal_description'])
        
        # Look for case number patterns in legal description
        case_patterns = [
            r'\b(\d{2}-\d{4}-[A-Z]{2}-\d+(?:-[A-Z0-9]+)?)\b',  # Brevard: 05-2024-CA-123456-XXCA-BC
            r'Case No\.?\s*(\d{2}-\d{4}-[A-Z]{2}-\d+)',         # "Case No. 05-2024-CA-123456"
            r'[Cc]ase\s*(?:Number|#)\s*:?\s*(\d{2}-\d{4}-[A-Z]{2}-\d+)',
        ]
        
        for pattern in case_patterns:
            match = re.search(pattern, legal_desc)
            if match:
                return match.group(1).strip()
    
    # Try comments field
    if 'comments' in record and record['comments']:
        comments = str(record['comments'])
        case_patterns = [
            r'\b(\d{2}-\d{4}-[A-Z]{2}-\d+(?:-[A-Z0-9]+)?)\b',
            r'Case\s*(?:No\.?|Number|#)\s*:?\s*(\d{2}-\d{4}-[A-Z]{2}-\d+)',
        ]
        
        for pattern in case_patterns:
            match = re.search(pattern, comments)
            if match:
                return match.group(1).strip()
    
    # Fallback: try instrument number if present
    if 'instrument' in record and record['instrument']:
        instrument = str(record['instrument']).strip()
        if instrument and not instrument.startswith('PO-'):
            return f"INSTR-{instrument}"
    
    return None

def extract_consideration_amount(staging_record):
    """Extract winning bid amount from consideration field"""
    if 'consideration' in staging_record and staging_record['consideration']:
        cons = staging_record['consideration']
        if isinstance(cons, (int, float)):
            return float(cons) if cons > 0 else None
        if isinstance(cons, str):
            # Try to parse monetary amount
            cons_clean = re.sub(r'[,$]', '', cons.strip())
            try:
                amount = float(cons_clean)
                return amount if amount > 0 else None
            except ValueError:
                pass
    
    # Try raw_jsonb consideration
    if 'raw_jsonb' in staging_record and staging_record['raw_jsonb']:
        try:
            raw_data = json.loads(staging_record['raw_jsonb']) if isinstance(staging_record['raw_jsonb'], str) else staging_record['raw_jsonb']
            if 'Consideration' in raw_data:
                cons = raw_data['Consideration']
                if isinstance(cons, (int, float)) and cons > 0:
                    return float(cons)
                if isinstance(cons, str):
                    cons_clean = re.sub(r'[,$]', '', cons.strip())
                    try:
                        amount = float(cons_clean)
                        return amount if amount > 0 else None
                    except ValueError:
                        pass
        except (json.JSONDecodeError, TypeError):
            pass
    
    return None

def determine_outcome_and_winner_type(staging_record):
    """Determine outcome and winner_type from staging record"""
    winner_name = None
    plaintiff_raw = None
    outcome = "sold"
    winner_type = "third_party"
    
    # Extract winner and plaintiff from staging
    if 'winner' in staging_record and staging_record['winner']:
        winner_name = str(staging_record['winner']).strip()
    
    if 'grantor' in staging_record and staging_record['grantor']:
        plaintiff_raw = str(staging_record['grantor']).strip()
    
    # Try raw_jsonb
    if 'raw_jsonb' in staging_record and staging_record['raw_jsonb']:
        try:
            raw_data = json.loads(staging_record['raw_jsonb']) if isinstance(staging_record['raw_jsonb'], str) else staging_record['raw_jsonb']
            
            if not winner_name and 'IndirectName' in raw_data:
                winner_name = str(raw_data['IndirectName']).strip() if raw_data['IndirectName'] else None
            if not winner_name and 'Grantee' in raw_data:
                winner_name = str(raw_data['Grantee']).strip() if raw_data['Grantee'] else None
                
            if not plaintiff_raw and 'DirectName' in raw_data:
                plaintiff_raw = str(raw_data['DirectName']).strip() if raw_data['DirectName'] else None
            if not plaintiff_raw and 'Grantor' in raw_data:
                plaintiff_raw = str(raw_data['Grantor']).strip() if raw_data['Grantor'] else None
                
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Determine if plaintiff won (struck to plaintiff)
    if winner_name and plaintiff_raw:
        winner_upper = winner_name.upper()
        plaintiff_upper = plaintiff_raw.upper()
        
        # Check if winner matches plaintiff
        if (winner_upper == plaintiff_upper or 
            winner_upper in plaintiff_upper or 
            plaintiff_upper in winner_upper):
            outcome = "struck_to_plaintiff"
            winner_type = "plaintiff"
    
    return outcome, winner_type, winner_name, plaintiff_raw

def get_staging_records():
    """Retrieve staging records that need to be mapped to outcomes"""
    client = httpx.Client(timeout=60)
    
    staging_records = []
    
    # Check for Duval staging tables mentioned in brief
    for table_name in ['duval_clerk_grantor_recordings_staging', 'duval_tax_deed_recordings_staging']:
        try:
            url = f"{SUPABASE_URL}/rest/v1/{table_name}"
            params = "select=*&limit=1000"  # Start with recent records
            
            r = client.get(f"{url}?{params}", headers=sb_headers())
            
            if r.status_code == 200:
                records = r.json()
                print(f"✅ Found {len(records)} staging records in {table_name}")
                
                for record in records:
                    record['_source_table'] = table_name
                    record['_county'] = 'duval'
                    staging_records.append(record)
            else:
                print(f"⚠️ Could not access {table_name}: {r.status_code}")
                
        except Exception as e:
            print(f"⚠️ Error accessing {table_name}: {e}")
    
    # Also check for any Brevard staging tables
    for table_name in ['brevard_fc_acclaim_raw', 'brevard_clerk_recordings_staging']:
        try:
            url = f"{SUPABASE_URL}/rest/v1/{table_name}"
            params = "select=*&limit=1000"
            
            r = client.get(f"{url}?{params}", headers=sb_headers())
            
            if r.status_code == 200:
                records = r.json()
                print(f"✅ Found {len(records)} staging records in {table_name}")
                
                for record in records:
                    record['_source_table'] = table_name  
                    record['_county'] = 'brevard'
                    staging_records.append(record)
            else:
                print(f"⚠️ Could not access {table_name}: {r.status_code}")
                
        except Exception as e:
            print(f"⚠️ Error accessing {table_name}: {e}")
    
    client.close()
    return staging_records

def map_staging_to_outcomes(staging_records):
    """Map staging records to foreclosure_outcomes format"""
    outcomes = []
    
    for staging_record in staging_records:
        try:
            # Extract case number - this is the critical missing piece
            case_number = extract_case_number_from_staging(staging_record)
            if not case_number:
                print(f"⚠️ Could not extract case_number from staging record: {staging_record.get('instrument', 'UNKNOWN')}")
                continue
            
            # Skip PO- case numbers (not real court cases)
            if case_number.startswith('PO-'):
                continue
            
            county = staging_record.get('_county', 'unknown')
            
            # Extract auction date (use rec_date as recording date)
            auction_date = staging_record.get('rec_date')
            if not auction_date:
                print(f"⚠️ No rec_date for case {case_number}")
                continue
            
            # Extract consideration amount
            winning_bid = extract_consideration_amount(staging_record)
            
            # Determine outcome and parties
            outcome, winner_type, winner_name, plaintiff_raw = determine_outcome_and_winner_type(staging_record)
            
            # Build data source
            source_table = staging_record.get('_source_table', 'unknown')
            data_source = f"acclaim_ct:{county.upper()}-FC-V1"
            
            # Create foreclosure outcome record
            outcome_record = {
                "case_number": case_number,
                "county": county,
                "sale_type": "foreclosure",
                "auction_date": auction_date,
                "outcome": outcome,
                "winner_type": winner_type,
                "data_source": data_source,
                "enriched_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Add optional fields if available
            if winning_bid is not None:
                outcome_record["winning_bid"] = winning_bid
            if winner_name:
                outcome_record["winner_name"] = winner_name
            if plaintiff_raw:
                outcome_record["plaintiff_raw"] = plaintiff_raw
            
            # Build source URL if possible
            if 'instrument' in staging_record and staging_record['instrument']:
                base_url = "https://vaclmweb1.brevardclerk.us" if county == 'brevard' else "https://or.duvalclerk.com"
                outcome_record["source_url"] = f"{base_url}/AcclaimWeb/Details/?insNm={staging_record['instrument']}"
            
            outcomes.append(outcome_record)
            
        except Exception as e:
            print(f"❌ Error processing staging record: {e}")
            traceback.print_exc()
            continue
    
    return outcomes

def write_outcomes_to_db(outcomes):
    """Write foreclosure outcomes to database"""
    if not outcomes:
        print("No outcomes to write")
        return 0
    
    client = httpx.Client(timeout=120)
    
    try:
        # Upsert to foreclosure_outcomes
        url = f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes"
        params = "?on_conflict=case_number,county,auction_date"
        
        headers = sb_headers()
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        
        r = client.post(f"{url}{params}", headers=headers, json=outcomes)
        
        if r.status_code in [201, 204]:
            print(f"✅ Successfully wrote {len(outcomes)} foreclosure outcomes")
            return len(outcomes)
        else:
            print(f"❌ Failed to write outcomes: {r.status_code} - {r.text}")
            return 0
            
    except Exception as e:
        print(f"❌ Error writing outcomes: {e}")
        traceback.print_exc()
        return 0
    finally:
        client.close()

def main():
    """Main execution for harvest→outcomes mapper"""
    print("🚀 SHARD-3 Harvest→Outcomes Mapper")
    print("Building missing link: staging records → foreclosure_outcomes")
    print("=" * 70)
    
    try:
        # Get staging records
        print("📥 Retrieving staging records...")
        staging_records = get_staging_records()
        
        if not staging_records:
            print("⚠️ No staging records found to process")
            return
        
        print(f"✅ Found {len(staging_records)} total staging records")
        
        # Map to outcomes
        print("🔄 Mapping staging records to outcomes...")
        outcomes = map_staging_to_outcomes(staging_records)
        
        print(f"✅ Successfully mapped {len(outcomes)} outcomes")
        
        if outcomes:
            # Write to database
            print("💾 Writing outcomes to foreclosure_outcomes...")
            written_count = write_outcomes_to_db(outcomes)
            
            print(f"✅ Harvest→outcomes mapping complete: {written_count} records written")
            
            # Show sample for verification
            if written_count > 0:
                print("\n📋 Sample mapped outcome:")
                sample = outcomes[0]
                for key, value in sample.items():
                    print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"❌ Critical error in mapper: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()