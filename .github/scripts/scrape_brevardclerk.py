#!/usr/bin/env python3
"""v9.7 - dump strategic markdown chunks to find pagination + try AID-based fetch."""
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
    'p_triggered_by':'gha_workflow_dispatch_v9_7_probe'})

# Fetch raw preview
fc = requests.post('https://api.firecrawl.dev/v1/scrape',
    headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
    json={'url':PREVIEW_URL,'formats':['markdown','html','links'],'waitFor':6000,
          'onlyMainContent':False,'timeout':60000}, timeout=120)
data = fc.json().get('data',{})
md = data.get('markdown','')
html = data.get('html','')
links = data.get('links',[])

# Find specific regions: where do parcel cards END and pagination/IDs begin?
# Sectioning markers
sections = {
    'len': len(md),
    'auctions_closed_pos': md.lower().find('auctions closed'),
    'page_word_pos': md.find('Page'),
    'pagination_pos': md.lower().find('next page'),
    'prev_page_pos': md.lower().find('previous'),
}

# Save chunks at key offsets
chunks = {}
for name, end_offset in [('around_3000',3000),('around_5000',5000),('around_7500',7500),('around_9000',9000)]:
    start = max(0, end_offset - 700)
    chunks[name] = md[start:end_offset]

# Look for AID/auction-id patterns
aid_matches = re.findall(r'AID[=:]?\s*[\'"]?(\d{6,8})', md + html, re.IGNORECASE)
parcel_list = re.findall(r'\b(\d{7})\b', md[-2000:])

# Pagination link patterns in HTML
html_pat = {
    'has_setPage': 'setPage' in html,
    'has_PageNo': 'PageNo' in html,
    'has_AjaxPage': 'AjaxPage' in html or 'ajaxpage' in html.lower(),
    'has_NaviSt': 'NaviSt' in html,
    'has_AuctionPage': 'AuctionPage' in html,
    'has_GetPage': 'GetPage' in html,
    'pagination_html_chunk': '',
}
for needle in ['setPage','PageNo','AjaxPage','NaviSt','AuctionPage','GetPage','fcdt']:
    idx = html.find(needle)
    if idx > 0:
        html_pat['pagination_html_chunk'] = html[max(0,idx-150):idx+400]
        html_pat['found_marker'] = needle
        break

# Check if any link looks like pagination
pag_links = [l for l in (links or []) if any(k in str(l).lower() for k in ['page','next','setpage','aid='])]

result = {
    'sections': sections,
    'chunks': chunks,
    'aid_matches_count': len(set(aid_matches)),
    'aid_sample': list(set(aid_matches))[:30],
    'parcel_list_tail_count': len(parcel_list),
    'html_patterns': html_pat,
    'pag_links_sample': pag_links[:10],
    'all_links_count': len(links) if links else 0,
}

rpc('scrape_log_finish', {'p_run_id':run_id,'p_status':'success',
    'p_rows_in':0,'p_rows_inserted':0,
    'p_notes':json.dumps(result)[:5800]})
print(json.dumps(result, indent=2)[:3000])
