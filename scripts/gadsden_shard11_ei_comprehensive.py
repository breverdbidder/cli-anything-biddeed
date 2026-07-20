#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-11: gadsden E+I comprehensive fix
dispatch_id: 52bf028c-78fe-49ad-ae77-284c02a1f201

Target: gadsden E=91.3% (21/23 parcel_linked), I=56.5% (13/23 card_complete)
Need: E >= 95% (>=22/23), I >= 95% (>=22/23)

CONTEXT (4+ prior sessions of exhaustive research):
E: 2 unlinked parcels:
  - 25000942CA "Woods" - manufactured home "2021 Live Oak", sold 2026-07-02
    * No WOODS owner in fl_parcels co_no=30 with "LIVE OAK" in any address field
    * DOR_UC=002 (mobile home) narrows to 2 WOODS candidates but neither on Live Oak St
    * CT recorded via CourtScribe - buyer "HOUSING FOR THE GLORY OF GOD", $137,720
    * CaseDataID=726421 confirmed working in prior session
  - 25000901CA "Ramon's Construction" - PLSS only "Section 26, Township 2 North"
    * 2 adjacent RAMONS CONSTRUCTION SERVICES L parcels on Ridgewood Rd (same entity)
    * Same PLSS section, same sale yr/price, no distinguisher
    * CaseDataID unknown - need to search for it

I: 10 incomplete cards (parcel_id IS NOT NULL but no zone_code in parcel_zones)
   - 8 municipal parcels (Quincy ~7, Chattahoochee 4) - zoning_districts catalog exists
     but no per-parcel parcel_zones assignment
   - 2 unlinked parcels (same E gap)
   
   BLOCKED PATH (exhausted):
   - qpublic.schneidercorp.com -> Cloudflare 403
   - gadsdenpa.com -> Cloudflare 403
   - gadsdencountyfl.gov -> Cloudflare WAF 403
   - ARPC ArcGIS org has Gadsden_FLUM (comp-plan, not zoning) + Havana_Zoning_Districts
     but parcel IDs don't match our auction rows (2022 snapshot)
   
   NEW ANGLES TO TRY:
   - ArcGIS Online search for "Quincy FL" or "Chattahoochee FL" zoning services
   - FL GIO for Gadsden parcels (co_no=30) to get per-parcel municipality + zone info
   - myfloridacounty.com Gadsden (county code 20)
   - Quincy City Hall GIS portal

HONESTY PROTOCOL:
- BLANK > WRONG: no parcel_id or zone_code written without confirmed source
- VERIFIED tag: proof attached (query result, URL response)
- INFERRED: guessing from context - not acceptable for parcel_id/zone_code

WIRING: This script is meant to be run in a GitHub Actions context with:
  - SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ACCESS_TOKEN env vars
  - Full network access (no sandbox restrictions)
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
UA_CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

DISPATCH_ID = "52bf028c-78fe-49ad-ae77-284c02a1f201"
COUNTY = "gadsden"


def ts():
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(path, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            log(f"  sb_get retry {attempt+1}/{retries}: {e}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                raise


def sb_patch(table, filters, data):
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={**HEADERS, "Prefer": "return=representation"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_post(table, data, prefer="resolution=merge-duplicates,return=minimal"):
    if isinstance(data, dict):
        data = [data]
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}/{table}", data=body,
        headers={**HEADERS, "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def mgmt_sql(sql, retries=3):
    if not SUPABASE_ACCESS_TOKEN:
        log("WARN: SUPABASE_ACCESS_TOKEN not set")
        return None
    proj_ref = "mocerqjnksmhcjzxrewo"
    url = f"https://api.supabase.com/v1/projects/{proj_ref}/database/query"
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            log(f"  mgmt_sql HTTP {e.code}: {body_text[:300]}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                return {"error": f"HTTP {e.code}: {body_text[:200]}"}
        except Exception as e:
            log(f"  mgmt_sql error: {e}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                return {"error": str(e)}


def pencil_dod():
    body = json.dumps({"p_county": COUNTY}).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/pencil_dod_evaluate_county",
        data=body, headers=HEADERS, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"pencil_dod error: {e}")
        return None


def fetch(url, ua=UA_CHROME, timeout=20, retries=2, post_data=None):
    for attempt in range(retries):
        try:
            data_bytes = post_data.encode() if isinstance(post_data, str) else post_data
            req = urllib.request.Request(url, data=data_bytes, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                return 0, str(e)


def log_audit(county, letter, claim, survived, refuter_evidence=None):
    row = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": json.dumps(refuter_evidence or {}),
        "survived": survived,
    }
    status, body = sb_post("gold_standard_ultraloop_audit", row, prefer="return=minimal")
    if status not in (200, 201, 204):
        log(f"  audit log write failed: HTTP {status}: {body[:200]}")


# ============================================================
# STEP 1: Current DB state
# ============================================================
def step1_current_state():
    log("=== STEP 1: Current DB state ===")

    rows = sb_get("multi_county_auctions?county=eq.gadsden"
                  "&select=id,case_number,parcel_id,property_address,assessed_value,"
                  "latitude,longitude,auction_status,plaintiff,defendant_name")
    log(f"Total gadsden rows: {len(rows)}")

    unlinked = [r for r in rows if not r.get("parcel_id")]
    linked = [r for r in rows if r.get("parcel_id")]
    log(f"Linked (parcel_id IS NOT NULL): {len(linked)}")
    log(f"Unlinked (parcel_id IS NULL): {len(unlinked)}")
    for r in unlinked:
        log(f"  UNLINKED: {r['case_number']} | "
            f"defendant={r.get('defendant_name')!r} | "
            f"addr={r.get('property_address')!r} | "
            f"status={r.get('auction_status')}")

    result = pencil_dod()
    if result:
        log(f"BEFORE evaluation: {json.dumps(result)}")
    else:
        log("WARNING: pencil_dod failed, using estimated state")
        result = {}

    return rows, linked, unlinked, result


# ============================================================
# STEP 2: CourtScribe investigation for parcel IDs
# ============================================================
def step2_courtscribe_investigation(unlinked):
    log("=== STEP 2: CourtScribe investigation for parcel IDs ===")
    COURTSCRIBE = "https://www.gadsdenclerk.com/CourtScribePublicInquiry/CourtScribe"

    results = {}

    # Initialize a cookie jar session (CourtScribe might need session cookies)
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def courtscribe_fetch(url, data=None):
        try:
            data_bytes = data.encode() if isinstance(data, str) else data
            req = urllib.request.Request(url, data=data_bytes, headers={"User-Agent": UA_CHROME})
            with opener.open(req, timeout=20) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:
            return 0, str(e)

    # First, get the main page to establish session
    status, body = courtscribe_fetch(COURTSCRIBE.replace("/CourtScribe", ""))
    log(f"CourtScribe main page: HTTP {status}")

    # 25000942CA: CaseDataID=726421 (confirmed from prior session)
    log("\n--- 25000942CA (Woods, sold 2026-07-02): Fetching full docket CaseDataID=726421 ---")
    status, body = courtscribe_fetch(f"{COURTSCRIBE}/GetCaseDetailsPI?CaseDataID=726421")
    log(f"HTTP {status}, body length {len(body)}")
    if status == 200:
        # Full docket text - look for parcel ID patterns
        log(f"Full docket:\n{body[:5000]}")

        # Gadsden parcel IDs: N-NN-NS-NW-NNNN-NNNNN-NNNN pattern
        parcel_patterns = [
            r'\d-\d{2}-\d{1,2}[NS]-\d{1,2}[EW]-\d{4}-\d{5}-\d{4}',
            r'\b\d-\d{2}-\d{1,2}[NnSs]-\d{1,2}[EeWw]-\w{4}-\w{5,6}-\w{4}\b',
        ]
        for pat in parcel_patterns:
            found = re.findall(pat, body, re.IGNORECASE)
            if found:
                log(f"PARCEL IDs found with pattern {pat!r}: {found}")
                results["25000942CA"] = {"parcel_ids_found": found, "source": f"courtscribe_CaseDataID=726421"}

        # Look for folio numbers, property ID, etc.
        folio_patterns = [
            r'folio[:\s#]+([0-9A-Z\-]+)',
            r'parcel[:\s#]+([0-9A-Z\-]+)',
            r'property\s+id[:\s:]+([0-9A-Z\-]+)',
        ]
        for pat in folio_patterns:
            found = re.findall(pat, body, re.IGNORECASE)
            if found:
                log(f"Found with pattern {pat!r}: {found}")

        # Look for legal description section
        if "legal" in body.lower():
            idx = body.lower().index("legal")
            log(f"Legal description context: {body[max(0,idx-50):idx+500]}")

        results.setdefault("25000942CA", {}).update({"docket_fetched": True, "http_status": status})
    else:
        log(f"CourtScribe returned HTTP {status} for CaseDataID=726421")
        results["25000942CA"] = {"error": f"HTTP {status}", "docket_fetched": False}

    # 25000901CA: Need to find CaseDataID first
    log("\n--- 25000901CA (Ramon's Construction): Search for CaseDataID ---")

    # Try case number search
    search_params = urllib.parse.urlencode({
        "CaseNumber": "25000901CA",
        "County": "Gadsden",
    })
    status, body = courtscribe_fetch(f"{COURTSCRIBE}/SearchClerk?{search_params}")
    log(f"SearchClerk HTTP {status}, body length {len(body)}")
    if status == 200:
        log(f"Search response: {body[:3000]}")
        # Look for CaseDataID in the response
        case_ids = re.findall(r'CaseDataID=(\d+)', body)
        if case_ids:
            log(f"Found CaseDataIDs: {case_ids}")
            # Try each one
            for cid in case_ids[:3]:
                log(f"  Fetching CaseDataID={cid}...")
                s2, b2 = courtscribe_fetch(f"{COURTSCRIBE}/GetCaseDetailsPI?CaseDataID={cid}")
                log(f"  HTTP {s2}, length {len(b2)}")
                if s2 == 200 and "25000901" in b2:
                    log(f"  CONFIRMED: CaseDataID={cid} is for 25000901CA")
                    log(f"  Full docket:\n{b2[:5000]}")
                    parcel_found = re.findall(r'\d-\d{2}-\d{1,2}[NS]-\d{1,2}[EW]-\d{4}-\d{5}-\d{4}', b2, re.IGNORECASE)
                    if parcel_found:
                        log(f"  PARCEL IDs: {parcel_found}")
                        results["25000901CA"] = {
                            "case_data_id": cid,
                            "parcel_ids_found": parcel_found,
                            "source": f"courtscribe_CaseDataID={cid}",
                        }

    # Try the older POST-based search form for CourtScribe (case search by party name)
    log("\n--- CourtScribe SearchClerk by defendant Ramon ---")
    search_params2 = urllib.parse.urlencode({
        "LastName": "Ramon",
        "County": "Gadsden",
    })
    status, body = courtscribe_fetch(f"{COURTSCRIBE}/SearchClerk?{search_params2}")
    log(f"Name search HTTP {status}, body length {len(body)}")
    if status == 200 and len(body) > 100:
        log(f"Name search response: {body[:2000]}")

    return results


# ============================================================
# STEP 3: FL GIO query for manufactured home with LIVE OAK
# ============================================================
def step3_fl_gio_live_oak(unlinked):
    log("=== STEP 3: FL GIO query for manufactured home 25000942CA ===")

    # Check if WOODS address match with "LIVE OAK" in any field
    # fl_parcels co_no=30 (Gadsden) with DOR_UC=002 (mobile/manufactured home)
    # Filter by own_name WOODS and check all address fields
    log("Querying fl_parcels co_no=30 for WOODS owners...")
    rows = sb_get("fl_parcels?co_no=eq.30&own_name=ilike.*WOODS*&select=parcel_id,own_name,phy_addr1,phy_city,phy_zipcd,own_addr1,dor_uc,jv,centroid_lat,centroid_lng")
    log(f"WOODS owners in co_no=30: {len(rows)}")
    for r in rows:
        log(f"  {r['parcel_id']} | {r['own_name']} | addr1={r.get('phy_addr1')} | city={r.get('phy_city')} | ownaddr={r.get('own_addr1')} | dor_uc={r.get('dor_uc')}")

    # Look for "LIVE OAK" anywhere in fl_parcels for co_no=30
    log("\nQuerying fl_parcels co_no=30 for 'LIVE OAK' in address...")
    rows_lo = sb_get("fl_parcels?co_no=eq.30&phy_addr1=ilike.*LIVE*OAK*&select=parcel_id,own_name,phy_addr1,phy_city,dor_uc,jv,centroid_lat,centroid_lng")
    log(f"LIVE OAK addresses in co_no=30: {len(rows_lo)}")
    for r in rows_lo:
        log(f"  {r['parcel_id']} | {r['own_name']} | {r.get('phy_addr1')} | {r.get('phy_city')} | dor_uc={r.get('dor_uc')}")

    # If any WOODS + LIVE OAK intersection exists
    woods_parcel_ids = {r['parcel_id'] for r in rows}
    lo_parcel_ids = {r['parcel_id'] for r in rows_lo}
    intersection = woods_parcel_ids & lo_parcel_ids
    if intersection:
        log(f"INTERSECTION (WOODS + LIVE OAK): {intersection}")
        return intersection

    # Check mailing address field (own_addr1) for LIVE OAK
    log("\nQuerying fl_parcels co_no=30 for 'LIVE OAK' in own_addr1...")
    rows_oa = sb_get("fl_parcels?co_no=eq.30&own_addr1=ilike.*LIVE*OAK*&own_name=ilike.*WOODS*&select=parcel_id,own_name,phy_addr1,phy_city,own_addr1,dor_uc,jv,centroid_lat,centroid_lng")
    if rows_oa:
        log(f"WOODS + LIVE OAK in own_addr1: {len(rows_oa)}")
        for r in rows_oa:
            log(f"  {r['parcel_id']} | {r['own_name']} | phy={r.get('phy_addr1')} | mail={r.get('own_addr1')} | dor_uc={r.get('dor_uc')}")

    # Try "2021" in phy_addr1 (the address in MCA is "2021 Live Oak Manufactured Home")
    log("\nQuerying fl_parcels co_no=30 for '2021' in phy_addr1 + WOODS owner...")
    rows_2021 = sb_get("fl_parcels?co_no=eq.30&phy_addr1=ilike.*2021*&own_name=ilike.*WOODS*&select=parcel_id,own_name,phy_addr1,phy_city,dor_uc,jv,centroid_lat,centroid_lng")
    if rows_2021:
        log(f"WOODS + 2021 in phy_addr1: {len(rows_2021)}")
        for r in rows_2021:
            log(f"  {r['parcel_id']} | {r['own_name']} | {r.get('phy_addr1')} | {r.get('phy_city')} | dor_uc={r.get('dor_uc')}")

    # If 25000942CA is a MANUFACTURED HOME PARK, the park itself is on a parcel
    # "Live Oak" might be the name of a manufactured home community
    log("\nQuerying fl_parcels co_no=30 for manufactured home parks ('LIVE OAK' name)...")
    rows_park = sb_get("fl_parcels?co_no=eq.30&own_name=ilike.*LIVE*OAK*&select=parcel_id,own_name,phy_addr1,phy_city,dor_uc,jv,centroid_lat,centroid_lng")
    if rows_park:
        log(f"'LIVE OAK' in own_name: {len(rows_park)}")
        for r in rows_park:
            log(f"  {r['parcel_id']} | {r['own_name']} | {r.get('phy_addr1')} | {r.get('phy_city')} | dor_uc={r.get('dor_uc')}")

    return None


# ============================================================
# STEP 4: Ramon's Construction disambiguation
# Both parcels: 3-26-2N-5W-0424-0000B-0500 and 3-26-2N-5W-0424-1000
# Try to find which one is the subject of the foreclosure
# ============================================================
def step4_ramons_construction_disambiguation():
    log("=== STEP 4: Ramon's Construction parcel disambiguation ===")

    # The two candidate parcels from prior session
    candidates = [
        "3-26-2N-5W-0424-0000B-0500",
        "3-26-2N-5W-0424-1000",
    ]

    # Verify both exist in fl_parcels
    for pid in candidates:
        rows = sb_get(f"fl_parcels?parcel_id=eq.{urllib.parse.quote(pid)}&co_no=eq.30&select=*")
        if rows:
            p = rows[0]
            log(f"Confirmed: {pid} | {p.get('own_name')} | {p.get('phy_addr1')} | {p.get('phy_city')} | "
                f"dor_uc={p.get('dor_uc')} | sale_yr1={p.get('sale_yr1')} | sale_prc1={p.get('sale_prc1')} | "
                f"jv={p.get('jv')} | tot_lnd_val={p.get('tot_lnd_val')} | acreage={p.get('acreage')} | "
                f"lat={p.get('centroid_lat')} | lng={p.get('centroid_lng')}")
        else:
            log(f"Not found in fl_parcels co_no=30: {pid}")
            # Try without co_no filter
            rows2 = sb_get(f"fl_parcels?parcel_id=eq.{urllib.parse.quote(pid)}&select=*")
            if rows2:
                log(f"  Found with different co_no: {rows2[0].get('co_no')}")

    # Check the judgment amount from the case - if different from both parcels' values,
    # the judgment amount might correlate with one parcel more than the other
    auc_row = sb_get("multi_county_auctions?case_number=eq.25000901CA&county=eq.gadsden&select=*")
    if auc_row:
        log(f"Case 25000901CA MCA row: {json.dumps(auc_row[0], indent=2)[:1000]}")

    # Try CourtScribe for 25000901CA - search by case number
    COURTSCRIBE = "https://www.gadsdenclerk.com/CourtScribePublicInquiry/CourtScribe"
    # Case number format in CourtScribe might be "2025-CA-000901" or "25000901CA"
    for case_fmt in ["25000901CA", "2025-CA-000901", "2025000901CA"]:
        search_url = f"{COURTSCRIBE}/SearchClerk?CaseNumber={urllib.parse.quote(case_fmt)}"
        status, body = fetch(search_url)
        log(f"CourtScribe search for '{case_fmt}': HTTP {status}")
        if status == 200 and len(body) > 200:
            log(f"  Response: {body[:2000]}")
            case_data_ids = re.findall(r'CaseDataID=(\d+)', body)
            if case_data_ids:
                log(f"  Found CaseDataIDs: {case_data_ids}")
                break

    return None


# ============================================================
# STEP 5: ArcGIS municipal zoning for 8 linked parcels
# ============================================================
def step5_municipal_zoning():
    log("=== STEP 5: ArcGIS municipal parcel zoning ===")

    # Get linked parcels that don't have parcel_zones entries
    log("Querying multi_county_auctions for gadsden linked parcels...")
    mca_rows = sb_get("multi_county_auctions?county=eq.gadsden&parcel_id=not.is.null"
                      "&select=id,case_number,parcel_id,property_address,latitude,longitude")
    log(f"Linked gadsden auction rows: {len(mca_rows)}")

    parcel_zones = sb_get("parcel_zones?county=eq.gadsden&select=parcel_id,zone_code,jurisdiction_id")
    pz_by_parcel = {r['parcel_id']: r for r in parcel_zones}
    log(f"Existing parcel_zones for gadsden: {len(parcel_zones)}")

    # Identify rows without zone_code
    no_zone = [r for r in mca_rows if r.get('parcel_id') and r['parcel_id'] not in pz_by_parcel]
    log(f"Linked rows WITHOUT parcel_zones: {len(no_zone)}")
    for r in no_zone:
        log(f"  {r['case_number']} | {r['parcel_id']} | {r.get('property_address')}")

    if not no_zone:
        log("All linked parcels have zone_code - I may already be passing!")
        return {}

    # Try ArcGIS Online for Quincy/Chattahoochee/Havana zoning
    agol_searches = [
        ("Quincy FL zoning owner:City_of_Quincy", "quincy_zoning"),
        ("Quincy Florida zoning parcel", "quincy_parcel_zoning"),
        ("Chattahoochee FL zoning", "chattahoochee_zoning"),
        ("Gadsden County Florida parcels zoning", "gadsden_parcel_zoning"),
    ]

    found_layers = {}
    for q, label in agol_searches:
        search_url = "https://www.arcgis.com/sharing/rest/search?" + urllib.parse.urlencode({
            "q": q,
            "f": "json",
            "num": 10,
            "sortField": "relevance",
        })
        status, body = fetch(search_url)
        log(f"ArcGIS Online search '{q}': HTTP {status}")
        if status == 200:
            try:
                data = json.loads(body)
                results = data.get("results", [])
                log(f"  Found {len(results)} results")
                for r in results[:5]:
                    url = r.get("url", "")
                    title = r.get("title", "")
                    owner = r.get("owner", "")
                    rtype = r.get("type", "")
                    log(f"    [{rtype}] {title} (owner={owner}) -> {url}")
                    if url and ("FeatureServer" in url or "MapServer" in url):
                        found_layers[label] = url
            except Exception as e:
                log(f"  Parse error: {e}")

    # Try the Apalachee RPC (ARPC) org more thoroughly
    log("\nProbing ARPC ArcGIS org services for Gadsden/Quincy zoning...")
    arpc_url = "https://services8.arcgis.com/N3lCn6dEKCL6LidU/arcgis/rest/services?f=json"
    status, body = fetch(arpc_url)
    log(f"ARPC services: HTTP {status}")
    if status == 200:
        try:
            data = json.loads(body)
            services = data.get("services", [])
            log(f"Total ARPC services: {len(services)}")
            for s in services:
                name = s.get("name", "")
                if any(kw in name.lower() for kw in ["quincy", "chattahoochee", "havana", "gadsden", "zoning", "parcel"]):
                    log(f"  MATCH: {name} | type={s.get('type')} | url={s.get('url')}")
                    found_layers[f"arpc_{name}"] = s.get("url", "")
        except Exception as e:
            log(f"  Parse error: {e}")

    # Try known Havana Zoning Districts (confirmed working in prior session)
    log("\nProbing Havana_Zoning_Districts_WFL1 for linked Havana parcels...")
    havana_fs = "https://services8.arcgis.com/N3lCn6dEKCL6LidU/arcgis/rest/services/Havana_Zoning_Districts_WFL1/FeatureServer"
    status, body = fetch(f"{havana_fs}?f=json")
    log(f"Havana FeatureServer: HTTP {status}")
    if status == 200:
        try:
            data = json.loads(body)
            layers = data.get("layers", [])
            log(f"Layers: {[{l.get('id'): l.get('name')} for l in layers]}")

            # Prior session found "Havana_Parcels" in layer 5 with PARCELID field
            # But parcel IDs didn't match - try a broader query to see what's there
            parcel_layer_url = f"{havana_fs}/5/query"
            for r in no_zone:
                pid = r.get("parcel_id", "")
                if pid and "havana" in (r.get("property_address") or "").lower():
                    query_url = parcel_layer_url + "?" + urllib.parse.urlencode({
                        "where": f"PARCELID='{pid}'",
                        "outFields": "*",
                        "f": "json",
                    })
                    s2, b2 = fetch(query_url)
                    log(f"  Havana parcel query for {pid}: HTTP {s2}")
                    if s2 == 200:
                        d2 = json.loads(b2)
                        feats = d2.get("features", [])
                        if feats:
                            log(f"  FOUND: {feats[0].get('attributes')}")

            # Try zone layer (layer 1: ZoningDistricts)
            zone_layer_url = f"{havana_fs}/1/query"
            # Get all zone features to understand the coverage
            q_all = zone_layer_url + "?" + urllib.parse.urlencode({
                "where": "1=1",
                "outFields": "ZONE_CODE,Category,OBJECTID",
                "resultRecordCount": 50,
                "f": "json",
            })
            s3, b3 = fetch(q_all)
            log(f"  Havana ZoningDistricts (all): HTTP {s3}")
            if s3 == 200:
                d3 = json.loads(b3)
                log(f"  Zone features: {[f.get('attributes') for f in d3.get('features', [])[:10]]}")
        except Exception as e:
            log(f"  Parse error: {e}")

    # Try spatial query: if we have lat/lon for the linked parcels, do point-in-polygon
    # against any found zoning layers
    log("\nTrying spatial point-in-polygon for linked parcels with coordinates...")
    for r in no_zone:
        lat = r.get("latitude")
        lng = r.get("longitude")
        if lat and lng and (lat != 30.5768 or lng != -84.5875):  # Skip county centroid proxies
            log(f"  {r['case_number']} lat={lat} lng={lng} addr={r.get('property_address')}")

            # Try against Havana layer
            spatial_url = ("https://services8.arcgis.com/N3lCn6dEKCL6LidU/arcgis/rest/services/"
                           "Havana_Zoning_Districts_WFL1/FeatureServer/1/query?"
                           + urllib.parse.urlencode({
                               "geometryType": "esriGeometryPoint",
                               "geometry": json.dumps({"x": lng, "y": lat, "spatialReference": {"wkid": 4326}}),
                               "spatialRel": "esriSpatialRelIntersects",
                               "outFields": "*",
                               "inSR": "4326",
                               "f": "json",
                           }))
            s4, b4 = fetch(spatial_url)
            log(f"    Havana spatial query: HTTP {s4}")
            if s4 == 200:
                d4 = json.loads(b4)
                feats = d4.get("features", [])
                if feats:
                    log(f"    FOUND ZONE: {feats[0].get('attributes')}")

    return found_layers


# ============================================================
# STEP 6: Try myfloridacounty.com for Gadsden official records
# ============================================================
def step6_myfloridacounty():
    log("=== STEP 6: myfloridacounty.com Gadsden ===")

    # Gadsden county code in FL ORI system
    for code in ["20", "gadsden", "30"]:
        url = f"https://www.myfloridacounty.com/orisearch/{code}"
        status, body = fetch(url, timeout=10)
        log(f"  {url}: HTTP {status}")
        if status == 200:
            log(f"    Response (first 300 chars): {body[:300]}")
        time.sleep(1)

    # Try the Gadsden County Clerk's official records page directly
    clerk_urls = [
        "https://www.gadsdenclerk.com/Official_Records/",
        "https://www.gadsdenclerk.com/OfficialRecords/",
        "https://secure.gadsdenclerk.com/",
        "https://gadsdenclerk.com/PublicRecords",
    ]
    for u in clerk_urls:
        status, body = fetch(u, timeout=10)
        log(f"  {u}: HTTP {status}")
        if status == 200:
            log(f"    Body snippet: {body[:200]}")


# ============================================================
# STEP 7: Write verified parcel_zones if found
# ============================================================
def step7_write_if_found(zone_findings, linked_rows):
    """
    Write parcel_zones rows if municipal zoning was found via ArcGIS.
    zone_findings: dict of {parcel_id: {zone_code, jurisdiction_id, source}}
    """
    if not zone_findings:
        log("No zone findings to write - I remains blocked")
        return 0

    log(f"=== STEP 7: Writing {len(zone_findings)} verified parcel_zones rows ===")
    written = 0
    for parcel_id, info in zone_findings.items():
        zone_code = info.get("zone_code")
        jurisdiction_id = info.get("jurisdiction_id")
        source = info.get("source", "arcgis_spatial_query")
        if not zone_code or not jurisdiction_id:
            log(f"  SKIP {parcel_id}: missing zone_code or jurisdiction_id")
            continue

        row = {
            "parcel_id": parcel_id,
            "county": COUNTY,
            "jurisdiction_id": jurisdiction_id,
            "zone_code": zone_code,
            "source": source,
        }
        status, body = sb_post("parcel_zones", row)
        if status in (200, 201, 204):
            log(f"  WROTE parcel_zones: {parcel_id} -> {zone_code} (jurisdiction={jurisdiction_id})")
            written += 1
        else:
            log(f"  FAIL writing parcel_zones for {parcel_id}: HTTP {status}: {body[:200]}")

    return written


# ============================================================
# STEP 8: Write parcel_id if found for unlinked cases
# ============================================================
def step8_write_parcel_id(case_number, parcel_id, source, mca_id, fl_parcel_row=None):
    """Write verified parcel_id to multi_county_auctions."""
    log(f"Writing parcel_id={parcel_id} for case {case_number} (source={source})...")

    payload = {
        "parcel_id": parcel_id,
    }
    if fl_parcel_row:
        if fl_parcel_row.get("phy_addr1") and fl_parcel_row.get("phy_city"):
            address = f"{fl_parcel_row['phy_addr1']}, {fl_parcel_row['phy_city']}, FL"
            if fl_parcel_row.get("phy_zipcd"):
                address += f" {fl_parcel_row['phy_zipcd']}"
            payload["property_address"] = address
        if fl_parcel_row.get("jv"):
            payload["assessed_value"] = fl_parcel_row["jv"]
            payload["assessed_value_source"] = "fl_parcels_jv"
        if fl_parcel_row.get("centroid_lat"):
            payload["latitude"] = fl_parcel_row["centroid_lat"]
        if fl_parcel_row.get("centroid_lng"):
            payload["longitude"] = fl_parcel_row["centroid_lng"]

    status, body = sb_patch("multi_county_auctions", f"id=eq.{mca_id}", payload)
    if status in (200, 204):
        log(f"  WRITE OK: {case_number} -> parcel_id={parcel_id}")

        # Verify
        check = sb_get(f"multi_county_auctions?id=eq.{mca_id}&select=parcel_id,property_address,assessed_value")
        if check and check[0].get("parcel_id") == parcel_id:
            log(f"  VERIFIED: {check[0]}")
            return True
        else:
            log(f"  FAIL-LOUD: post-write verify failed: {check}")
            return False
    else:
        log(f"  FAIL writing parcel_id for {case_number}: HTTP {status}: {body[:200]}")
        return False


# ============================================================
# FINAL EVALUATION
# ============================================================
def final_evaluation():
    log("=== FINAL: pencil_dod_evaluate_county('gadsden') ===")
    result = pencil_dod()
    if result:
        log(f"AFTER evaluation: {json.dumps(result)}")
        e_metric = result.get("E", {}).get("metric")
        i_metric = result.get("I", {}).get("metric")
        e_pass = result.get("E", {}).get("pass")
        i_pass = result.get("I", {}).get("pass")
        log(f"E: {e_metric}% (pass={e_pass}), I: {i_metric}% (pass={i_pass})")
    return result


# ============================================================
# MAIN
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    DRY_RUN = args.dry_run
    if DRY_RUN:
        log("DRY RUN mode - no writes will be performed")

    log(f"GADSDEN SHARD-11 E+I FIX | dispatch_id={DISPATCH_ID}")

    # Step 1: Current state
    rows, linked, unlinked, before_eval = step1_current_state()

    if not unlinked:
        log("All parcels already linked! Checking I...")
    else:
        log(f"\n{len(unlinked)} parcels to link:")
        for r in unlinked:
            log(f"  {r['case_number']}: {r.get('defendant_name')} / {r.get('property_address')}")

    # Step 2: CourtScribe investigation
    courtscribe_findings = step2_courtscribe_investigation(unlinked)
    log(f"\nCourtScribe findings: {json.dumps(courtscribe_findings, indent=2)}")

    # Step 3: FL GIO Live Oak search
    live_oak_result = step3_fl_gio_live_oak(unlinked)
    if live_oak_result:
        log(f"FL GIO Live Oak result: {live_oak_result}")

    # Step 4: Ramon's Construction disambiguation
    step4_ramons_construction_disambiguation()

    # Step 5: Municipal zoning for I
    zone_findings_raw = step5_municipal_zoning()
    log(f"\nZone findings: {json.dumps(zone_findings_raw, indent=2)}")

    # Step 6: myfloridacounty.com
    step6_myfloridacounty()

    # Evaluate what we found and write if appropriate
    zone_writes = {}
    parcel_writes = {}

    # Check if CourtScribe found unique parcel IDs
    for case_number, findings in courtscribe_findings.items():
        if findings.get("parcel_ids_found"):
            pids = findings["parcel_ids_found"]
            if len(pids) == 1:
                log(f"UNIQUE PARCEL ID found for {case_number}: {pids[0]} (source: CourtScribe)")
                mca_row = next((r for r in unlinked if r["case_number"] == case_number), None)
                if mca_row and not DRY_RUN:
                    # Verify against fl_parcels
                    pid = pids[0]
                    parcel_row = sb_get(f"fl_parcels?parcel_id=eq.{urllib.parse.quote(pid)}&co_no=eq.30&select=*")
                    if parcel_row:
                        log(f"  Confirmed in fl_parcels: {parcel_row[0]}")
                        success = step8_write_parcel_id(
                            case_number, pid,
                            f"courtscribe_docket_parcel_reference",
                            mca_row["id"],
                            parcel_row[0],
                        )
                        if success:
                            parcel_writes[case_number] = pid
                    else:
                        log(f"  WARN: {pid} not found in fl_parcels co_no=30 - cannot verify")
                        log_audit(COUNTY, "E", f"courtscribe parcel {pid} for {case_number}", False,
                                  {"reason": "parcel not found in fl_parcels co_no=30"})
            elif len(pids) > 1:
                log(f"MULTIPLE parcel IDs for {case_number}: {pids} - AMBIGUOUS, not writing")
                log_audit(COUNTY, "E", f"courtscribe multiple parcels for {case_number}", False,
                          {"reason": f"ambiguous: {pids}"})

    # Write zone_findings if any found via ArcGIS
    if zone_writes and not DRY_RUN:
        written_count = step7_write_if_found(zone_writes, linked)
        log(f"Wrote {written_count} parcel_zones rows")

    # Final evaluation
    after_eval = final_evaluation()

    # Log audit rows
    if after_eval:
        for letter in ["E", "I"]:
            letter_data = after_eval.get(letter, {})
            survived = letter_data.get("pass", False)
            metric = letter_data.get("metric")
            claim = f"gadsden {letter} metric={metric}"
            log_audit(COUNTY, letter, claim, survived, {
                "before": before_eval.get(letter, {}) if before_eval else {},
                "after": letter_data,
                "dispatch_id": DISPATCH_ID,
            })

    # Summary
    log("\n=== SESSION SUMMARY ===")
    log(f"BEFORE: {json.dumps(before_eval)}")
    log(f"AFTER:  {json.dumps(after_eval)}")
    if parcel_writes:
        log(f"Parcel IDs written: {parcel_writes}")
    else:
        log("No parcel IDs written (all paths blocked)")
    if zone_writes:
        log(f"Zone assignments written: {zone_writes}")
    else:
        log("No zone assignments written (all paths blocked)")

    return after_eval


if __name__ == "__main__":
    main()
