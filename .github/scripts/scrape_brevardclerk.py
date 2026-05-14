#!/usr/bin/env python3
"""v9.8 - capture chunk around 'Auctions Closed' header to find pagination control."""
import os, json, re, requests
from datetime import date

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ['FIRECRAWL_API_KEY']
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
DATE_SLASH = date.fromisoformat(AUCTION_DATE_STR).strftime('%m/%d/%Y')
PREVIEW_URL = f'https://brevard.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    r.raise_for_status()
    return r.json() if r.text and r.text.strip() else None

run_id = rpc('scrape_log_start', {'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_workflow_dispatch_v9_8_probe'})

fc = requests.post('https://api.firecrawl.dev/v1/scrape',
    headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
    json={'url':PREVIEW_URL,'formats':['markdown','html'],'waitFor':6000,
          'onlyMainContent':False,'timeout':60000}, timeout=120)
data = fc.json().get('data',{})
md = data.get('markdown','')
html = data.get('html','')

# Around "Auctions Closed or Canceled" header
ac_pos = md.lower().find('auctions closed')
prev_pos = md.lower().find('previous')
next_pos = md.lower().find('next page')

# In HTML — look for pagination controls
html_lower = html.lower()
all_handlers = re.findall(r'onclick=[\'"]([^\'"]{5,200})[\'"]', html, re.IGNORECASE)
unique_handlers = sorted(set(all_handlers))[:30]

result = {
    'md_len': len(md),
    'html_len': len(html),
    'chunk_around_auctions_closed': md[max(0,ac_pos-200):ac_pos+800] if ac_pos > 0 else '',
    'chunk_around_prev': md[max(0,prev_pos-100):prev_pos+500] if prev_pos > 0 else '',
    'chunk_around_next_page': md[max(0,next_pos-100):next_pos+400] if next_pos > 0 else '',
    'html_onclick_handlers': unique_handlers,
    'html_chunk_5000_6000': html[5000:6000],
    'html_chunk_15000_16500': html[15000:16500] if len(html) > 15000 else '',
    'html_chunk_25000_26500': html[25000:26500] if len(html) > 25000 else '',
}

rpc('scrape_log_finish', {'p_run_id':run_id,'p_status':'success',
    'p_rows_in':0,'p_rows_inserted':0,
    'p_notes':json.dumps(result)[:5800]})
