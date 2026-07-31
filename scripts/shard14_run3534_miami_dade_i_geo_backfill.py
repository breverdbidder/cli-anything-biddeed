#!/usr/bin/env python3
"""SHARD-14 (miami_dade only), continuation of shard14_run3534_miami_dade_cd_i_fix.py.

Backfills the lat/long portion of the I (card_complete) gap that the AJAX
harvester fix does NOT cover. Live diagnosis this session: 49 miami_dade
rows have NULL latitude, 48 of which have a parcel_id (folio) already
present -- 1 has a malformed parcel_id ("Property Appraiser", a pre-existing
AITEM-decoder anchor-text artifact, not real folio data).

Source: fl_parcels table, co_no=23 (Miami-Dade), already fully populated
with ArcGIS-sourced centroids by scripts/fl_parcel_centroids_all.py
(fl_parcel_centroid_progress row for co_no=23: status=done,
centroids_done=585220, completed 2026-06-23). This script does NOT call any
external geocoder or ArcGIS endpoint -- it is a pure DB-to-DB join against
data that already exists, using the same undash-folio transform verified
live this session (multi_county_auctions.parcel_id is dashed
"01-4104-013-0290"; fl_parcels.parcel_id for co_no=23 is the same 13 digits
undashed "0141040130290" -- confirmed via direct REST lookup, exact match).

Idempotent: only patches latitude/longitude when both are currently NULL on
the multi_county_auctions row and fl_parcels has a non-null centroid for the
matching undashed folio. Never overwrites existing non-null geo data.

Usage: python3 scripts/shard14_run3534_miami_dade_i_geo_backfill.py
"""
import os
import re
import json
import time
import urllib.request
import urllib.parse
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY = "miami_dade"
CO_NO = 23  # Miami-Dade FL DOR county number, confirmed via fl_parcel_centroid_progress


def is_real_parcel_id(pid):
    """Same guard as shard14_run3534_miami_dade_cd_i_fix.py: some AITEM blocks
    decode the parcel-appraiser link as its own anchor text ('Property
    Appraiser') instead of the parcel number."""
    if not pid:
        return False
    return bool(re.search(r"\d", pid)) and pid.strip().lower() != "property appraiser"


def undash(pid):
    return re.sub(r"[^0-9]", "", pid or "")


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
        req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                      headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body, timeout=30):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def main():
    gap_rows = rest_get(
        "multi_county_auctions?county=eq.miami_dade"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&latitude=is.null&parcel_id=not.is.null"
        "&select=id,case_number,parcel_id,latitude,longitude")
    print(f"diagnosis: {len(gap_rows)} miami_dade rows with NULL latitude and non-null parcel_id")

    geocoded = 0
    skipped_bad_format = 0
    skipped_no_match = 0
    skipped_null_centroid = 0
    failed = 0

    for row in gap_rows:
        pid = row["parcel_id"]
        if not is_real_parcel_id(pid):
            print(f"  {row['case_number']}: SKIP bad-format parcel_id '{pid}'")
            skipped_bad_format += 1
            continue

        folio = undash(pid)
        try:
            matches = rest_get(
                f"fl_parcels?co_no=eq.{CO_NO}&parcel_id=eq.{urllib.parse.quote(folio)}"
                f"&select=parcel_id,centroid_lat,centroid_lng")
        except Exception as e:
            print(f"  {row['case_number']}: fl_parcels lookup FAILED for folio {folio}: {e}")
            failed += 1
            continue

        if not matches:
            skipped_no_match += 1
            continue
        centroid = matches[0]
        if centroid.get("centroid_lat") is None or centroid.get("centroid_lng") is None:
            skipped_null_centroid += 1
            continue

        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"latitude": centroid["centroid_lat"], "longitude": centroid["centroid_lng"]})
        except Exception as e:
            print(f"  {row['case_number']}: PATCH FAILED: {e}")
            failed += 1
            continue

        geocoded += 1
        print(f"  {row['case_number']} (folio {pid}): lat={centroid['centroid_lat']} lon={centroid['centroid_lng']}")
        time.sleep(0.1)

    print(f"\nTOTALS: geocoded={geocoded} skipped_bad_format={skipped_bad_format} "
          f"skipped_no_fl_parcels_match={skipped_no_match} skipped_null_centroid={skipped_null_centroid} "
          f"failed={failed} of {len(gap_rows)} gap rows")


if __name__ == "__main__":
    main()
