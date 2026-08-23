#!/usr/bin/env python3
"""
shard4_run8166_osceola_i_gis_backfill_41bd7ce3.py

Gold Standard shard-4 (dispatch 41bd7ce3, loop run 8166) — osceola criterion I.

CONTEXT (fresh live check, 2026-08-23):
  osceola I = 90.7% (card_complete=136 of 150). Live diagnosis (this session)
  found exactly 14 incomplete rows:
    - 1 row (case 2025 CA 001721 MF, parcel OSC-2CEAE2B1037A) is missing
      property_address/lat/lon/value entirely -- a PropertyOnion-shaped
      parcel_id with tier1_authoritative unset; NOT touched here (out of
      scope: no real source identified for it this session, see NOT FIXED
      below).
    - 13 rows have full address/geo/value but NO parcel_zones row at all,
      so they never resolve through v_zoning_gold_standard_card. These are
      the SAME underlying batch as the C/D gap rows fixed alongside this
      script (case_numbers 17532024, 28622024, 28952024, 28972024,
      29202024, 29462024, 34492024, 37342024, 53772024*, 53942024*,
      59612024, 61152024, 61172024, 61212024, 61362024, 6632024*
      -- *note: 53772024/53942024/6632024 were in the original C/D-gap-16
      list but are NOT in this I-gap-13 list; they already had parcel_zones
      coverage. Full overlap verified live, not assumed.)

  PRIOR SESSION GUARDRAIL (scripts/shard4_run5153_osceola_i_enrichment.py,
  2026-07-19): a "PD fallback" for any Osceola parcel gis.osceola.org could
  not resolve (INCORP/no-match/unrecognized code) was flagged and REVERTED
  as fabrication (410 ghost rows, migrations/20260704_shard9_osceola_
  ghost_success_revert.sql and 20260711t_..._ghost_purge_rebuild.sql). This
  script follows the CORRECTED convention from that same file's step2:
  insert ONLY when gis.osceola.org Zoning_Parcels FeatureServer returns a
  real PRIM_ZON code that exists in osceola's zoning_districts table
  (jurisdiction_id=1186). Parcels returning 'INCORP' (annexed into a
  municipality, outside county zoning jurisdiction) are SKIPPED, not
  defaulted.

LIVE GIS RESULT (this session, gis.osceola.org Zoning_Parcels/FeatureServer/0,
field PARCELNO/PRIM_ZON -- note: TLS cert chain on gis.osceola.org is
broken government-side (verified: also fails via plain `curl` against the
system CA store, not a sandbox artifact); using -k/verify=False for this
one read-only public GIS GET only):
    142731000043110020 -> AC      (real zoning_districts.id=11793)
    152529105000TL0040 -> INCORP  (SKIP -- inside Kissimmee)
    182529184900011105 -> INCORP  (SKIP -- inside Kissimmee, "4117 OAK
                                    CANOPY CT" -- this is the SRPUD-adjacent
                                    parcel referenced in the dispatch brief;
                                    live GIS confirms it is annexed/INCORP,
                                    not a county SRPUD parcel this session
                                    can zone -- no real code to assign)
    352630495000010480 -> R-2     (real zoning_districts.id=10778)
    152529157000010890 -> INCORP  (SKIP)
    182733272000011140 -> PD      (real zoning_districts.id=11796)
    152529543000010100 -> CR      (real zoning_districts.id=11794)
    082530289200010080 -> E-1     (real zoning_districts.id=13182)
    152529105000TL0010 -> INCORP  (SKIP)
    3627316000000L1050 -> AC      (real)
    3627316000000L1145 -> AC      (real)
    3627316000000L1240 -> AC      (real)
    3627316000000L1620 -> AC      (real)

  9 real inserts, 4 INCORP skips. All 6 zone codes used (AC, R-2, PD, CR,
  E-1) verified live to exist in zoning_districts for jurisdiction_id=1186
  before this script runs (fail-loud if that changes).

FAIL-LOUD: if candidate inserts > 0 and inserted == 0, raises RuntimeError.

Usage:
    python3 scripts/shard4_run8166_osceola_i_gis_backfill_41bd7ce3.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

COUNTY = "osceola"
JURISDICTION_ID = 1186
DRY_RUN = "--dry-run" in sys.argv

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Live GIS result captured this session (see docstring) -- real codes only,
# INCORP parcels already excluded from this map.
GIS_ZONE_MAP = {
    "142731000043110020": "AC",
    "352630495000010480": "R-2",
    "182733272000011140": "PD",
    "152529543000010100": "CR",
    "082530289200010080": "E-1",
    "3627316000000L1050": "AC",
    "3627316000000L1145": "AC",
    "3627316000000L1240": "AC",
    "3627316000000L1620": "AC",
}
SKIPPED_INCORP = [
    "152529105000TL0040",
    "182529184900011105",
    "152529157000010890",
    "152529105000TL0010",
]


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _retry(fn, retries=3):
    last = None
    for i in range(retries):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            wait = 2 ** i
            log(f"retry {i+1}/{retries} in {wait}s: {exc}", "UNTESTED")
            time.sleep(wait)
    raise RuntimeError(f"All {retries} retries exhausted: {last}")


def sb_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{path}",
            headers={k: v for k, v in SB_HDR.items() if k not in ("Prefer", "Content-Type")},
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    return _retry(_do)


def sb_post(table, records):
    if DRY_RUN:
        log(f"DRY-RUN POST {table}: {len(records)} records", "UNTESTED")
        return len(records)
    if not records:
        return 0
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{table}",
            data=json.dumps(records).encode(),
            headers={**SB_HDR, "Prefer": "resolution=ignore-duplicates,return=representation"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    result = _retry(_do)
    return len(result) if isinstance(result, list) else 0


def sb_rpc(fn, params):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/rpc/{fn}",
            data=json.dumps(params).encode(),
            headers={k: v for k, v in SB_HDR.items() if k != "Prefer"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _retry(_do)


def main():
    log("=== SHARD-4 RUN-8166 OSCEOLA I GIS BACKFILL (dispatch 41bd7ce3) ===")
    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE I: {baseline.get('I')} | C: {baseline.get('C')} | D: {baseline.get('D')}", "VERIFIED")

    # Guard: confirm no parcel_zones row already exists for these 9 parcels
    # (avoid duplicate-insert confusion; ignore-duplicates makes it safe
    # either way, but we want an honest inserted-count).
    parcel_ids = list(GIS_ZONE_MAP.keys())
    existing = sb_get(
        "parcel_zones?select=parcel_id,zone_code&parcel_id=in.(" + ",".join(parcel_ids) + ")"
    )
    existing_ids = {r["parcel_id"] for r in existing}
    log(f"Pre-check: {len(existing_ids)}/{len(parcel_ids)} already have a parcel_zones row", "VERIFIED")

    # Guard: confirm each zone_code exists in zoning_districts for jurisdiction 1186
    districts = sb_get(f"zoning_districts?select=code&jurisdiction_id=eq.{JURISDICTION_ID}")
    valid_codes = {d["code"] for d in districts}
    for pid, zc in GIS_ZONE_MAP.items():
        if zc not in valid_codes:
            raise RuntimeError(
                f"FAIL-LOUD: zone_code {zc} for parcel {pid} not found in "
                f"zoning_districts for jurisdiction {JURISDICTION_ID} -- refusing to insert an unverified code."
            )
    log(f"Zone-code guard passed: all {len(GIS_ZONE_MAP)} codes exist in zoning_districts", "VERIFIED")

    inserts = [
        {
            "parcel_id": pid,
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": zc,
            "source": f"shard4_run8166_osceola_gis_live_41bd7ce3:{zc}",
        }
        for pid, zc in GIS_ZONE_MAP.items()
        if pid not in existing_ids
    ]
    log(f"Inserting {len(inserts)} parcel_zones rows (skipping {len(existing_ids)} already present)", "UNTESTED")
    log(f"Skipped as INCORP (no county-zoning jurisdiction, no fallback): {SKIPPED_INCORP}", "VERIFIED")

    inserted = sb_post("parcel_zones", inserts)

    if inserts and inserted == 0:
        raise RuntimeError("FAIL-LOUD: built inserts but 0 rows inserted -- check logs above.")

    if not DRY_RUN:
        log("Waiting 3s for DB to settle before re-evaluating...", "UNTESTED")
        time.sleep(3)
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        log(f"AFTER I: {after.get('I')} | C: {after.get('C')} | D: {after.get('D')}", "VERIFIED")

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print("\n### SQL VERIFICATION")
        print(f"Timestamp UTC: {now_iso}")
        print("-- Re-run to confirm:")
        print("SELECT public.pencil_dod_evaluate_county('osceola');")
        print(f"BEFORE: I={baseline.get('I')} C={baseline.get('C')} D={baseline.get('D')}")
        print(f"AFTER:  I={after.get('I')} C={after.get('C')} D={after.get('D')}")
        print(f"parcel_zones_inserted={inserted}")
    else:
        print(f"\nDRY-RUN COMPLETE. Would insert {len(inserts)} parcel_zones rows.")


if __name__ == "__main__":
    main()
