#!/usr/bin/env python3
"""
sumter_e_parcel_fresh_probe.py — Gold Standard Shard-7 (loop 6080), sumter E fix attempt.

Criterion E (parcel linkage >=95%) is at 90.9% — 10/11 parcels linked.
Missing: case 2025-CA-000255 "Wildwood Phase One LLC" / "TL Gulf Coast Holdings LLC".

Prior sessions have attempted (and found blocked):
  - Sumter GIS (no parcels/ownership layer on server)
  - Sumter PA/qPublic (Cloudflare 403)
  - Sunbiz entity search (Cloudflare 403)
  - FL DOR cadastral OWN_NAME filter (HTTP 400 - PARCEL_ID-only supported)
  - myfloridacounty.com/orisearch/60 (Cloudflare Turnstile)
  - Civitek OCRS (Cloudflare Turnstile)

NEW ANGLES TO TRY:
1. FL DOR cadastral - search by PHY_CITY + broader approach
2. opendata.arcgis.com - Florida parcel search by owner name (different API)
3. Sumter County GIS property viewer direct map service probe
4. sumtercountyfl.gov search
5. Wildwood city GIS (if Wildwood Phase One LLC is in Wildwood)

IMPORTANT: 2025-CA-000255 is a CANCELLED foreclosure (per prior research).
The case was for property belonging to "Wildwood Phase One LLC" or
"TL Gulf Coast Holdings LLC" (plaintiff). The property may be in Wildwood
(one of Sumter's municipalities), which could have separate GIS data.
"""
import json
import os
import urllib.request
import urllib.error
import urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]

H = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

CASE_NUMBER = "2025-CA-000255"
COUNTY = "sumter"


def fetch_url(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; research-bot)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return 0, str(e)


def probe_wildwood_gis():
    """
    Probe Wildwood's own GIS/zoning data layer. Wildwood Phase One LLC may 
    appear in Wildwood city's property data.
    The interactive FLU/Zoning FeatureServer found in prior sessions:
    https://gis.sumtercountyfl.gov/sumtergis/rest/services/Interactive/FLU_Zoning/FeatureServer/
    Layer 0 is Wildwood zoning. Try OWN_NAME or similar field search.
    """
    base = "https://gis.sumtercountyfl.gov/sumtergis/rest/services/"
    print("\n[1] Probing Wildwood-specific GIS layers...")
    
    # First check available layers on the zoning FeatureServer
    url = f"{base}Interactive/FLU_Zoning/FeatureServer/0/query?where=1%3D1&outFields=*&f=json&resultRecordCount=1"
    status, body = fetch_url(url)
    print(f"  FLU_Zoning FeatureServer/0 sample: HTTP {status}")
    if status == 200:
        try:
            data = json.loads(body)
            fields = [f["name"] for f in data.get("fields", [])]
            print(f"  Available fields: {fields}")
        except Exception:
            print(f"  Response: {body[:200]}")
    
    return None


def probe_sumter_gis_ownername():
    """
    Re-try sumter GIS with known working hostname but checking if there's
    an ownership/parcel search layer we missed.
    """
    print("\n[2] Probing sumter GIS parcels layer for owner search...")
    
    # Check the Development_Services MapServer for any parcel/owner layer
    layers_url = "https://gis.sumtercountyfl.gov/sumtergis/rest/services/DevelopmentServices/Development_Services/MapServer?f=json"
    status, body = fetch_url(layers_url)
    print(f"  Development_Services MapServer: HTTP {status}")
    if status == 200:
        try:
            data = json.loads(body)
            layers = [(l.get("id"), l.get("name")) for l in data.get("layers", [])]
            print(f"  Layers: {layers}")
        except Exception:
            print(f"  Response: {body[:200]}")
    
    # Check the Operations MapServer (has the geocoder)
    ops_url = "https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations?f=json"
    status, body = fetch_url(ops_url)
    print(f"  Operations services: HTTP {status}")
    if status == 200:
        try:
            data = json.loads(body)
            svcs = [(s.get("name"), s.get("type")) for s in data.get("services", [])]
            print(f"  Services: {svcs}")
        except Exception:
            print(f"  Response: {body[:300]}")
    
    return None


def probe_sumter_property_search():
    """
    Try sumtercountyfl.gov property/parcel search directly.
    Some county portals have ungated parcel search APIs.
    """
    print("\n[3] Probing sumtercountyfl.gov for parcel search...")
    
    # Try the property appraiser's main page to find API endpoints
    url = "https://app.sumterpa.com/SCPA-GIS/api/search?query=wildwood+phase"
    status, body = fetch_url(url)
    print(f"  SCPA-GIS API search: HTTP {status}")
    print(f"  Response: {body[:200]}")
    
    # Try a different endpoint pattern
    url2 = "https://app.sumterpa.com/SCPA-GIS/search?q=wildwood+phase+one"
    status2, body2 = fetch_url(url2)
    print(f"  SCPA-GIS search alt: HTTP {status2}")
    print(f"  Response: {body2[:200]}")
    
    return None


def probe_fl_dor_cadastral_city():
    """
    FL DOR cadastral - search by PHY_CITY=WILDWOOD to find parcels near the case.
    The OWN_NAME filter is broken (HTTP 400) but PHY_CITY might work.
    Try to get all Wildwood parcels and look for ones owned by entities
    matching "Wildwood Phase" or "TL Gulf Coast".
    """
    print("\n[4] FL DOR cadastral - PHY_CITY=WILDWOOD search...")
    
    url = (
        "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
        "Florida_Statewide_Cadastral/FeatureServer/0/query"
        "?where=CO_NO%3D60%20AND%20PHY_CITY%3D%27WILDWOOD%27"
        "&outFields=PARCEL_ID%2COWN_NAME%2CPHY_ADDR1%2CPHY_CITY"
        "&f=json&resultRecordCount=10"
    )
    status, body = fetch_url(url)
    print(f"  CO_NO=60 PHY_CITY=WILDWOOD: HTTP {status}")
    if status == 200:
        try:
            data = json.loads(body)
            feats = data.get("features", [])
            print(f"  Records found: {len(feats)}")
            for f in feats[:5]:
                attrs = f["attributes"]
                own = attrs.get("OWN_NAME", "").upper()
                if "WILDWOOD" in own or "TL GULF" in own or "PHASE" in own:
                    print(f"  *** MATCH: {attrs} ***")
                else:
                    print(f"  {attrs.get('PARCEL_ID')} | {attrs.get('OWN_NAME')} | {attrs.get('PHY_ADDR1')}")
        except Exception as e:
            print(f"  Parse error: {e}")
            print(f"  Response: {body[:300]}")
    else:
        print(f"  Response: {body[:200]}")


def probe_sumter_clerk_case_direct():
    """
    Try to access the sumter clerk case 2025-CA-000255 directly through
    civitekflorida.com (OCRS) without the PrimeFaces form by trying the
    direct document URL pattern used by some FL counties.
    """
    print("\n[5] Sumter OCRS direct case probe (case 2025-CA-000255)...")
    
    # Try the REST-style case lookup if available
    urls = [
        "https://civitekflorida.com/ocrs/county/60/case/2025-CA-000255",
        "https://civitekflorida.com/ocrs/county/60/case?caseNumber=2025CA000255",
        "https://www.sumterclerk.com/?a=Case.CaseSearch&caseType=CA&year=2025&num=255",
    ]
    for url in urls:
        status, body = fetch_url(url)
        print(f"  {url[:60]}: HTTP {status}")
        if status == 200 and len(body) > 100:
            if "parcel" in body.lower() or "folio" in body.lower() or "legal" in body.lower():
                print(f"  -> PARCEL DATA FOUND in response!")
                print(body[:500])
    
    return None


def update_parcel_if_found(parcel_id):
    """Write parcel_id to multi_county_auctions if we actually find one."""
    url = (
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        f"?case_number=eq.{CASE_NUMBER}&county=eq.{COUNTY}"
    )
    payload = json.dumps({"parcel_id": parcel_id}).encode()
    req = urllib.request.Request(url, data=payload, headers=H, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            print(f"  PATCH result: {len(rows)} row(s) updated with parcel_id={parcel_id}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  PATCH failed: {e.code}: {e.read().decode()}")
        return False


def main():
    print("=" * 70)
    print(f"SUMTER E-FIX: Parcel probe for {CASE_NUMBER} (Gold Standard Loop 6080)")
    print("=" * 70)
    print("Target: 'Wildwood Phase One LLC' / 'TL Gulf Coast Holdings LLC'")
    print("This is a CANCELLED foreclosure with no parcel_id in our DB.")
    print("4+ prior sessions confirmed all standard lookup paths are blocked.")
    print("Trying fresh angles...")

    probe_wildwood_gis()
    probe_sumter_gis_ownername()
    probe_sumter_property_search()
    probe_fl_dor_cadastral_city()
    probe_sumter_clerk_case_direct()

    print("\n" + "=" * 70)
    print("PROBE COMPLETE")
    print("If no parcel_id was found above, E and I remain blocked at 90.9%.")
    print("BLANK > WRONG: reporting honest 90.9% rather than fabricating a match.")
    print("=" * 70)


if __name__ == "__main__":
    main()
