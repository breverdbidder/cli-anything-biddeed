#!/usr/bin/env python3
"""
calendar_sweep_mca.py — BIDDEED 67-County Calendar Sweep v3.0

Phase A: Discover future auction dates from PREVIEW page navigation links (server-side rendered)
Phase B: Pull auction cards via the JSON UPDATE endpoint that the RealAuction JS calls
Phase C: Upsert to multi_county_auctions

No Firecrawl required — uses requests sessions + the internal JSON AJAX endpoint.

Env (required): COUNTY_SLUG, BASE_URL, PLATFORM, SALE_TYPE,
                SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Exit codes:
  0 = success (≥1 row upserted)
  1 = fatal error (Supabase write error, unrecoverable network failure)
  2 = county genuinely dark (zero future dates, zero listings, or auth wall)
      — non-fatal for GHA (continue-on-error: true)
"""
import os, re, sys, json, time
from datetime import date, datetime
import requests


# ── ENV ──────────────────────────────────────────────────────────────────────

def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f'Missing required env: {name}')
    return v

COUNTY    = _req('COUNTY_SLUG').lower().strip()
_raw_url  = _req('BASE_URL').rstrip('/')
BASE_URL  = _raw_url.split('/index.cfm')[0] if '/index.cfm' in _raw_url else _raw_url
PLATFORM  = _req('PLATFORM').lower().strip()
SALE_TYPE = _req('SALE_TYPE').lower().strip()
SUPA_URL  = _req('SUPABASE_URL').rstrip('/')
SUPA_KEY  = _req('SUPABASE_SERVICE_ROLE_KEY')

TODAY = date.today()
REST  = f'{SUPA_URL}/rest/v1'
SUPA_H = {
    'apikey': SUPA_KEY,
    'Authorization': f'Bearer {SUPA_KEY}',
    'Content-Type': 'application/json',
}

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
)

print(f'>>> calendar_sweep_mca v3.0 | {COUNTY} ({SALE_TYPE}) | {PLATFORM} | today={TODAY}')
print(f'    BASE_URL={BASE_URL}')

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})


# ── HTTP HELPERS ──────────────────────────────────────────────────────────────

def _get(url: str, retries: int = 2, **kwargs) -> tuple[int, str]:
    """Return (status_code, text). Never raises; returns (0, '') on total failure."""
    for attempt in range(retries + 1):
        try:
            r = SESSION.get(url, timeout=30, allow_redirects=True, **kwargs)
            return r.status_code, r.text
        except requests.RequestException as e:
            if attempt < retries:
                time.sleep(3)
            else:
                print(f'  ! GET {url}: {e}', file=sys.stderr)
                return 0, ''
    return 0, ''


def _strip_html(s: str) -> str | None:
    if not s:
        return None
    t = re.sub(r'<[^>]+>', '', s)
    t = re.sub(r'&amp;', '&', t)
    t = re.sub(r'&nbsp;', ' ', t)
    t = re.sub(r'&#\d+;', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t or None


def _to_float(s: str | None) -> float | None:
    if not s:
        return None
    # strip any HTML tags first
    s = re.sub(r'<[^>]+>', '', s)
    clean = re.sub(r'[^\d.]', '', s)
    if clean:
        try:
            return float(clean)
        except ValueError:
            pass
    return None


def _parse_date(s: str) -> date | None:
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None


# ── PHASE A: DATE DISCOVERY FROM PREVIEW PAGE NAVIGATION ─────────────────────

def discover_auction_dates() -> list[date]:
    """
    Fetch the PREVIEW page (no specific date) and follow navigation links
    (Previous Auction / Current / Next Auction) to collect upcoming dates.
    These links are server-side rendered — no JS required.
    Returns sorted list of unique future dates (>= TODAY), capped at 5.
    """
    collected: set[date] = set()

    # Start from the base PREVIEW page (shows most recent / current auction)
    seed_url = f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW'
    status, html = _get(seed_url)
    if status == 0 or (status >= 400 and status != 403):
        print(f'  [dates] seed page failed: HTTP {status}', file=sys.stderr)
        return []

    # Extract all AuctionDate params from seed page
    for m in re.finditer(r'AuctionDate=([\d/]+)', html, re.IGNORECASE):
        d = _parse_date(m.group(1))
        if d and d >= TODAY:
            collected.add(d)

    # Also pick up the "Next Auction" date and navigate forward
    # Find the most recent upcoming date to start navigation from
    future_seed = sorted(collected) or [TODAY]
    nav_date = future_seed[0] if future_seed else TODAY

    # Navigate forward through "Next Auction" links, up to 5 hops
    for _ in range(8):
        if len(collected) >= 5:
            break
        date_str = nav_date.strftime('%m/%d/%Y')
        status, nav_html = _get(f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_str}')
        if status == 0 or status >= 400:
            break

        all_nav = re.findall(r'AuctionDate=([\d/]+)', nav_html, re.IGNORECASE)
        new_dates = [_parse_date(x) for x in all_nav]
        new_dates = [d for d in new_dates if d and d > nav_date]

        if not new_dates:
            break

        next_d = min(new_dates)   # the closest future date from here
        if next_d <= nav_date:
            break
        if next_d >= TODAY:
            collected.add(next_d)
        nav_date = next_d
        time.sleep(1)

    future = sorted(d for d in collected if d >= TODAY)
    print(f'  [dates] discovered {len(future)} upcoming dates: {future[:7]}')
    return future[:5]


# ── PHASE B: AUCTION CARDS VIA JSON UPDATE ENDPOINT ──────────────────────────

def _get_json_page(auction_date: date, area: str, page_dir: int, do_r: int) -> tuple[str, str]:
    """Call the UPDATE JSON endpoint. Returns (retHTML, rlist)."""
    ts = int(time.time() * 1000)
    url = (
        f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=UPDATE'
        f'&FNC=LOAD&AREA={area}&PageDir={page_dir}&doR={do_r}&tx={ts}&bypassPage=0'
    )
    date_str = auction_date.strftime('%m/%d/%Y')
    try:
        r = SESSION.get(
            url,
            headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_str}',
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f'    JSON endpoint HTTP {r.status_code}', file=sys.stderr)
            return '', ''
        data = r.json()
        return data.get('retHTML', ''), data.get('rlist', '')
    except (requests.RequestException, ValueError) as e:
        print(f'    JSON endpoint error: {e}', file=sys.stderr)
        return '', ''


_PARCEL_RE = re.compile(r'^[\dA-Z\-\./]{5,30}$', re.IGNORECASE)
# Parcel cells that show descriptive text instead of the actual ID
_BAD_PARCEL_WORDS = {'property appraiser', 'multiple', 'various', 'see attachment',
                      'n/a', 'na', 'none', 'unknown', 'see documents'}

def _clean_parcel(raw: str | None, block: str) -> str | None:
    """
    Validate/clean parcel ID. RealAuction Parcel ID cells sometimes show
    link text like "Property Appraiser" or "MULTIPLE" instead of the actual ID;
    in that case fall back to extracting the STRAP param from the href URL.
    """
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower() in _BAD_PARCEL_WORDS:
        m = re.search(r'[?&]STRAP=([^&"\'<>\s]+)', block, re.IGNORECASE)
        return m.group(1).strip() if m else None
    if _PARCEL_RE.match(raw):
        return raw
    # Try URL extraction for anything that didn't match the pattern
    m = re.search(r'[?&]STRAP=([^&"\'<>\s]+)', block, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _parse_ret_html(ret_html: str, auction_date: date) -> list[dict]:
    """
    Parse AITEM blocks from the retHTML returned by the JSON UPDATE endpoint.

    The retHTML uses template shortcodes (@A, @B, @C, @F, @G, @H, @I)
    as placeholders for HTML tags. We regex-extract data directly from
    the compressed format without expanding the template.

    Label→value pattern:  LabelText:@F[^>]*>optionalAnchor VALUE optionalClose@G
    """
    items = []
    # Split on AITEM boundaries
    parts = re.split(r'<div id="AITEM_(\d+)"', ret_html)
    # parts[0] = preamble; then pairs: parts[1]=AID, parts[2]=content, ...
    for i in range(1, len(parts), 2):
        aid     = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ''

        def get_field(label: str) -> str | None:
            # After the label text, the value follows @F ... > VALUE @G
            # The value might be wrapped in <a ...>VALUE</a>
            pattern = rf'{re.escape(label)}:@F[^@>]*>[^>]*>(?:<a[^>]*>)?(.*?)(?:</a>)?@G'
            m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if not m:
                # Simpler fallback: label text directly before @F, value up to @G
                pattern2 = rf'{re.escape(label)}[^@]*@F[^>]*>(.*?)@G'
                m = re.search(pattern2, content, re.DOTALL | re.IGNORECASE)
            if m:
                val = _strip_html(m.group(1).replace('@G', '').replace('@F', '').replace('@B', ''))
                return val
            return None

        case_num    = get_field('Case #') or get_field('Case Number')
        parcel_raw  = get_field('Parcel ID') or get_field('Parcel No')
        parcel_id   = _clean_parcel(parcel_raw, content)
        auction_typ = get_field('Auction Type')
        judgment    = get_field('Final Judgment Amount') or get_field('Judgment Amount')
        assessed    = get_field('Assessed Value')
        cert_num    = get_field('Certificate #') or get_field('Certificate Number') or get_field('Cert #')
        opening_bid = get_field('Opening Bid') or get_field('Minimum Bid') or get_field('Opening Amount')

        # Address: label "Property Address" then value, followed by continuation line(s) with empty label
        addr_parts: list[str] = []
        addr_m = re.search(
            r'Property Address:@F[^>]*>(?:<a[^>]*>)?(.*?)(?:</a>)?@G',
            content, re.DOTALL | re.IGNORECASE
        )
        if addr_m:
            line1 = _strip_html(addr_m.group(1))
            if line1:
                addr_parts.append(line1)
            # Continuation: @H@CAD_LBL... >@F ... >LINE2@G  (empty label cell)
            rest_of_content = content[addr_m.end():]
            line2_m = re.search(
                r'@H[^@]*@CAD_LBL[^@]*@F[^>]*>(.*?)@G',
                rest_of_content, re.DOTALL | re.IGNORECASE
            )
            if line2_m:
                line2 = _strip_html(line2_m.group(1))
                if line2 and line2 not in (None, '', line1):
                    addr_parts.append(line2)
        prop_addr = ', '.join(addr_parts) if addr_parts else None

        # opening_bid: prefer explicit, else judgment amount as proxy
        opening_bid_f = _to_float(opening_bid) if opening_bid and opening_bid.lower() not in ('hidden',) else None
        if opening_bid_f is None:
            opening_bid_f = _to_float(judgment)

        if not case_num and not parcel_id and not cert_num:
            continue

        # Use AID as case_number fallback so each AITEM has a unique key
        effective_case = case_num or cert_num or f'AID_{aid}'

        items.append({
            'aid':              aid,
            'case_number':      effective_case,
            'parcel_id':        parcel_id,
            'property_address': prop_addr,
            'opening_bid':      opening_bid_f,
            'assessed_value':   assessed,
            'auction_type':     auction_typ,
            'certificate_number': cert_num,
        })

    return items


def scrape_preview_json(auction_date: date) -> list[dict]:
    """
    Pull all auction cards for a given date using the JSON UPDATE endpoint.
    1. GET the preview page to set session context (AUCTIONDATE cookie/session var)
    2. Call AREA=W with PageDir=0 for page 1, then PageDir=1 for subsequent pages.
    """
    date_str = auction_date.strftime('%m/%d/%Y')
    date_enc = date_str.replace('/', '%2F')
    preview_url = f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_enc}'

    print(f'  [preview] {auction_date} via JSON UPDATE endpoint')

    # Step 1: set session context
    status, _ = _get(preview_url)
    if status == 0 or status >= 400:
        print(f'    preview context-set failed: HTTP {status}', file=sys.stderr)
        return []

    # Step 2: load page 1 (doR=1 = fresh load)
    ret_html, rlist = _get_json_page(auction_date, area='W', page_dir=0, do_r=1)
    if not ret_html:
        print(f'    JSON page 1 empty', file=sys.stderr)
        return []

    all_cards  = _parse_ret_html(ret_html, auction_date)
    seen_aids  = set(c['aid'] for c in all_cards)
    print(f'    page 1: {len(all_cards)} cards (rlist={rlist[:40]})')

    # Step 3: paginate forward (PageDir=1, doR=0) until empty or duplicates
    MAX_PAGES = 15
    for pg in range(2, MAX_PAGES + 1):
        time.sleep(1)
        ret_html2, rlist2 = _get_json_page(auction_date, area='W', page_dir=1, do_r=0)
        if not ret_html2:
            print(f'    page {pg}: empty — stopping')
            break
        page_cards = _parse_ret_html(ret_html2, auction_date)
        if not page_cards:
            print(f'    page {pg}: 0 cards — stopping')
            break
        new_cards = [c for c in page_cards if c['aid'] not in seen_aids]
        if not new_cards:
            print(f'    page {pg}: no new AIDs — stopping (rlist={rlist2[:40]})')
            break
        for c in new_cards:
            seen_aids.add(c['aid'])
        all_cards.extend(new_cards)
        print(f'    page {pg}: +{len(new_cards)} new | total={len(all_cards)}')

    return all_cards


# ── PHASE C: UPSERT → MULTI_COUNTY_AUCTIONS ──────────────────────────────────

_BASE_COLUMNS = [
    'county', 'case_number', 'auction_date', 'sale_type', 'auction_type',
    'source_platform', 'auction_status', 'state', 'last_seen_at', 'data_source',
]
_OPTIONAL_FIELDS = ('property_address', 'opening_bid', 'parcel_id')


def upsert_to_mca(cards: list[dict], auction_date: date) -> tuple[int, list[str]]:
    """Batch-upsert cards to multi_county_auctions. Returns (inserted, errors)."""
    import datetime as _dt
    now_iso  = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    date_iso = auction_date.isoformat()

    # ALL rows must have identical key sets for PostgREST PGRST102 compliance.
    # Use None for optional fields so every row has the same schema.
    # Also deduplicate by (county, case_number, sale_type) within the batch —
    # duplicates in a single ON CONFLICT batch cause a 500 "cannot affect row twice".
    seen_keys: set[tuple] = set()
    rows = []
    for c in cards:
        cn = c['case_number']  # already set to AID fallback in parser
        key = (COUNTY, cn, SALE_TYPE)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        rows.append({
            'county':            COUNTY,
            'case_number':       cn,
            'auction_date':      date_iso,
            'sale_type':         SALE_TYPE,
            'auction_type':      SALE_TYPE,
            'source_platform':   PLATFORM,
            'auction_status':    'upcoming',
            'state':             'FL',
            'last_seen_at':      now_iso,
            'data_source':       'calendar_sweep_mca_v3',
            'property_address':  c.get('property_address') or None,
            'opening_bid':       c.get('opening_bid'),          # None if not found
            'parcel_id':         c.get('parcel_id') or None,
        })

    if not rows:
        return 0, []

    inserted = 0
    errors   = []
    BATCH    = 50
    prefer_h = {**SUPA_H, 'Prefer': 'resolution=merge-duplicates,return=minimal'}

    def _upsert_url(present_optional: tuple) -> str:
        """
        Build an upsert URL scoped via columns= to base columns plus only the
        optional fields present in this sub-batch. PostgREST's columns= param
        restricts BOTH the INSERT column list and the ON CONFLICT DO UPDATE
        SET clause to exactly these columns — so an optional field omitted
        here is left untouched on conflict (no null-wipe of prior enrichment),
        while it still defaults to NULL correctly on a genuine first INSERT.
        """
        cols = ','.join(_BASE_COLUMNS + list(present_optional))
        return f'{REST}/multi_county_auctions?on_conflict=county,case_number,sale_type&columns={cols}'

    def _row_for_columns(row: dict, present_optional: tuple) -> dict:
        out = {k: row[k] for k in _BASE_COLUMNS}
        for f in present_optional:
            out[f] = row[f]
        return out

    def _upsert_rows(row_list: list[dict]) -> tuple[int, list[str]]:
        """
        Group rows by which optional fields they actually have a value for,
        then issue one columns=-scoped request per group so absent fields
        never participate in that request's DO UPDATE SET (and thus never
        null out a previously-enriched value). Falls back to per-row retry
        on batch failure.
        """
        groups: dict[tuple, list[dict]] = {}
        for row in row_list:
            present = tuple(f for f in _OPTIONAL_FIELDS if row.get(f) is not None)
            groups.setdefault(present, []).append(row)

        ok, errs = 0, []
        for present_optional, group_rows in groups.items():
            url = _upsert_url(present_optional)
            payload = [_row_for_columns(r, present_optional) for r in group_rows]
            try:
                r = requests.post(url, json=payload, headers=prefer_h, timeout=30)
                if 200 <= r.status_code < 300:
                    ok += len(group_rows)
                    continue
                if len(group_rows) == 1:
                    errs.append(f'http {r.status_code} {r.text[:200]}')
                    continue
                # Group failed — retry each row individually (same grouping logic)
                for row in group_rows:
                    cnt, e = _upsert_rows([row])
                    ok += cnt
                    errs.extend(e)
            except requests.RequestException as e:
                errs.append(str(e))
        return ok, errs

    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        cnt, errs = _upsert_rows(batch)
        inserted += cnt
        if errs:
            for e in errs:
                print(f'  ! {e}', file=sys.stderr)
            errors.extend(errs)

    return inserted, errors


# ── GHA HELPERS ───────────────────────────────────────────────────────────────

def _write_summary(lines: list[str]) -> None:
    gh_summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if gh_summary:
        with open(gh_summary, 'a') as f:
            f.write('\n'.join(lines) + '\n')


# ── MAIN ─────────────────────────────────────────────────────────────────────

# Phase A
target_dates = discover_auction_dates()
if not target_dates:
    print(f'NOTE: {COUNTY}/{SALE_TYPE} — zero future auction dates discovered; county is genuinely dark',
          file=sys.stderr)
    _write_summary([
        f'## {COUNTY}/{SALE_TYPE}: DARK (no future dates found in navigation links)',
        f'- Platform: {PLATFORM}', f'- Base: {BASE_URL}'
    ])
    sys.exit(2)

print(f'\nScraping {len(target_dates)} future dates: {target_dates}')

# Phase B + C
total_upserted = 0
all_errors: list[str] = []

for auction_date in target_dates:
    print(f'\n--- {COUNTY} | {auction_date} ---')
    time.sleep(2)
    cards = scrape_preview_json(auction_date)
    if not cards:
        print(f'  NOTE: Zero cards for {auction_date}')
        continue
    upserted, errs = upsert_to_mca(cards, auction_date)
    total_upserted += upserted
    all_errors.extend(errs)
    print(f'  → upserted {upserted} / {len(cards)} cards for {auction_date}')

# Verify via SELECT
verify_url = (
    f'{REST}/multi_county_auctions?county=eq.{COUNTY}'
    f'&auction_date=gte.{TODAY.isoformat()}'
    f'&source_platform=eq.{PLATFORM}'
    '&select=auction_date,case_number&limit=5'
)
try:
    vr = requests.get(verify_url, headers=SUPA_H, timeout=20)
    if vr.status_code == 200:
        sample = vr.json()
        print(f'\nVERIFY: {len(sample)} rows in MCA for {COUNTY}/{PLATFORM} (sample: {sample[:3]})')
    else:
        print(f'\nVERIFY: SELECT returned {vr.status_code}', file=sys.stderr)
except Exception as e:
    print(f'\nVERIFY: {e}', file=sys.stderr)

_write_summary([
    f'## {COUNTY}/{SALE_TYPE} on {PLATFORM}',
    f'- Target dates: `{target_dates}`',
    f'- Rows upserted: **{total_upserted}**',
    *(f'- Errors: {all_errors[:3]}' for _ in [1] if all_errors),
])

gh_out = os.environ.get('GITHUB_OUTPUT')
if gh_out:
    with open(gh_out, 'a') as f:
        f.write(f'rows_upserted={total_upserted}\n')
        f.write(f'dates_scraped={len(target_dates)}\n')

if total_upserted == 0 and all_errors:
    print(f'ERROR: 0 rows upserted, {len(all_errors)} errors', file=sys.stderr)
    sys.exit(1)

if total_upserted == 0:
    print(f'NOTE: Zero rows upserted — {COUNTY}/{SALE_TYPE} has no cards for discovered dates',
          file=sys.stderr)
    sys.exit(2)

print(f'\nSUCCESS: {total_upserted} rows upserted to multi_county_auctions for {COUNTY}/{SALE_TYPE}')
sys.exit(0)
