#!/usr/bin/env python3
"""
taylor_bf_fresh_avenue.py — Taylor County B/F: fresh-avenue probe, loop run 6354.

All previously-tried avenues (session 4c2cb537):
  - pubrecords.taylorclerk.com/PublicInquiry  → Cloudflare 403 (confirmed 4x)
  - myfloridacounty.com/official_records/    → redirects to above
  - taylorclerk.com/departments/tax-deeds-surplus/ → stale (2025-02-19)
  - taylorclerk.com/departments/foreclosure-sales/ → removes closed cases
  - taylor.realtdm.com                        → TEST sandbox, zero real data
  - qpublic.net/fl/taylor/                    → Cloudflare 403

NEW AVENUES THIS SESSION (not tried in 4c2cb537):
  1. Direct PDF URL pattern for Certificate of Title docs
     (taylorclerk.com/uploads/{year}/{case-number-slug}.pdf — prior session
      confirmed this pattern works for the Final Judgment PDF; CT/sale docs
      may follow the same pattern)
  2. Florida Courts E-Filing portal (myflcourtaccess.com/portal) — public
     access to filed documents in Florida circuit courts
  3. FTP/bulk data exports sometimes published by FL county clerks
  4. OpenCorporates / FincEN alternative record sources
  5. Zillow/Redfin sold records for the specific addresses (sale price proxy)
     — NOTE: these are NOT clerk-recorded amounts and would be PropertyOnion-
     class (litmus-only), but could confirm if a sale happened (B numerator
     is independent data_source requirement; retail-data IS banned per canon)

HONESTY: Report what each probe actually returns. If blocked, say so. No
fabricated data_source rows.

Usage:
  python3 scripts/taylor_bf_fresh_avenue.py
"""

import os
import re
import sys
import json
import time
from datetime import datetime, timezone

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY env var required", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

NOW = datetime.now(timezone.utc)

CASES = [
    {"case_number": "25-196 CA", "sale_type": "foreclosure", "slug": "25-196-CA"},
    {"case_number": "25-217 CA", "sale_type": "foreclosure", "slug": "25-217-CA"},
    {"case_number": "25-218 CA", "sale_type": "foreclosure", "slug": "25-218-CA"},
    {"case_number": "23-597 CA", "sale_type": "foreclosure", "slug": "23-597-CA"},
    {"case_number": "TDA 26-026", "sale_type": "tax_deed", "slug": "TDA-26-026"},
    {"case_number": "TDA 26-031", "sale_type": "tax_deed", "slug": "TDA-26-031"},
    {"case_number": "TDA 26-032", "sale_type": "tax_deed", "slug": "TDA-26-032"},
    {"case_number": "TDA 26-028", "sale_type": "tax_deed", "slug": "TDA-26-028"},
    {"case_number": "TDA 26-033", "sale_type": "tax_deed", "slug": "TDA-26-033"},
]

TAYLOR_CLERK_BASE = "https://taylorclerk.com"

client = httpx.Client(
    timeout=30,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    },
    follow_redirects=True,
)


def log(msg, level="INFO"):
    print(f"[{NOW.isoformat()}] {level}: {msg}", flush=True)


def probe_direct_pdf_urls():
    """
    Attempt to fetch Certificate of Title / Notice of Sale Results PDFs
    using the same upload URL pattern that worked for 23-597-CA.pdf.

    Pattern confirmed working: taylorclerk.com/uploads/{year}/{case-slug}.pdf
    Try variations: -Certificate-of-Title, -CT, -Sale-Result, -Sold
    """
    log("=== AVENUE 1: Direct PDF URL pattern for Certificate of Title ===")
    found = []

    for year in ["2025", "2026"]:
        for case in CASES:
            slug = case["slug"]
            variants = [
                f"/{year}/{slug}.pdf",
                f"/{year}/{slug}-Certificate-of-Title.pdf",
                f"/{year}/{slug}-CT.pdf",
                f"/{year}/{slug}-Sale-Results.pdf",
                f"/{year}/{slug}-Sold.pdf",
                f"/{year}/{slug}-Notice-of-Sale.pdf",
                f"/{year}/{slug}-Surplus.pdf",
                f"/{year}/{slug.lower()}.pdf",
                f"/{year}/{slug.upper()}.pdf",
            ]
            for variant in variants:
                url = f"{TAYLOR_CLERK_BASE}/uploads{variant}"
                try:
                    r = client.head(url, timeout=10)
                    if r.status_code == 200:
                        ct = r.headers.get("content-type", "")
                        log(f"  FOUND: {url} ({r.status_code}) ct={ct}")
                        found.append({"url": url, "case": case["case_number"], "year": year})
                        # Try GET to extract sale amount from PDF content
                        rg = client.get(url, timeout=20)
                        if rg.status_code == 200 and len(rg.content) > 1000:
                            # Look for dollar amounts in binary content
                            text = rg.content.decode("latin-1", errors="replace")
                            amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
                            log(f"    PDF dollar amounts found: {amounts[:10]}")
                    elif r.status_code == 404:
                        pass  # Expected for non-existent files
                    else:
                        log(f"  {url}: HTTP {r.status_code}")
                    time.sleep(0.2)
                except Exception as e:
                    log(f"  {url}: {type(e).__name__}: {str(e)[:80]}", "WARN")
                    time.sleep(0.5)

    log(f"Avenue 1 result: {len(found)} accessible PDFs found")
    return found


def probe_myflcourtaccess():
    """
    Try the Florida Courts E-Filing portal for Taylor County case documents.
    Public access is available at myflcourtaccess.com/portal/
    """
    log("=== AVENUE 2: Florida Courts E-Filing Portal (myflcourtaccess.com) ===")

    base_url = "https://myflcourtaccess.com/portal/"
    found = []

    # Try county code for Taylor County (FL circuit court county code)
    # Taylor County is in the 3rd Judicial Circuit (Suwannee, Columbia, Hamilton, Lafayette, Madison, Taylor, Dixie)
    # County code for Taylor in FL eCourt may be 'TAY' or numeric

    # Try case search endpoints
    search_urls = [
        f"{base_url}",
        "https://myflcourtaccess.com/portal/Home/WorkspaceUrl?wa=wsignin1.0",
        "https://myflcourtaccess.com/portal/PublicAccess/",
    ]

    for url in search_urls:
        try:
            r = client.get(url, timeout=15)
            log(f"  {url}: HTTP {r.status_code}")
            if r.status_code == 200:
                if "Taylor" in r.text or "login" in r.text.lower():
                    log(f"    Content snippet: {r.text[:200]}")
        except Exception as e:
            log(f"  {url}: {type(e).__name__}: {str(e)[:80]}", "WARN")
        time.sleep(0.5)

    # Try the Tyler Technologies / Odyssey case portal used by many FL counties
    odyssey_urls = [
        "https://public.courts.in.gov/",  # Indiana reference implementation
        "https://ccpa.flcourts.org/",
        "https://www.flclerks.com/",
    ]
    for url in odyssey_urls:
        try:
            r = client.get(url, timeout=10)
            log(f"  {url}: HTTP {r.status_code}")
        except Exception as e:
            log(f"  {url}: {type(e).__name__}: {str(e)[:40]}", "WARN")
        time.sleep(0.3)

    return found


def probe_taylor_clerk_pages():
    """
    Check additional pages on taylorclerk.com not tried in prior sessions.
    """
    log("=== AVENUE 3: Additional taylorclerk.com pages ===")
    found = []

    pages = [
        "/departments/clerk-of-courts/",
        "/departments/official-records/",
        "/departments/court-records/",
        "/departments/surplus-funds/",
        "/departments/civil-records/",
        "/departments/foreclosures/",
        "/wp-json/wp/v2/posts",  # WordPress REST API
        "/sitemap.xml",
        "/sitemap_index.xml",
    ]

    for page in pages:
        url = f"{TAYLOR_CLERK_BASE}{page}"
        try:
            r = client.get(url, timeout=15)
            log(f"  {url}: HTTP {r.status_code} ({len(r.text)} chars)")
            if r.status_code == 200:
                # Look for any sale amount patterns
                amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', r.text)
                if amounts:
                    log(f"    Dollar amounts: {amounts[:5]}")
                # Look for certificate of title mentions
                if "certificate of title" in r.text.lower() or "winning bid" in r.text.lower():
                    log(f"    CT/winning bid content found!")
                    log(f"    Snippet: {r.text[:500]}")
                    found.append({"url": url, "content": r.text[:2000]})
        except Exception as e:
            log(f"  {url}: {type(e).__name__}: {str(e)[:80]}", "WARN")
        time.sleep(0.5)

    return found


def probe_fl_dept_of_state():
    """
    Check Florida Department of State CORPS records for Taylor County 
    auction results — sometimes property sales show up in lien/assignment records.
    Also check Sunbiz property-related records.
    """
    log("=== AVENUE 4: FL Dept of State / alternative state portals ===")

    urls = [
        "https://search.sunbiz.org/",
        "https://www.myflorida.com/tax_deed_auctions/",
        "https://dos.fl.gov/sunbiz/",
    ]

    for url in urls:
        try:
            r = client.get(url, timeout=10)
            log(f"  {url}: HTTP {r.status_code}")
        except Exception as e:
            log(f"  {url}: {type(e).__name__}: {str(e)[:50]}", "WARN")
        time.sleep(0.3)


def probe_ncfrpc_taylor_records():
    """
    The North Central Florida Regional Planning Council (NCFRPC) sometimes
    publishes property records or assessment data for member counties including Taylor.
    """
    log("=== AVENUE 5: NCFRPC and other regional portals ===")

    urls = [
        "https://ncfrpc.org/",
        "https://ncfrpc.org/MapsAndPlans/Counties/Taylor/",
        "https://flpatools.com/taylor/",
        "https://www.taylorfl.gov/",
    ]

    for url in urls:
        try:
            r = client.get(url, timeout=15)
            log(f"  {url}: HTTP {r.status_code} ({len(r.text)} chars)")
            if r.status_code == 200 and len(r.text) > 100:
                log(f"    Title: {r.text[:200]}")
        except Exception as e:
            log(f"  {url}: {type(e).__name__}: {str(e)[:60]}", "WARN")
        time.sleep(0.5)


def main():
    log("=" * 70)
    log("taylor_bf_fresh_avenue.py — Taylor County B/F probe, run 6354")
    log("=" * 70)

    results = {}

    # Avenue 1: Direct PDF URLs
    results["pdf_direct"] = probe_direct_pdf_urls()

    # Avenue 2: FL Courts E-Filing
    results["myflcourtaccess"] = probe_myflcourtaccess()

    # Avenue 3: Additional clerk pages
    results["clerk_pages"] = probe_taylor_clerk_pages()

    # Avenue 4: FL Dept of State
    probe_fl_dept_of_state()

    # Avenue 5: NCFRPC and regional
    probe_ncfrpc_taylor_records()

    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    for avenue, found in results.items():
        log(f"  {avenue}: {len(found)} useful hits")

    total_hits = sum(len(v) for v in results.values())
    if total_hits > 0:
        log(f"RESULT: {total_hits} new avenues found — see above for details")
        log("NEXT: Extract sale amounts and write foreclosure_outcomes / tax_deed_outcomes rows")
    else:
        log("RESULT: No new accessible sources found — B/F remain structurally blocked")
        log("RECOMMENDATION: Require Firecrawl credit top-up ($10 spend approval) for")
        log("  pubrecords.taylorclerk.com Cloudflare bypass via JS-render + waitFor")

    return total_hits


if __name__ == "__main__":
    main()
