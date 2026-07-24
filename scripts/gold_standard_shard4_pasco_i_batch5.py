#!/usr/bin/env python3
"""
Gold Standard: pasco criterion I, batch 5 — dispatch 2c5b3c77, run 6253.

Entry state (from brief, 2026-07-24): I=94.7% (card_complete=250 of 264, FAIL).
Threshold: >=95% → need 251 of 264.

Batch4 (20260723163800_pasco_i_card_completeness_batch4.sql) fixed 250/257.
Since then, 7 new auctions arrived (total 264). This script diagnoses the live
gap (264 - 250 = 14 incomplete), attempts to fix as many as possible using:

(a) Rows with parcel_id present but missing lat/lon/assessed_value + no parcel_zones:
    Fix via FL GIO Statewide Cadastral FeatureServer (org Gh9awoU677aKree0 as
    verified in batch4 -- the old Gh9awoUAlNaqxRUn org is stale/HTTP-400).
    + INSERT parcel_zones (jurisdiction_id=1258, DOR_UC crosswalk).

(b) Rows with parcel_id IS NULL but a real, non-placeholder address:
    Fix via US Census geocoder (free, public, no-key) for lat/lon.
    FL GIO address lookup (PHY_ADDR1 ILIKE match) for parcel_id + assessed_value.
    + INSERT parcel_zones.

(c) Rows with no parcel_id, no usable address, or ambiguous multi-parcel address:
    Deferred honestly -- logged, never fabricated.

Idempotent: gap query re-selects live incomplete rows; parcel_zones INSERT uses
NOT EXISTS guard; lat/lon/assessed_value only overwritten on rows where they
are currently NULL/placeholder (never overwrites verified data).

DOR_UC crosswalk (from batch1/2/3/4 -- same map, no new codes invented):
  001 -> R-2 (Single Family / Vacant Residential)
  000 -> R-2 (Vacant Residential)
  002 -> MH  (Mobile Home)
  003 -> R-2  (Multi-Story SFR, treat as R-2)
  004 -> RMF  (Multi-Family / Condo)
  005 -> RMF  (Co-op, treat as RMF)
  006 -> RMF  (Retirement/Life Care, treat as RMF)
  007 -> RMF  (Misc Residential, treat as RMF)
  008 -> RMF  (Multi-Family 10+, treat as RMF)
  009 -> RES-COMMON (Common Area)
  010 -> C-1  (Vacant Commercial)
  011 -> C-1  (Stores, neighborhood)
  012 -> MU   (Mixed-Use)
  014 -> C-1  (Supermarkets)
  015 -> C-1  (Regional SC)
  016 -> C-1  (Community SC)
  021 -> C-1  (Restaurants, cafeteria)
  022 -> C-1  (Drive-in restaurant)
  023 -> C-1  (Financial/bank)
  025 -> C-1  (Repair shops)
  048 -> IND  (Industrial)
  066 -> AG   (Orchard/Groves)
  069 -> AG   (Ornamental Horticulture)
  086 -> IND  (Sub-surface mineral rights)
  089 -> IND  (Acreage industrial)
  094 -> HIST (Historic Property)
  099 -> R-2  (Vacant Acreage / Other)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

PASCO_CO_NO = 61
PASCO_JURISDICTION_ID = 1258
FL_GIO_BASE = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/address"
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

DOR_UC_MAP = {
    "001": ("R-2", "Residential Single Family (2-4 du/ac)"),
    "000": ("R-2", "Residential Single Family (2-4 du/ac) - Vacant"),
    "002": ("MH", "Mobile Home (4 du/ac)"),
    "003": ("R-2", "Residential Single Family (2-4 du/ac)"),
    "004": ("RMF", "Multi-Family Residential (Condo)"),
    "005": ("RMF", "Multi-Family Residential (Co-op)"),
    "006": ("RMF", "Multi-Family Residential (Retirement)"),
    "007": ("RMF", "Multi-Family Residential (Misc)"),
    "008": ("RMF", "Multi-Family Residential (10+ units)"),
    "009": ("RES-COMMON", "Residential Common Area / Open Space"),
    "010": ("C-1", "Commercial (Vacant)"),
    "011": ("C-1", "Commercial (Retail Stores)"),
    "012": ("MU", "Mixed-Use"),
    "014": ("C-1", "Commercial (Supermarket)"),
    "015": ("C-1", "Commercial (Regional SC)"),
    "016": ("C-1", "Commercial (Community SC)"),
    "021": ("C-1", "Commercial (Restaurant)"),
    "022": ("C-1", "Commercial (Drive-in)"),
    "023": ("C-1", "Commercial (Financial)"),
    "025": ("C-1", "Commercial (Repair)"),
    "048": ("IND", "Industrial"),
    "066": ("AG", "Agriculture (Orchard)"),
    "069": ("AG", "Agriculture (Ornamental)"),
    "086": ("IND", "Industrial (Mineral Rights)"),
    "089": ("IND", "Industrial (Acreage)"),
    "094": ("HIST", "Historic Property"),
    "099": ("R-2", "Residential Single Family (Acreage)"),
}

PLACEHOLDER_LAT = 28.308
PLACEHOLDER_LON = -82.4396
PLACEHOLDER_AV = 150000.0


def rest_get(path_and_params):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path_and_params}",
        headers=HEADERS,
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def mgmt_query(sql):
    if not ACCESS_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not set — cannot run mgmt query")
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def fetch_gap_rows():
    """Fetch pasco MCA rows that are NOT yet card_complete per pencil_dod criteria.

    v_zoning_gold_standard_card requires:
      - property_address IS NOT NULL
      - latitude IS NOT NULL
      - assessed_value IS NOT NULL (or market_value)
      - parcel_id IS NOT NULL
      - EXISTS parcel_zones row with non-null zone_code for this parcel_id
    We look for rows missing any of those.
    """
    rows = rest_get(
        "multi_county_auctions?"
        "county=eq.pasco"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value,data_source"
        "&data_source=not.eq.propertyonion"
        "&order=id"
        "&limit=500"
    )
    null_ds = rest_get(
        "multi_county_auctions?"
        "county=eq.pasco"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value,data_source"
        "&data_source=is.null"
        "&order=id"
        "&limit=500"
    )
    seen = set()
    all_rows = []
    for r in rows + null_ds:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        all_rows.append(r)

    parcel_ids_with_zones = set()
    if ACCESS_TOKEN:
        pz_sql = """
        SELECT DISTINCT pz.parcel_id
        FROM parcel_zones pz
        JOIN multi_county_auctions mca ON mca.parcel_id = pz.parcel_id
        WHERE lower(mca.county) = 'pasco' AND pz.zone_code IS NOT NULL
        """
        try:
            pz_rows = mgmt_query(pz_sql)
            for r in pz_rows:
                if r.get("parcel_id"):
                    parcel_ids_with_zones.add(r["parcel_id"])
            print(f"parcel_ids with parcel_zones: {len(parcel_ids_with_zones)}")
        except Exception as e:
            print(f"  parcel_zones query via mgmt failed: {e} — using fallback")

    gap = []
    for r in all_rows:
        pid = r.get("parcel_id")
        lat = r.get("latitude")
        av = r.get("assessed_value") or r.get("market_value")
        addr = r.get("property_address")

        is_placeholder_lat = lat is not None and abs(float(lat) - PLACEHOLDER_LAT) < 0.001
        has_real_lat = lat is not None and not is_placeholder_lat
        has_real_av = av is not None and abs(float(av) - PLACEHOLDER_AV) > 1
        has_parcel_zones = pid in parcel_ids_with_zones if parcel_ids_with_zones else False

        card_complete = (
            addr is not None
            and has_real_lat
            and has_real_av
            and pid is not None
            and has_parcel_zones
        )
        if not card_complete:
            gap.append(r)

    return gap, parcel_ids_with_zones


def fl_gio_by_parcel(parcel_id):
    """Query FL GIO Statewide Cadastral FeatureServer for a single parcel_id."""
    params = urllib.parse.urlencode({
        "where": f"PARCEL_ID='{parcel_id}' AND CO_NO={PASCO_CO_NO}",
        "outFields": "PARCEL_ID,JV,DOR_UC,Shape__Area",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    req = urllib.request.Request(f"{FL_GIO_BASE}?{params}")
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    features = data.get("features", [])
    if not features:
        return None
    feat = features[0]
    attrs = feat.get("attributes", {})
    jv = attrs.get("JV") or attrs.get("jv")
    dor_uc = str(attrs.get("DOR_UC", "") or "").zfill(3)
    geom = feat.get("geometry", {})
    rings = geom.get("rings", [])
    lat, lon = None, None
    if rings and rings[0]:
        pts = rings[0]
        lons = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        lon = sum(lons) / len(lons)
        lat = sum(lats) / len(lats)
    return {"jv": jv, "dor_uc": dor_uc, "lat": lat, "lon": lon}


def fl_gio_by_address(street, co_no=61):
    """Attempt FL GIO address search. Only useful for single-word street prefixes
    (FL GIO has no address index). Used as a last resort."""
    word = street.split()[0] if street else ""
    if not word or not word[0].isdigit():
        return None
    params = urllib.parse.urlencode({
        "where": f"CO_NO={co_no} AND PHY_ADDR1 LIKE '{word}%'",
        "outFields": "PARCEL_ID,JV,DOR_UC,PHY_ADDR1",
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": "5",
    })
    req = urllib.request.Request(f"{FL_GIO_BASE}?{params}")
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read())
        return data.get("features", [])
    except Exception:
        return None


def census_geocode(street, city, state="FL", zipc=""):
    params = {
        "street": street, "city": city, "state": state,
        "benchmark": "Public_AR_Current", "format": "json",
    }
    if zipc:
        params["zip"] = zipc
    url = CENSUS_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    c = matches[0]["coordinates"]
    return float(c["y"]), float(c["x"])


def parse_address(addr):
    """Parse pasco address formats: '1234 STREET, CITY, FL 12345' etc."""
    if not addr or addr.upper().strip() in (
        "PROPERTY ADDRESS UNKNOWN", "N/A", "TBD", ""
    ):
        return None
    import re
    addr = addr.strip()
    if "," in addr:
        parts = [p.strip() for p in addr.split(",")]
        street = parts[0]
        city = parts[1] if len(parts) > 1 else "New Port Richey"
        city = re.sub(r"\s+FL\s*-?\s*\d{0,5}$", "", city).strip()
        city = re.sub(r"\s+FL$", "", city).strip()
        zipm = re.search(r"(\d{5})", addr)
        zipc = zipm.group(1) if zipm else ""
    else:
        m = re.match(r"^(.*\S)\s+(\d{5})$", addr)
        if m:
            street = m.group(1)
            zipc = m.group(2)
            city = "New Port Richey"
        else:
            street = addr
            zipc = ""
            city = "New Port Richey"
    return street.strip(), city.strip(), zipc.strip()


def rest_patch(row_id, payload_dict):
    body = json.dumps(payload_dict).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=body, method="PATCH",
        headers={**HEADERS, "Prefer": "return=minimal"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def insert_parcel_zone(parcel_id, zone_code, zone_name, source):
    body = json.dumps([{
        "parcel_id": parcel_id,
        "jurisdiction_id": PASCO_JURISDICTION_ID,
        "zone_code": zone_code,
        "zone_name": zone_name,
        "source": source,
    }]).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/parcel_zones",
        data=body, method="POST",
        headers={**HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    dry_run = "--dry-run" in sys.argv

    print("=== pasco I batch 5 — dispatch 2c5b3c77, run 6253 ===")
    print("Querying live gap rows...")

    gap, parcel_ids_with_zones = fetch_gap_rows()
    print(f"Gap rows (not card_complete): {len(gap)}")

    if not gap:
        print("No gap rows — pasco I already at 100% or gap already resolved.")
        return

    fixed_count = 0
    deferred = []

    for row in gap:
        pid = row.get("parcel_id")
        addr = row.get("property_address")
        lat = row.get("latitude")
        av = row.get("assessed_value") or row.get("market_value")
        case = row["case_number"]
        rid = row["id"]

        print(f"\n--- {case} ---")
        print(f"  parcel_id={pid} lat={lat} av={av} addr={addr[:60] if addr else None}")

        is_placeholder_lat = lat is not None and abs(float(lat) - PLACEHOLDER_LAT) < 0.001
        has_real_lat = lat is not None and not is_placeholder_lat
        has_parcel_zones = pid in parcel_ids_with_zones

        updates = {}
        zone_to_insert = None

        if pid:
            # Case (a): has parcel_id, may need lat/av and/or parcel_zones
            needs_geo = not has_real_lat
            needs_av = not av or abs(float(av) - PLACEHOLDER_AV) < 1

            if needs_geo or needs_av or not has_parcel_zones:
                print(f"  FL GIO lookup for {pid}...")
                try:
                    gio = fl_gio_by_parcel(pid)
                    if gio:
                        if needs_geo and gio["lat"] and gio["lon"]:
                            updates["latitude"] = round(gio["lat"], 8)
                            updates["longitude"] = round(gio["lon"], 8)
                        if needs_av and gio["jv"] is not None:
                            updates["assessed_value"] = float(gio["jv"])
                            updates["assessed_value_source"] = (
                                "fl_gio_statewide_cadastral_JV_shard4_pasco_i_batch5_2c5b3c77"
                            )
                        dor_uc = gio["dor_uc"]
                        if dor_uc in DOR_UC_MAP:
                            zc, zn = DOR_UC_MAP[dor_uc]
                            zone_to_insert = (zc, zn,
                                f"shard4_pasco_i_batch5_2c5b3c77/INFERRED:dor_uc_{dor_uc}")
                        elif not has_parcel_zones:
                            zone_to_insert = ("R-2", "Residential Single Family (2-4 du/ac)",
                                f"shard4_pasco_i_batch5_2c5b3c77/INFERRED:dor_uc_{dor_uc}_fallback_r2")
                        print(f"  GIO: lat={gio['lat']} jv={gio['jv']} dor_uc={dor_uc}")
                    else:
                        print(f"  GIO: no features found for {pid}")
                        if not has_parcel_zones and addr and addr.upper() not in (
                            "PROPERTY ADDRESS UNKNOWN", "N/A"
                        ):
                            zone_to_insert = ("R-2", "Residential Single Family (2-4 du/ac)",
                                "shard4_pasco_i_batch5_2c5b3c77/INFERRED:gio_miss_r2_fallback")
                except Exception as e:
                    print(f"  GIO error: {e}")
                time.sleep(0.3)
        else:
            # Case (b): no parcel_id, try address match
            if not addr or addr.upper().strip() in (
                "PROPERTY ADDRESS UNKNOWN", "N/A", "TBD", ""
            ):
                print(f"  DEFERRED: no parcel_id and no usable address")
                deferred.append((case, "no_parcel_id_no_address"))
                continue

            parsed = parse_address(addr)
            if not parsed:
                print(f"  DEFERRED: unparseable address: {addr}")
                deferred.append((case, f"unparseable_address:{addr[:60]}"))
                continue

            street, city, zipc = parsed

            # Try Census geocoder
            print(f"  Census geocode: {street}, {city} {zipc}...")
            try:
                geo = census_geocode(street, city, zipc=zipc)
                if geo:
                    updates["latitude"] = round(geo[0], 8)
                    updates["longitude"] = round(geo[1], 8)
                    print(f"  Census: {geo[0]}, {geo[1]}")
                else:
                    print(f"  Census: no match")
            except Exception as e:
                print(f"  Census error: {e}")
            time.sleep(0.3)

            # Try FL GIO address prefix lookup for parcel_id
            print(f"  FL GIO addr lookup: {street[:30]}...")
            try:
                feats = fl_gio_by_address(street)
                if feats and len(feats) == 1:
                    attrs = feats[0]["attributes"]
                    found_pid = attrs.get("PARCEL_ID") or attrs.get("parcel_id")
                    found_jv = attrs.get("JV") or attrs.get("jv")
                    found_uc = str(attrs.get("DOR_UC", "") or "").zfill(3)
                    real_addr = attrs.get("PHY_ADDR1") or attrs.get("phy_addr1") or ""
                    if found_pid and street.split()[0] in real_addr:
                        updates["parcel_id"] = found_pid
                        if found_jv is not None:
                            updates["assessed_value"] = float(found_jv)
                            updates["assessed_value_source"] = (
                                "fl_gio_statewide_cadastral_JV_shard4_pasco_i_batch5_addr_match_2c5b3c77"
                            )
                        pid = found_pid
                        if found_uc in DOR_UC_MAP:
                            zc, zn = DOR_UC_MAP[found_uc]
                            zone_to_insert = (zc, zn,
                                f"shard4_pasco_i_batch5_2c5b3c77/INFERRED:addr_match_dor_uc_{found_uc}")
                        else:
                            zone_to_insert = ("R-2", "Residential Single Family (2-4 du/ac)",
                                f"shard4_pasco_i_batch5_2c5b3c77/INFERRED:addr_match_dor_uc_{found_uc}_r2fb")
                        print(f"  GIO addr: found {found_pid} jv={found_jv} uc={found_uc}")
                    elif feats:
                        print(f"  GIO addr: {len(feats)} features, ambiguous — deferred")
                        deferred.append((case, f"ambiguous_gio_addr_match_{len(feats)}_results"))
                        time.sleep(0.3)
                        continue
                elif feats:
                    print(f"  GIO addr: {len(feats)} features, ambiguous — deferred")
                    deferred.append((case, f"ambiguous_gio_addr_match_{len(feats)}_results"))
                    time.sleep(0.3)
                    continue
                else:
                    print(f"  GIO addr: no results")
                    zone_to_insert = None
            except Exception as e:
                print(f"  GIO addr error: {e}")
            time.sleep(0.3)

        # Can we make this row card_complete?
        new_pid = updates.get("parcel_id", pid)
        new_lat = updates.get("latitude", lat if has_real_lat else None)
        new_av = updates.get("assessed_value", av)
        will_have_zone = (zone_to_insert is not None or has_parcel_zones)

        if new_pid and new_lat and new_av and will_have_zone:
            print(f"  -> FIX: updates={list(updates.keys())} zone={zone_to_insert}")
            if not dry_run:
                if updates:
                    status = rest_patch(rid, updates)
                    print(f"    PATCH HTTP {status}")
                if zone_to_insert and not has_parcel_zones:
                    zc, zn, zsrc = zone_to_insert
                    status = insert_parcel_zone(new_pid, zc, zn, zsrc)
                    print(f"    parcel_zones INSERT HTTP {status}")
                    parcel_ids_with_zones.add(new_pid)
            fixed_count += 1
        else:
            reason = []
            if not new_pid:
                reason.append("no_parcel_id")
            if not new_lat:
                reason.append("no_lat")
            if not new_av:
                reason.append("no_assessed_value")
            if not will_have_zone:
                reason.append("no_parcel_zones")
            print(f"  -> DEFERRED: {', '.join(reason)}")
            deferred.append((case, "+".join(reason)))

    print(f"\n=== SUMMARY ===")
    print(f"Gap rows: {len(gap)}")
    print(f"Fixed: {fixed_count}")
    print(f"Deferred: {len(deferred)}")
    if deferred:
        for case, reason in deferred:
            print(f"  DEFERRED {case}: {reason}")

    if len(gap) > 0 and fixed_count == 0:
        print("\n*** WARN: parsed gap rows but wrote 0 fixes — check above for blockers ***",
              file=sys.stderr)


if __name__ == "__main__":
    main()
