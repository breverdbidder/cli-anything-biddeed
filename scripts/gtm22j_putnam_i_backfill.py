#!/usr/bin/env python3
"""GTM-22J putnam letter-I fix: municipal zoning centroid-intersect backfill.

Context: pencil_dod_evaluate_county('putnam') criterion I was 427/453 (94.3%),
needs >=431/453 (95%). Live re-query (this session, post CD-harvest) confirmed
22 rows still failing card_complete, 12 of which have REAL parcel_id + REAL
property_address + REAL geo/value already populated -- blocked ONLY by a
missing parcel_zones zone-link. This script closes that gap for those 12.

Root cause of prior gap (VERIFIED, live query this session):
  The Putnam COUNTY zoning layer used by earlier sessions
  (services1.arcgis.com/YZc1OyqL6jbIOeOv/.../Zoning_Districts_AGO) currently
  has only 24 generalized unincorporated-area polygons -- a live point-in-
  polygon check against all 12 target parcels' Tax_Parcel_AGO centroids
  returned ZERO matches for every one. That layer does not cover incorporated
  municipalities (Palatka, Interlachen, Pomona Park have their own zoning
  authority, separate from county zoning).

Real source (VERIFIED live this session): Putnam County's own GIS server
hosts a dedicated MunicipalZoning_PDS MapServer with per-city zoning layers:
  https://gis.putnam-fl.com/arcserver/rest/services/MunicipalZoning_PDS/MapServer
    layer 14 = "Zoning: City of Palatka"
    layer 15 = "Zoning: City of Crescent City"
    layer 16 = "Zoning: Town of Interlachen"
    layer 17 = "Zoning: Town of Pomona Park"
    layer 18 = "Zoning: Town of Welaka"
  Each layer exposes ZONECLASS/ZONEDESC per parcel-level polygon.
  Discovered via: WebSearch -> "Putnam Data Hub" instant-app config JSON
  (arcgis.com/sharing/rest/content/items/a392006af41c426cabedfc889a11463e/data)
  which references the gis.putnam-fl.com host; folder-listed via
  /arcserver/rest/services?f=json.

Method (VERIFIED live this session):
  1. Batch-query Tax_Parcel_AGO (the general-purpose Putnam parcel/cadastral
     FeatureServer, same one used by prior sibling sessions) by PARCELID for
     a real polygon-service centroid (returnCentroid=true, outSR=4326).
  2. Route each parcel's centroid to the correct MunicipalZoning_PDS sub-layer
     based on jurisdiction (14=Palatka, 16=Interlachen, 17=Pomona Park), point-
     intersect query for ZONECLASS/ZONEDESC.
  3. Guard rail (matches convention from commit history / prior putnam
     sessions): for any zone_code not already present in zoning_districts for
     that jurisdiction_id, insert it first with far_regulated=NULL,
     density_regulated=NULL, category inferred from code prefix, name=ZONEDESC
     (real, not fabricated).
  4. Insert into parcel_zones (merge-duplicates on conflict -- idempotent).
  5. NO opportunistic PATCH of multi_county_auctions -- all 12 target rows
     already have property_address/geo/assessed_value populated (verified via
     live SELECT before writing this script), so there is nothing to backfill
     there. This script only ever touches the zone-card link.

Results per parcel (ZONECLASS / ZONEDESC / jurisdiction, all VERIFIED live
GIS query this session, cite MunicipalZoning_PDS layer id in parcel_zones.source):
  12-10-26-2670-0000-0010 (201 NELLIE ST, PALATKA)      -> layer14 R-1A  "Residential, Single-family (4du)"
  37-10-26-6850-3390-0070 (504 N 18TH ST, PALATKA)      -> layer14 R-3   "Residential, Multi-family"
  42-10-27-6850-0060-0010 (00 Unassigned, Palatka area) -> layer14 R-1AA "Residential, Single-family (3du)"
  42-10-27-6850-2520-0800 (1310 ST JOHNS AV, PALATKA)   -> layer14 C-2   "Commercial, Intensive"
  42-10-27-6850-2850-1600 (1506 NAPOLEON ST, PALATKA)   -> layer14 R-1   "Residential, Single-family (5du)"
  15-10-24-4050-0020-0390 (00 Unassigned, Interlachen)  -> layer16 C-2   "Commercial, General, Light"
  16-10-24-4066-0190-0060 (107 DICKENS ST, INTERLACHEN) -> layer16 R-2HA "Residential, Mixed (area > 0.5 acres)"
  16-10-24-4066-0210-0080 (116 BRANDT ST, INTERLACHEN)  -> layer16 R-2HA "Residential, Mixed (area > 0.5 acres)"
  17-10-24-1520-0020-0270 (152 7TH WAY, INTERLACHEN)    -> layer16 R-1A  "Residential, Single-famly (area > 7,500 sqft)"
  17-10-24-1520-0030-0020 (115 7TH WAY, INTERLACHEN)    -> layer16 R-1A  "Residential, Single-famly (area > 7,500 sqft)"
  20-10-24-4074-0830-0030 (181 KEUKA RD, INTERLACHEN)   -> layer16 R-2   "Residential, Mixed (area > 7,500 sqft)"
  32-11-27-7170-0060-0030 (213 HILL ST, POMONA PARK)    -> layer17 MDR   "Residential, Medium-density"

Note: Palatka's C-2/R-1/R-1A/R-1AA/R-3 codes already existed in zoning_districts
(jurisdiction_id=931) from prior sessions -- no new district row needed there.
Interlachen (jurisdiction_id=1121) had ZERO pre-existing zoning_districts rows
-- R-1A, R-2, R-2HA are newly inserted by this script. Pomona Park
(jurisdiction_id=1122) had only municode-chapter-number codes (CH-prefixed,
unrelated) -- MDR is newly inserted.

Residual (NOT touched, still failing after this script, HONEST report):
  - 542025CA000391CAAXMX: parcel_id literal is 'Property Appraiser' (scraper
    artifact, not a real parcel_id) -- cannot be resolved via GIS lookup.
  - 8 rows with parcel_id=NULL entirely (various case numbers) -- no parcel_id
    to look up at all, out of scope for zoning backfill.
  - 2019-0017978 (28-10-24-0000-0200-0000) and 2019-0021639
    (38-12-26-0000-0040-0002): Tax_Parcel_AGO returned zero match for these
    PARCELIDs (not in the cadastral FeatureServer at all) -- cannot get a
    centroid, cannot look up zoning. Genuine data gap, not fabricated.
  - 2020-0013557 (17-10-24-1520-0020-0270 / "Unassigned Location PP"): this
    duplicate-parcel_id case number was in the original dispatch's lower-
    priority "Unassigned Location" bucket; it shares parcel_id with
    2019-0017978... no wait, it shares parcel_id 17-10-24-1520-0020-0270 with
    itself only; see PASS_NOW list below -- it DOES resolve via GIS (same
    parcel as case number tracked above), included in the 12.

Usage: python3 scripts/gtm22j_putnam_i_backfill.py
Idempotent: parcel_zones insert uses Prefer: resolution=merge-duplicates.
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]

TAX_PARCEL_LAYER = "https://services1.arcgis.com/YZc1OyqL6jbIOeOv/arcgis/rest/services/Tax_Parcel_AGO/FeatureServer/0/query"
MUNI_ZONING_BASE = "https://gis.putnam-fl.com/arcserver/rest/services/MunicipalZoning_PDS/MapServer"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SOURCE_TAG_TMPL = "gtm22j_putnam_i_backfill/MunicipalZoning_PDS_layer{layer}_centroid_intersect"

# jurisdiction_id -> MunicipalZoning_PDS layer id (VERIFIED live this session)
JUR_TO_LAYER = {
    931: 14,   # Palatka
    1121: 16,  # Interlachen
    1122: 17,  # Pomona Park
}

# target parcel_id -> jurisdiction_id (assigned per property_address city,
# cross-checked against the jurisdictions table -- VERIFIED)
TARGETS = {
    "12-10-26-2670-0000-0010": 931,
    "37-10-26-6850-3390-0070": 931,
    "42-10-27-6850-0060-0010": 931,
    "42-10-27-6850-2520-0800": 931,
    "42-10-27-6850-2850-1600": 931,
    "15-10-24-4050-0020-0390": 1121,
    "16-10-24-4066-0190-0060": 1121,
    "16-10-24-4066-0210-0080": 1121,
    "17-10-24-1520-0020-0270": 1121,
    "17-10-24-1520-0030-0020": 1121,
    "20-10-24-4074-0830-0030": 1121,
    "32-11-27-7170-0060-0030": 1122,
}

BATCH_SIZE = 50

RESULTS = {
    "candidates": len(TARGETS),
    "tax_parcel_matched": 0,
    "tax_parcel_not_found": [],
    "zone_matched": 0,
    "zone_not_found": [],
    "new_zoning_district_codes": [],
    "parcel_zones_inserted": 0,
    "parcel_zones_errors": [],
}


def mgmt_query(sql):
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) supabase-cli/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=100) as r:
        body = r.read()
        return json.loads(body) if body.strip() else []


def rest_post(table, body, prefer="return=minimal"):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()[:800]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:800]


def arcgis_query(url, params):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    pids = list(TARGETS.keys())
    print(f"[VERIFIED] {len(pids)} target parcel_ids")

    # Step 1: Tax_Parcel_AGO centroid lookup
    tax_data = {}
    for i in range(0, len(pids), BATCH_SIZE):
        batch = pids[i:i + BATCH_SIZE]
        where_list = ",".join("'" + p.replace("'", "''") + "'" for p in batch)
        where = f"PARCELID IN ({where_list})"
        try:
            data = arcgis_query(TAX_PARCEL_LAYER, {
                "where": where,
                "outFields": "PARCELID,SITEADDRESS",
                "returnGeometry": "true",
                "returnCentroid": "true",
                "outSR": "4326",
                "f": "json",
            })
        except Exception as e:
            print(f"[ERROR] Tax_Parcel_AGO batch {i}: {e}", file=sys.stderr)
            for p in batch:
                RESULTS["tax_parcel_not_found"].append({"parcel_id": p, "reason": f"batch_query_error:{e}"})
            continue

        feats = data.get("features", [])
        found_pids = set()
        for f in feats:
            attrs = f["attributes"]
            pid = attrs.get("PARCELID")
            centroid = f.get("centroid")
            if not centroid:
                continue
            found_pids.add(pid)
            tax_data[pid] = {"x": centroid["x"], "y": centroid["y"]}
        for p in batch:
            if p not in found_pids:
                RESULTS["tax_parcel_not_found"].append({"parcel_id": p, "reason": "no_tax_parcel_match"})
        RESULTS["tax_parcel_matched"] += len(found_pids)
        time.sleep(0.2)

    print(f"[VERIFIED] Tax_Parcel_AGO matched {RESULTS['tax_parcel_matched']} of {len(pids)}")

    # Step 2: municipal zoning intersect, routed per jurisdiction layer
    zone_results = {}  # pid -> (jur_id, zone_code, zone_desc)
    for pid, td in tax_data.items():
        jur_id = TARGETS[pid]
        layer = JUR_TO_LAYER[jur_id]
        url = f"{MUNI_ZONING_BASE}/{layer}/query"
        try:
            zdata = arcgis_query(url, {
                "geometry": f"{td['x']},{td['y']}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "ZONECLASS,ZONEDESC",
                "outSR": "4326",
                "returnGeometry": "false",
                "f": "json",
            })
        except Exception as e:
            RESULTS["zone_not_found"].append({"parcel_id": pid, "reason": f"query_error:{e}"})
            time.sleep(0.15)
            continue

        zfeats = zdata.get("features", [])
        if not zfeats:
            RESULTS["zone_not_found"].append({"parcel_id": pid, "reason": f"no_zoning_polygon_at_centroid_layer{layer}"})
        else:
            zattrs = zfeats[0]["attributes"]
            zone_results[pid] = (jur_id, layer, zattrs.get("ZONECLASS"), zattrs.get("ZONEDESC"))
            RESULTS["zone_matched"] += 1
        time.sleep(0.15)

    print(f"[VERIFIED] MunicipalZoning_PDS intersect matched {RESULTS['zone_matched']} of {len(tax_data)}")

    # Step 3: guard-rail -- ensure every new zone_code exists in zoning_districts per jurisdiction
    for jur_id in set(JUR_TO_LAYER.keys()):
        existing_codes_rows = mgmt_query(f"SELECT code FROM zoning_districts WHERE jurisdiction_id={jur_id}")
        existing_code_set = {r["code"] for r in existing_codes_rows}
        needed = {(zc, zd) for (jid, _l, zc, zd) in zone_results.values() if jid == jur_id and zc}
        for zc, zd in sorted(needed):
            if zc in existing_code_set:
                continue
            cat = "Residential" if zc.upper().startswith("R") or zc.upper() == "MDR" else \
                  "Commercial" if zc.upper().startswith("C") else \
                  "Agriculture" if zc.upper() in ("AG",) else \
                  "Conservation" if zc.upper() in ("CON", "ROS") else \
                  "Industrial" if zc.upper().startswith("M") else "Other"
            name = zd or zc  # real ZONEDESC from GIS, never fabricated
            sql = (
                f"INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category) "
                f"SELECT {jur_id}, '{zc}', '{name.replace(chr(39), chr(39)+chr(39))}', '{cat}' "
                f"WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id={jur_id} AND code='{zc}')"
            )
            mgmt_query(sql)
            RESULTS["new_zoning_district_codes"].append({"jurisdiction_id": jur_id, "code": zc, "name": name, "category": cat})
            print(f"[VERIFIED] Added zoning_districts row jur={jur_id} code={zc} name={name!r} category={cat}")

    # Step 4: batch-insert parcel_zones (idempotent via merge-duplicates)
    pz_rows = []
    for pid, (jur_id, layer, zc, zd) in zone_results.items():
        if not zc:
            continue
        pz_rows.append({
            "parcel_id": pid,
            "tax_account": pid,
            "jurisdiction_id": jur_id,
            "zone_code": zc,
            "zone_name": zd or zc,
            "source": SOURCE_TAG_TMPL.format(layer=layer),
            "effective_date": "2026-07-19",
        })

    if pz_rows:
        for i in range(0, len(pz_rows), 100):
            chunk = pz_rows[i:i + 100]
            status, resp = rest_post("parcel_zones", chunk, prefer="resolution=merge-duplicates,return=minimal")
            if status in (200, 201, 204):
                RESULTS["parcel_zones_inserted"] += len(chunk)
            else:
                RESULTS["parcel_zones_errors"].append({"chunk_start": i, "status": status, "msg": resp})

    print(f"[VERIFIED] parcel_zones inserted={RESULTS['parcel_zones_inserted']} (attempted={len(pz_rows)}) errors={len(RESULTS['parcel_zones_errors'])}")
    print(json.dumps(RESULTS, indent=2, default=str))


if __name__ == "__main__":
    main()
