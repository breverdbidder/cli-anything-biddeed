#!/usr/bin/env python3
"""v9.11 - find AJAX pagination endpoint by scanning JS files + scripts in HTML."""
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
    'p_triggered_by':'gha_workflow_dispatch_v9_11_endpoint_probe'})

fc = requests.post('https://api.firecrawl.dev/v1/scrape',
    headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
    json={'url':PREVIEW_URL,'formats':['html'],'waitFor':6000,
          'onlyMainContent':False,'timeout':60000}, timeout=120)
html = fc.json().get('data',{}).get('html','')

# Find ALL inline scripts and external JS URLs
script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
inline_scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.IGNORECASE | re.DOTALL)
total_inline = '\n'.join(inline_scripts)

# Look for function names related to pagination
function_calls = re.findall(r'(\w*[Pp]age\w*\s*[\(:][^;]{0,300})', total_inline)[:20]
url_refs = re.findall(r"['\"]([^'\"]*index\.cfm[^'\"]*)['\"]", total_inline)
ajax_patterns = re.findall(r'\$\.(?:ajax|get|post)\s*\([^)]{10,400}', total_inline)[:10]

# Around the Next Page img tags - get the HTML context
next_page_img_pos = []
search_pos = 0
while True:
    p = html.find('alt="Next Page"', search_pos)
    if p < 0: break
    next_page_img_pos.append(p)
    search_pos = p + 1

# HTML around each Next Page img (parent tag, click handlers)
img_contexts = []
for p in next_page_img_pos[:4]:
    img_contexts.append(html[max(0,p-400):p+200])

result = {
    'html_len': len(html),
    'next_page_img_count': len(next_page_img_pos),
    'next_page_positions': next_page_img_pos,
    'img_contexts': img_contexts,
    'script_srcs': script_srcs[:10],
    'function_calls_sample': function_calls[:15],
    'url_refs_sample': list(set(url_refs))[:15],
    'ajax_patterns_sample': ajax_patterns,
    'total_inline_script_chars': len(total_inline),
}

rpc('scrape_log_finish', {'p_run_id':run_id,'p_status':'success',
    'p_rows_in':0,'p_rows_inserted':0,
    'p_notes':json.dumps(result, default=str)[:5800]})
