#!/usr/bin/env python3
"""Gold Standard alachua letter I (card_complete) fix -- 3rd generation.
Continues the proven pattern from scripts/alachua-I_fix.py and
scripts/alachua-I_fix2.py (same ArcGIS Parcels35_view FeatureServer, same
check-then-insert idempotent convention, same density_regulated=false
"avoid the G-regression trap" rule when no discoverable numeric standard).

Target rows (2 untried rows, confirmed live via PostgREST just before this
script was written -- NOT touched by alachua-I_fix.py or alachua-I_fix2.py):

  01 2025 CA 003160 (60710aa0-4d96-4b1a-aeae-c46f059067a4) parcel 06014-010-029
    -- property_address/latitude/longitude/assessed_value ALL already
       populated on multi_county_auctions. Missing ONLY the parcel_zones
       link. ArcGIS: JurisNo=300 (Gainesville, CityDescription=GAINESVILLE)
       -> jurisdiction_id=915 (already mapped), ZONEDISTRICT=SF
       ("Single Family"). zoning_districts row for (915, 'SF') ALREADY
       EXISTS (id=9155) -- only parcel_zones needs inserting.

  01 2025 CA 002954 (600b4647-204d-4be2-a414-e45b004e4572) parcel 19567-000-000
    -- property_address/assessed_value already populated; latitude/longitude
       are NULL (confirmed live -- prior recon's NULL claim for
       assessed_value did not hold live, but geo backfill is still needed).
       ArcGIS: JurisNo=400 (Hawthorne, CityDescription=HAWTHORNE) ->
       jurisdiction_id=979 (looked up live via `jurisdictions` table --
       NEW mapping, not present in either prior fix script's
       JURIS_NO_TO_ID), ZONEDISTRICT=RSF-2 ("Residential Single Family
       (RSF-2)"). No existing zoning_districts row for (979, 'RSF-2') --
       needs both zoning_districts + parcel_zones insert. Centroid lat/lon
       backfilled from the same ArcGIS geometry (outSR=4326, ring-average
       centroid -- identical method to alachua-I_fix.py).

Source (VERIFIED live this session): Alachua County Property Appraiser
ArcGIS FeatureServer (Parcels35_view), same layer used by both prior scripts.

Idempotent: every field write is gated on the current DB value being NULL at
PATCH time. zoning_districts / parcel_zones inserts use POST with
Prefer: resolution=ignore-duplicates so re-running is a no-op, not an error.

Usage: python3 scripts/alachua-I_fix3.py
"""
import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ARCGIS_BASE = ("https://services1.arcgis.com/MiBZ4u97DWldovjI/arcgis/rest/services/"
               "Parcels35_view/FeatureServer/0/query")

TARGETS = [
    {"id": "60710aa0-4d96-4b1a-aeae-c46f059067a4", "case_number": "01 2025 CA 003160",
     "parcel_id": "06014-010-029"},
    {"id": "600b4647-204d-4be2-a414-e45b004e4572", "case_number": "01 2025 CA 002954",
     "parcel_id": "19567-000-000"},
]

# JurisNo -> jurisdictions.id. 300 (Gainesville) confirmed in prior scripts;
# 400 (Hawthorne) -> 979 looked up live via `jurisdictions?county=eq.Alachua`
# this session (new mapping).
JURIS_NO_TO_ID = {300: 915, 400: 979}


def _with_retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 409 or i == attempts - 1:
                raise
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def rest_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body, timeout=90):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_post_ignore_dupes(path, body, timeout=90):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json",
                     "Prefer": "resolution=ignore-duplicates,return=representation"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body_txt = r.read()
            return json.loads(body_txt) if body_txt else []
    return _with_retry(_do)


def arcgis_query_parcel(parcel_id):
    params = {
        "where": f"parcel='{parcel_id}'",
        "outFields": "parcel,ZONECODE,ZONEDISTRICT,ZoneDefin,FluDefin,JurisNo,CityDescription,JustValue",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = f"{ARCGIS_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    feats = data.get("features") or []
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    geom = feats[0].get("geometry") or {}
    centroid = None
    rings = geom.get("rings")
    if rings:
        ring = rings[0]
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        centroid = (sum(ys) / len(ys), sum(xs) / len(xs))  # (lat, lon)
    return {"attrs": attrs, "centroid": centroid}


def main():
    ids = ",".join(t["id"] for t in TARGETS)
    current_rows = rest_get(
        f"multi_county_auctions?id=in.({ids})"
        f"&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        f"assessed_value,market_value")
    current_by_id = {r["id"]: r for r in current_rows}

    print(f"alachua-I fix3: {len(TARGETS)} target rows")

    mca_patched = 0
    zoning_districts_inserted = 0
    parcel_zones_inserted = 0
    skipped_no_fix = []

    for t in TARGETS:
        rid, cn, pid = t["id"], t["case_number"], t["parcel_id"]
        row = current_by_id.get(rid)
        if row is None:
            skipped_no_fix.append({"id": rid, "case_number": cn, "reason": "row not found live"})
            print(f"  {cn}: SKIP -- row not found in multi_county_auctions at run time")
            continue

        gis = arcgis_query_parcel(pid)
        if gis is None:
            skipped_no_fix.append({"id": rid, "case_number": cn, "reason": "ArcGIS returned no feature"})
            print(f"  {cn} ({pid}): SKIP -- ArcGIS returned no feature")
            continue

        # --- multi_county_auctions patch: only currently-NULL fields ---
        patch = {}
        reasons = []
        if row.get("latitude") is None and gis["centroid"]:
            lat, lon = gis["centroid"]
            patch["latitude"] = round(lat, 6)
            patch["longitude"] = round(lon, 6)
            reasons.append(f"latitude/longitude={round(lat,6)},{round(lon,6)} (ArcGIS Parcels35_view centroid, outSR=4326)")

        if row.get("assessed_value") is None and row.get("market_value") is None:
            jv = gis["attrs"].get("JustValue")
            if jv is not None and jv > 0:
                patch["assessed_value"] = jv
                reasons.append(f"assessed_value={jv} (ArcGIS Parcels35_view JustValue)")

        if patch:
            rest_patch(f"multi_county_auctions?id=eq.{rid}", patch)
            mca_patched += 1
            print(f"  PATCHED multi_county_auctions {rid} ({cn}): {reasons}")
        else:
            print(f"  {cn} ({pid}): no card-field patch needed (already complete)")

        # --- zoning_districts + parcel_zones insert ---
        juris_no = gis["attrs"].get("JurisNo")
        zone_code = gis["attrs"].get("ZONEDISTRICT")
        zone_defin = gis["attrs"].get("ZoneDefin") or zone_code
        juris_id = JURIS_NO_TO_ID.get(juris_no)
        if juris_id is None or not zone_code:
            skipped_no_fix.append({"id": rid, "case_number": cn,
                                    "reason": f"unmapped JurisNo={juris_no} or missing zone_code"})
            print(f"  {cn} ({pid}): SKIP zoning link -- unmapped JurisNo={juris_no} "
                  f"(CityDescription={gis['attrs'].get('CityDescription')!r}) or no zone_code")
            continue

        existing_zd = rest_get(
            f"zoning_districts?jurisdiction_id=eq.{juris_id}&code=eq.{urllib.parse.quote(zone_code)}&select=id")
        if not existing_zd:
            zd_body = [{
                "jurisdiction_id": juris_id,
                "code": zone_code,
                "name": zone_defin,
                "category": "residential",
                "far_regulated": False,
                "density_regulated": False,  # N/A -- no discoverable numeric standard, avoids G-regression trap
                "pk1000_regulated": False,
            }]
            inserted = rest_post_ignore_dupes("zoning_districts", zd_body)
            if inserted:
                zoning_districts_inserted += 1
                print(f"  INSERTED zoning_districts (jurisdiction_id={juris_id}, code={zone_code})")
        else:
            print(f"  zoning_districts (jurisdiction_id={juris_id}, code={zone_code}) already exists -- skip insert")

        existing_pz = rest_get(f"parcel_zones?parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
        if not existing_pz:
            source = (f"{ARCGIS_BASE.split('?')[0]} (parcel={pid}, "
                      f"ZONECODE={gis['attrs'].get('ZONECODE')}, ZONEDISTRICT={zone_code}, "
                      f"JurisNo={juris_no}/{gis['attrs'].get('CityDescription')})")
            pz_body = [{
                "parcel_id": pid,
                "jurisdiction_id": juris_id,
                "zone_code": zone_code,
                "zone_name": zone_defin,
                "source": source,
            }]
            inserted = rest_post_ignore_dupes("parcel_zones", pz_body)
            if inserted:
                parcel_zones_inserted += 1
                print(f"  INSERTED parcel_zones (parcel_id={pid}, zone_code={zone_code})")
        else:
            print(f"  parcel_zones (parcel_id={pid}) already exists -- skip insert")

        time.sleep(0.3)

    print(json.dumps({
        "mca_rows_patched": mca_patched,
        "zoning_districts_inserted": zoning_districts_inserted,
        "parcel_zones_inserted": parcel_zones_inserted,
        "skipped": skipped_no_fix,
    }, indent=2, default=str))

    total_writes = mca_patched + zoning_districts_inserted + parcel_zones_inserted
    if total_writes == 0:
        raise SystemExit(
            "FAIL-LOUD: fetched/parsed target rows but wrote 0 rows across all tables. "
            "This is a blocker, not a silent no-op.")

    return {
        "mca_rows_patched": mca_patched,
        "zoning_districts_inserted": zoning_districts_inserted,
        "parcel_zones_inserted": parcel_zones_inserted,
    }


if __name__ == "__main__":
    main()
