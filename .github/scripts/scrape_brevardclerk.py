#!/usr/bin/env python3
"""v9.6 DEBUG - dump markdown tail directly to scrape_runs.notes."""
import os, json, requests
from datetime import date

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ['FIRECRAWL_API_KEY']
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
DATE_SLASH = date.fromisoformat(AUCTION_DATE_STR).strftime('%m/%d/%Y')
PREVIEW_URL = f'https://brevard.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'
DAYLIST_URL = f'https://brevard.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    r.raise_for_status()
    return r.json() if r.text and r.text.strip() else None

def fc(url, actions=None):
    body = {'url':url,'formats':['markdown','html'],'waitFor':6000,'onlyMainContent':False,'timeout':60000}
    if actions: body['actions'] = actions
    r = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
        json=body, timeout=120)
    return r.status_code, (r.json().get('data',{}) if r.status_code==200 else {'error':r.text[:300]})

run_id = rpc('scrape_log_start', {'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_workflow_dispatch_v9_6_probe'})

results = {}

# Probe 1: PREVIEW vanilla
s1, d1 = fc(PREVIEW_URL)
md1 = d1.get('markdown','')
results['preview_vanilla'] = {
    'status': s1,
    'md_chars': len(md1),
    'md_tail_1500': md1[-1500:] if md1 else '',
}

# Probe 2: DAYLIST vanilla
s2, d2 = fc(DAYLIST_URL)
md2 = d2.get('markdown','')
results['daylist_vanilla'] = {
    'status': s2,
    'md_chars': len(md2),
    'md_tail_1500': md2[-1500:] if md2 else '',
}

# Probe 3: PREVIEW with click via broad selector
s3, d3 = fc(PREVIEW_URL, actions=[
    {'type':'wait','milliseconds':6000},
    {'type':'click','selector':'img[src*="next"], img[src*="Next"], a[onclick*="setPage"], a[onclick*="Page"], #fcdt, .NaviSt, .pagiNext'},
    {'type':'wait','milliseconds':3000},
])
md3 = d3.get('markdown','')
results['preview_clicked'] = {
    'status': s3,
    'md_chars': len(md3),
    'first_parcel_match': md3.find('Parcel ID') if md3 else -1,
    'md_tail_1000': md3[-1000:] if md3 else '',
}

rpc('scrape_log_finish', {'p_run_id':run_id,'p_status':'success',
    'p_rows_in':3,'p_rows_inserted':0,
    'p_notes':json.dumps(results)[:5800]})
print(json.dumps(results, indent=2)[:3000])
