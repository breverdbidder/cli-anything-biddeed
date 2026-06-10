#!/usr/bin/env python3
"""
GOLD STANDARD Letter B: Charlotte County Verified Outcomes Scraper
=================================================================

Scrapes https://charlotte.realforeclose.com for verified auction outcomes
to populate foreclosure_outcomes table with INDEPENDENT clerk data.

Target: ≥95% of closed auctions have verified outcomes from clerk source.
Data source: Charlotte County RealForeclose (independent, not PropertyOnion-derived)

Usage:
  python scripts/charlotte_verified_outcomes.py --date 2026-06-01
  python scripts/charlotte_verified_outcomes.py --recent-dates  # last 30 days
  python scripts/charlotte_verified_outcomes.py --backfill    # all dates with closed auctions
"""

import os
import re
import sys
import json
import time
import httpx
import argparse
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

# Environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

# Constants
COUNTY = "charlotte"
BASE_URL = "https://charlotte.realforeclose.com"
PLATFORM = "realforeclose"
SALE_TYPE = "foreclosure"
SOURCE_TAG = f"{COUNTY}_{PLATFORM}"

# HTTP clients
http_client = httpx.Client(timeout=30, headers={"User-Agent": "GoldStandard-Charlotte-Scraper"})


def log(msg):
    """Simple logging with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def sb_headers():
    """Supabase REST API headers"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }


def sb_get(table, params=""):
    """GET from Supabase REST API"""
    r = http_client.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=sb_headers())
    if r.status_code == 200:
        return r.json()
    else:
        log(f"❌ GET {table} failed: {r.status_code} {r.text[:200]}")
        return []


def sb_upsert(table, rows):
    """Upsert to Supabase REST API"""
    if not rows:
        return 0
    
    r = http_client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), json=rows)
    if r.status_code in (200, 201, 204):
        log(f"✅ Upserted {len(rows)} rows to {table}")
        return len(rows)
    else:
        log(f"❌ Upsert to {table} failed: {r.status_code} {r.text[:200]}")
        return 0


def firecrawl_scrape(url, wait_for=None):
    """Scrape URL using Firecrawl"""
    if not FIRECRAWL_KEY:
        log("❌ FIRECRAWL_API_KEY not configured")
        return None
    
    log(f"🔥 Firecrawl scraping: {url}")
    
    payload = {
        "url": url,
        "formats": ["markdown"],
        "includeTags": ["div", "table", "span", "p"],
        "timeout": 30000
    }
    
    if wait_for:
        payload["waitFor"] = wait_for
    
    try:
        r = httpx.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {FIRECRAWL_KEY}"},
            json=payload,
            timeout=60
        )
        
        if r.status_code == 200:
            data = r.json()
            if data.get("success") and data.get("data", {}).get("markdown"):
                log(f"✅ Firecrawl success: {len(data['data']['markdown'])} chars")
                return data["data"]["markdown"]
            else:
                log(f"❌ Firecrawl success=false: {data}")
                return None
        else:
            log(f"❌ Firecrawl failed: {r.status_code} {r.text[:300]}")
            return None
            
    except Exception as e:
        log(f"❌ Firecrawl error: {e}")
        return None


def canonicalize_status(status_text, sold_to_text=None):
    """Canonicalize auction status for standardized outcomes"""
    s = (status_text or '').lower()
    if 'redeem' in s:
        return 'REDEEMED'
    if 'cancel' in s:
        return 'CANCELED'
    if 'postpon' in s:
        return 'POSTPONED'
    if 'struck' in s:
        return 'STRUCK_OFF'
    if 'wait' in s or 'pending' in s or 'list' in s:
        return 'LISTED'
    if 'sold' in s:
        st = (sold_to_text or '').lower()
        if 'cert' in st or 'c/h' in st or 'certificate' in st:
            return 'SOLD_CERT_HOLDER'
        if 'plaintiff' in st:
            return 'SOLD_PLAINTIFF'
        if '3rd' in st or 'third' in st or 'bidder' in st:
            return 'SOLD_3RD_PARTY'
        return 'SOLD_3RD_PARTY'  # Default for sold items
    return 'LISTED'


def extract_auction_outcomes(markdown, auction_date):
    """Extract auction outcomes from Firecrawl markdown"""
    outcomes = []
    
    # Find the "Auctions Closed" section or similar
    ac_pos = markdown.lower().find('auctions closed')
    if ac_pos < 0:
        ac_pos = markdown.lower().find('closed auctions')
    if ac_pos < 0:
        ac_pos = 0  # Use entire document if no section found
    
    region = markdown[ac_pos:]
    
    # Find parcel ID anchors - these are the key identifiers
    parcel_patterns = [
        r'Parcel\s*ID[^\d]*?\[(\d{6,15})\]',  # [123456789] format
        r'Parcel\s*ID[^\d]+?(\d{6,15})',      # plain number format
        r'Case\s*#[^\w]*?(\d{4}[A-Z]{2}\d+)',  # case number format
    ]
    
    anchors = []
    for pattern in parcel_patterns:
        matches = list(re.finditer(pattern, region, re.IGNORECASE))
        anchors.extend(matches)
    
    if not anchors:
        log(f"⚠️  No parcel/case anchors found in markdown")
        return outcomes
    
    log(f"📍 Found {len(anchors)} potential auction items")
    
    # Process each anchor to extract outcome data
    for i, anchor in enumerate(anchors):
        # Define segment boundaries
        start_pos = anchors[i-1].end() if i > 0 else 0
        end_pos = anchors[i+1].start() if i+1 < len(anchors) else len(region)
        segment = region[start_pos:end_pos]
        
        outcome = {
            'county': COUNTY,
            'auction_date': auction_date,
            'data_source': SOURCE_TAG,
            'scraped_at': datetime.now().isoformat(),
            'raw_segment': segment[:1000]  # Store segment for debugging
        }
        
        # Extract identifier (parcel or case number)
        identifier = anchor.group(1)
        if identifier.isdigit():
            outcome['parcel_id'] = identifier
        else:
            outcome['case_number'] = identifier
        
        # Find segment from previous item to this parcel ID for status extraction
        id_pos = segment.find(identifier)
        if id_pos > 0:
            pre_segment = segment[:id_pos]
        else:
            pre_segment = segment
        
        # Extract status information
        status_text = None
        sold_amount = None
        sold_to = None
        sold_timestamp = None
        
        # Check for "Auction Sold" patterns
        if re.search(r'Auction\s*Sold', pre_segment, re.IGNORECASE):
            status_text = 'Auction Sold'
            
            # Extract timestamp
            ts_match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)\s*ET)', pre_segment)
            if ts_match:
                sold_timestamp = ts_match.group(1)
            
            # Extract amount
            amt_patterns = [
                r'Amount\s*\n+\s*\$([\d,]+\.\d{2})',
                r'\$([\d,]+\.\d{2})',
                r'Winning\s*Bid[^\$]*\$([\d,]+\.\d{2})',
            ]
            for pattern in amt_patterns:
                amt_match = re.search(pattern, pre_segment)
                if amt_match:
                    sold_amount = amt_match.group(1)
                    break
            
            # Extract buyer type
            buyer_labels = [
                '3rd Party Bidder', 'Certificate Holder', 'Cert Holder', 
                'Plaintiff', 'Tax Deed Applicant', '3rd Party'
            ]
            for label in buyer_labels:
                if re.search(re.escape(label), pre_segment, re.IGNORECASE):
                    sold_to = label
                    break
        
        # Check for other status types
        elif re.search(r'Auction\s*Status\s*\n+\s*Redeemed', pre_segment, re.IGNORECASE):
            status_text = 'Redeemed'
        elif re.search(r'Auction\s*Status\s*\n+\s*Cancell?ed', pre_segment, re.IGNORECASE):
            status_text = 'Canceled'
        elif re.search(r'Auction\s*Status\s*\n+\s*Postponed', pre_segment, re.IGNORECASE):
            status_text = 'Postponed'
        elif re.search(r'Auction\s*Status\s*\n+\s*Struck', pre_segment, re.IGNORECASE):
            status_text = 'Struck-Off'
        elif re.search(r'Auction\s*Status\s*\n+\s*Waiting', pre_segment, re.IGNORECASE):
            status_text = 'Waiting'
        
        # Extract additional details using table patterns
        def extract_field(label):
            pattern = label + r':\s*\|\s*([^\|\n]+?)\s*\|'
            match = re.search(pattern, segment, re.IGNORECASE)
            if match:
                val = re.sub(r'\s+', ' ', match.group(1)).strip()
                return val[:200] if val else None
            return None
        
        case_num = extract_field('Case #')
        opening_bid = extract_field('Opening Bid')
        property_addr = extract_field('Property Address')
        assessed_val = extract_field('Assessed Value')
        
        if case_num:
            outcome['case_number'] = case_num
        if opening_bid:
            outcome['opening_bid_text'] = opening_bid
        if property_addr:
            outcome['property_address'] = property_addr
        if assessed_val:
            outcome['assessed_value_text'] = assessed_val
        
        # Add extracted outcome data
        if status_text:
            outcome['raw_status'] = status_text
        if sold_amount:
            outcome['sold_amount_text'] = sold_amount
            # Convert to float for storage
            try:
                outcome['winning_bid'] = float(sold_amount.replace(',', ''))
            except:
                pass
        if sold_timestamp:
            outcome['sold_timestamp_text'] = sold_timestamp
        if sold_to:
            outcome['sold_to'] = sold_to
        
        # Canonicalize status
        outcome['auction_status'] = canonicalize_status(status_text, sold_to)
        
        # Set confidence level
        outcome['parse_confidence'] = 'high' if (
            outcome.get('case_number') and 
            outcome.get('opening_bid_text') and 
            status_text
        ) else 'partial'
        
        # Only include outcomes with meaningful data
        if outcome.get('case_number') or outcome.get('parcel_id'):
            outcomes.append(outcome)
    
    return outcomes


def scrape_charlotte_outcomes(auction_date_str):
    """Scrape Charlotte County outcomes for a specific auction date"""
    log(f"🎯 Scraping Charlotte County outcomes for {auction_date_str}")
    
    # Convert date format for URL
    date_obj = date.fromisoformat(auction_date_str)
    date_slash = date_obj.strftime('%m/%d/%Y')
    
    # Build RealForeclose URL
    preview_url = f"{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_slash}"
    
    # Scrape using Firecrawl
    markdown = firecrawl_scrape(preview_url, wait_for=2000)  # Wait for JS to load
    
    if not markdown:
        log(f"❌ Failed to scrape {preview_url}")
        return []
    
    # Extract outcomes from markdown
    outcomes = extract_auction_outcomes(markdown, auction_date_str)
    
    log(f"📊 Extracted {len(outcomes)} outcomes")
    
    # Debug: show sample outcome
    if outcomes:
        sample = outcomes[0]
        log(f"📋 Sample outcome: case={sample.get('case_number')}, status={sample.get('auction_status')}, amount={sample.get('winning_bid')}")
    
    return outcomes


def get_auction_dates_to_scrape(mode):
    """Get list of auction dates that need outcome verification"""
    if mode == "recent":
        # Last 30 days of auction dates
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        dates = []
        current = start_date
        while current <= end_date:
            # Typically auctions are on business days
            if current.weekday() < 5:  # Monday=0, Friday=4
                dates.append(current.isoformat())
            current += timedelta(days=1)
        return dates
    
    elif mode == "backfill":
        # Find closed auctions in multi_county_auctions that don't have outcomes
        params = "select=distinct(auction_date)&county=eq.charlotte&auction_status=eq.closed&order=auction_date.desc&limit=100"
        closed_auctions = sb_get("multi_county_auctions", params)
        return [row["auction_date"] for row in closed_auctions]
    
    else:
        return []


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description="Charlotte County verified outcomes scraper")
    parser.add_argument("--date", help="Scrape specific date (YYYY-MM-DD)")
    parser.add_argument("--recent-dates", action="store_true", help="Scrape last 30 days")
    parser.add_argument("--backfill", action="store_true", help="Backfill closed auctions")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no database writes")
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY required")
        return 1
    
    if not FIRECRAWL_KEY:
        log("❌ FIRECRAWL_API_KEY required")
        return 1
    
    # Determine dates to scrape
    dates_to_scrape = []
    
    if args.date:
        dates_to_scrape = [args.date]
    elif args.recent_dates:
        dates_to_scrape = get_auction_dates_to_scrape("recent")
    elif args.backfill:
        dates_to_scrape = get_auction_dates_to_scrape("backfill")
    else:
        # Default: yesterday
        yesterday = date.today() - timedelta(days=1)
        dates_to_scrape = [yesterday.isoformat()]
    
    log(f"📅 Will scrape {len(dates_to_scrape)} dates")
    
    total_outcomes = 0
    
    # Process each date
    for auction_date in dates_to_scrape:
        try:
            outcomes = scrape_charlotte_outcomes(auction_date)
            total_outcomes += len(outcomes)
            
            if outcomes and not args.dry_run:
                # Upsert to foreclosure_outcomes table
                upserted = sb_upsert("foreclosure_outcomes", outcomes)
                log(f"💾 Saved {upserted} outcomes for {auction_date}")
            elif args.dry_run:
                log(f"🔍 DRY RUN: Would save {len(outcomes)} outcomes for {auction_date}")
            
            # Rate limiting
            time.sleep(2)
            
        except Exception as e:
            log(f"❌ Error processing {auction_date}: {e}")
            continue
    
    log(f"🎉 COMPLETED: Processed {total_outcomes} total outcomes")
    
    # Log to insights for tracking
    insight = {
        "type": "verified_outcomes_scrape",
        "county": COUNTY,
        "dates_processed": len(dates_to_scrape),
        "outcomes_extracted": total_outcomes,
        "timestamp": datetime.now().isoformat(),
        "dry_run": args.dry_run
    }
    
    if not args.dry_run:
        sb_upsert("insights", [insight])
    
    return 0


if __name__ == "__main__":
    sys.exit(main())