#!/usr/bin/env python3
"""v9.5 - DEBUG: fetch page 1 and save the markdown end-tail + try multiple selectors via screenshot."""
import os, re, sys, json
from datetime import date
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ['FIRECRAWL_API_KEY']
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)
DATE_SLASH = AUCTION_DATE.strftime('%m/%d/%Y')
PREVIEW_URL = f'https://brevard.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json','Prefer':'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    if r.status_code >= 400: raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

run_id = rpc('scrape_log_start', {
    'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_workflow_dispatch_v9_5_debug',
})
print(f'>>> v9.5 DEBUG run={run_id}')

# Fetch full HTML + markdown to inspect pagination structure
fc = requests.post('https://api.firecrawl.dev/v1/scrape',
    headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
    json={'url':PREVIEW_URL,'formats':['markdown','html','links'],
          'waitFor':6000,'onlyMainContent':False,'timeout':60000},
    timeout=120)

data = fc.json().get('data',{})
md = data.get('markdown','')
html = data.get('html','')
links = data.get('links',[])

print(f'md={len(md)} html={len(html)} links={len(links)}')

# Save full markdown + html chunks + links to scrape_payloads for inspection
requests.post(f'{REST}/rpc/scrape_payload_insert', json={
    'p_run_id': run_id,
    'p_row_data': {
        'md_full': md,
        'md_tail_2000': md[-2000:] if md else '',
        'html_tail_3000': html[-3000:] if html else '',
        'links_sample': links[:50] if links else [],
        'pagination_keywords': {
            'next_in_md': 'Next Page' in md or 'NextPage' in md,
            'next_in_html': 'Next' in html,
            'setpage_in_html': 'setPage' in html,
            'pageno_in_html': 'PageNo' in html,
            'pagination_block_md': md[md.find('Page') if 'Page' in md else 0 : (md.find('Page')+500) if 'Page' in md else 500],
        }
    }
}, headers=H, timeout=30)

rpc('scrape_log_finish', {
    'p_run_id':run_id,'p_status':'success',
    'p_rows_in':1,'p_rows_inserted':1,
    'p_notes':json.dumps({'parser':'v9.5_debug','md_chars':len(md),'html_chars':len(html),'links':len(links)}),
})
print('Done. Inspect pipeline.scrape_payloads for full markdown.')
