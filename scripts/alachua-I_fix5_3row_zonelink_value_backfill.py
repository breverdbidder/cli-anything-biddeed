#!/usr/bin/env python3
"""Gold Standard alachua letter I (card_complete) fix -- 5th generation.

Live re-check (2026-08-30) of the I predicate found 11 failing rows out of 91:
  - 8 rows are fully blank (no parcel_id/address/geo/value at all) -- these
    are structurally blocked on letter E's parcel-linkage backfill (a sibling
    task is working E concurrently). NOT touched by this script.
  - 3 rows already have parcel_id + property_address + lat/lon +
    assessed/market value, but have ZERO parcel_zones row (zone_linked=false
    against v_zoning_gold_standard_card). These are independently fixable now:
      06014-015-043 (case 01 2025 CA 001863) -> Gainesville (JurisNo=300)
      19878-001-000 (case 01 2025 CA 002072) -> Unincorporated (JurisNo=0)
      06178-005-000 (case 01 2026 CA 000169) -> Unincorporated (JurisNo=0),
        ALSO missing assessed_value/market_value (both NULL live)

Source (VERIFIED live this session, 2026-08-30): Alachua County Property
Appraiser ArcGIS FeatureServer (Parcels35_view) -- same layer used by
alachua-I_fix.py through fix4. Live query for each parcel_id returned a real
feature with JurisNo/ZONEDISTRICT/ZoneDefin/JustValue:
  06014-015-043 -> ZONEDISTRICT=SF, ZoneDefin="Single Family", JurisNo=300
                    (Gainesville), JustValue=226078 (row already has
                    assessed_value=226078 -- matches, no value patch needed)
  19878-001-000 -> ZONEDISTRICT=A, ZoneDefin="Agricultural (A)", JurisNo=0
                    (Alachua County/Unincorporated), JustValue=175886 (row
                    already has assessed_value=89482 -- real distinct value,
                    NOT overwritten; only the zoning link was missing)
  06178-005-000 -> ZONEDISTRICT=R-1A, ZoneDefin="Residential Single Family
                    (R-1A)", JurisNo=0 (Unincorporated), JustValue=300669
                    (row has assessed_value=NULL, market_value=NULL -> patch
                    assessed_value=300669 from ArcGIS JustValue)

jurisdiction_id mapping confirmed live via jurisdictions?county=ilike.alachua:
  JurisNo 300 (Gainesville) -> jurisdiction_id=915
  JurisNo 0   (Unincorporated/Alachua County) -> jurisdiction_id=1404

zoning_districts rows ALREADY EXIST for both target codes (verified live,
no insert needed this run):
  (915, 'SF')    -> id=9155
  (1404, 'A')    -> id=13147
  (1404, 'R-1A') -> id=11782

Idempotent: every field write is gated on the current DB value being NULL at
PATCH time (assessed_value) or the parcel having zero parcel_zones rows
(zone link insert). Re-running is a safe no-op.

Usage: python3 scripts/alachua-I_fix5_3row_zonelink_value_backfill.py
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

TARGET_PARCELS = ["06014-015-043", "19878-001-000", "06178-005-000"]

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
    print(f"alachua-I fix5 (3-row zone-link + value backfill): {len(TARGET_PARCELS)} target parcels")

    mca_patched = 0
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

        # --- assessed_value patch (only for rows currently NULL on both cols) ---
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
            else:
                print(f"  {rid} ({cn}, {pid}): value already present "
                      f"(assessed={row.get('assessed_value')}, market={row.get('market_value')}) -- no value patch")

        # --- parcel_zones insert (idempotent, only if zero rows exist for this parcel) ---
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
                print(f"  INSERTED parcel_zones (parcel_id={pid}, jurisdiction_id={juris_id}, zone_code={zone_code})")
        else:
            print(f"  parcel_zones (parcel_id={pid}) already exists -- skip insert")

        time.sleep(0.3)

    result = {
        "mca_rows_patched": mca_patched,
        "parcel_zones_inserted": parcel_zones_inserted,
        "skipped": skipped_no_fix,
    }
    print(json.dumps(result, indent=2, default=str))

    total_writes = mca_patched + parcel_zones_inserted
    if total_writes == 0:
        raise SystemExit(
            "FAIL-LOUD: fetched/parsed target rows but wrote 0 rows across all tables. "
            "This is a blocker, not a silent no-op.")

    return result


if __name__ == "__main__":
    main()
