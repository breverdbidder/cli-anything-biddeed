#!/usr/bin/env python3
"""Gold Standard shard-3 dispatch b57474e3 -- alachua letter I (card_complete)
follow-on fix, 2nd generation (after scripts/alachua-I_fix.py already closed
the 3-row zoning gap in commit 54c17c98, 77.6%->82.8%). Live re-diagnosis this
session (auctions_total grew 58->73) found exactly 2 rows with real
parcel_id + full address/geo/value already populated, but with NO
parcel_zones row -- i.e. structurally identical to the pattern the first
I fix script already proved out, just a fresh pair of rows:

  01 2026 CA 000211 (fd94302a-bd97-4ebd-a84d-0ee3b0a83e69) parcel 07332-200-004
    -- Gainesville (JurisNo=300 -> jurisdiction_id=915), ZONEDISTRICT=U7
       "Urban 7". This is the SAME parcel that letter E's diagnosis flagged
       as one of 2 ArcGIS owner-name candidates for a different, still-
       unlinked case (2900 Gainesville Holdings LLC); here it is already the
       resolved parcel_id on ITS OWN row, so no re-litigation of that
       ambiguity is needed for this row -- it just never got a zoning link.
  01 2025 CA 003415 (68525856-1a2c-44fd-805c-3d102e8f6d74) parcel 05900-903-016
    -- City of Alachua (JurisNo=100, confirmed live via CityDescription=
       "ALACHUA" field on the ArcGIS feature -- new JurisNo not previously
       mapped, resolved to jurisdiction_id=973 "Alachua" per
       `jurisdictions` table lookup), ZONEDISTRICT=PUD "Planned Unit
       Development(PUD)".

Both parcels' address/latitude/longitude/assessed_value are ALREADY non-NULL
on multi_county_auctions, so this script only inserts zoning_districts +
parcel_zones rows (idempotent, check-then-insert, same convention as
alachua-I_fix.py: density_regulated/far_regulated/pk1000_regulated all False
-- no discoverable numeric standard this session, avoids the G-regression
trap documented in supabase/migrations/20260725_gold_standard_shard6_
alachua_i_zoning_coverage.sql).

Source (VERIFIED live this session): Alachua County Property Appraiser
ArcGIS FeatureServer (Parcels35_view), same layer used by alachua-I_fix.py.

Usage: python3 scripts/alachua-I_fix2.py
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
    {"id": "fd94302a-bd97-4ebd-a84d-0ee3b0a83e69", "case_number": "01 2026 CA 000211",
     "parcel_id": "07332-200-004"},
    {"id": "68525856-1a2c-44fd-805c-3d102e8f6d74", "case_number": "01 2025 CA 003415",
     "parcel_id": "05900-903-016"},
]

# JurisNo -> jurisdictions.id, confirmed live via CityDescription field on
# the ArcGIS feature this session.
JURIS_NO_TO_ID = {300: 915, 100: 973}  # Gainesville, City of Alachua


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
    print(f"alachua-I fix2: {len(TARGETS)} target rows")

    zoning_districts_inserted = 0
    parcel_zones_inserted = 0
    skipped_no_fix = []

    for t in TARGETS:
        rid, cn, pid = t["id"], t["case_number"], t["parcel_id"]

        attrs = arcgis_query_parcel(pid)
        if attrs is None:
            skipped_no_fix.append({"id": rid, "case_number": cn, "reason": "ArcGIS returned no feature"})
            print(f"  {cn} ({pid}): SKIP -- ArcGIS returned no feature")
            continue

        juris_no = attrs.get("JurisNo")
        zone_code = attrs.get("ZONEDISTRICT")
        zone_defin = attrs.get("ZoneDefin") or zone_code
        juris_id = JURIS_NO_TO_ID.get(juris_no)
        if juris_id is None or not zone_code:
            skipped_no_fix.append({"id": rid, "case_number": cn,
                                    "reason": f"unmapped JurisNo={juris_no} or missing zone_code"})
            print(f"  {cn} ({pid}): SKIP zoning link -- unmapped JurisNo={juris_no} "
                  f"(CityDescription={attrs.get('CityDescription')!r}) or no zone_code")
            continue

        print(f"  {cn} ({pid}): JurisNo={juris_no} ({attrs.get('CityDescription')}) "
              f"-> jurisdiction_id={juris_id}, zone={zone_code} ({zone_defin})")

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
                print(f"    INSERTED zoning_districts (jurisdiction_id={juris_id}, code={zone_code})")
        else:
            print(f"    zoning_districts (jurisdiction_id={juris_id}, code={zone_code}) already exists -- skip")

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
                print(f"    INSERTED parcel_zones (parcel_id={pid}, zone_code={zone_code})")
        else:
            print(f"    parcel_zones (parcel_id={pid}) already exists -- skip")

        time.sleep(0.3)

    print(json.dumps({
        "zoning_districts_inserted": zoning_districts_inserted,
        "parcel_zones_inserted": parcel_zones_inserted,
        "skipped": skipped_no_fix,
    }, indent=2, default=str))

    total_writes = zoning_districts_inserted + parcel_zones_inserted
    if total_writes == 0:
        raise SystemExit(
            "FAIL-LOUD: fetched/parsed target rows but wrote 0 rows across all tables. "
            "This is a blocker, not a silent no-op.")

    return {
        "zoning_districts_inserted": zoning_districts_inserted,
        "parcel_zones_inserted": parcel_zones_inserted,
    }


if __name__ == "__main__":
    main()
