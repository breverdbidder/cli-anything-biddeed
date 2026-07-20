#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-11: gadsden E+I fix
dispatch_id: 52bf028c-78fe-49ad-ae77-284c02a1f201
session: architect-20260720T210000

Target: gadsden E=91.3% (21/23), I=56.5% (13/23)

STRATEGY:
1. First, query live DB to understand current state exactly
2. For E: investigate Gadsden AcclaimWeb/CourtScribe for parcel IDs
   - 25000942CA: sold 2026-07-02, CourtScribe CaseDataID=726421 - check if CT doc has parcel
   - 25000901CA: Ramon's Construction, 2 ambiguous parcels - look for better disambiguator
3. For I: investigate ArcGIS for municipal parcel zoning
   - Try ARPCmaps Gadsden_FLUM for Quincy/Chattahoochee/Havana parcels
   - Try myfloridacounty.com/orisearch/20 for Gadsden official records
   - Try FL GIO /arcgis/rest/services/ for county=20 parcel zoning

All data writes require independent verification per HONESTY PROTOCOL.
BLANK > WRONG: no fabricated parcel_ids or zone_codes.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def log(msg):
    import datetime
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    print(f"[{ts}] {msg}", flush=True)


def sb_get(path, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                log(f"  GET retry {attempt+1}: {e}")
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
    body = json.dumps([data] if isinstance(data, dict) else data).encode()
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
    """Execute SQL via Supabase Management API. Requires SUPABASE_ACCESS_TOKEN."""
    token = SUPABASE_ACCESS_TOKEN
    if not token:
        log("WARN: SUPABASE_ACCESS_TOKEN not set, falling back to RPC")
        return None
    proj_ref = "mocerqjnksmhcjzxrewo"
    url = f"https://api.supabase.com/v1/projects/{proj_ref}/database/query"
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"Bearer {token}",
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
            log(f"  mgmt_sql HTTP {e.code}: {body_text[:200]}")
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


def fetch_url(url, ua=UA, timeout=20, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                return 0, str(e)


def run_pencil_dod():
    """Run pencil_dod_evaluate_county via PostgREST RPC."""
    body = json.dumps({"p_county": "gadsden"}).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/pencil_dod_evaluate_county",
        data=body,
        headers=HEADERS,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"pencil_dod_evaluate_county RPC error: {e}")
        return None


def step1_query_current_state():
    """Query the current state of gadsden E and I."""
    log("=== STEP 1: Query current DB state ===")

    # Get all gadsden auctions
    rows = sb_get("multi_county_auctions?county=eq.gadsden&select=id,case_number,parcel_id,property_address,assessed_value,latitude,longitude,auction_status")
    log(f"Total gadsden auctions: {len(rows)}")

    unlinked = [r for r in rows if not r.get("parcel_id")]
    linked = [r for r in rows if r.get("parcel_id")]
    log(f"Linked (parcel_id IS NOT NULL): {len(linked)}")
    log(f"Unlinked (parcel_id IS NULL): {len(unlinked)}")
    for r in unlinked:
        log(f"  UNLINKED: {r['case_number']} | address={r.get('property_address', 'NULL')!r} | status={r.get('auction_status')}")

    # Get parcel_zones for gadsden to understand I state
    if SUPABASE_ACCESS_TOKEN:
        pz_result = mgmt_sql("""
            SELECT mca.case_number, mca.parcel_id, pz.zone_code, pz.jurisdiction_id,
                   mca.assessed_value, mca.latitude, mca.longitude, mca.property_address
            FROM multi_county_auctions mca
            LEFT JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
            WHERE mca.county = 'gadsden'
            ORDER BY mca.case_number
        """)
        log(f"Parcel zones query result: {json.dumps(pz_result, indent=2)[:2000]}")
    else:
        log("WARN: no SUPABASE_ACCESS_TOKEN, skipping parcel_zones query")

    return rows, linked, unlinked


def step2_live_evaluation():
    """Run pencil_dod_evaluate_county to get current E and I."""
    log("=== STEP 2: Live pencil_dod_evaluate_county('gadsden') ===")
    result = run_pencil_dod()
    if result:
        log(f"CURRENT EVALUATION: {json.dumps(result, indent=2)}")
        e_metric = result.get("E", {}).get("metric")
        i_metric = result.get("I", {}).get("metric")
        log(f"E metric: {e_metric}, I metric: {i_metric}")
        return result
    else:
        log("WARNING: Could not get live evaluation")
        return None


def step3_investigate_courtscribe_parcel():
    """
    Try to get parcel IDs from CourtScribe dockets for the 2 unlinked cases.
    The full docket for 25000942CA might have a legal description with parcel info.
    CaseDataID=726421 was confirmed working in prior session.
    """
    log("=== STEP 3: CourtScribe investigation for parcel IDs ===")

    COURTSCRIBE_BASE = "https://www.gadsdenclerk.com/CourtScribePublicInquiry/CourtScribe"

    # Try to get the FULL docket for 25000942CA (CaseDataID=726421)
    # Prior session got a summary; full docket may have more detail
    log("Trying CourtScribe full docket for 25000942CA (CaseDataID=726421)...")
    status, body = fetch_url(f"{COURTSCRIBE_BASE}/GetCaseDetailsPI?CaseDataID=726421")
    log(f"HTTP {status}, body length {len(body)}")
    if status == 200:
        log(f"FULL DOCKET (first 3000 chars): {body[:3000]}")
        # Look for parcel ID patterns in the docket text
        import re
        # Gadsden parcel IDs follow pattern: N-NN-NN-NW-NNNN-NNNNN-NNNN
        parcel_pattern = r'\d-\d{2}-\d{1,2}[NS]-\d{1,2}[EW]-\d{4}-\d{5}-\d{4}'
        parcels_found = re.findall(parcel_pattern, body)
        if parcels_found:
            log(f"PARCEL IDs found in docket: {parcels_found}")
        else:
            log("No parcel ID pattern found in docket text")

        # Also look for legal description info
        if "legal" in body.lower() or "parcel" in body.lower():
            log("Found 'legal' or 'parcel' keyword in docket")
    else:
        log(f"CourtScribe returned HTTP {status} for case 726421")

    # Try to search for 25000901CA by case number to get its CaseDataID
    log("\nSearching CourtScribe for 25000901CA...")
    search_url = f"{COURTSCRIBE_BASE}/SearchClerk"
    # The CourtScribe search might accept case number
    case_search = urllib.parse.urlencode({
        "CaseNumber": "25000901CA",
        "County": "Gadsden",
    })
    status, body = fetch_url(f"{search_url}?{case_search}")
    log(f"Search HTTP {status}, body length {len(body)}")
    if status == 200 and body:
        log(f"Search response (first 2000 chars): {body[:2000]}")

    return None


def step4_investigate_arcgis_municipal_zoning():
    """
    Try new ArcGIS angles for Quincy/Chattahoochee/Havana parcel zoning.
    Previous sessions tried:
    - ARPC Gadsden_FLUM (county categories, not municipal zoning)
    - No Quincy_Zoning or Chattahoochee_Zoning FeatureServer found in ARPC org

    NEW ANGLES (not yet tried):
    - Search ArcGIS Online for "Quincy FL zoning" or "Chattahoochee FL zoning"
    - Try Quincy city's own GIS portal (quincy.fl.gov/gis?)
    - Try myfloridacounty.com/orisearch/20 for Gadsden
    - Try FL GIO for parcel data with parcel_id cross-reference

    The 8 municipal parcels that are linked but lack zone_code:
    We know their parcel_ids (from prior session queries).
    If we can find which parcel is in which zone, we can insert parcel_zones rows.
    """
    log("=== STEP 4: ArcGIS municipal zoning investigation ===")

    # First, get the parcel_ids and jurisdiction info for the municipal parcels
    # These are confirmed from 20260718k migration comments:
    # Quincy: 11 auction rows with addresses in Quincy
    # Chattahoochee: 4 auction rows
    # Havana: 3 auction rows (but might be unincorporated)

    # Try ArcGIS Online REST API for Quincy/Chattahoochee zoning layers
    log("Probing ArcGIS Online for Quincy FL zoning FeatureServer...")
    agol_search = (
        "https://www.arcgis.com/sharing/rest/search?"
        + urllib.parse.urlencode({
            "q": "Quincy Florida zoning owner:quincy",
            "f": "json",
            "num": 10,
        })
    )
    status, body = fetch_url(agol_search)
    log(f"AGOL search for Quincy: HTTP {status}")
    if status == 200:
        try:
            data = json.loads(body)
            results = data.get("results", [])
            log(f"Found {len(results)} results")
            for r in results[:5]:
                log(f"  - {r.get('title')} | type={r.get('type')} | owner={r.get('owner')} | url={r.get('url')}")
        except Exception as e:
            log(f"Parse error: {e}")

    log("\nProbing ArcGIS Online for Chattahoochee FL zoning...")
    agol_search2 = (
        "https://www.arcgis.com/sharing/rest/search?"
        + urllib.parse.urlencode({
            "q": "Chattahoochee Florida zoning Gadsden",
            "f": "json",
            "num": 10,
        })
    )
    status, body = fetch_url(agol_search2)
    log(f"AGOL search for Chattahoochee: HTTP {status}")
    if status == 200:
        try:
            data = json.loads(body)
            results = data.get("results", [])
            log(f"Found {len(results)} results")
            for r in results[:5]:
                log(f"  - {r.get('title')} | type={r.get('type')} | owner={r.get('owner')} | url={r.get('url')}")
        except Exception as e:
            log(f"Parse error: {e}")

    # Try the ARPC org more thoroughly
    log("\nProbing ARPC ArcGIS org for any Quincy/Chattahoochee layers...")
    arpc_base = "https://services8.arcgis.com/N3lCn6dEKCL6LidU/arcgis/rest/services"
    status, body = fetch_url(f"{arpc_base}?f=json")
    log(f"ARPC services list: HTTP {status}")
    if status == 200:
        try:
            data = json.loads(body)
            services = data.get("services", [])
            for s in services:
                name = s.get("name", "").lower()
                if any(kw in name for kw in ["quincy", "chattahoochee", "havana", "gadsden", "zoning"]):
                    log(f"  MATCH: {s.get('name')} type={s.get('type')}")
        except Exception as e:
            log(f"Parse error: {e}")

    # Try Florida GIO for Gadsden parcel data (co_no=20 for Gadsden)
    log("\nProbing FL GIO ArcGIS for Gadsden parcels (co_no=20)...")
    fl_gio_url = (
        "https://maps.fdot.gov/arcgis/rest/services/FDOTGISData/Parcels/FeatureServer/0/query?"
        + urllib.parse.urlencode({
            "where": "co_no=20",
            "outFields": "parcel_id,own_name,phy_addr1,dor_uc,mu_code",
            "resultRecordCount": 5,
            "f": "json",
        })
    )
    status, body = fetch_url(fl_gio_url)
    log(f"FL GIO Gadsden parcels: HTTP {status}, len={len(body)}")

    # More targeted: FL GIO statewide cadastral FeatureServer
    log("\nProbing FL GIO statewide cadastral for co_no=20 sample...")
    fl_gio2 = (
        "https://services2.arcgis.com/BX2nkjIblBWwRUPi/arcgis/rest/services/FLStatewid_Parcel_Cadastral_OpenData/FeatureServer/0/query?"
        + urllib.parse.urlencode({
            "where": "CO_NO=20",
            "outFields": "CO_NO,PARCELNO,PHY_ADDR1,OWN_NAME,MU_CODE",
            "resultRecordCount": 5,
            "f": "json",
        })
    )
    status, body = fetch_url(fl_gio2)
    log(f"FL GIO cadastral co_no=20: HTTP {status}, len={len(body)}")
    if status == 200 and len(body) > 100:
        try:
            data = json.loads(body)
            features = data.get("features", [])
            log(f"Found {len(features)} features (sample)")
            for f in features[:3]:
                log(f"  - {f.get('attributes')}")
        except Exception as e:
            log(f"Parse error: {e}")

    return None


def step5_check_myfloridacounty_gadsden():
    """
    Check myfloridacounty.com/orisearch/20 for Gadsden official records.
    Gadsden county number in FL ORI system is 20.
    """
    log("=== STEP 5: myfloridacounty.com Gadsden official records ===")

    # myfloridacounty.com typically uses county code in URL
    url = "https://www.myfloridacounty.com/orisearch/20"
    status, body = fetch_url(url)
    log(f"myfloridacounty.com/orisearch/20: HTTP {status}")
    if status == 200:
        log(f"Response (first 500 chars): {body[:500]}")
    elif status == 302:
        log(f"Redirect response")

    # Also try direct clerk portal lookup
    # Gadsden clerk may use myeclerk or similar
    urls_to_try = [
        "https://www.myfloridacounty.com/ori/",
        "https://myeclerk.com/search?county=gadsden",
        "https://secure.gadsdenclerk.com/",
    ]
    for u in urls_to_try:
        status, body = fetch_url(u, timeout=10)
        log(f"{u}: HTTP {status}")


def step6_try_quincy_gis():
    """
    Try to find Quincy city's own GIS portal.
    """
    log("=== STEP 6: Quincy FL city GIS portal ===")

    urls_to_try = [
        "https://www.quincy.fl.gov/gis",
        "https://gis.quincy.fl.gov/",
        "https://gis.quincyfl.gov/",
        "https://maps.quincy.fl.gov/",
        "http://quincy.fl.gov/government/departments/gis",
    ]
    for u in urls_to_try:
        status, body = fetch_url(u, timeout=10)
        log(f"{u}: HTTP {status}")
        if status == 200 and "arcgis" in body.lower():
            log(f"  Found ArcGIS reference! Body snippet: {body[:300]}")


def main():
    log("Starting gadsden E+I investigation (shard-11, dispatch 52bf028c)")

    # Step 1: Get current DB state
    rows, linked, unlinked = step1_query_current_state()

    # Step 2: Get live evaluation
    evaluation = step2_live_evaluation()

    if evaluation:
        e_pass = evaluation.get("E", {}).get("pass", False)
        i_pass = evaluation.get("I", {}).get("pass", False)
        e_metric = evaluation.get("E", {}).get("metric")
        i_metric = evaluation.get("I", {}).get("metric")
        log(f"\nCURRENT STATE: E={e_metric}% (pass={e_pass}), I={i_metric}% (pass={i_pass})")

        if e_pass and i_pass:
            log("BOTH E AND I ALREADY PASS - no work needed!")
            return

    # Step 3: CourtScribe parcel investigation
    step3_investigate_courtscribe_parcel()

    # Step 4: ArcGIS municipal zoning
    step4_investigate_arcgis_municipal_zoning()

    # Step 5: myfloridacounty.com
    step5_check_myfloridacounty_gadsden()

    # Step 6: Quincy city GIS
    step6_try_quincy_gis()

    log("\n=== INVESTIGATION COMPLETE ===")
    log("Review output above to determine next steps.")
    log("Per HONESTY PROTOCOL: BLANK > WRONG - no parcel_id or zone_code written without proof.")


if __name__ == "__main__":
    main()
