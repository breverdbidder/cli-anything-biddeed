#!/usr/bin/env python3
"""v9.17 - dump actual backend response structure"""
import os, json, time, requests
from datetime import date

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
DATE_SLASH = date.fromisoformat(os.environ.get('AUCTION_DATE','2026-05-14')).strftime('%m/%d/%Y')
BASE = 'https://brevard.realforeclose.com'
PREVIEW_URL = f'{BASE}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    r.raise_for_status()
    return r.json() if r.text and r.text.strip() else None

run_id = rpc('scrape_log_start', {'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':os.environ.get('AUCTION_DATE','2026-05-14'),
    'p_triggered_by':'gha_workflow_dispatch_v9_17_dump'})

sess = requests.Session()
sess.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0) Chrome/122.0.0.0',
    'Accept': 'text/html,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})

# Step 1: session
r0 = sess.get(PREVIEW_URL, timeout=30)
print(f'PREVIEW: {r0.status_code} {len(r0.text):,}b cookies={dict(sess.cookies)}')

# Step 2: hit backend for page 3 (user's screenshot showed page 3)
sess.headers['Referer'] = PREVIEW_URL
sess.headers['X-Requested-With'] = 'XMLHttpRequest'
sess.headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'

results = {}
for pg in [1, 3, 12]:
    tx = int(time.time() * 1000)
    url = f'{BASE}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&PageDir=0&doR=1&tx={tx}&bypassPage={pg}'
    rr = sess.get(url, params={'test':1}, timeout=30)
    body = rr.text
    # Try JSON
    is_json = False
    try:
        j = rr.json()
        is_json = True
        results[f'page_{pg}'] = {
            'status': rr.status_code,
            'bytes': len(body),
            'is_json': True,
            'json_keys': list(j.keys()) if isinstance(j, dict) else 'not-dict',
            'first_500': body[:500],
            'last_500': body[-500:] if len(body) > 1000 else '',
            'middle_chunk': body[max(0,len(body)//2-500):len(body)//2+500],
            'content_type': rr.headers.get('Content-Type'),
        }
    except Exception:
        results[f'page_{pg}'] = {
            'status': rr.status_code,
            'bytes': len(body),
            'is_json': False,
            'first_2000': body[:2000],
            'last_500': body[-500:],
            'content_type': rr.headers.get('Content-Type'),
        }

rpc('scrape_log_finish', {'p_run_id':run_id,'p_status':'success',
    'p_rows_in':0,'p_rows_inserted':0,
    'p_notes':json.dumps(results, default=str)[:5800]})
