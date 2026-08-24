#!/usr/bin/env python3
"""Gold Standard alachua letter I (card_complete) fix -- 4th generation.
Dispatch 39359e83. Continues the proven pattern from scripts/alachua-I_fix.py,
alachua-I_fix2.py, alachua-I_fix3.py (same ArcGIS Parcels35_view FeatureServer,
same check-then-insert idempotent convention).

Target: 9 rows confirmed live via public.v_auction_property_card for
county=alachua that already have parcel_id + property_address but are
missing zoning_code (parcel_zones link never ran), 3 of which are also
missing assessed_value. Source (VERIFIED live this session, 2026-08-24):
Alachua County Property Appraiser ArcGIS FeatureServer (Parcels35_view),
same layer used by all three prior scripts. Live query for each parcel_id
returned a real feature with JurisNo/ZONEDISTRICT/ZoneDefin/JustValue.

  10498-000-000 -> JurisNo=300 Gainesville -> jurisdiction_id=915 (existing),
                    ZONEDISTRICT=SF (zoning_districts id=9155 already exists)
  04334-024-000 -> JurisNo=0 Unincorporated -> jurisdiction_id=1404 (existing),
                    ZONEDISTRICT=R-1A (zoning_districts id=11782 already exists)
  06650-208-004 -> JurisNo=0 Unincorporated -> jurisdiction_id=1404,
                    ZONEDISTRICT=R-3 (zoning_districts id=13419 already exists)
                    ALSO missing assessed_value -> JustValue=72000
  00206-002-003 -> JurisNo=500 High Springs -> jurisdiction_id=891 (existing
                    jurisdiction, NEW JurisNo mapping -- not present in any
                    prior fix script's JURIS_NO_TO_ID), ZONEDISTRICT=R-1
                    ("Single Family Residential (R-1)") -- NO existing
                    zoning_districts row for (891, 'R-1') -- needs insert
  03307-001-000 -> JurisNo=100 Alachua -> jurisdiction_id=973 (existing),
                    ZONEDISTRICT=RSF-3 (zoning_districts id=7111 already exists)
  04603-005-000 -> JurisNo=0 Unincorporated -> jurisdiction_id=1404,
                    ZONEDISTRICT=A (zoning_districts id=13147 already exists)
                    ALSO missing assessed_value -> JustValue=184692
  14785-000-000 -> JurisNo=300 Gainesville -> jurisdiction_id=915,
                    ZONEDISTRICT=U2 (zoning_districts id=12934 already exists)
                    ALSO missing assessed_value -> JustValue=356520
  18470-009-001 -> JurisNo=0 Unincorporated -> jurisdiction_id=1404,
                    ZONEDISTRICT=A (zoning_districts id=13147 already exists)
  06014-001-008 -> JurisNo=300 Gainesville -> jurisdiction_id=915,
                    ZONEDISTRICT=SF (zoning_districts id=9155 already exists)

Idempotent: every field write is gated on the current DB value being NULL at
PATCH time. zoning_districts / parcel_zones inserts use POST with
Prefer: resolution=ignore-duplicates so re-running is a no-op, not an error.

Usage: python3 scripts/alachua-I_fix4_gold_standard_c39359e83.py
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

TARGET_PARCELS = [
    "10498-000-000", "04334-024-000", "06650-208-004", "00206-002-003",
    "03307-001-000", "04603-005-000", "14785-000-000", "18470-009-001",
    "06014-001-008",
]

# JurisNo -> jurisdictions.id. 300 (Gainesville), 0 (Unincorporated), 100
# (Alachua) confirmed in prior scripts. 500 (High Springs) -> 891 is a NEW
# mapping, looked up live via `jurisdictions?county=eq.Alachua` this session.
JURIS_NO_TO_ID = {300: 915, 0: 1404, 100: 973, 400: 979, 500: 891}


def _with_retry(fn, attempts=5):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 409 or (e.code not in (500, 502, 503, 504) and i > 0) or i == attempts - 1:
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
        "returnGeometry": "false",
        "f": "json",
    }
    url = f"{ARCGIS_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    feats = data.get("features") or []
    if not feats:
        return None
    return feats[0]["attributes"]


def main():
    print(f"alachua-I fix4 (dispatch 39359e83): {len(TARGET_PARCELS)} target parcels")

    mca_patched = 0
    zoning_districts_inserted = 0
    parcel_zones_inserted = 0
    skipped_no_fix = []

    for pid in TARGET_PARCELS:
        rows = rest_get(
            f"multi_county_auctions?parcel_id=eq.{urllib.parse.quote(pid)}&county=eq.alachua"
            f"&select=id,case_number,parcel_id,assessed_value,market_value")
        if not rows:
            skipped_no_fix.append({"parcel_id": pid, "reason": "no multi_county_auctions row found live"})
            print(f"  {pid}: SKIP -- no MCA row found live")
            continue

        attrs = arcgis_query_parcel(pid)
        if attrs is None:
            skipped_no_fix.append({"parcel_id": pid, "reason": "ArcGIS returned no feature"})
            print(f"  {pid}: SKIP -- ArcGIS returned no feature")
            continue

        juris_no = attrs.get("JurisNo")
        zone_code = attrs.get("ZONEDISTRICT")
        zone_defin = attrs.get("ZoneDefin") or zone_code
        juris_id = JURIS_NO_TO_ID.get(juris_no)

        if juris_id is None or not zone_code:
            skipped_no_fix.append({"parcel_id": pid,
                                    "reason": f"unmapped JurisNo={juris_no} or missing zone_code"})
            print(f"  {pid}: SKIP zoning link -- unmapped JurisNo={juris_no} "
                  f"(CityDescription={attrs.get('CityDescription')!r}) or no zone_code")
            continue

        # --- assessed_value patch (only for rows currently NULL) ---
        for row in rows:
            rid = row["id"]
            cn = row["case_number"]
            patch = {}
            if row.get("assessed_value") is None and row.get("market_value") is None:
                jv = attrs.get("JustValue")
                if jv is not None and jv > 0:
                    patch["assessed_value"] = jv
            if patch:
                rest_patch(f"multi_county_auctions?id=eq.{rid}", patch)
                mca_patched += 1
                print(f"  PATCHED multi_county_auctions {rid} ({cn}, {pid}): "
                      f"assessed_value={patch['assessed_value']} (ArcGIS Parcels35_view JustValue)")

        # --- zoning_districts insert (idempotent) ---
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

        # --- parcel_zones insert (idempotent) ---
        existing_pz = rest_get(f"parcel_zones?parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
        if not existing_pz:
            source = (f"{ARCGIS_BASE.split('?')[0]} (parcel={pid}, "
                      f"ZONECODE={attrs.get('ZONECODE')}, ZONEDISTRICT={zone_code}, "
                      f"JurisNo={juris_no}/{attrs.get('CityDescription')})")
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

    result = {
        "mca_rows_patched": mca_patched,
        "zoning_districts_inserted": zoning_districts_inserted,
        "parcel_zones_inserted": parcel_zones_inserted,
        "skipped": skipped_no_fix,
    }
    print(json.dumps(result, indent=2, default=str))

    total_writes = mca_patched + zoning_districts_inserted + parcel_zones_inserted
    if total_writes == 0:
        raise SystemExit(
            "FAIL-LOUD: fetched/parsed target rows but wrote 0 rows across all tables. "
            "This is a blocker, not a silent no-op.")

    return result


if __name__ == "__main__":
    main()
