#!/usr/bin/env python3
"""v9.14 - Fetch auction.js via Firecrawl, find AJAX pagination endpoint."""
import os, re, json, requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ['FIRECRAWL_API_KEY']

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    r.raise_for_status()
    return r.json() if r.text and r.text.strip() else None

run_id = rpc('scrape_log_start', {'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':'2026-05-14',
    'p_triggered_by':'gha_workflow_dispatch_v9_14_jsprobe'})

# Fetch auction.js raw content via Firecrawl
fc = requests.post('https://api.firecrawl.dev/v1/scrape',
    headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
    json={'url':'https://brevard.realforeclose.com/CORE/System/JS/auction.js',
          'formats':['rawHtml','markdown'],'waitFor':2000,
          'onlyMainContent':False,'timeout':60000},
    timeout=120)

data = fc.json().get('data',{})
js = data.get('rawHtml','') or data.get('markdown','')
# Firecrawl wraps JS files in <pre> sometimes
js = re.sub(r'<[^>]+>', '', js) if js.startswith('<') else js

result = {
    'js_chars': len(js),
    'has_curPCA': 'curPCA' in js,
    'has_Area_C': 'Area_C' in js,
    'has_Auct_Area': 'Auct_Area' in js,
    'has_arid': 'arid' in js,
    'cfm_endpoints': list(set(re.findall(r'["\']([^"\']*\.cfm[^"\']*)["\']', js)))[:30],
    'zmethod_values': list(set(re.findall(r"Zmethod=([A-Z_]+)", js, re.IGNORECASE))),
    'ajax_blocks': [],
    'function_names_with_page': re.findall(r'function\s+(\w*[Pp]age\w*)', js)[:20],
}

# Find blocks around curPCA references and around ajax patterns
for keyword in ['curPCA', 'Area_C', '$.ajax', '$.get', '$.post', 'arid', 'auct_area']:
    idx = js.find(keyword)
    if idx >= 0:
        result['ajax_blocks'].append({'kw':keyword,'pos':idx,'chunk':js[max(0,idx-300):idx+800]})

rpc('scrape_log_finish', {'p_run_id':run_id,'p_status':'success',
    'p_rows_in':0,'p_rows_inserted':0,
    'p_notes':json.dumps(result, default=str)[:5800]})
print(json.dumps(result, indent=2)[:3000])
