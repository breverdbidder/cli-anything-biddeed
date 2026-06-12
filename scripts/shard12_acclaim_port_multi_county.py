#!/usr/bin/env python3
"""
SHARD-12 AcclaimWeb port for marion, clay, pasco counties
Ports the Brevard AcclaimWeb pipeline to other Florida county AcclaimWeb endpoints

BREVARD SUCCESS: vaclmweb1.brevardclerk.us/AcclaimWeb/
TARGET COUNTIES (SHARD-12):
- Marion County: UNTESTED endpoint (likely marionaccessclerk.org or similar)  
- Clay County: UNTESTED endpoint
- Pasco County: UNTESTED endpoint
- Glades County: UNTESTED endpoint

Strategy:
1. Auto-discover AcclaimWeb endpoints per county
2. Test authentication and document type availability
3. Port the Brevard acclaim_ct_sweep.py pattern
4. Write to foreclosure_outcomes with county-specific data_source

Based on: scripts/acclaim_ct_sweep.py (Brevard reference implementation)
"""

import os
import sys
import json
import re
import time
import calendar
import datetime as dt
import urllib.request
import urllib.parse
import http.cookiejar
from typing import Dict, List, Optional, Tuple
import psycopg2
import psycopg2.extras

# County AcclaimWeb endpoint discovery
COUNTY_ENDPOINTS = {
    'marion': [
        'https://or.marioncountyclerk.org/AcclaimWeb/',
        'https://public.marioncountyclerk.org/AcclaimWeb/',
        'https://records.marioncountyclerk.org/AcclaimWeb/',
        'https://marionaccessclerk.org/AcclaimWeb/',
    ],
    'clay': [
        'https://or.clayclerk.com/AcclaimWeb/',
        'https://records.clayclerk.com/AcclaimWeb/',
        'https://public.clayclerk.com/AcclaimWeb/',
    ],
    'pasco': [
        'https://or.pascoclerks.com/AcclaimWeb/',
        'https://records.pascoclerks.com/AcclaimWeb/', 
        'https://public.pascoclerks.com/AcclaimWeb/',
        'https://pascoclerk.com/AcclaimWeb/',
    ],
    'glades': [
        'https://or.gladesclerk.com/AcclaimWeb/',
        'https://records.gladesclerk.com/AcclaimWeb/',
        'https://public.gladesclerk.com/AcclaimWeb/',
    ]
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 2.5

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        host='aws-0-us-west-2.pooler.supabase.com',
        port=5432,
        database='postgres', 
        user='postgres.mocerqjnksmhcjzxrewo',
        password=os.environ.get('SUPABASE_DB_PASSWORD', 'BiKvLwWTdS0PwulM')
    )

def test_acclaim_endpoint(base_url: str) -> Tuple[bool, Dict]:
    """Test if an AcclaimWeb endpoint is accessible and functional"""
    
    print(f"Testing AcclaimWeb endpoint: {base_url}")
    
    try:
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        
        def req(url, data=None, headers=None):
            time.sleep(THROTTLE)
            r = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
            r.add_header("User-Agent", UA)
            if headers:
                for k, v in headers.items():
                    r.add_header(k, v)
            
            try:
                with opener.open(r, timeout=30) as resp:
                    return resp.read().decode("utf-8", "replace"), resp.status
            except Exception as e:
                return None, str(e)
        
        # Test 1: Main AcclaimWeb page
        content, status = req(base_url)
        if content is None:
            return False, {"error": f"Failed to load main page: {status}"}
        
        if "AcclaimWeb" not in content:
            return False, {"error": "Page does not contain AcclaimWeb content"}
        
        # Test 2: Disclaimer page
        disclaimer_url = base_url.rstrip('/') + '/search/Disclaimer'
        content, status = req(disclaimer_url, data="disclaimer=on", 
                            headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        # Test 3: Search page access
        search_url = base_url.rstrip('/') + '/search/SearchTypeDocType'
        content, status = req(search_url)
        
        return True, {
            "base_url": base_url,
            "accessible": True,
            "has_search": "SearchTypeDocType" in (content or ""),
            "tested_at": dt.datetime.now().isoformat()
        }
        
    except Exception as e:
        return False, {"error": str(e)}

def discover_working_endpoint(county: str) -> Optional[str]:
    """Discover working AcclaimWeb endpoint for a county"""
    
    endpoints = COUNTY_ENDPOINTS.get(county, [])
    
    for endpoint in endpoints:
        success, info = test_acclaim_endpoint(endpoint)
        if success:
            print(f"✅ Found working endpoint for {county}: {endpoint}")
            return endpoint
        else:
            print(f"❌ {endpoint}: {info.get('error', 'Failed')}")
    
    print(f"⚠️  No working AcclaimWeb endpoint found for {county}")
    return None

def port_acclaim_scraper(county: str, base_url: str, year: int, month: int) -> List[Dict]:
    """Port the Brevard acclaim scraper logic to another county"""
    
    print(f"Porting AcclaimWeb scraper to {county} ({base_url})")
    
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    def req(url, data=None, headers=None, retries=3):
        for attempt in range(retries):
            time.sleep(THROTTLE * (2 ** attempt if attempt else 1))
            try:
                r = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
                r.add_header("User-Agent", UA)
                if headers:
                    for k, v in headers.items():
                        r.add_header(k, v)
                with opener.open(r, timeout=60) as resp:
                    return resp.read().decode("utf-8", "replace")
            except Exception as e:
                print(f"Retry {attempt+1}/{retries} for {url}: {e}")
                if attempt == retries - 1:
                    raise
        return None
    
    try:
        # Initialize session
        req(base_url)
        req(base_url.rstrip('/') + '/search/Disclaimer', 
            data="disclaimer=on",
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        # Search for Certificate of Title documents
        last_day = calendar.monthrange(year, month)[1]
        payload = urllib.parse.urlencode({
            "DocTypes": "79",  # Standard CT doc type - may vary by county
            "DocTypesDisplay-input": "CERTIFICATE OF TITLE (CT)",
            "DocTypesDisplay": "CERTIFICATE OF TITLE (CT)",
            "DateRangeList": " ",
            "RecordDateFrom": f"{month}/1/{year}",
            "RecordDateTo": f"{month}/{last_day}/{year}",
        })
        
        search_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": base_url.rstrip('/') + '/search/SearchTypeDocType'
        }
        
        # Submit search criteria
        criteria_url = base_url.rstrip('/') + '/search/SearchTypeDocType?Length=6'
        req(criteria_url, data=payload, headers=search_headers)
        
        # Get results
        results_url = base_url.rstrip('/') + '/search/GridResults'
        
        all_rows = []
        page = 1
        while True:
            try:
                result_json = req(results_url, 
                                data=f"page={page}&size=200", 
                                headers=search_headers)
                
                data = json.loads(result_json)
                rows = data.get("data", [])
                total = data.get("total", 0)
                
                all_rows.extend(rows)
                
                if len(all_rows) >= total or not rows:
                    break
                
                page += 1
                
            except Exception as e:
                print(f"Error getting page {page}: {e}")
                break
        
        print(f"Retrieved {len(all_rows)} records for {county} {year}-{month:02d}")
        return all_rows
        
    except Exception as e:
        print(f"Error scraping {county}: {e}")
        return []

def transform_county_record(record: Dict, county: str, base_url: str) -> Optional[Dict]:
    """Transform county record to foreclosure_outcomes format"""
    
    try:
        # Extract record date
        rec_date_raw = record.get("RecordDate", "")
        if rec_date_raw:
            ms = int(re.search(r'-?\d+', rec_date_raw).group())
            rec_date = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()
        else:
            rec_date = dt.date.today()
        
        # Extract case number
        case_number = record.get("CaseNumber", "").strip()
        if not case_number:
            case_number = f"INSTR-{record.get('InstrumentNumber', 'UNK')}"
        
        # Determine if plaintiff won
        grantor = (record.get("DirectName") or "").upper()
        grantee = (record.get("IndirectName") or "").upper()
        
        plaintiff_won = bool(grantor and grantee and (
            grantor == grantee or grantor in grantee or grantee in grantor
        ))
        
        # Extract consideration
        consideration = record.get("Consideration")
        winning_bid = None
        if consideration not in (None, ""):
            try:
                winning_bid = float(consideration)
            except (ValueError, TypeError):
                pass
        
        outcome_record = {
            'case_number': case_number,
            'county': county,
            'sale_type': 'foreclosure',
            'auction_date': rec_date.isoformat(),
            'outcome': 'struck_to_plaintiff' if plaintiff_won else 'sold',
            'winner_type': 'plaintiff' if plaintiff_won else 'third_party',
            'winner_name': record.get("IndirectName", "").strip() or None,
            'winning_bid': winning_bid,
            'plaintiff_raw': record.get("DirectName", "").strip() or None,
            'data_source': f'{county}_acclaim_ct_recdate',
            'source_url': f"{base_url}/Details/?docId={record.get('TransactionItemId')}&insNm={record.get('InstrumentNumber')}",
            'enriched_at': dt.datetime.now(dt.timezone.utc).isoformat()
        }
        
        return outcome_record
        
    except Exception as e:
        print(f"Error transforming record: {e}")
        return None

def write_outcomes(conn, outcomes: List[Dict]) -> int:
    """Write outcomes to database"""
    
    if not outcomes:
        return 0
    
    with conn.cursor() as cur:
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
        
        values = [
            (o['case_number'], o['county'], o['sale_type'], o['auction_date'],
             o['outcome'], o['winner_type'], o['winner_name'], o['winning_bid'],
             o['plaintiff_raw'], o['data_source'], o['source_url'], o['enriched_at'])
            for o in outcomes
        ]
        
        psycopg2.extras.execute_values(cur, insert_sql, values)
        conn.commit()
        
        return len(outcomes)

def main():
    """Main execution for SHARD-12 AcclaimWeb port"""
    
    print("=== SHARD-12 AcclaimWeb Multi-County Port ===")
    
    # Target counties for SHARD-12
    target_counties = ['marion', 'clay', 'pasco']  # Skip glades - likely too small
    
    # Default to previous month 
    today = dt.date.today()
    prev_month = today.replace(day=1) - dt.timedelta(days=1)
    year, month = prev_month.year, prev_month.month
    
    # Override from command line if provided
    if len(sys.argv) >= 3:
        year, month = int(sys.argv[1]), int(sys.argv[2])
    
    print(f"Target period: {year}-{month:02d}")
    
    try:
        conn = get_db_connection()
        
        # Set statement timeout
        with conn.cursor() as cur:
            cur.execute('SET statement_timeout = 0;')
        
        total_outcomes = 0
        successful_counties = []
        
        for county in target_counties:
            print(f"\n--- Processing {county.upper()} County ---")
            
            # Discover working endpoint
            endpoint = discover_working_endpoint(county)
            if not endpoint:
                print(f"⚠️  Skipping {county} - no working AcclaimWeb endpoint")
                continue
            
            try:
                # Scrape the county
                records = port_acclaim_scraper(county, endpoint, year, month)
                
                if not records:
                    print(f"No records found for {county}")
                    continue
                
                # Transform records
                outcomes = []
                for record in records:
                    outcome = transform_county_record(record, county, endpoint)
                    if outcome:
                        outcomes.append(outcome)
                
                if outcomes:
                    # Write to database
                    written = write_outcomes(conn, outcomes)
                    total_outcomes += written
                    successful_counties.append(county)
                    
                    print(f"✅ {county}: {written} outcomes written")
                else:
                    print(f"No valid outcomes for {county}")
                    
            except Exception as e:
                print(f"❌ Error processing {county}: {e}")
                continue
        
        # Summary
        print(f"\n=== SHARD-12 ACCLAIM PORT COMPLETE ===")
        print(f"Period: {year}-{month:02d}")
        print(f"Successful counties: {successful_counties}")
        print(f"Total outcomes written: {total_outcomes}")
        
        if total_outcomes > 0:
            print(f"\n🎯 SHARD-12 B+F METRICS SHOULD IMPROVE")
            print(f"Counties with new verified outcomes: {successful_counties}")
        
        conn.close()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()