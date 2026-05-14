#!/usr/bin/env python3
"""v9.15 - dump full keyPage/changePage/pageLoad function bodies from auction.js."""
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
    'p_triggered_by':'gha_workflow_dispatch_v9_15_keypage'})

fc = requests.post('https://api.firecrawl.dev/v1/scrape',
    headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
    json={'url':'https://brevard.realforeclose.com/CORE/System/JS/auction.js',
          'formats':['rawHtml'],'waitFor':2000,'onlyMainContent':False,'timeout':60000},
    timeout=120)
js = fc.json().get('data',{}).get('rawHtml','')
js = re.sub(r'<[^>]+>', '', js) if js.startswith('<') else js

# Pull out specific function bodies
def extract_function(code, name, max_chars=2500):
    m = re.search(r'function\s+' + re.escape(name) + r'\b[^{]*\{', code)
    if not m: return ''
    start = m.start()
    depth = 0
    i = m.end() - 1
    while i < len(code):
        if code[i] == '{': depth += 1
        elif code[i] == '}':
            depth -= 1
            if depth == 0:
                return code[start:min(i+1, start+max_chars)]
        i += 1
    return code[start:start+max_chars]

result = {
    'js_chars': len(js),
    'keyPage_body': extract_function(js, 'keyPage'),
    'changePage_body': extract_function(js, 'changePage'),
    'pageLoad_body': extract_function(js, 'pageLoad'),
    'loadArea_body': extract_function(js, 'loadArea'),
    'getArea_body': extract_function(js, 'getArea'),
    'updateArea_body': extract_function(js, 'updateArea'),
    'all_load_calls': re.findall(r'(\$\.(?:get|post|ajax)\s*\([^)]{10,500})', js)[:10],
    'all_url_strings': sorted(set(re.findall(r'["\']([^"\']*FNC[^"\']*)["\']', js)))[:15],
}

rpc('scrape_log_finish', {'p_run_id':run_id,'p_status':'success',
    'p_rows_in':0,'p_rows_inserted':0,
    'p_notes':json.dumps(result, default=str)[:5800]})
