#!/usr/bin/env python3
"""
propertyonion_brevard_fill.py — Fill opening_bid for Brevard courthouse FC auctions.
Dispatch: 895e6ae7-fdfd-4dde-a85f-b636b498f49f

Approach (in order):
  Pass A: Firecrawl PropertyOnion listing pages (paginated) — extracts case_number +
          judgment_amount for all upcoming Brevard FC auctions. Matches to DB by
          case_number and patches opening_bid. Angular SPA — requires Firecrawl.
  Pass B: Firecrawl individual PropertyOnion case pages — for any case not found in
          listing pages, search by normalized case_number slug on PropertyOnion.
  Verify: exact DB count (HONESTY PROTOCOL — BLANK > WRONG, never claim DONE
          without DB proof).

Env required:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FIRECRAWL_API_KEY

set -euo pipefail equivalent: sys.exit(1) on unrecoverable failures.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

# ── Config ────────────────────────────────────────────────────────────────────
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
FC_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

if not SB_URL or not SB_KEY:
    print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
    sys.exit(1)

if not FC_KEY:
    print("ERROR: FIRECRAWL_API_KEY required", file=sys.stderr)
    sys.exit(1)

# PropertyOnion URL structures to try (the SPA redirects /florida/ → / path)
PO_LISTING_URLS = [
    "https://propertyonion.com/foreclosure/brevard-county-fl",
    "https://www.propertyonion.com/florida/brevard-county/foreclosure",
]
FC_API = "https://api.firecrawl.dev/v1/scrape"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# ── Supabase helpers ──────────────────────────────────────────────────────────
def _H(extra: dict = None) -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
         "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h

def sb_get(path: str, params: str = "") -> list:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += ("&" if "?" in path else "?") + params
    req = urllib.request.Request(url, headers=_H())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  sb_get {path} HTTP {e.code}: {e.read()[:300]}", file=sys.stderr)
        return []

def sb_patch(path: str, payload) -> tuple[int, str]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=body, headers=_H(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

def count_null_bids() -> int:
    rows = sb_get("multi_county_auctions",
                  f"county=eq.brevard&auction_date=gte.{date.today().isoformat()}"
                  "&opening_bid=is.null&select=id&limit=500")
    return len(rows) if isinstance(rows, list) else 0

def fetch_null_rows() -> list:
    return sb_get("multi_county_auctions",
                  f"county=eq.brevard&auction_date=gte.2026-01-01&opening_bid=is.null"
                  "&select=id,case_number,auction_date&limit=500") or []

# ── Parsing helpers ───────────────────────────────────────────────────────────
def to_float(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r'\$?([\d,]+\.?\d*)', str(s))
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
        return v if v > 0 else None
    except ValueError:
        return None

def norm_case(s: str) -> str:
    """Normalize case number — strip non-alphanumeric for fuzzy matching."""
    return re.sub(r"[^0-9A-Z]", "", str(s).upper())

def extract_case_numbers(text: str) -> list[str]:
    """Extract FL foreclosure case numbers from scraped text.
    Patterns: 05-2024-CA-042890-XXCA-BC, 2024-CA-042890, etc."""
    found = set()
    # Full Brevard format
    found.update(re.findall(r'\d{2}-\d{4}-C[ACO]-\d{5,6}-[A-Z0-9X]+-[A-Z]+', text))
    # Short format (year-type-number)
    found.update(re.findall(r'\d{4}-C[ACO]-\d{5,6}', text))
    return list(found)

def extract_amounts_near(text: str, case_num_pattern: str) -> list[float]:
    """Find monetary amounts near a case number in text."""
    idx = text.find(case_num_pattern)
    if idx < 0:
        return []
    window = text[max(0, idx - 200):idx + 800]
    amounts = []
    for m in re.finditer(r'\$\s*([\d,]+\.?\d*)', window):
        try:
            v = float(m.group(1).replace(",", ""))
            if v > 1000:
                amounts.append(v)
        except ValueError:
            pass
    return amounts

# ── Firecrawl helper ──────────────────────────────────────────────────────────
def firecrawl_scrape(url: str, wait_ms: int = 8000, extra_actions: list = None,
                     with_scroll: bool = False) -> dict:
    """Scrape a URL with Firecrawl. Returns Firecrawl response dict."""
    actions = list(extra_actions or [])
    # Add a wait action for Angular SPA hydration
    if not any(a.get("type") == "wait" for a in actions):
        actions = [{"type": "wait", "milliseconds": wait_ms}] + actions

    # Add scroll actions for virtual-scroll SPAs (loads lazily-rendered content)
    if with_scroll:
        actions += [
            {"type": "scroll", "direction": "down", "amount": 800},
            {"type": "wait", "milliseconds": 1500},
            {"type": "scroll", "direction": "down", "amount": 800},
            {"type": "wait", "milliseconds": 1500},
            {"type": "scroll", "direction": "down", "amount": 800},
            {"type": "wait", "milliseconds": 1500},
            {"type": "scroll", "direction": "down", "amount": 800},
            {"type": "wait", "milliseconds": 2000},
        ]

    payload = json.dumps({
        "url": url,
        "formats": ["markdown", "rawHtml"],
        "waitFor": wait_ms,
        "actions": actions,
        "timeout": 150000,
    }).encode()
    req = urllib.request.Request(FC_API, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {FC_KEY}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"  Firecrawl HTTP {e.code}: {body}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"  Firecrawl error: {e}", file=sys.stderr)
        return {}

def get_markdown(fc_response: dict) -> str:
    """Extract markdown from Firecrawl response."""
    data = fc_response.get("data", {})
    return data.get("markdown", "") or ""

def get_html(fc_response: dict) -> str:
    """Extract rawHtml from Firecrawl response."""
    data = fc_response.get("data", {})
    return data.get("rawHtml", "") or ""

# ── Parse PropertyOnion markdown for case→amount map ─────────────────────────
def parse_po_markdown(md: str) -> dict[str, float]:
    """Parse PropertyOnion markdown and return {norm_case_number: amount} map.
    Handles multiple layout patterns across PropertyOnion listing pages."""
    result: dict[str, float] = {}
    if not md:
        return result

    # Pattern 1: case number followed by judgment/opening bid amount on same or adjacent line
    # PropertyOnion markdown typically shows: "Case #: 05-XXXX-CA-XXXXXX ..."  "Judgment: $XXX,XXX"
    # Look for case numbers first
    case_patterns = [
        r'(?:Case\s*#?:?\s*)(0?5-\d{4}-C[ACO]-\d{5,6}[-\w]*)',
        r'(?:Case\s+Number:?\s*)(0?5-\d{4}-C[ACO]-\d{5,6}[-\w]*)',
        r'\b(0?5-\d{4}-C[ACO]-\d{5,6}-[A-Z0-9X]+-[A-Z]+)\b',
        r'\b(\d{4}-C[ACO]-\d{5,6})\b',
    ]

    # Also look for dollar amounts labeled as judgment/opening bid
    amount_patterns = [
        r'(?:Opening\s+Bid|Final\s+Judgment|Judgment\s+Amount|Starting\s+Bid)[^\d$]*\$\s*([\d,]+\.?\d*)',
        r'(?:Bid\s+Amount|Min(?:imum)?\s+Bid)[^\d$]*\$\s*([\d,]+\.?\d*)',
    ]

    # Split markdown into property blocks — PropertyOnion separates listings with horizontal rules
    # or repeated header patterns
    blocks = re.split(r'\n---+\n|\n\*\*\*+\n|\n#{1,3}\s', md)
    if len(blocks) <= 1:
        # Try splitting on property card boundaries
        blocks = re.split(r'\n\n(?=(?:##|\*\*|Case|Property))', md)

    for block in blocks:
        # Find case number in block
        cn_found = None
        for pat in case_patterns:
            m = re.search(pat, block, re.IGNORECASE)
            if m:
                cn_found = m.group(1)
                break
        if not cn_found:
            continue

        # Find amount in same block
        amt_found = None
        for pat in amount_patterns:
            m = re.search(pat, block, re.IGNORECASE)
            if m:
                v = to_float(m.group(1))
                if v and v > 1000:
                    amt_found = v
                    break

        if amt_found:
            result[norm_case(cn_found)] = amt_found

    # Fallback: scan whole markdown for case# then look for nearby dollar amounts
    # (handles continuous markdown without clear block separators)
    if not result:
        for pat in case_patterns:
            for m in re.finditer(pat, md, re.IGNORECASE):
                cn = m.group(1)
                nk = norm_case(cn)
                if nk in result:
                    continue
                # Look for amounts in 500-char window after case number
                window = md[m.start():m.start() + 500]
                for apat in amount_patterns:
                    am = re.search(apat, window, re.IGNORECASE)
                    if am:
                        v = to_float(am.group(1))
                        if v and v > 1000:
                            result[nk] = v
                            break
                # Also try any dollar amount in the window
                if nk not in result:
                    dollar_amounts = [
                        to_float(x) for x in
                        re.findall(r'\$\s*([\d,]+\.?\d*)', window)
                    ]
                    valid = [x for x in dollar_amounts if x and x > 5000]
                    if valid:
                        result[nk] = max(valid)

    return result

# ── Pass A: Firecrawl PropertyOnion listing pages ─────────────────────────────
def pass_a_listing_pages(null_rows: list) -> int:
    """Scrape PropertyOnion listing pages for Brevard County FC auctions.
    Tries paginated listing + search with case number filter.
    Returns count of rows filled."""
    print("\n═══ Pass A: Firecrawl PropertyOnion listing pages ═══")
    if not null_rows:
        print("  No NULL rows — skip")
        return 0

    # Build normalized lookup from DB rows
    db_map: dict[str, dict] = {}
    for row in null_rows:
        cn = row.get("case_number") or ""
        if cn:
            db_map[norm_case(cn)] = row

    print(f"  {len(db_map)} NULL Brevard cases to fill")

    combined: dict[str, float] = {}  # norm_case → amount

    # Try up to 25 listing pages (Brevard has ~112 upcoming auctions, ~8–12 per page)
    listing_base = PO_LISTING_URLS[0]
    for page_num in range(1, 26):
        page_url = f"{listing_base}?page={page_num}" if page_num > 1 else listing_base
        print(f"  Scraping page {page_num}: {page_url}")

        # Use scroll actions on listing pages to trigger lazy-load of SPA content
        resp = firecrawl_scrape(page_url, wait_ms=8000, with_scroll=True)
        if not resp.get("success") and not resp.get("data"):
            print(f"  Page {page_num}: Firecrawl returned no data — stopping pagination")
            break

        md = get_markdown(resp)
        html = get_html(resp)

        # Check for end of pagination (no more listings or error page)
        if "404" in (resp.get("data", {}).get("statusCode", "") or "") or \
           "page not found" in md.lower() or \
           "no properties" in md.lower() or \
           "no results" in md.lower():
            print(f"  Page {page_num}: end of listings")
            break

        md_len = len(md)
        html_len = len(html)
        print(f"  Page {page_num}: md_len={md_len}, html_len={html_len}")

        if md_len < 200 and html_len < 5000:
            print(f"  Page {page_num}: empty page — stopping pagination")
            break

        # Parse from both markdown and HTML
        page_map = parse_po_markdown(md)
        if not page_map and html:
            # Fallback: parse from raw HTML
            page_map = parse_po_markdown(html)

        print(f"  Page {page_num}: found {len(page_map)} case→amount pairs")
        combined.update(page_map)

        # Also try the /florida/ URL variant on page 1
        if page_num == 1 and not page_map:
            alt_url = PO_LISTING_URLS[1] if len(PO_LISTING_URLS) > 1 else None
            if alt_url:
                print(f"  Page 1 returned 0 pairs — trying alternate URL: {alt_url}")
                resp2 = firecrawl_scrape(alt_url, wait_ms=10000, with_scroll=True)
                md2 = get_markdown(resp2)
                page_map2 = parse_po_markdown(md2)
                print(f"  Alternate URL: {len(page_map2)} pairs")
                combined.update(page_map2)

        # Stop early if we've found all 112 cases
        matched = sum(1 for k in combined if k in db_map)
        print(f"  Cumulative: {len(combined)} total pairs, {matched}/{len(db_map)} DB matches")
        if matched >= len(db_map):
            print("  All NULL cases found — stopping pagination early")
            break

        # No new cases on this page → probably at end
        if not page_map and page_num > 3:
            print(f"  Page {page_num}: 0 pairs on 4th+ page — stopping pagination")
            break

        time.sleep(3)  # throttle Firecrawl calls

    # Apply matches to DB
    filled = 0
    for nk, amount in combined.items():
        row = db_map.get(nk)
        if not row:
            continue
        st, body = sb_patch(
            f"multi_county_auctions?id=eq.{row['id']}",
            {"opening_bid": amount,
             "judgment_amount": amount,
             "judgment_source": "propertyonion_firecrawl_2026"})
        if st in (200, 201, 204):
            print(f"  FILLED id={row['id']} case={row['case_number']} bid={amount}")
            filled += 1
        else:
            print(f"  PATCH FAILED id={row['id']}: HTTP {st} {body[:100]}")

    print(f"  Pass A filled: {filled}")
    return filled


# ── Pass B: Individual PropertyOnion case page lookup ─────────────────────────
def pass_b_individual_lookup(null_rows: list) -> int:
    """For cases not found in listing pages, try individual PropertyOnion case pages.
    PropertyOnion case URLs: /foreclosure/{county}-fl/{case-slug} or search by case number.
    Returns count of rows filled."""
    print("\n═══ Pass B: Individual PropertyOnion case lookups ═══")
    if not null_rows:
        print("  No NULL rows — skip")
        return 0

    print(f"  {len(null_rows)} cases remaining — attempting individual lookups")
    filled = 0

    for row in null_rows:
        cn = (row.get("case_number") or "").strip()
        if not cn:
            continue

        # PropertyOnion case URL slug format (observed from existing data):
        # The case number slug is typically the case number with dashes → URL-encoded
        # Try multiple URL patterns
        cn_slug = cn.replace(" ", "-").lower()
        urls_to_try = [
            f"https://propertyonion.com/foreclosure/brevard-county-fl/{urllib.parse.quote(cn_slug)}",
            f"https://propertyonion.com/foreclosure/brevard-county-fl/{urllib.parse.quote(cn)}",
            # PropertyOnion search by case number
            f"https://propertyonion.com/foreclosure?search={urllib.parse.quote(cn)}&county=brevard",
        ]

        found_amount = None
        for url in urls_to_try:
            print(f"  case={cn} → {url[:80]}")
            resp = firecrawl_scrape(url, wait_ms=6000)
            if not resp.get("success") and not resp.get("data"):
                continue

            md = get_markdown(resp)
            html = get_html(resp)
            combined_text = md + "\n" + html

            # Look for amount near the case number in the page
            amounts_near = extract_amounts_near(combined_text, cn)
            if not amounts_near:
                # Try normalized form
                amounts_near = extract_amounts_near(combined_text, norm_case(cn))

            # Also try explicit amount patterns on the page
            for pat in [
                r'(?:Opening\s+Bid|Final\s+Judgment|Judgment\s+Amount|Starting\s+Bid)[^\d$]*\$\s*([\d,]+\.?\d*)',
                r'(?:Bid|Amount)[^\d$]*\$\s*([\d,]+\.?\d*)',
            ]:
                for m in re.finditer(pat, combined_text, re.IGNORECASE):
                    v = to_float(m.group(1))
                    if v and v > 1000:
                        amounts_near.append(v)

            if amounts_near:
                # Use the largest amount found (judgment amounts are typically the largest)
                found_amount = max(amounts_near)
                print(f"  Found: {found_amount} for case={cn}")
                break

            time.sleep(2)

        if found_amount:
            st, body = sb_patch(
                f"multi_county_auctions?id=eq.{row['id']}",
                {"opening_bid": found_amount,
                 "judgment_amount": found_amount,
                 "judgment_source": "propertyonion_firecrawl_individual_2026"})
            if st in (200, 201, 204):
                print(f"  FILLED id={row['id']} case={cn} bid={found_amount}")
                filled += 1
            else:
                print(f"  PATCH FAILED id={row['id']}: HTTP {st} {body[:100]}")
        else:
            print(f"  NOT FOUND on PropertyOnion: case={cn}")

        time.sleep(2)

    print(f"  Pass B filled: {filled}")
    return filled


# ── Pass C: FL Dept of Revenue property tax data (no Firecrawl needed) ────────
def pass_c_judgment_fallback_check(null_rows: list) -> int:
    """Final fallback: check if any remaining NULL rows have judgment_amount > 1000
    already in DB (judgment_source set by a previous run) and copy it to opening_bid.
    Catches rows where judgment_amount was filled but opening_bid wasn't synced."""
    print("\n═══ Pass C: judgment_amount sync fallback ═══")
    if not null_rows:
        return 0

    ids = [r["id"] for r in null_rows if r.get("id")]
    if not ids:
        return 0

    # Re-fetch with judgment_amount
    id_filter = "in.(" + ",".join(str(i) for i in ids) + ")"
    rows = sb_get("multi_county_auctions",
                  f"id={id_filter}&judgment_amount=gt.1000"
                  "&select=id,case_number,judgment_amount&limit=500")
    if not rows:
        print("  No rows with judgment_amount > 1000 — skip")
        return 0

    filled = 0
    for row in rows:
        amt = row.get("judgment_amount")
        if not amt:
            continue
        st, body = sb_patch(
            f"multi_county_auctions?id=eq.{row['id']}",
            {"opening_bid": amt, "judgment_source": "judgment_amount_sync"})
        if st in (200, 201, 204):
            print(f"  SYNCED id={row['id']} case={row['case_number']} bid={amt}")
            filled += 1
        else:
            print(f"  SYNC FAILED id={row['id']}: HTTP {st}")

    print(f"  Pass C synced: {filled}")
    return filled


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 70)
    print("propertyonion_brevard_fill.py  dispatch=895e6ae7")
    print(f"Date: {date.today().isoformat()}")
    print("=" * 70)

    before = count_null_bids()
    print(f"\nBASELINE: {before} Brevard auctions with NULL opening_bid")

    if before == 0:
        print("DoD already satisfied — 0 NULLs. Exiting.")
        return

    # Fetch all NULL rows once
    null_rows = fetch_null_rows()
    print(f"  Fetched {len(null_rows)} NULL rows from DB")

    # Pass A: PropertyOnion listing pages
    pass_a_listing_pages(null_rows)
    after_a = count_null_bids()
    print(f"\nAfter Pass A: {after_a} NULLs remaining (filled {before - after_a})")

    # Pass B: individual case lookups for anything still NULL
    pass_b_cap = int(os.environ.get("PASS_B_CAP", "30"))
    if after_a > 0:
        remaining_rows = fetch_null_rows()
        pass_b_individual_lookup(remaining_rows[:pass_b_cap])  # cap to control Firecrawl cost
        after_b = count_null_bids()
        print(f"\nAfter Pass B: {after_b} NULLs remaining (filled {after_a - after_b})")
    else:
        after_b = after_a

    # Pass C: sync judgment_amount to opening_bid for any remaining rows
    if after_b > 0:
        remaining_rows = fetch_null_rows()
        pass_c_judgment_fallback_check(remaining_rows)

    # Verification — HONESTY PROTOCOL: always query DB, never estimate
    final = count_null_bids()
    print("\n" + "=" * 70)
    print("### SQL VERIFICATION")
    print(f"SELECT COUNT(*) FROM multi_county_auctions")
    print(f"WHERE county='brevard' AND auction_date >= CURRENT_DATE AND opening_bid IS NULL;")
    print(f"-- Result: {final}")
    print(f"\nBrevard opening_bid NULLs: {before} → {final}")
    print(f"Filled this run: {before - final}")
    dod = (final == 0)
    print(f"Gate 2 (COUNT=0): {'PASS ✓' if dod else 'FAIL ✗'}")
    print("=" * 70)

    if not dod:
        print(f"\nUNTESTED residual: {final} rows remain NULL.")
        print("Possible causes:")
        print("  1. PropertyOnion does not index these specific Brevard cases yet")
        print("  2. Angular SPA hydration timing — increase waitFor to 12000ms")
        print("  3. PropertyOnion requires auth for judgment amounts on some listings")
        print("  4. Case number format mismatch between PropertyOnion and DB")
        sys.exit(2)  # 2 = partial (not all filled)


if __name__ == "__main__":
    main()
