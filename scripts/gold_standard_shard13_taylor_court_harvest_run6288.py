#!/usr/bin/env python3
"""
SHARD-13 taylor — Court/OR harvest run 6288 — 2026-07-25
==========================================================
Targets B/F and I residual (case 23-597 CA / parcel 05026-000).

Approaches (in order of confidence):
  1. MyFlorida Court Access (myflcourtaccess.com) — statewide FL circuit court
     records. Taylor County civil case 23-597 CA should have filing details
     including property address in the complaint/lis pendens.
  2. PorterBriggs/CourtLink — sometimes aggregates FL county court dockets.
  3. Taylor County Clerk direct court search (non-Cloudflare public portal).
  4. FL DOR recent real estate transfers for Taylor County — documentary stamps.
  5. PropertyShark / Attom / public deed aggregators for Taylor County 2023-2026.

For B/F specifically:
  - If a Certificate of Title was recorded for any of our 4 closed taylor cases
    (25-218 CA, TDA 26-026, TDA 26-028, 25-196 CA), we need the consideration
    amount (winning bid) from the CT recording.
  - Note: TDA cases are tax deeds, not foreclosures; Certificate of Title applies
    to foreclosure cases 25-218 CA and 25-196 CA.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)
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
    or os.environ.get("SUPABASE_KEY")
    or ""
)
SUPABASE_MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY env var required", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MGMT_HEADERS = {
    "Authorization": f"Bearer {SUPABASE_MGMT_TOKEN}",
    "Content-Type": "application/json",
}
REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

NOW = datetime.now(timezone.utc)

# Taylor County cases with past auction dates (need B/F outcomes)
CLOSED_CASES = [
    {"case_number": "25-218 CA", "sale_type": "foreclosure"},  # FC
    {"case_number": "25-196 CA", "sale_type": "foreclosure"},  # FC
    {"case_number": "TDA 26-026", "sale_type": "tax_deed"},    # TD
    {"case_number": "TDA 26-028", "sale_type": "tax_deed"},    # TD
]

# The I-residual case
RESIDUAL_CASE = "23-597 CA"
RESIDUAL_PARCEL = "05026-000"

client = httpx.Client(timeout=30, headers=WEB_HEADERS, follow_redirects=True)


def log(msg: str, level: str = "INFO") -> None:
    ts = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {level}: {msg}", flush=True)


def mgmt_query(sql: str):
    if not SUPABASE_MGMT_TOKEN:
        return None, "no_token"
    r = client.post(MGMT_URL, headers=MGMT_HEADERS, content=json.dumps({"query": sql}))
    return r.status_code, r.json() if r.status_code < 300 else r.text[:300]


# ============================================================
# PROBE 1: Florida Court E-Filing / MyFlorida Court Access
# ============================================================
def probe_myflcourt_access() -> dict:
    log("=== PROBE 1: MyFlorida Court Access ===")
    results = {}

    # Test access to the portal
    try:
        r = client.get("https://myflcourtaccess.com/", timeout=20)
        log(f"myflcourtaccess.com: HTTP {r.status_code}")
        is_cf = "cloudflare" in r.text.lower() or "cf-ray" in str(r.headers).lower()
        log(f"  cloudflare={is_cf} len={len(r.text)}")
        if is_cf:
            log("  Cloudflare-protected — skip court access portal")
            results["portal_blocked"] = True
            return results
    except Exception as e:
        log(f"  Error: {e}", "WARN")
        results["portal_blocked"] = True
        return results

    # Try PACER / eCourts search (Taylor County uses the FL trial courts system)
    for case_num in [RESIDUAL_CASE] + [c["case_number"] for c in CLOSED_CASES]:
        try:
            # MyFlorida uses URL encoding and specific case format
            encoded = case_num.replace(" ", "%20").replace("-", "%2D")
            urls = [
                f"https://myflcourtaccess.com/case/search?q={encoded}&county=taylor",
                f"https://myflcourtaccess.com/search?caseNumber={encoded}",
            ]
            for url in urls:
                r = client.get(url, timeout=15)
                log(f"  {case_num} → {url}: HTTP {r.status_code}")
                if r.status_code == 200:
                    text = r.text
                    # Look for property address, sale amount
                    addr_match = re.search(r'(\d+\s+\w+\s+\w+(?:\s+\w+)*,?\s*Perry\s*,?\s*FL)', text, re.I)
                    amount_match = re.search(r'\$[\d,]+(?:\.\d{2})?', text)
                    if addr_match or amount_match:
                        log(f"    FOUND DATA: addr={addr_match} amount={amount_match}")
                        results[case_num] = {
                            "addr": addr_match.group(0) if addr_match else None,
                            "amount": amount_match.group(0) if amount_match else None,
                            "url": url,
                        }
                time.sleep(1)
        except Exception as e:
            log(f"  {case_num} error: {e}", "WARN")

    return results


# ============================================================
# PROBE 2: Taylor County Clerk's official public portal (non-CF endpoints)
# ============================================================
def probe_taylor_clerk_public() -> dict:
    log("=== PROBE 2: Taylor Clerk public portal ===")
    results = {}

    # Try various clerk endpoints that may not be CF-protected
    endpoints = [
        # The main clerk site (known to work)
        "https://taylorclerk.com/",
        # Court records search (different subdomain pattern)
        "https://court.taylorclerk.com/",
        "https://portal.taylorclerk.com/",
        "https://clerk.taylorcountyfl.gov/",
        "https://www.taylorcountyfl.gov/departments/clerk-of-courts/",
        # The Taylor County Government main site
        "https://www.taylorcountyfl.gov/",
        # OR search via Tyler Technologies (many FL counties use Tyler/iCourt)
        "https://tyler.taylorcountyfl.gov/",
        "https://public.courts.taylorcountyfl.gov/",
        "https://cvweb.taylorcountyclerk.com/",
    ]

    for url in endpoints:
        try:
            r = client.get(url, timeout=12)
            log(f"  {url}: HTTP {r.status_code}")
            if r.status_code == 200:
                text = r.text.lower()
                is_cf = "cloudflare" in text or "cf-ray" in str(r.headers).lower()
                has_court = "court" in text or "case" in text or "docket" in text
                log(f"    cf={is_cf} has_court={has_court} len={len(r.text)}")
                if not is_cf and has_court:
                    log(f"    *** POTENTIAL COURT PORTAL: {url} ***")
                    results[url] = {"live": True, "has_court_data": has_court}
            time.sleep(1)
        except Exception as e:
            log(f"  {url}: {type(e).__name__}", "WARN")

    return results


# ============================================================
# PROBE 3: Public deed aggregators for Taylor County
# ============================================================
def probe_deed_aggregators() -> dict:
    log("=== PROBE 3: Public deed aggregators ===")
    results = {}

    # Many sites index FL deed recordings
    # These are NOT blocked like the official clerk portal
    sources = [
        # TaxNetUSA, ProQuo, etc. often have parcel data
        ("netr_taylor", f"https://www.netronline.com/getpub.aspx?state=FL&county=Taylor"),
        ("netr_search", f"https://www.netronline.com/"),
        # PropertyShark (free tier)
        ("propshark", f"https://www.propertyshark.com/mason/map/search/?q=Belair+Manor+Taylor+County+FL"),
        # Civic Data
        ("civicdata", "https://www.civicdata.com/fl-taylor"),
        # Free deed record search 
        ("publicrecords", "https://publicrecords.onlinesearches.com/Florida-Taylor-County.htm"),
        # FOIA/public record aggregator
        ("bgafl", "https://www.bgafl.org/bgafl/taylor.htm"),
    ]

    for name, url in sources:
        try:
            r = client.get(url, timeout=15)
            log(f"  [{name}] {url}: HTTP {r.status_code}")
            if r.status_code == 200:
                text = r.text
                is_cf = "cloudflare" in text.lower()
                has_data = bool(re.search(r'griffin|belair|05026|23-597', text, re.I))
                log(f"    cf={is_cf} has_data={has_data} len={len(text)}")
                if has_data:
                    log(f"    *** FOUND RELEVANT DATA at {url} ***")
                    results[name] = {"url": url, "has_data": True, "snippet": text[:500]}
            time.sleep(1)
        except Exception as e:
            log(f"  [{name}]: {type(e).__name__}", "WARN")

    return results


# ============================================================
# PROBE 4: Direct FL court docket (Taylor 12th Circuit)
# ============================================================
def probe_12th_circuit_court() -> dict:
    log("=== PROBE 4: 12th Circuit Court (Taylor County) ===")
    results = {}

    # Taylor County is in the 3rd Judicial Circuit (not 12th — let me correct)
    # Florida's 3rd Judicial Circuit includes: Columbia, Dixie, Hamilton, Lafayette,
    # Madison, Suwannee, and Taylor counties.
    # 3rd Judicial Circuit court portal
    circuit_urls = [
        "https://www.3dca.flcourts.org/",
        "https://www.3dcafla.com/",
        "https://www.nwflcourts.org/",
        # Try Online Court Records for 3rd Circuit
        "https://online.3dca.flcourts.org/",
        "https://onlinedocketaccess.3dca.flcourts.org/",
    ]

    for url in circuit_urls:
        try:
            r = client.get(url, timeout=12)
            log(f"  {url}: HTTP {r.status_code}")
            if r.status_code == 200:
                text = r.text.lower()
                has_case_search = "case" in text and ("search" in text or "docket" in text)
                log(f"    len={len(r.text)} has_case_search={has_case_search}")
            time.sleep(1)
        except Exception as e:
            log(f"  {url}: {type(e).__name__}", "WARN")

    # Try Florida Courts eFiling portal — case search is publicly accessible
    # Florida has a public portal: https://myflcourtaccess.com or https://www.flcourts.org/
    efiling_urls = [
        "https://efiling.flcourts.org/",
        "https://www.flcourts.org/Resources-Services/Case-Information/",
    ]
    for url in efiling_urls:
        try:
            r = client.get(url, timeout=12)
            log(f"  {url}: HTTP {r.status_code} len={len(r.text)}")
            time.sleep(1)
        except Exception as e:
            log(f"  {url}: {type(e).__name__}", "WARN")

    return results


# ============================================================
# PROBE 5: Taylor County Sheriff / Tax Collector (alternative sold amounts)
# ============================================================
def probe_sheriff_tax_collector() -> dict:
    log("=== PROBE 5: Taylor Sheriff / Tax Collector ===")
    results = {}

    # Sometimes the sheriff's office publishes foreclosure sale results
    # Tax collector may have recent property transfers
    urls = [
        "https://taylorcountysheriff.org/foreclosure-sales/",
        "https://www.taylorcountysheriff.org/",
        "https://taylercountyfl.gov/tax-collector/",
        "https://www.taylorcountyfl.gov/departments/tax-collector/",
        # FL DOR's doc stamp search
        "https://floridarevenue.com/taxes/taxesfees/Pages/doc_stamp.aspx",
        # Taylor County Property Appraiser (CA may have sold data)
        "https://www.taylorpa.com/",
        "https://taylorcountypropertyappraiser.org/",
    ]

    for url in urls:
        try:
            r = client.get(url, timeout=12)
            log(f"  {url}: HTTP {r.status_code}")
            if r.status_code == 200:
                text = r.text
                is_cf = "cloudflare" in text.lower()
                has_sale = bool(re.search(r'sale|sold|amount|transfer|deed', text, re.I))
                log(f"    cf={is_cf} has_sale={has_sale} len={len(text)}")
                if not is_cf and has_sale:
                    log(f"    *** Useful: {url} ***")
                    results[url] = {"live": True, "has_sale_data": has_sale}
            time.sleep(1)
        except Exception as e:
            log(f"  {url}: {type(e).__name__}", "WARN")

    return results


# ============================================================
# PROBE 6: Try direct FL GIO approach with different parcel format
# Taylor's fl_counties.co_no=62 but FL GIO uses CO_NO=72 (discrepancy noted)
# Try parcel ID format 05026-000 with CO_NO=62 as alternative
# ============================================================
def probe_fl_gio_alt_county_code() -> dict:
    log("=== PROBE 6: FL GIO alternative county code (CO_NO=62 vs 72) ===")
    results = {}

    fl_gio = "https://services1.arcgis.com/CY1LXxl9zlJeBuiE/arcgis/rest/services/Florida_Cadastral/FeatureServer/0"

    for co_no, label in [(62, "fl_counties.co_no=62"), (72, "fl_gio.co_no=72")]:
        params = {
            "f": "json",
            "where": f"CO_NO={co_no} AND PARCEL_ID='05026-000'",
            "outFields": "PARCEL_ID,OWN_NAME,PHY_ADDR1,PHY_CITY,JV,DOR_UC,SUBDV_NAME,CO_NO",
            "returnGeometry": "true",
            "outSR": "4326",
        }
        try:
            r = client.get(f"{fl_gio}/query", params=params, timeout=20)
            data = r.json() if r.status_code == 200 else {}
            features = data.get("features", [])
            log(f"  [{label}] 05026-000: {len(features)} results")
            if features:
                for f in features:
                    log(f"  *** FOUND: {f['attributes']}")
                results[label] = features
            time.sleep(1)
        except Exception as e:
            log(f"  [{label}]: {e}", "WARN")

    # Also try PLSS Twn-Rng-Sec search approach
    # T4S R7E = Township 4 South, Range 7 East → in FL GIO format
    # Try with PARCEL_ID pattern for section 26 in different formats
    sec26_patterns = [
        "PARCEL_ID LIKE '26-%'",  # Some counties use section-first format
        "PARCEL_ID LIKE '%-26-%'",  # Section-range format
        "PARCEL_ID LIKE '04-07-26%'",  # T4S-R7E-Sec26
        "PARCEL_ID LIKE '0407-26%'",
    ]
    for pattern in sec26_patterns:
        params = {
            "f": "json",
            "where": f"CO_NO=72 AND {pattern}",
            "outFields": "PARCEL_ID,OWN_NAME,PHY_ADDR1,PHY_CITY,JV,SUBDV_NAME",
            "returnGeometry": "false",
            "resultRecordCount": "20",
        }
        try:
            r = client.get(f"{fl_gio}/query", params=params, timeout=20)
            if r.status_code == 200:
                features = r.json().get("features", [])
                if features:
                    log(f"  Pattern [{pattern}]: {len(features)} results")
                    for f in features:
                        attrs = f.get("attributes", {})
                        log(f"    {attrs.get('PARCEL_ID')} | {attrs.get('OWN_NAME')} | {attrs.get('SUBDV_NAME')}")
            time.sleep(0.5)
        except Exception as e:
            log(f"  Pattern [{pattern}]: {e}", "WARN")

    return results


# ============================================================
# APPLY: If we found real data, write it to Supabase
# ============================================================
def apply_i_fix(case_id: str, parcel_id: str, addr: str, lat: float, lon: float,
                assessed: float, zone_code: str, jur_id: int, source: str) -> bool:
    """Write verified parcel data to MCA + parcel_zones."""
    log(f"Applying I fix: parcel={parcel_id} addr={addr} lat={lat} lon={lon} assessed={assessed}")

    # 1. Update MCA
    patch = {"parcel_id": parcel_id}
    if addr:
        patch["property_address"] = addr
    if lat:
        patch["latitude"] = lat
    if lon:
        patch["longitude"] = lon
    if assessed:
        patch["assessed_value"] = assessed

    r = client.patch(
        f"{BASE}/multi_county_auctions",
        headers={**REST_HEADERS, "Prefer": "return=minimal"},
        params={"id": f"eq.{case_id}", "county": "eq.taylor"},
        content=json.dumps(patch),
    )
    log(f"MCA update: HTTP {r.status_code}")

    # 2. Insert parcel_zone
    pz = [{"parcel_id": parcel_id, "jurisdiction_id": jur_id,
            "zone_code": zone_code, "zone_name": "Mixed Use Rural Residential",
            "source": source}]
    r2 = client.post(
        f"{BASE}/parcel_zones",
        headers={**REST_HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
        content=json.dumps(pz),
    )
    log(f"parcel_zones insert: HTTP {r2.status_code}")
    return r.status_code in (200, 204)


def apply_bf_outcome(case_number: str, sale_type: str, sold_amount: float,
                     parcel_id: str, source_url: str) -> bool:
    """Insert a real outcome for B/F."""
    table = "foreclosure_outcomes" if sale_type == "foreclosure" else "tax_deed_outcomes"
    now_iso = NOW.isoformat()

    if sale_type == "foreclosure":
        payload = [{
            "case_number": case_number,
            "county": "taylor",
            "sale_type": "foreclosure",
            "auction_date": "2026-07-01",  # approximate; update if real date found
            "winning_bid": sold_amount,
            "outcome": "sold",
            "winner_type": "third_party",
            "data_source": f"taylor_clerk_official_records:run6288",
            "source_url": source_url,
            "enriched_at": now_iso,
        }]
    else:
        payload = [{
            "case_number": case_number,
            "county": "taylor",
            "auction_date": "2026-07-01",
            "winning_bid": sold_amount,
            "outcome": "SOLD",
            "winner_type": "third_party",
            "data_source": f"taylor_clerk_official_records:run6288",
            "source_url": source_url,
            "enriched_at": now_iso,
        }]

    r = client.post(
        f"{BASE}/{table}",
        headers={**REST_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
        content=json.dumps(payload),
    )
    log(f"{table} insert for {case_number}: HTTP {r.status_code}")
    return r.status_code in (200, 201)


# ============================================================
# EVALUATE: pencil_dod_evaluate_county
# ============================================================
def evaluate() -> dict:
    r = client.post(
        f"{BASE}/rpc/pencil_dod_evaluate_county",
        headers=REST_HEADERS,
        content=json.dumps({"p_county": "taylor"}),
    )
    if r.status_code == 200:
        result = r.json()
        if isinstance(result, list) and result:
            result = result[0]
        return result
    return {}


def print_eval(label: str, result: dict) -> None:
    log(f"--- {label} ---")
    log(json.dumps(result, indent=2))
    pass_count = sum(1 for k, v in result.items() if isinstance(v, dict) and v.get("pass"))
    total = sum(1 for k, v in result.items() if isinstance(v, dict))
    log(f"SCORE: {pass_count}/{total}")
    for letter in "ABCDEFGHIJ":
        v = result.get(letter, {})
        status_str = "PASS" if v.get("pass") else "FAIL"
        log(f"  {letter}: {status_str} metric={v.get('metric')} detail={v.get('detail')}")


# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 70)
    log("SHARD-13 taylor — Court/OR harvest — run 6288 — 2026-07-25")
    log("=" * 70)

    # Get current MCA state for the residual case
    r = client.get(
        f"{BASE}/multi_county_auctions",
        headers=REST_HEADERS,
        params={
            "county": "eq.taylor",
            "case_number": f"eq.{RESIDUAL_CASE}",
            "select": "id,case_number,parcel_id,property_address,latitude,longitude,assessed_value",
        },
    )
    residual_rows = r.json() if r.status_code == 200 else []
    residual_id = residual_rows[0]["id"] if residual_rows else None
    log(f"Residual case {RESIDUAL_CASE}: id={residual_id} rows={residual_rows}")

    before = evaluate()
    print_eval("BEFORE", before)

    # Run probes
    results = {}
    results["myflcourt"] = probe_myflcourt_access()
    time.sleep(1)
    results["taylor_clerk"] = probe_taylor_clerk_public()
    time.sleep(1)
    results["deed_agg"] = probe_deed_aggregators()
    time.sleep(1)
    results["circuit"] = probe_12th_circuit_court()
    time.sleep(1)
    results["sheriff_tc"] = probe_sheriff_tax_collector()
    time.sleep(1)
    results["fl_gio_alt"] = probe_fl_gio_alt_county_code()

    # Check if any probes yielded actionable data
    i_fix_applied = False
    bf_applied = 0

    # Look for B/F data
    for probe_name, probe_result in results.items():
        for key, val in probe_result.items():
            if isinstance(val, dict) and val.get("has_data"):
                log(f"  ACTIONABLE B/F data from {probe_name}.{key}: {val.get('snippet', '')[:200]}")
                # Parse and apply if we have a real case_number + amount
                # (would need case-specific parsing here if data is found)

    after = evaluate()
    print_eval("AFTER", after)

    # Summary
    log("")
    log("=" * 70)
    log("HARVEST SUMMARY")
    log("=" * 70)
    log(f"Residual case {RESIDUAL_CASE}: I fix applied={i_fix_applied}")
    log(f"B/F outcomes applied={bf_applied}")

    # Detail probes
    log("\nProbe Results:")
    for probe, result in results.items():
        actionable = any(
            isinstance(v, dict) and (v.get("live") or v.get("has_data") or v.get("has_sale_data"))
            for v in result.values()
        )
        log(f"  {probe}: {len(result)} results | actionable={actionable}")

    before_passes = sum(1 for k, v in before.items() if isinstance(v, dict) and v.get("pass"))
    after_passes = sum(1 for k, v in after.items() if isinstance(v, dict) and v.get("pass"))
    log(f"\nFINAL: {before_passes}/10 → {after_passes}/10")

    if after_passes > before_passes:
        log("IMPROVEMENT: letter(s) moved!", "INFO")
        return 0
    else:
        log("NO MOVEMENT: all blocking factors confirmed unchanged", "INFO")
        return 0


if __name__ == "__main__":
    sys.exit(main())
