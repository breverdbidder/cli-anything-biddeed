#!/usr/bin/env python3
"""GOLD STANDARD shard3, county=st_lucie: E/I zoning+geo backfill.

Forked from scripts/gold_standard_shard7_stlucie_cdi_fix.py (same live
endpoints, same fallback order: unincorporated -> fort_pierce ->
port_st_lucie spatial). PostgREST only.

TARGET SET 1 (8 rows promoted to matched_clean by
gold_standard_shard3_stlucie_cd_ajax_harvest.py, all already carry
parcel_id + property_address + assessed_value, missing only lat/long and
zone_code link):
  2025CC004353 (parcel_id 171578)
  2025CC005297 (parcel_id 59352)
  26-009  (parcel_id 1312-701-0085-000-2)
  26-017  (parcel_id 3420-660-1849-000-7)
  26-024  (parcel_id 3420-515-0259-000-0)
  26-029  (parcel_id 2404-510-0053-000-8)
  26-034  (parcel_id 3312-700-0199-000-7)
  26-045  (parcel_id 3420-720-0488-000-4)

Method per parcel:
  1. Geocode property_address via US Census Bureau geocoder (free, no key).
  2. Zoning lookup: try unincorporated (Parcel_num undashed direct match),
     then fort_pierce (Parcel_Num undashed direct match), then Port St
     Lucie spatial point-in-polygon using the geocoded lat/lon.
  3. Insert parcel_zones row (source tagged arcgis_live_lookup_shard3_stlucie).
  4. PATCH multi_county_auctions.latitude/longitude where missing.

TARGET SET 2 (address-based parcel_id resolution attempt via PA ArcGIS
SiteAddress match, for the 2 rows that have a real address but no
parcel_id): 2024CA000958 ("436 SW CRAWFISH DR, PORT SAINT LUCIE , FL-
34953"), 2025CA001086 ("2306 CANOE CREEK LN, FORT PIERCE, FL- 34981" --
already has real geo, only missing parcel_id/zone).
If SiteAddress LIKE match resolves a ParcelID, backfill parcel_id (undashed)
onto MCA, then attempt zoning same as above (geocoding if geo missing).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BASE = f"{SB_URL}/rest/v1"

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

HEADERS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}

UNINC_URL = "https://slcgis.stlucieco.gov/hosting/rest/services/LandUse/Zoning/MapServer/0"
FTPIERCE_URL = "https://slcgis.stlucieco.gov/hosting/rest/services/LandUse/ForttPierceZoningFLU/MapServer/0"
PSL_ZONING_URL = "https://services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/Zoning/FeatureServer/1"
PA_URL = "https://map.paslc.gov/arcgis/rest/services/PROD/SLCPA_PublicParcels/MapServer/0"

JURISDICTIONS = {"unincorporated": 1400, "fort_pierce": 971, "port_st_lucie": 953}

# TARGET SET 1: case_number -> parcel_id (as stored on MCA row, may be dashed already)
TARGET_SET_1 = {
    "2025CC004353": "171578",
    "2025CC005297": "59352",
    "26-009": "1312-701-0085-000-2",
    "26-017": "3420-660-1849-000-7",
    "26-024": "3420-515-0259-000-0",
    "26-029": "2404-510-0053-000-8",
    "26-034": "3312-700-0199-000-7",
    "26-045": "3420-720-0488-000-4",
}

TARGET_SET_2_CASES = ["2024CA000958", "2025CA001086"]


def ts():
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table, params):
    url = f"{BASE}/{table}?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  GET {table} ERROR {e.code}: {e.read().decode()}")
        return []


def sb_patch(table, filters, data):
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={**HEADERS, "Prefer": "return=minimal"}, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_post(table, rows, prefer="return=representation"):
    url = f"{BASE}/{table}"
    body = json.dumps(rows).encode()
    req = urllib.request.Request(url, data=body, headers={**HEADERS, "Prefer": prefer}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def undash(pid):
    return re.sub(r"[^0-9]", "", pid or "")


def geocode(address):
    params = {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read())
        matches = res.get("result", {}).get("addressMatches", [])
        if matches:
            c = matches[0]["coordinates"]
            return c["y"], c["x"]
    except Exception as e:
        log(f"    geocode ERROR for {address!r}: {e}")
    return None


def arcgis_query(base_url, where, out_fields="*", geometry=None):
    params = {"where": where, "outFields": out_fields, "returnGeometry": "false", "f": "json"}
    if geometry:
        params.update(geometry)
    url = base_url + "/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def try_zoning(pid_undashed, lat, lon):
    """Returns (zone_code, zone_name, jurisdiction_id, source_tag) or None."""
    res = arcgis_query(UNINC_URL, f"Parcel_num = '{pid_undashed}'", "Parcel_num,Zoned")
    feats = res.get("features", [])
    if feats:
        a = feats[0]["attributes"]
        return a.get("Zoned"), None, JURISDICTIONS["unincorporated"], "arcgis_live_lookup_shard3_stlucie_unincorporated"

    res = arcgis_query(FTPIERCE_URL, f"Parcel_Num = '{pid_undashed}'", "Parcel_Num,Zoning,ZoningDesc")
    feats = res.get("features", [])
    if feats:
        a = feats[0]["attributes"]
        return a.get("Zoning"), a.get("ZoningDesc"), JURISDICTIONS["fort_pierce"], "arcgis_live_lookup_shard3_stlucie_fort_pierce"

    if lat is not None and lon is not None:
        geometry = {
            "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        }
        res = arcgis_query(PSL_ZONING_URL, "1=1", "ZOLEGEND,ZONING,ZO_ID", geometry)
        feats = res.get("features", [])
        if feats:
            a = feats[0]["attributes"]
            return a.get("ZOLEGEND"), a.get("ZONING"), JURISDICTIONS["port_st_lucie"], "arcgis_live_lookup_shard3_stlucie_port_st_lucie_spatial"
    return None


def dashify(pid_undashed):
    p = pid_undashed
    if len(p) != 15:
        return None
    return f"{p[0:4]}-{p[4:7]}-{p[7:11]}-{p[11:14]}-{p[14:15]}"


def main():
    today = time.strftime("%Y%m%d", time.gmtime())
    zoning_inserted = 0
    geo_backfilled = 0
    address_lookups_resolved = 0
    residual = []

    log("=== TARGET SET 1: geo + zoning for 8 already-parcel-linked rows ===")
    mca_rows = sb_get(
        "multi_county_auctions",
        "county=eq.st_lucie&case_number=in.(" + ",".join(urllib.parse.quote(c) for c in TARGET_SET_1) + ")"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude",
    )
    by_case = {r["case_number"]: r for r in mca_rows}

    insert_rows = []
    for case, expected_pid in TARGET_SET_1.items():
        row = by_case.get(case)
        if not row:
            log(f"  {case}: MCA row not found -- skipping")
            residual.append({"case_number": case, "reason": "MCA row not found in TARGET SET 1 re-fetch"})
            continue
        addr = row.get("property_address")
        lat, lon = row.get("latitude"), row.get("longitude")
        if (lat is None or lon is None) and addr:
            g = geocode(addr)
            if g:
                lat, lon = g
                status, _ = sb_patch("multi_county_auctions", f"id=eq.{row['id']}",
                                      {"latitude": lat, "longitude": lon})
                log(f"  {case}: geocoded lat={lat} lon={lon} -> PATCH HTTP {status}")
                geo_backfilled += 1
            else:
                log(f"  {case}: geocode NO MATCH for {addr!r} -- leaving lat/lon NULL (honest gap)")

        # ArcGIS layers key on the undashed form (Parcel_num/Parcel_Num), but
        # parcel_zones must be inserted with parcel_id in WHATEVER format
        # multi_county_auctions.parcel_id already uses for this row -- the
        # gold-standard card view joins on raw string equality, no
        # normalization. Do NOT store the undashed form if the MCA row's
        # parcel_id is dashed (verified live bug this session: v3 of this
        # script inserted undashed and silently failed the E/I join for 6
        # tax_deed rows until manually corrected).
        mca_pid_raw = row.get("parcel_id") or expected_pid
        pid_undashed = undash(mca_pid_raw)
        zres = try_zoning(pid_undashed, lat, lon)
        if zres:
            zone_code, zone_name, jur_id, source_tag = zres
            if zone_code:
                insert_rows.append({
                    "parcel_id": mca_pid_raw,
                    "jurisdiction_id": jur_id,
                    "zone_code": zone_code,
                    "zone_name": zone_name,
                    "source": f"{source_tag}_{today}",
                })
                log(f"  {case}: ZONE {zone_code} via {source_tag}")
            else:
                log(f"  {case}: zoning layer matched but zone_code empty -- honest gap")
                residual.append({"case_number": case, "reason": "zoning layer matched but zone_code field empty"})
        else:
            log(f"  {case}: NO ZONING COVERAGE in any live layer -- honest gap")
            residual.append({"case_number": case, "reason": "no zoning layer match (unincorporated/fort_pierce/PSL spatial all missed)"})
        time.sleep(0.3)

    if insert_rows:
        status, body = sb_post("parcel_zones", insert_rows, prefer="return=representation")
        log(f"  POST parcel_zones ({len(insert_rows)} rows): HTTP {status}")
        if status not in (200, 201):
            log(f"  BODY: {body}")
        else:
            zoning_inserted += len(insert_rows)

    log("=== TARGET SET 2: address-based parcel_id resolution ===")
    mca2 = sb_get(
        "multi_county_auctions",
        "county=eq.st_lucie&case_number=in.(" + ",".join(TARGET_SET_2_CASES) + ")"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude",
    )
    insert_rows_2 = []
    for row in mca2:
        case = row["case_number"]
        addr = row.get("property_address")
        if not addr:
            log(f"  {case}: no address on file -- cannot attempt lookup")
            residual.append({"case_number": case, "reason": "no property_address to look up"})
            continue
        # normalize: "436 SW CRAWFISH DR, PORT SAINT LUCIE , FL- 34953" -> street only for LIKE
        street = addr.split(",")[0].strip()
        street_esc = street.replace("'", "''")
        try:
            res = arcgis_query(PA_URL, f"SiteAddress LIKE '{street_esc}%'",
                                "ParcelID,AccountNumber,SiteAddress,JustMarketValue", )
        except Exception as e:
            log(f"  {case}: PA lookup ERROR {e}")
            residual.append({"case_number": case, "reason": f"PA ArcGIS query error: {e}"})
            continue
        feats = res.get("features", [])
        if not feats:
            log(f"  {case}: PA SiteAddress NO MATCH for {street!r} -- honest gap")
            residual.append({"case_number": case, "reason": f"PA ArcGIS SiteAddress LIKE '{street}%' returned 0 features"})
            continue
        a = feats[0]["attributes"]
        dashed_pid = a.get("ParcelID")
        pid_undashed = undash(dashed_pid)
        log(f"  {case}: PA MATCH ParcelID={dashed_pid} SiteAddress={a.get('SiteAddress')!r} JustMarketValue={a.get('JustMarketValue')}")

        patch_body = {"parcel_id": pid_undashed}
        if not row.get("assessed_value") and a.get("JustMarketValue"):
            patch_body["market_value"] = a.get("JustMarketValue")
        status, _ = sb_patch("multi_county_auctions", f"id=eq.{row['id']}", patch_body)
        log(f"  {case}: PATCH parcel_id/market_value HTTP {status}")
        address_lookups_resolved += 1
        # MCA row now stores pid_undashed (set just above) -- parcel_zones
        # insert below must match that exact string, not a different format.

        lat, lon = row.get("latitude"), row.get("longitude")
        if (lat is None or lon is None):
            g = geocode(addr)
            if g:
                lat, lon = g
                status, _ = sb_patch("multi_county_auctions", f"id=eq.{row['id']}",
                                      {"latitude": lat, "longitude": lon})
                log(f"  {case}: geocoded lat={lat} lon={lon} -> PATCH HTTP {status}")
                geo_backfilled += 1

        zres = try_zoning(pid_undashed, lat, lon)
        if zres:
            zone_code, zone_name, jur_id, source_tag = zres
            if zone_code:
                insert_rows_2.append({
                    "parcel_id": pid_undashed,
                    "jurisdiction_id": jur_id,
                    "zone_code": zone_code,
                    "zone_name": zone_name,
                    "source": f"{source_tag}_{today}",
                })
                log(f"  {case}: ZONE {zone_code} via {source_tag}")
        else:
            log(f"  {case}: NO ZONING COVERAGE in any live layer -- honest gap")
            residual.append({"case_number": case, "reason": "parcel_id resolved but no zoning layer match"})
        time.sleep(0.3)

    if insert_rows_2:
        status, body = sb_post("parcel_zones", insert_rows_2, prefer="return=representation")
        log(f"  POST parcel_zones ({len(insert_rows_2)} rows): HTTP {status}")
        if status not in (200, 201):
            log(f"  BODY: {body}")
        else:
            zoning_inserted += len(insert_rows_2)

    print("\n=== SUMMARY ===")
    print(json.dumps({
        "zoning_rows_inserted": zoning_inserted,
        "geo_rows_backfilled": geo_backfilled,
        "address_based_parcel_lookups_resolved": address_lookups_resolved,
        "residual": residual,
    }, indent=2))


if __name__ == "__main__":
    main()
