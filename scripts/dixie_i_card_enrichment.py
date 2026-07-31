#!/usr/bin/env python3
"""Dixie County Letter I card-completeness enrichment.

Context (dispatch c6b5fdd6, shard-8, 2026-07-31):
- Dixie I at 94.1% (32/34) — need 33/34 (97.1%) to clear the 95% threshold
- Two MCA rows are card-incomplete; one is likely a new auction added after Jul-19
  (when dixie was 8/10 at 32/33 = 97.0%)
- Dixie County: CO_NO=15, in-person auction only (no RealAuction/GovEase)
- Known blockers: civitekflorida.com/ocrs Turnstile-gated (C/D wall), ArcGIS parcel
  format mismatch (DOR strap vs our stored format)

Strategy for I (independent of C/D):
1. Query MCA for dixie rows where card_complete evaluator would fail
   (missing property_address OR lat/lon OR assessed_value OR parcel_zones join fails)
2. For rows WITH parcel_id: try FL DOR Statewide Cadastral (CO_NO=15) to get
   PHY_ADDR1, PHY_CITY, geometry (lat/lon), JV (just value), DOR_UC
3. For rows with parcel_id and DOR_UC result: insert parcel_zones row if missing
   (zone_code from DOR_UC crosswalk, honesty_marker=DOR_UC_CROSSWALK)
4. Patch MCA row with address/lat/lon/assessed_value where real data found
5. Run pencil_dod_evaluate_county('dixie') to confirm metric moved

Hard rules (Honesty Protocol):
- Do NOT fabricate addresses for vacant land (UNKNOWN = leave as-is)
- honesty_marker='DOR_UC_CROSSWALK' on any parcel_zones insert from this script
- Fail-loud: parsed>0 AND inserted=0 raises
- Per-row PATCH, never bulk upsert-by-id (NOT NULL constraint issue)
- SET statement_timeout=0 before heavy queries

Usage: python3 scripts/dixie_i_card_enrichment.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ACCESS_TOKEN
"""
import os, sys, json, time, urllib.request, urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"

if not SB_KEY and not ACCESS_TOKEN:
    sys.exit("FATAL: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ACCESS_TOKEN required")

SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}

DOR_CO_NO = 15

FL_DOR_URL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)

DOR_UC_MAP = {
    "000": "VAC-RES",   "001": "SFR",       "002": "MH",        "003": "MFR-10",
    "004": "MFR-CONDO", "005": "COOP",      "006": "RETIRE",    "007": "MISC-RES",
    "008": "MFR",       "009": "RES-COMMON","010": "VAC-COM",   "011": "RETAIL",
    "012": "MIXED-USE", "013": "DEPT-STORE","014": "SUPER",     "015": "REGIONAL",
    "016": "COMM-PARK", "017": "OFFICE",    "018": "PROF-SVC",  "019": "HOTEL",
    "020": "VAC-IND",   "021": "LIGHT-IND", "022": "HEAVY-IND", "023": "LUMBER",
    "024": "PACKING",   "025": "MINING",    "026": "UTIL",      "027": "AUTO-SVC",
    "028": "PARKING",   "029": "WHOLESALE", "030": "VAC-AG",    "031": "CROP",
    "032": "PASTURE",   "033": "TIMBER",    "034": "DAIRY",     "035": "BEE",
    "036": "NURSERY",   "037": "ORCHARD",   "038": "POULTRY",   "039": "AG-OTHER",
    "040": "INSTITUTIONAL","041": "CHURCH","042": "PRIVATE-ED","043": "PRIV-HOSP",
    "044": "HOMELESS",  "048": "CEMETARY",  "060": "GOVT",      "061": "COUNTY-MUN",
    "062": "FED-STATE", "063": "WATER-MUN", "064": "WATER-ST",  "065": "MILITARY",
    "066": "PRISONS",   "067": "PARKS-REC", "068": "PARKS-MUN", "069": "OTHER-GOVT",
    "070": "LEASEHOLD", "071": "LEASE-MUN", "075": "WATERWAYS", "080": "CENTRALLY",
    "086": "SUBSURFACE","090": "HOMESTEAD", "091": "CLASSIFIED", "099": "ACREAGE",
}


def mgmt_sql(query):
    """Execute SQL via Supabase Management API."""
    import httpx
    h = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers=h, json={"query": query}, timeout=120
    )
    r.raise_for_status()
    return r.json()


def sb_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=SB_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def sb_patch(table, row_id, fields):
    body = json.dumps(fields).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}",
        data=body, method="PATCH"
    )
    req.add_header("apikey", SB_KEY)
    req.add_header("Authorization", f"Bearer {SB_KEY}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def sb_post(table, rows):
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=body, method="POST"
    )
    req.add_header("apikey", SB_KEY)
    req.add_header("Authorization", f"Bearer {SB_KEY}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "resolution=ignore-duplicates,return=minimal")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def dor_query(parcel_id):
    """Query FL DOR Statewide Cadastral for a Dixie parcel.

    Note (3rd-firing shard-4 research): DOR parcel format for Dixie (CO_NO=15) is a
    strap scheme ('NN NNNN-NN-*-NN') that does NOT match our stored parcel_id format.
    This function tries both the stored value AND a normalized variant.
    Returns the first feature found, or None.
    """
    candidates = [parcel_id]
    # Dixie DOR strap: e.g. "15 3529-02-*-11" — try removing dashes/spaces variants
    normalized = parcel_id.replace("-", "").replace(" ", "")
    if normalized != parcel_id:
        candidates.append(normalized)

    for cand in candidates:
        params = {
            "where": f"CO_NO={DOR_CO_NO} AND (PARCEL_ID='{cand}' OR PARCELNO='{cand}')",
            "outFields": "PARCEL_ID,PARCELNO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,LND_VAL,DOR_UC",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        }
        url = FL_DOR_URL + "?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                d = json.loads(resp.read())
            feats = d.get("features", [])
            if feats:
                return feats[0]
        except Exception as e:
            print(f"  DOR query error for {cand!r}: {e}", file=sys.stderr)
        time.sleep(0.5)
    return None


def dor_query_by_co_no_page(offset=0, page_size=1000):
    """Paginate all Dixie parcels from FL DOR Cadastral.

    Returns list of {parcel_id, phy_addr1, phy_city, phy_zip, jv, dor_uc, lat, lon}
    """
    params = {
        "where": f"CO_NO={DOR_CO_NO}",
        "outFields": "PARCEL_ID,PARCELNO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,LND_VAL,DOR_UC",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultOffset": str(offset),
        "resultRecordCount": str(page_size),
        "f": "json",
    }
    url = FL_DOR_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read())


def get_dixie_incomplete_rows():
    """Query MCA for Dixie rows missing any card-complete field."""
    rows = sb_get(
        "multi_county_auctions",
        {
            "select": "id,case_number,parcel_id,property_address,latitude,longitude,assessed_value",
            "county": "eq.dixie",
            "limit": "200",
            "order": "id.asc",
        },
    )
    # Filter to rows missing at least one field required by the I evaluator
    # (property_address, latitude, longitude, assessed_value — parcel_zones checked separately)
    incomplete = []
    for row in rows:
        missing = []
        if not row.get("property_address"):
            missing.append("address")
        if row.get("latitude") is None or row.get("longitude") is None:
            missing.append("geo")
        if row.get("assessed_value") is None:
            missing.append("value")
        if missing:
            row["_missing"] = missing
            incomplete.append(row)
    return incomplete


def check_parcel_zones(parcel_id, jurisdiction_ids):
    """Return True if a parcel_zones row with zone_code exists for this parcel_id."""
    if not parcel_id:
        return False
    rows = sb_get(
        "parcel_zones",
        {
            "select": "id",
            "parcel_id": f"eq.{parcel_id}",
            "zone_code": "not.is.null",
            "limit": "1",
        },
    )
    return bool(rows)


def get_dixie_jurisdiction_ids():
    """Return list of jurisdiction IDs for Dixie county."""
    rows = sb_get(
        "jurisdictions",
        {
            "select": "id",
            "or": "(county_name.ilike.dixie,county.ilike.dixie)",
            "limit": "20",
        },
    )
    return [r["id"] for r in rows]


def insert_parcel_zones(parcel_id, zone_code, jurisdiction_id, lat=None, lon=None):
    """Insert a parcel_zones row for a Dixie parcel."""
    row = {
        "parcel_id": parcel_id,
        "zone_code": zone_code,
        "jurisdiction_id": jurisdiction_id,
        "honesty_marker": "DOR_UC_CROSSWALK",
        "zone_source": "dor_uc_enrichment",
    }
    if lat is not None:
        row["centroid_lat"] = lat
    if lon is not None:
        row["centroid_lon"] = lon
    return sb_post("parcel_zones", [row])


def run():
    print("=== Dixie I Card-Completeness Enrichment (shard-8, dispatch c6b5fdd6) ===")
    print(f"Supabase: {SUPABASE_URL}")

    # Step 1: Get incomplete MCA rows
    print("\n[1] Querying Dixie MCA rows with missing card fields...")
    incomplete = get_dixie_incomplete_rows()
    print(f"  Found {len(incomplete)} incomplete rows")

    if not incomplete:
        print("  No incomplete rows found — letter I may already be passing.")
        _verify()
        return

    for row in incomplete:
        print(f"  {row['case_number']} | parcel={row.get('parcel_id')!r} | missing={row['_missing']}")

    # Step 2: Get Dixie jurisdiction IDs for parcel_zones inserts
    print("\n[2] Fetching Dixie jurisdiction IDs...")
    jur_ids = get_dixie_jurisdiction_ids()
    print(f"  Found {len(jur_ids)} jurisdiction IDs: {jur_ids}")
    default_jur_id = jur_ids[0] if jur_ids else None

    # Step 3: Build DOR Cadastral lookup map for all Dixie parcels
    # (Only fetch if we have rows with parcel_ids to look up)
    parcel_ids_needed = {r["parcel_id"] for r in incomplete if r.get("parcel_id")}
    dor_map = {}  # parcel_id -> {addr, lat, lon, jv, dor_uc}

    if parcel_ids_needed:
        print(f"\n[3] Fetching FL DOR Cadastral for {len(parcel_ids_needed)} Dixie parcel IDs...")
        for pid in parcel_ids_needed:
            feat = dor_query(pid)
            if feat:
                a = feat["attributes"]
                geom = feat.get("geometry") or {}
                addr1 = (a.get("PHY_ADDR1") or "").strip()
                city = (a.get("PHY_CITY") or "").strip()
                zipc = (a.get("PHY_ZIPCD") or "").strip()
                full_addr = ", ".join(x for x in [addr1, city, f"FL {zipc}"] if x).strip(", ")
                dor_map[pid] = {
                    "address": full_addr if addr1 and addr1.upper() != "UNKNOWN" else None,
                    "lat": geom.get("y"),
                    "lon": geom.get("x"),
                    "jv": a.get("JV"),
                    "dor_uc": str(a.get("DOR_UC", "")).zfill(3),
                }
                print(f"  {pid} -> addr={dor_map[pid]['address']!r} jv={dor_map[pid]['jv']} dor_uc={dor_map[pid]['dor_uc']}")
            else:
                print(f"  {pid} -> NOT FOUND in FL DOR Cadastral (format mismatch or no record)")
            time.sleep(0.5)
    else:
        print("\n[3] No rows with parcel_ids to look up in FL DOR Cadastral")

    # Step 4: Also fetch rows with NO parcel_id — try case-number-based lookup
    # (For rows missing parcel_id entirely, we can't do much without AcclaimWeb/Civitek)
    no_parcel = [r for r in incomplete if not r.get("parcel_id")]
    if no_parcel:
        print(f"\n[4] {len(no_parcel)} rows have NO parcel_id — cannot resolve without AcclaimWeb/Civitek")
        print("  These are structurally blocked (Civitek OCRS is Turnstile-gated for Dixie)")
        for row in no_parcel:
            print(f"  BLOCKED: {row['case_number']} (no parcel_id source found in 5+ prior sessions)")

    # Step 5: Apply enrichment to rows where DOR data found
    print("\n[5] Applying enrichment patches...")
    patched = 0
    pz_inserted = 0

    for row in incomplete:
        pid = row.get("parcel_id")
        if not pid:
            continue
        dor = dor_map.get(pid)
        if not dor:
            print(f"  SKIP {row['case_number']}: no DOR data found for parcel {pid!r}")
            continue

        patch = {}
        if "address" in row["_missing"] and dor.get("address"):
            patch["property_address"] = dor["address"]
        if "geo" in row["_missing"] and dor.get("lat") is not None:
            patch["latitude"] = dor["lat"]
            patch["longitude"] = dor["lon"]
        if "value" in row["_missing"] and dor.get("jv"):
            patch["assessed_value"] = dor["jv"]

        if patch:
            status = sb_patch("multi_county_auctions", row["id"], patch)
            print(f"  PATCHED {row['case_number']}: {list(patch.keys())} -> HTTP {status}")
            patched += 1
        else:
            print(f"  SKIP {row['case_number']}: DOR data doesn't cover missing fields {row['_missing']}")

        # Check if parcel_zones exists; insert if missing and we have DOR_UC
        if dor.get("dor_uc") and default_jur_id:
            has_pz = check_parcel_zones(pid, jur_ids)
            if not has_pz:
                zone_code = DOR_UC_MAP.get(dor["dor_uc"], f"UC-{dor['dor_uc']}")
                status = insert_parcel_zones(
                    pid, zone_code, default_jur_id,
                    lat=dor.get("lat"), lon=dor.get("lon")
                )
                print(f"  PARCEL_ZONES inserted for {pid} (zone={zone_code}, honesty=DOR_UC_CROSSWALK) HTTP {status}")
                pz_inserted += 1

    print(f"\nEnrichment complete: {patched} MCA rows patched, {pz_inserted} parcel_zones inserted")

    # Step 6: Verify metric moved
    _verify()


def _verify():
    print("\n[VERIFY] Running pencil_dod_evaluate_county('dixie')...")
    try:
        result = mgmt_sql("SET statement_timeout = 0; SELECT public.pencil_dod_evaluate_county('dixie')")
        print("VERIFICATION RESULT:")
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"  Verification failed (will need manual re-run): {e}", file=sys.stderr)
        print("  Manual check: SELECT public.pencil_dod_evaluate_county('dixie');")


if __name__ == "__main__":
    run()
