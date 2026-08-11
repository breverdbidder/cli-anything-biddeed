#!/usr/bin/env python3
"""GOLD STANDARD workstream hl_EIJ, dispatch 8d4cd6c7-e51a-4a0d-a8da-6995f13bad43.
County: highlands. Letter: I (card_complete), gated on E.

After highlands_e_parcel_linkage.py resolved 29 gap rows for letter E, the
I letter needs those same 29 parcels to have a public.parcel_zones row with
zone_code IS NOT NULL (per v_zoning_gold_standard_card / pencil_dod_evaluate_county
contract). Source: live Highlands County zoning ArcGIS MapServer (already
used and documented in a prior session,
supabase/migrations/20260723170500_shard8_gadsden_highlands_e_i_g_close_740368a6.sql):

  https://gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0
  fields: STRAP_NUM (= our dashed parcel_id with dashes removed), ZON (zone code)

Verified live transform: parcel_id.replace('-', '') == STRAP_NUM
  e.g. C-04-34-28-110-2010-0200 -> C04342811020100200 -> ZON='R1'

jurisdiction_id resolved from property_address's city token against the
existing highlands jurisdictions rows (Sebring=918, Avon Park=955,
Lake Placid=840, Highlands County=1654 for unincorporated / LORIDA / VENUS).

Usage:
  python3 scripts/highlands_i_zone_backfill.py            # dry-run
  python3 scripts/highlands_i_zone_backfill.py --apply    # write to DB

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)
"""
from __future__ import annotations
import json
import os
import re
import ssl
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
DISPATCH_ID = "8d4cd6c7-e51a-4a0d-a8da-6995f13bad43"

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

ZONING_QUERY_URL = "https://gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0/query"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Highlands county jurisdictions table (verified live 2026-08-11 via
# GET /jurisdictions?county=ilike.highlands)
JURISDICTION_BY_CITY = {
    "SEBRING": 918,
    "AVON PARK": 955,
    "LAKE PLACID": 840,
    "LORIDA": 1654,        # unincorporated -> Highlands County
    "VENUS": 1654,          # unincorporated -> Highlands County
}
DEFAULT_JURISDICTION = 1654  # unincorporated Highlands County


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table: str, params: str, limit: int = 2000):
    url = f"{BASE}/{table}?{params}&limit={limit}"
    req = urllib.request.Request(url, headers={**HEADERS, "Prefer": ""})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_post(table: str, data: list, prefer: str = "resolution=merge-duplicates,return=minimal"):
    if not data:
        return 200, "no-op"
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}/{table}", data=body, headers={**HEADERS, "Prefer": prefer}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def http_get(url: str, timeout=30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
        return r.read()


# The live ZON field prefixes some codes with a municipal abbreviation for
# parcels inside that municipality's boundary (verified live against the
# ArcGIS layer: 'AP R1', 'AP C2', 'AP PUD' for Avon Park; 'LP R1', 'LP C2'
# for Lake Placid; 'S R1' style for Sebring rows). jurisdiction_id already
# encodes the municipality via parcel_zones.jurisdiction_id, and this
# county's existing zoning_districts rows (from a prior session's real
# ordinance research) use the bare code without the prefix (e.g. 918/'R1',
# 918/'R3', 955 has no entries yet) — strip the prefix so new rows land on
# the same canonical code space instead of minting near-duplicate codes.
_MUNI_PREFIX = {918: "S", 955: "AP", 840: "LP"}


def _strip_muni_prefix(zon: str, jurisdiction_id: int) -> str:
    prefix = _MUNI_PREFIX.get(jurisdiction_id)
    if prefix and zon.startswith(prefix + " "):
        return zon[len(prefix) + 1:].strip()
    return zon


def zoning_lookup(strap_num: str) -> str | None:
    q = urllib.parse.urlencode({
        "where": f"STRAP_NUM='{strap_num}'",
        "outFields": "STRAP_NUM,ZON",
        "returnGeometry": "false",
        "f": "json",
    })
    raw = http_get(f"{ZONING_QUERY_URL}?{q}")
    data = json.loads(raw)
    feats = data.get("features") or []
    if not feats:
        return None
    zon = feats[0]["attributes"].get("ZON")
    return zon.strip() if zon else None


def jurisdiction_for_address(address: str) -> int:
    addr_upper = (address or "").upper()
    for city, jid in JURISDICTION_BY_CITY.items():
        if city in addr_upper:
            return jid
    return DEFAULT_JURISDICTION


def main():
    apply = "--apply" in sys.argv

    log("Fetching highlands parcels with parcel_id but no parcel_zones row...")
    rows = sb_get(
        "multi_county_auctions",
        "select=parcel_id,property_address&county=ilike.highlands&parcel_id=not.is.null",
    )
    # de-dup by parcel_id, then filter to those genuinely missing parcel_zones
    by_parcel = {}
    for r in rows:
        if r["parcel_id"] and r["parcel_id"] not in by_parcel:
            by_parcel[r["parcel_id"]] = r["property_address"]
    log(f"  {len(by_parcel)} distinct parcel_ids in multi_county_auctions for highlands")

    existing = sb_get("parcel_zones", "select=parcel_id&parcel_id=in.(" +
                       ",".join(f'"{p}"' for p in by_parcel) + ")", limit=5000)
    existing_ids = {r["parcel_id"] for r in existing}
    gap = {pid: addr for pid, addr in by_parcel.items() if pid not in existing_ids}
    log(f"  {len(gap)} parcels missing a parcel_zones row")

    inserts = []
    skipped = []
    for parcel_id, address in gap.items():
        strap = parcel_id.replace("-", "")
        try:
            zon = zoning_lookup(strap)
        except Exception as e:
            skipped.append((parcel_id, f"ArcGIS query error: {e}"))
            continue
        if not zon:
            skipped.append((parcel_id, f"no zoning feature found for STRAP_NUM={strap}"))
            continue
        jid = jurisdiction_for_address(address)
        code = _strip_muni_prefix(zon, jid)
        inserts.append({
            "parcel_id": parcel_id,
            "jurisdiction_id": jid,
            "zone_code": code,
            "source": f"hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:{DISPATCH_ID}",
        })
        log(f"  OK {parcel_id} ({address}) -> zone={zon} -> code={code} jurisdiction_id={jid}")
        time.sleep(0.3)

    log("")
    log(f"RESOLVED: {len(inserts)} / {len(gap)}")
    for pid, reason in skipped:
        log(f"  SKIP {pid}: {reason}")

    if not apply:
        log("")
        log("DRY RUN (no --apply flag). No DB writes performed.")
        return

    if not inserts:
        log("No inserts to write.")
        return

    status, body = sb_post("parcel_zones", inserts)
    if status in (200, 201):
        log(f"WRITTEN: {len(inserts)} rows into parcel_zones")
    else:
        log(f"INSERT FAILED: status={status} body={body[:500]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
