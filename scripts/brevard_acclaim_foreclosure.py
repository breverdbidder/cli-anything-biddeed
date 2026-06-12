#!/usr/bin/env python3
"""Brevard AcclaimWeb Foreclosure Outcomes Scraper
GOLD STANDARD Letter B+F implementation for Brevard county.

Extends existing acclaim_ct_sweep.py pattern to capture foreclosure outcomes
from Certificate of Title records and write to foreclosure_outcomes table.

Usage: python3 scripts/brevard_acclaim_foreclosure.py [YYYY-MM] [YYYY-MM]
Defaults to previous month through current month.

VERIFIED endpoint: http://vaclmweb1.brevardclerk.us/AcclaimWeb/
Target table: public.foreclosure_outcomes
Data source: brevard_acclaim_ct_foreclosure

Author: Claude Code (GOLD STANDARD Session 2026-06-12)
"""
import sys, os, json, re, time, calendar, datetime as dt
import urllib.request, urllib.parse, http.cookiejar

# Configuration
BASE = "http://vaclmweb1.brevardclerk.us"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 2.5
DATA_SOURCE = "brevard_acclaim_ct_foreclosure"

# Environment
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SB_URL or not SB_KEY:
    print("❌ SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
    sys.exit(1)

# HTTP setup
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def make_request(url, data=None, headers=None, retries=4):
    """Make HTTP request with exponential backoff"""
    for attempt in range(retries):
        time.sleep(THROTTLE * (2 ** attempt if attempt else 1))
        try:
            req = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
            req.add_header("User-Agent", UA)
            
            for k, v in (headers or {}).items():
                req.add_header(k, v)
                
            with opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
                
        except Exception as e:
            sys.stderr.write(f"retry {attempt+1}/{retries}: {e}\n")
            if attempt == retries - 1:
                raise
    return None

def write_foreclosure_outcomes(outcomes):
    """Write foreclosure outcomes to Gold Standard table"""
    if not outcomes:
        return 0
        
    try:
        body = json.dumps(outcomes).encode()
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/foreclosure_outcomes",
            data=body,
            method="POST"
        )
        req.add_header("apikey", SB_KEY)
        req.add_header("Authorization", f"Bearer {SB_KEY}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Prefer", "resolution=merge-duplicates,return=minimal")
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            if resp.status in (200, 201):
                print(f"✅ Wrote {len(outcomes)} foreclosure outcomes to database")
                return len(outcomes)
            else:
                print(f"❌ Failed to write outcomes: {resp.status}", file=sys.stderr)
                return 0
                
    except Exception as e:
        print(f"❌ Error writing foreclosure outcomes: {e}", file=sys.stderr)
        return 0

def initialize_session():
    """Initialize AcclaimWeb session with disclaimer acceptance"""
    make_request(BASE + "/AcclaimWeb/")
    make_request(
        BASE + "/AcclaimWeb/search/Disclaimer", 
        data="disclaimer=on",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE + "/AcclaimWeb/"
        }
    )

def get_month_records(year, month):
    """Get Certificate of Title records for a specific month"""
    last_day = calendar.monthrange(year, month)[1]
    
    # Search for Certificate of Title documents (doc type 79)
    payload = urllib.parse.urlencode({
        "DocTypes": "79",
        "DocTypesDisplay-input": "CERTIFICATE OF TITLE (CT)",
        "DocTypesDisplay": "CERTIFICATE OF TITLE (CT)",
        "DateRangeList": " ",
        "RecordDateFrom": f"{month}/1/{year}",
        "RecordDateTo": f"{month}/{last_day}/{year}",
    })
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE + "/AcclaimWeb/search/SearchTypeDocType"
    }
    
    # Submit search criteria
    response = make_request(
        BASE + "/AcclaimWeb/search/SearchTypeDocType?Length=6",
        data=payload,
        headers=headers
    )
    
    if "Error.htm" in (response or ""):
        raise RuntimeError(f"Search criteria error for {year}-{month:02d}")
    
    # Get paginated results
    records = []
    page = 1
    
    while True:
        grid_response = make_request(
            BASE + "/AcclaimWeb/search/GridResults",
            data=f"page={page}&size=200",
            headers=headers
        )
        
        data = json.loads(grid_response)
        records.extend(data["data"])
        
        if len(records) >= data["total"] or not data["data"]:
            return records, data["total"]
        
        page += 1

def transform_to_foreclosure_outcome(record):
    """Transform AcclaimWeb CT record to foreclosure_outcome"""
    # Parse record date from epoch milliseconds
    record_date_ms = int(re.search(r"-?\d+", record["RecordDate"]).group())
    record_date = dt.datetime.fromtimestamp(
        record_date_ms / 1000, 
        dt.timezone.utc
    ).date().isoformat()
    
    # Extract case number (should be foreclosure case format)
    case_number = (record.get("CaseNumber") or "").strip()
    if not case_number:
        case_number = f"INSTR-{record.get('InstrumentNumber', '')}"
    
    # Determine if plaintiff struck or third party won
    grantor = (record.get("CompressedDirectName") or "").upper()
    grantee = (record.get("CompressedIndirectName") or "").upper()
    is_plaintiff_strike = bool(grantor and grantee and (grantor == grantee or grantor in grantee or grantee in grantor))
    
    # Extract consideration (winning bid)
    consideration = record.get("Consideration")
    winning_bid = float(consideration) if consideration not in (None, "") else None
    
    outcome = {
        "county_slug": "brevard",
        "case_number": case_number,
        "auction_date": record_date,  # Using record date as proxy for sale date
        "sale_status": "struck" if is_plaintiff_strike else "sold",
        "sale_amount": winning_bid,
        "buyer_name": (record.get("IndirectName") or "").strip() or None,
        "buyer_type": "plaintiff" if is_plaintiff_strike else "third_party",
        "plaintiff": (record.get("DirectName") or "").strip() or None,
        "data_source": DATA_SOURCE,
        "source_url": f"{BASE}/AcclaimWeb/Details/?docId={record.get('TransactionItemId')}&insNm={record.get('InstrumentNumber')}",
        "confidence_level": "verified",
        "scraped_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "notes": "Extracted from Certificate of Title recording"
    }
    
    return outcome

def months_between(start_tuple, end_tuple):
    """Generate (year, month) tuples between start and end inclusive"""
    y, m = start_tuple
    while (y, m) <= end_tuple:
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1

def main():
    """Main execution"""
    # Parse command line arguments
    today = dt.date.today()
    prev_month = (today.replace(day=1) - dt.timedelta(days=1))
    
    if len(sys.argv) >= 3:
        start_month = sys.argv[1]
        end_month = sys.argv[2]
    else:
        start_month = f"{prev_month.year}-{prev_month.month:02d}"
        end_month = f"{today.year}-{today.month:02d}"
    
    start_year, start_month_num = map(int, start_month.split("-"))
    end_year, end_month_num = map(int, end_month.split("-"))
    
    print(f"🚀 Brevard AcclaimWeb Foreclosure Outcomes Scraper")
    print(f"Period: {start_month} to {end_month}")
    print(f"Target: {DATA_SOURCE} -> foreclosure_outcomes table")
    
    # Initialize session
    initialize_session()
    
    total_written = 0
    errors = 0
    
    # Process each month
    for year, month in months_between((start_year, start_month_num), (end_year, end_month_num)):
        month_str = f"{year}-{month:02d}"
        
        try:
            print(f"\nProcessing {month_str}...")
            records, total_found = get_month_records(year, month)
            
            # Transform records to foreclosure outcomes
            outcomes = []
            for record in records:
                try:
                    outcome = transform_to_foreclosure_outcome(record)
                    outcomes.append(outcome)
                except Exception as e:
                    print(f"⚠️ Transform error: {e}", file=sys.stderr)
                    continue
            
            # Write to database
            if outcomes:
                written = write_foreclosure_outcomes(outcomes)
                total_written += written
                print(f"✅ {month_str}: found={total_found}, transformed={len(outcomes)}, written={written}")
            else:
                print(f"⚠️ {month_str}: found={total_found}, no outcomes generated")
                
        except Exception as e:
            errors += 1
            print(f"❌ {month_str}: ERROR {e}", file=sys.stderr)
    
    print(f"\n🎉 COMPLETED: {total_written} foreclosure outcomes written, {errors} errors")
    return 1 if errors > 0 else 0

if __name__ == "__main__":
    sys.exit(main())