#!/usr/bin/env python3
"""
maxbid_sweep.py — MAXBID SWEEP (issue #12854)

Captures RealAuction's "Plaintiff Max Bid" field during its early-morning
public visibility window (field-proven, Marion 2026-07-20: disclosed at
11:56Z, "Hidden" for all cases by 12:10Z). There is no separate disclosing
vs hiding endpoint — the PREVIEW page ships zero embedded auction data (it
is a JS shell); the JSON Zmethod=UPDATE endpoint is the only place any
consumer, human browser or scraper, ever sees the field. The window is a
server-side time gate applied uniformly to that one endpoint, so this
script hits the same endpoint calendar_sweep_mca.py already uses, just on
an earlier schedule (before the window closes) and scoped to TODAY only.

Every capture (value OR "Hidden") appends a row to
public.mca_maxbid_observations. If PROJECT_TO_MCA=true, a non-hidden value
is also projected onto multi_county_auctions.plaintiff_max_bid — using the
same columns-scoped upsert pattern as calendar_sweep_mca.py, so a later
"Hidden" observation never nulls out an earlier disclosed number.

Env (required): COUNTY_SLUG, BASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Env (optional):  PROJECT_TO_MCA (default 'false'), SWEEP_RUN_ID

Exit codes:
  0 = success (ran to completion; 0 cases for today is not an error)
  1 = fatal error (network/Supabase failure)
"""
import os, re, sys, json, time
from datetime import date, datetime, timezone
import requests


def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f'Missing required env: {name}')
    return v

COUNTY   = _req('COUNTY_SLUG').lower().strip()
_raw_url = _req('BASE_URL').rstrip('/')
BASE_URL = _raw_url.split('/index.cfm')[0] if '/index.cfm' in _raw_url else _raw_url
SUPA_URL = _req('SUPABASE_URL').rstrip('/')
SUPA_KEY = _req('SUPABASE_SERVICE_ROLE_KEY')
PROJECT_TO_MCA = os.environ.get('PROJECT_TO_MCA', 'false').strip().lower() == 'true'
SWEEP_RUN_ID = os.environ.get('SWEEP_RUN_ID', '')

TODAY = date.today()
REST  = f'{SUPA_URL}/rest/v1'
SUPA_H = {
    'apikey': SUPA_KEY,
    'Authorization': f'Bearer {SUPA_KEY}',
    'Content-Type': 'application/json',
}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')

print(f'>>> maxbid_sweep | {COUNTY} | today={TODAY} | project_to_mca={PROJECT_TO_MCA}')

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})


def _strip_html(s):
    if not s:
        return None
    t = re.sub(r'<[^>]+>', '', s)
    t = re.sub(r'&amp;', '&', t)
    t = re.sub(r'&nbsp;', ' ', t)
    t = re.sub(r'&#\d+;', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t or None


def _to_float(s):
    if not s:
        return None
    s = re.sub(r'<[^>]+>', '', s)
    clean = re.sub(r'[^\d.]', '', s)
    if clean:
        try:
            return float(clean)
        except ValueError:
            pass
    return None


def _get_field(content, label):
    pattern = rf'{re.escape(label)}:@F[^@>]*>[^>]*>(?:<a[^>]*>)?(.*?)(?:</a>)?@G'
    m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if not m:
        pattern2 = rf'{re.escape(label)}:[^@]*@F[^>]*>(.*?)@G'
        m = re.search(pattern2, content, re.DOTALL | re.IGNORECASE)
    if m:
        return _strip_html(m.group(1).replace('@G', '').replace('@F', '').replace('@B', ''))
    return None


def _get_json_page(auction_date, page_dir, do_r):
    ts = int(time.time() * 1000)
    url = (f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=UPDATE'
           f'&FNC=LOAD&AREA=W&PageDir={page_dir}&doR={do_r}&tx={ts}&bypassPage=0')
    date_str = auction_date.strftime('%m/%d/%Y')
    try:
        r = SESSION.get(url, headers={
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_str}',
        }, timeout=30)
        if r.status_code != 200:
            print(f'    JSON endpoint HTTP {r.status_code}', file=sys.stderr)
            return '', ''
        data = r.json()
        return data.get('retHTML', ''), data.get('rlist', '')
    except (requests.RequestException, ValueError) as e:
        print(f'    JSON endpoint error: {e}', file=sys.stderr)
        return '', ''


def _parse_cards(ret_html):
    """Extract (case_number, plaintiff_max_bid_raw) per AITEM block."""
    out = []
    parts = re.split(r'<div id="AITEM_(\d+)"', ret_html)
    for i in range(1, len(parts), 2):
        content = parts[i + 1] if i + 1 < len(parts) else ''
        case_num = _get_field(content, 'Case #') or _get_field(content, 'Case Number')
        if not case_num:
            continue
        plaintiff_mb = _get_field(content, 'Plaintiff Max Bid')
        out.append((case_num, plaintiff_mb))
    return out


def scrape_today():
    date_str = TODAY.strftime('%m/%d/%Y')
    date_enc = date_str.replace('/', '%2F')
    preview_url = f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_enc}'

    status = SESSION.get(preview_url, timeout=30).status_code
    if status >= 400:
        print(f'  preview context-set failed: HTTP {status}', file=sys.stderr)
        return []

    all_cards = []
    seen = set()
    ret_html, _ = _get_json_page(TODAY, page_dir=0, do_r=1)
    if not ret_html:
        return []
    for case_num, pmb in _parse_cards(ret_html):
        if case_num in seen:
            continue
        seen.add(case_num)
        all_cards.append((case_num, pmb))

    for pg in range(2, 16):
        time.sleep(1)
        ret_html2, _ = _get_json_page(TODAY, page_dir=1, do_r=0)
        if not ret_html2:
            break
        page_cards = _parse_cards(ret_html2)
        new = [(c, p) for c, p in page_cards if c not in seen]
        if not new:
            break
        for c, p in new:
            seen.add(c)
        all_cards.extend(new)

    return all_cards


def upsert_observations(rows):
    """Insert into mca_maxbid_observations; on_conflict do nothing = idempotent."""
    if not rows:
        return 0, []
    url = f'{REST}/mca_maxbid_observations?on_conflict=case_number,county,observed_at'
    h = {**SUPA_H, 'Prefer': 'resolution=ignore-duplicates,return=minimal'}
    try:
        r = requests.post(url, json=rows, headers=h, timeout=30)
        if 200 <= r.status_code < 300:
            return len(rows), []
        return 0, [f'http {r.status_code} {r.text[:300]}']
    except requests.RequestException as e:
        return 0, [str(e)]


def project_to_mca(case_number, county, value, observed_at_iso, source_path):
    """Non-destructive: only touches plaintiff_max_bid* columns, only for a
    real (non-hidden) value, using columns= scoping so no other field is
    ever part of this request's DO UPDATE SET."""
    url = (f'{REST}/multi_county_auctions?county=eq.{county}&case_number=eq.{case_number}'
           f'&columns=plaintiff_max_bid,plaintiff_max_bid_source,plaintiff_max_bid_observed_at')
    payload = {
        'plaintiff_max_bid': value,
        'plaintiff_max_bid_source': f'maxbid_sweep_{source_path}_{observed_at_iso}',
        'plaintiff_max_bid_observed_at': observed_at_iso,
    }
    h = {**SUPA_H, 'Prefer': 'return=minimal'}
    try:
        r = requests.patch(url, json=payload, headers=h, timeout=30)
        return 200 <= r.status_code < 300, r.status_code, r.text[:300]
    except requests.RequestException as e:
        return False, 0, str(e)


# ── MAIN ─────────────────────────────────────────────────────────────────
cards = scrape_today()
print(f'  {COUNTY}: {len(cards)} cases found for {TODAY}')

now_bucket = datetime.now(timezone.utc).replace(second=0, microsecond=0)
observed_at_iso = now_bucket.strftime('%Y-%m-%dT%H:%M:00Z')

obs_rows = []
projections = []
n_hidden = 0
n_value = 0
for case_num, pmb_raw in cards:
    is_hidden = pmb_raw is None or pmb_raw.strip().lower() == 'hidden'
    value = None if is_hidden else _to_float(pmb_raw)
    if not is_hidden and value is None:
        # unparseable, non-"Hidden" text — treat as hidden/unknown rather than
        # guess a number; never write 0 for something we couldn't parse.
        is_hidden = True
    if is_hidden:
        n_hidden += 1
    else:
        n_value += 1

    obs_rows.append({
        'case_number': case_num,
        'county': COUNTY,
        'observed_at': observed_at_iso,
        'value': value,
        'is_hidden': is_hidden,
        'source_path': 'json_update_endpoint',
        'sweep_run_id': SWEEP_RUN_ID or None,
    })
    if not is_hidden:
        projections.append((case_num, value))

inserted, errs = upsert_observations(obs_rows)
print(f'  observations: {inserted} attempted, hidden={n_hidden} value={n_value}')
for e in errs:
    print(f'  ! observation insert error: {e}', file=sys.stderr)

proj_results = []
if PROJECT_TO_MCA:
    for case_num, value in projections:
        ok, code, body = project_to_mca(case_num, COUNTY, value, observed_at_iso, 'json_update_endpoint')
        proj_results.append((case_num, value, ok, code))
        if not ok:
            print(f'  ! MCA projection failed for {case_num}: HTTP {code} {body}', file=sys.stderr)
else:
    print(f'  REPORT-ONLY: {len(projections)} projected MCA update(s) NOT applied (PROJECT_TO_MCA=false)')
    for case_num, value in projections:
        print(f'    would update {COUNTY}/{case_num}: plaintiff_max_bid={value}')

gh_summary = os.environ.get('GITHUB_STEP_SUMMARY')
if gh_summary:
    with open(gh_summary, 'a') as f:
        f.write(f'\n## maxbid_sweep — {COUNTY} ({TODAY})\n')
        f.write(f'- Cases seen: {len(cards)}\n')
        f.write(f'- Hidden: {n_hidden} | Value: {n_value}\n')
        f.write(f'- Observations inserted (attempted): {inserted}\n')
        f.write(f'- PROJECT_TO_MCA: {PROJECT_TO_MCA} | projections: {len(projections)}\n')
        if errs:
            f.write(f'- Errors: {errs[:3]}\n')

gh_out = os.environ.get('GITHUB_OUTPUT')
if gh_out:
    with open(gh_out, 'a') as f:
        f.write(f'cases_seen={len(cards)}\n')
        f.write(f'n_hidden={n_hidden}\n')
        f.write(f'n_value={n_value}\n')
        f.write(f'projected={len(projections) if PROJECT_TO_MCA else 0}\n')

if errs and inserted == 0 and obs_rows:
    sys.exit(1)

print(f'SUCCESS: {COUNTY} maxbid sweep complete')
sys.exit(0)
