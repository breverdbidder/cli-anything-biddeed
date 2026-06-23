#!/usr/bin/env python3
"""
calendar_sweep_mca.py — BIDDEED 67-County Calendar Sweep v2.0

Phase A: Scrape CALENDAR page → discover future auction dates (direct HTTP, no Firecrawl)
Phase B: Scrape PREVIEW page per date → extract upcoming listings via AITEM HTML blocks
Phase C: Upsert directly into multi_county_auctions

No Firecrawl dependency — uses requests + regex against server-side-rendered HTML.
Detection: login-wall, empty calendar, 403 all exit(2) (genuinely dark / blocked).

Env (required): COUNTY_SLUG, BASE_URL, PLATFORM, SALE_TYPE,
                SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Exit codes:
  0 = success (≥1 row upserted)
  1 = fatal error (Supabase error, unrecoverable network failure)
  2 = county genuinely dark (zero future dates, zero listings, login wall, or 403)
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
HTTP_H = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

print(f'>>> calendar_sweep_mca v2.0 | {COUNTY} ({SALE_TYPE}) | {PLATFORM} | today={TODAY}')
print(f'    BASE_URL={BASE_URL}')

SESSION = requests.Session()
SESSION.headers.update(HTTP_H)


# ── HTTP HELPERS ──────────────────────────────────────────────────────────────

def _get_html(url: str, retries: int = 2) -> tuple[str, str]:
    """Return (html, error_note). Never raises; returns ('', note) on failure."""
    for attempt in range(retries + 1):
        try:
            r = SESSION.get(url, timeout=30, allow_redirects=True)
            print(f'    GET {url} → {r.status_code} ({len(r.text)} bytes)')
            if r.status_code == 403:
                return '', f'403 Forbidden'
            if r.status_code >= 400:
                return '', f'HTTP {r.status_code}'
            return r.text, ''
        except requests.RequestException as e:
            if attempt < retries:
                time.sleep(3)
            else:
                return '', str(e)
    return '', 'exhausted retries'


def _is_login_wall(html: str) -> bool:
    """
    True only when the page IS a login wall (no auction content present).
    RealAuction sites have a login header link on every page — that is NOT a wall.
    A wall is: login form is the dominant content AND no AITEM/calendar data present.
    """
    if not html:
        return False
    has_login_form = bool(
        re.search(r'id=["\']logPassword["\']', html, re.IGNORECASE) or
        (re.search(r'name=["\']UserID["\']', html, re.IGNORECASE) and
         re.search(r'<form', html, re.IGNORECASE))
    )
    if not has_login_form:
        return False
    # Has a login form — but does the page also have auction content?
    has_auction_content = bool(
        re.search(r'AUCTIONDATE=', html, re.IGNORECASE) or
        re.search(r'<div[^>]*id=["\']AITEM_', html, re.IGNORECASE) or
        re.search(r'class=["\'][^"\']*TDsmal', html, re.IGNORECASE) or   # calendar cells
        re.search(r'class=["\'][^"\']*AD_LBL', html, re.IGNORECASE)       # card labels
    )
    return not has_auction_content


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
    t = re.sub(r'<[^>]+>', '', s)
    clean = re.sub(r'[^\d.]', '', t)
    if clean:
        try:
            return float(clean)
        except ValueError:
            pass
    return None


# ── PHASE A: CALENDAR → FUTURE DATES ─────────────────────────────────────────

def scrape_calendar() -> tuple[list[date], str]:
    """Fetch both calendar endpoints; return sorted list of future dates."""
    urls = [
        f'{BASE_URL}/index.cfm?zaction=USER&zmethod=CALENDAR',
        f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=CALENDAR',
    ]

    raw_dates: set[date] = set()
    any_html = False

    for url in urls:
        print(f'  [calendar] {url}')
        html, err = _get_html(url)
        if err:
            print(f'    skipped: {err}')
            time.sleep(2)
            continue
        if _is_login_wall(html):
            print(f'    login wall detected — skipping')
            time.sleep(2)
            continue

        any_html = True
        _extract_dates(html, raw_dates)
        time.sleep(2)

    if not any_html:
        return [], 'All calendar fetches failed or returned login walls'

    future = sorted(d for d in raw_dates if d >= TODAY)
    print(f'  [calendar] raw={len(raw_dates)} total dates; future={len(future)}: {future[:7]}')
    return future, ''


def _extract_dates(html: str, out: set[date]) -> None:
    """Extract all plausible auction dates from raw HTML into out set."""
    # Pattern 1: AUCTIONDATE=MM/DD/YYYY in hrefs/links (primary RealAuction pattern)
    for m in re.finditer(r'AUCTIONDATE=([\d%/]+)', html, re.IGNORECASE):
        raw = m.group(1).replace('%2F', '/').replace('%2f', '/')
        try:
            d = datetime.strptime(raw, '%m/%d/%Y').date()
            if 2024 <= d.year <= 2030:
                out.add(d)
        except ValueError:
            pass

    # Pattern 2: MM/DD/YYYY free text / cell text
    for m in re.finditer(r'(\d{2})/(\d{2})/(\d{4})', html):
        try:
            d = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            if 2024 <= d.year <= 2030:
                out.add(d)
        except (ValueError, OverflowError):
            pass

    # Pattern 3: YYYY-MM-DD in data attrs or iso strings
    for m in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', html):
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if 2024 <= d.year <= 2030:
                out.add(d)
        except (ValueError, OverflowError):
            pass

    # Pattern 4: data-auction-date="..." attributes
    for m in re.finditer(r'data-(?:auction-?)?date=["\']([\d/\-]+)["\']', html, re.IGNORECASE):
        raw = m.group(1)
        for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
            try:
                d = datetime.strptime(raw, fmt).date()
                if 2024 <= d.year <= 2030:
                    out.add(d)
                break
            except ValueError:
                pass


# ── PHASE B: PREVIEW → UPCOMING LISTINGS ─────────────────────────────────────

def scrape_preview(auction_date: date) -> list[dict]:
    """
    Fetch PREVIEW pages for a specific auction date.
    Paginates via ?curPCA=N up to MAX_PAGES.
    Returns list of card dicts.
    """
    MAX_PAGES = 10
    date_slash = auction_date.strftime('%m/%d/%Y')
    date_enc   = date_slash.replace('/', '%2F')
    base_preview = (
        f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW'
        f'&AUCTIONDATE={date_enc}'
    )
    print(f'  [preview] {base_preview}')

    html, err = _get_html(base_preview)
    if err:
        print(f'    page 1 failed: {err}')
        return []
    if _is_login_wall(html):
        print(f'    page 1: login wall — county requires auth')
        return []

    cards = _parse_aitem_blocks(html, auction_date)
    seen  = {c['parcel_id'] for c in cards if c.get('parcel_id')}
    print(f'    page 1: {len(html)} bytes, {len(cards)} cards')

    for pg in range(2, MAX_PAGES + 1):
        time.sleep(2)
        pg_url = f'{base_preview}&curPCA={pg}'
        pg_html, pg_err = _get_html(pg_url)
        if pg_err or not pg_html:
            print(f'    page {pg} failed: {pg_err} — stopping')
            break
        if _is_login_wall(pg_html):
            break

        pg_cards = _parse_aitem_blocks(pg_html, auction_date)
        new = [c for c in pg_cards if c.get('parcel_id') and c['parcel_id'] not in seen]
        if not new:
            print(f'    page {pg}: no new cards — stopping')
            break
        for c in new:
            if c.get('parcel_id'):
                seen.add(c['parcel_id'])
        cards.extend(new)
        print(f'    page {pg}: {len(new)} new | total={len(cards)}')

    return cards


def _parse_aitem_blocks(html: str, auction_date: date) -> list[dict]:
    """
    Parse <div id="AITEM_XXXXXXXX"> blocks from RealAuction PREVIEW HTML.
    Pattern proven in fill_opening_bids_brevard_duval.py.
    """
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+[^>]*id=["\']AITEM_\d+["\']', html)]
    if not starts:
        # Fallback: try older "Upcoming Auctions" section with card-style divs
        items = _parse_legacy_cards(html, auction_date)
        if items:
            print(f'      (legacy card parser: {len(items)} cards)')
        return items

    starts.append(len(html))
    for i in range(len(starts) - 1):
        block = html[starts[i]:starts[i + 1]]

        # Extract AID (unique auction ID)
        aid_m = re.search(r'\baid=["\']?(\d+)["\']?', block)
        aid = aid_m.group(1) if aid_m else None

        # Auction status
        if re.search(r'Auction\s*Sold', block, re.IGNORECASE):
            status = 'SOLD'
        elif re.search(r'Auction\s*Status[^<]*Redeemed', block, re.IGNORECASE | re.DOTALL):
            status = 'REDEEMED'
        elif re.search(r'Auction\s*Status[^<]*Cancell?ed', block, re.IGNORECASE | re.DOTALL):
            status = 'CANCELED'
        elif re.search(r'Auction\s*Status[^<]*Postponed', block, re.IGNORECASE | re.DOTALL):
            status = 'POSTPONED'
        else:
            status = 'LISTED'

        # Extract label/value pairs from AD_LBL + AD_DTA table cells
        rows = re.findall(
            r'<td[^>]*class=["\'][^"\']*AD_LBL[^"\']*["\'][^>]*>(.*?)</td>\s*'
            r'<td[^>]*class=["\'][^"\']*AD_DTA[^"\']*["\'][^>]*>(.*?)</td>',
            block, re.DOTALL | re.IGNORECASE
        )

        data: dict[str, str] = {}
        addr_parts: list[str] = []
        last_addr = False

        for lbl_h, dta_h in rows:
            lbl = _strip_html(lbl_h) or ''
            lbl_lower = lbl.lower().rstrip(':').strip()
            if 'property address' in lbl_lower:
                t = _strip_html(dta_h)
                if t:
                    addr_parts.append(t)
                last_addr = True
                continue
            if last_addr and not lbl_lower:
                t = _strip_html(dta_h)
                if t:
                    addr_parts.append(t)
                continue
            last_addr = False
            if lbl_lower:
                data[lbl_lower] = dta_h

        case_num = (
            _strip_html(data.get('case #')) or
            _strip_html(data.get('case number')) or
            _strip_html(data.get('case no')) or
            _strip_html(data.get('case no.'))
        )
        parcel_id = (
            _strip_html(data.get('parcel id')) or
            _strip_html(data.get('parcel #')) or
            _strip_html(data.get('parcel no'))
        )
        prop_addr = ', '.join(addr_parts) if addr_parts else _strip_html(data.get('address'))
        opening_bid = _to_float(data.get('opening bid') or data.get('minimum bid'))
        assessed_val = _strip_html(data.get('assessed value') or data.get('assessed val'))
        auction_type = _strip_html(data.get('auction type') or data.get('type'))
        cert_num = _strip_html(data.get('certificate #') or data.get('cert #') or data.get('certificate number'))

        if not case_num and not parcel_id:
            continue

        items.append({
            'aid':              aid,
            'case_number':      case_num,
            'parcel_id':        parcel_id,
            'property_address': prop_addr,
            'opening_bid':      opening_bid,
            'assessed_value':   assessed_val,
            'auction_type':     auction_type,
            'certificate_number': cert_num,
            'auction_status':   status,
            '_auction_date':    auction_date,
        })

    return items


def _parse_legacy_cards(html: str, auction_date: date) -> list[dict]:
    """
    Fallback for RealAuction variants that use different markup.
    Looks for case number patterns in the page text.
    """
    items = []
    # Find case numbers (FL format: XX-YYYY-CA-XXXXXX or similar)
    case_nums = re.findall(
        r'(?:Case\s*#?|Case\s*No\.?)\s*[:\|]?\s*'
        r'([\dA-Z]{2}-\d{4}-[A-Z]{2}-\d+|[\dA-Z]+-\d+)',
        html, re.IGNORECASE
    )
    seen_cases = set()
    for cn in case_nums:
        cn = cn.strip().upper()
        if cn in seen_cases:
            continue
        seen_cases.add(cn)
        # Find parcel near this case number
        case_pos = html.upper().find(cn)
        nearby = html[max(0, case_pos - 200):case_pos + 500]
        pid_m = re.search(r'Parcel\s*ID[^\d]*(\d{6,15})', nearby, re.IGNORECASE)
        bid_m = re.search(r'Opening\s*Bid[^\$\d]*\$?([\d,]+(?:\.\d{2})?)', nearby, re.IGNORECASE)
        items.append({
            'aid':              None,
            'case_number':      cn,
            'parcel_id':        pid_m.group(1) if pid_m else None,
            'property_address': None,
            'opening_bid':      _to_float(bid_m.group(1)) if bid_m else None,
            'assessed_value':   None,
            'auction_type':     None,
            'certificate_number': None,
            'auction_status':   'LISTED',
            '_auction_date':    auction_date,
        })
    return items


# ── PHASE C: UPSERT → MULTI_COUNTY_AUCTIONS ──────────────────────────────────

def upsert_to_mca(cards: list[dict], auction_date: date) -> tuple[int, list[str]]:
    """Batch-upsert cards to multi_county_auctions. Returns (inserted, errors)."""
    now_iso  = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    date_iso = auction_date.isoformat()

    rows = []
    for c in cards:
        row = {
            'county':          COUNTY,
            'case_number':     c['case_number'] or c.get('parcel_id', 'UNKNOWN'),
            'auction_date':    date_iso,
            'sale_type':       SALE_TYPE,
            'auction_type':    SALE_TYPE,
            'source_platform': PLATFORM,
            'auction_status':  'upcoming',
            'state':           'FL',
            'last_seen_at':    now_iso,
            'data_source':     'calendar_sweep_mca_v2',
        }
        if c.get('property_address'):
            row['property_address'] = c['property_address']
        if c.get('opening_bid') is not None:
            row['opening_bid'] = c['opening_bid']
        if c.get('parcel_id'):
            row['parcel_id'] = c['parcel_id']
        rows.append(row)

    if not rows:
        return 0, []

    inserted = 0
    errors   = []
    BATCH    = 50
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        try:
            r = requests.post(
                f'{REST}/multi_county_auctions',
                json=batch,
                headers={**SUPA_H, 'Prefer': 'resolution=merge-duplicates,return=minimal'},
                timeout=30,
            )
            if r.status_code in (200, 201):
                inserted += len(batch)
            else:
                err = f'batch {i // BATCH + 1}: http {r.status_code} {r.text[:200]}'
                errors.append(err)
                print(f'  ! {err}', file=sys.stderr)
        except requests.RequestException as e:
            err = f'batch {i // BATCH + 1}: {e}'
            errors.append(err)
            print(f'  ! {err}', file=sys.stderr)

    return inserted, errors


# ── MAIN ─────────────────────────────────────────────────────────────────────

def _write_summary(lines: list[str]) -> None:
    gh_summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if gh_summary:
        with open(gh_summary, 'a') as f:
            f.write('\n'.join(lines) + '\n')


# Phase A
future_dates, cal_err = scrape_calendar()
if cal_err and not future_dates:
    print(f'NOTE: Calendar unavailable — {cal_err}', file=sys.stderr)
    _write_summary([f'## {COUNTY}/{SALE_TYPE}: DARK (calendar unreachable: {cal_err})'])
    sys.exit(2)

if not future_dates:
    print(f'NOTE: {COUNTY}/{SALE_TYPE} — zero future dates on calendar; county is genuinely dark',
          file=sys.stderr)
    _write_summary([
        f'## {COUNTY}/{SALE_TYPE}: DARK (no future dates)',
        f'- Platform: {PLATFORM}', f'- Base: {BASE_URL}'
    ])
    sys.exit(2)

# Cap at 5 future dates to control cost
target_dates = future_dates[:5]
print(f'\nScraping {len(target_dates)} future dates: {target_dates}')

# Phase B + C
total_upserted = 0
all_errors     = []

for auction_date in target_dates:
    print(f'\n--- {COUNTY} | {auction_date} ---')
    time.sleep(2)
    cards = scrape_preview(auction_date)
    if not cards:
        print(f'  NOTE: Zero cards for {auction_date} (no listings or parse failure)')
        continue
    upserted, errs = upsert_to_mca(cards, auction_date)
    total_upserted += upserted
    all_errors.extend(errs)
    print(f'  → upserted {upserted} / {len(cards)} cards for {auction_date}')

# Verify: quick SELECT to confirm rows landed
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
    print(f'\nVERIFY: failed: {e}', file=sys.stderr)

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
    print(f'NOTE: Zero rows upserted — {COUNTY}/{SALE_TYPE} has no upcoming listings on calendar',
          file=sys.stderr)
    sys.exit(2)

print(f'\nSUCCESS: {total_upserted} rows upserted to multi_county_auctions for {COUNTY}/{SALE_TYPE}')
sys.exit(0)
