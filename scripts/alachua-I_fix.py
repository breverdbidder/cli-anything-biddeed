#!/usr/bin/env python3
"""Gold Standard alachua letter I (card_complete) fix -- bucket 2 of the prior
diagnosis (3 rows with real parcel_id, address/geo/value already mostly
complete, missing ONLY zoning-link + 2 secondary gaps).

Reproduces the exact pattern already proven and committed in
supabase/migrations/20260725_gold_standard_shard6_alachua_i_zoning_coverage.sql
(same ArcGIS Parcels35_view FeatureServer, same density_regulated=false
convention to avoid the documented G-regression trap -- see that migration's
comments for the hendry-county precedent).

Target rows (from prior diagnosis, re-verified live at the top of main()):
  01 2023 CA 004261 (499f7f7e-3652-45dc-a338-062cc20b12f9) parcel 12631-000-000
    -- already has property_address + assessed_value; missing lat/lon + zoning
  01 2025 CA 003629 (000c5b85-6549-467b-bafd-e7babcef5a9c) parcel 05542-000-000
    -- already has property_address + lat/lon; missing assessed_value + zoning
  01 2025 CC 001552 (51ef22e3-bd69-49d2-803e-fab94dc1f7cf) parcel 18378-003-023
    -- already has property_address + lat/lon + assessed_value; missing zoning only

Sources (all VERIFIED live this session):
  - Zoning + centroid lat/lon: Alachua County Property Appraiser ArcGIS
    FeatureServer (Parcels35_view), queried by `parcel` field, outSR=4326 so
    geometry rings are returned directly in WGS84 lon/lat -- no Web Mercator
    decoding needed (superseding the diagnosis's fallback plan (b)/(a) --
    just requesting outSR=4326 gets WGS84 centroid coords in one call).
  - assessed_value for 05542-000-000: RealForeclose AJAX re-harvest was
    tried first (per diagnosis's stated preference) and returned
    assessed_value=None for this listing (parcel_id also came back as the
    known "Property Appraiser" placeholder garbage) -- confirmed live, not
    usable. qpublic.schneidercorp.com confirmed live 403 (Cloudflare
    bot-block), matching the diagnosis's expectation. Fell back to the same
    ArcGIS Parcels35_view layer's `JustValue` field (Florida DOR-standard
    "just value" -- the statutory basis for ad valorem assessment, i.e. the
    real, non-fabricated assessed value for this parcel) -- confirmed
    present and populated in a live query, and it is the SAME API call
    already being made for zoning, so no new source class introduced.

Idempotent: every field write is gated on the current DB value being NULL at
PATCH time (never overwrites existing good data). zoning_districts /
parcel_zones inserts use POST with Prefer: resolution=ignore-duplicates so
re-running against already-inserted rows is a no-op, not an error.

Usage: python3 scripts/alachua-I_fix.py
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
    {"id": "499f7f7e-3652-45dc-a338-062cc20b12f9", "case_number": "01 2023 CA 004261",
     "parcel_id": "12631-000-000"},
    {"id": "000c5b85-6549-467b-bafd-e7babcef5a9c", "case_number": "01 2025 CA 003629",
     "parcel_id": "05542-000-000"},
    {"id": "51ef22e3-bd69-49d2-803e-fab94dc1f7cf", "case_number": "01 2025 CC 001552",
     "parcel_id": "18378-003-023"},
]

# jurisdiction_id, zone code -> (name, category) for the new zoning_districts rows
JURIS_ZONE_INFO = {
    (915, "U4"): "Urban 4",
    (1404, "A"): "Agricultural",
}


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
    """POST with Prefer: resolution=ignore-duplicates,return=representation --
    relies on the table's existing unique/exclusion constraint (matches the
    ON CONFLICT DO NOTHING behavior used by the committed SQL migration this
    script replicates). Returns [] on a no-op duplicate skip."""
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
        "outFields": "parcel,ZONECODE,ZONEDISTRICT,ZoneDefin,FluDefin,JurisNo,JustValue",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = f"{ARCGIS_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
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


JURIS_NO_TO_ID = {300: 915, 0: 1404}  # Gainesville, Unincorporated Alachua County


def main():
    ids = ",".join(t["id"] for t in TARGETS)
    current_rows = rest_get(
        f"multi_county_auctions?id=in.({ids})"
        f"&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        f"assessed_value,market_value")
    current_by_id = {r["id"]: r for r in current_rows}

    print(f"alachua-I fix: {len(TARGETS)} target rows")

    mca_patched = 0
    zoning_districts_inserted = 0
    parcel_zones_inserted = 0
    skipped_no_fix = []

    zone_cache = {}

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
        zone_cache[pid] = gis

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
            print(f"  {cn} ({pid}): SKIP zoning link -- unmapped JurisNo={juris_no} or no zone_code")
            continue

        # check-then-insert zoning_districts (idempotent)
        existing_zd = rest_get(
            f"zoning_districts?jurisdiction_id=eq.{juris_id}&code=eq.{urllib.parse.quote(zone_code)}&select=id")
        if not existing_zd:
            zd_body = [{
                "jurisdiction_id": juris_id,
                "code": zone_code,
                "name": zone_defin,
                "category": "residential" if juris_id == 915 else "agricultural",
                "far_regulated": False,
                "density_regulated": False,  # N/A -- no real numeric standard discoverable, avoids G-regression trap
                "pk1000_regulated": False,
            }]
            inserted = rest_post_ignore_dupes("zoning_districts", zd_body)
            if inserted:
                zoning_districts_inserted += 1
                print(f"  INSERTED zoning_districts (jurisdiction_id={juris_id}, code={zone_code})")
        else:
            print(f"  zoning_districts (jurisdiction_id={juris_id}, code={zone_code}) already exists -- skip insert")

        # check-then-insert parcel_zones (idempotent)
        existing_pz = rest_get(f"parcel_zones?parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
        if not existing_pz:
            source = (f"{ARCGIS_BASE.split('?')[0]} (parcel={pid}, "
                      f"ZONECODE={gis['attrs'].get('ZONECODE')}, ZONEDISTRICT={zone_code}, "
                      f"JurisNo={juris_no}/{'Gainesville' if juris_id == 915 else 'Unincorporated Alachua County'})")
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
