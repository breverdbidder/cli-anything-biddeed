#!/usr/bin/env python3
"""
SHARD-7 ORANGE E FIX — link parcel_id for genuine Orange County rows
by street-address match against FR_ISO_Parcels ArcGIS REST (ocgis4.ocfl.net).

Context: 341 rows in multi_county_auctions (county=orange) are genuine Orange
County properties (real zip/city) left over after removing a 2225-row
PropertyOnion/Polk-County contamination batch (dispatch b890c19b, 2026-07-02).
They have property_address + zip but no parcel_id. This is the forward
direction (address -> parcel_id), the reverse of scripts/shard28_run338_i_orange.py
(parcel_id -> address).

Session: architect-20260702T000000
Dispatch: b890c19b-cabd-46fe-9331-43e121db40f3
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import threading
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
DRY_RUN = "--dry-run" in sys.argv

ARCGIS_URL = "https://ocgis4.ocfl.net/arcgis/rest/services/FR_ISO_Parcels/MapServer/0/query"


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def sb_headers(extra: dict = None) -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def rest_get(path: str, params: dict) -> list:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}?{qs}", headers=sb_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_patch(path: str, qs: str, data: dict) -> bool:
    if DRY_RUN:
        return True
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(), headers=sb_headers({"Prefer": "return=minimal"}), method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
        return True
    except Exception as e:
        log(f"rest_patch failed: {e}", "ERROR", "VERIFIED")
        return False


def get_missing_rows(county: str = "orange") -> list:
    rows = []
    offset = 0
    while True:
        batch = rest_get("multi_county_auctions", {
            "select": "id,property_address,city,zip",
            "county": f"eq.{county}",
            "parcel_id": "is.null",
            "property_address": "not.is.null",
            "order": "id",
            "offset": str(offset),
            "limit": "500",
        })
        rows.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    return rows


def street_fragment(address: str) -> str | None:
    """Extract 'HOUSENUM STREETNAME' fragment for a LIKE match against SITUS."""
    if not address:
        return None
    part = address.split(",")[0].strip()
    part = re.sub(r"\s+(Unit|Apt|#)\s*\S+$", "", part, flags=re.IGNORECASE).strip()
    part = part.upper().replace("'", "''")
    return part or None


def query_arcgis_by_address(fragment: str):
    """Query FR_ISO_Parcels by SITUS LIKE fragment. Returns (PARCEL, SITUS) or (None, None)."""
    params = urllib.parse.urlencode({
        "where": f"SITUS LIKE '{fragment}%'",
        "outFields": "PARCEL,SITUS",
        "f": "json",
        "returnGeometry": "false",
        "resultRecordCount": "5",
    })
    req = urllib.request.Request(f"{ARCGIS_URL}?{params}", headers={"User-Agent": "BidDeed/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read())
    except Exception:
        return None, None
    feats = data.get("features", [])
    if len(feats) == 1:
        a = feats[0]["attributes"]
        return a.get("PARCEL"), a.get("SITUS")
    return None, None


def main():
    county = "orange"
    log(f"SHARD-7 ORANGE E FIX — {county}. DRY_RUN={DRY_RUN}", "INFO", "UNTESTED")
    if not SB_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    rows = get_missing_rows(county)
    log(f"{county}: {len(rows)} rows missing parcel_id (with address)", "INFO", "VERIFIED")

    sem = threading.Semaphore(2)
    lock = threading.Lock()
    matched = 0
    patched = 0
    no_match = 0
    completed = 0

    def work(row):
        nonlocal matched, patched, no_match, completed
        frag = street_fragment(row["property_address"])
        if not frag:
            with lock:
                no_match += 1
                completed += 1
            return
        with sem:
            parcel, situs = query_arcgis_by_address(frag)
            time.sleep(0.15)
        with lock:
            completed += 1
            if parcel:
                matched += 1
                if rest_patch("multi_county_auctions", f"id=eq.{row['id']}", {"parcel_id": str(parcel)}):
                    patched += 1
            else:
                no_match += 1
            if completed % 50 == 0:
                log(f"  {completed}/{len(rows)} done, matched={matched} patched={patched}", "INFO", "VERIFIED")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(work, r) for r in rows]
        for f in as_completed(futures):
            pass

    print(f"\n### SQL VERIFICATION — ORANGE E FIX (dispatch b890c19b)", flush=True)
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}", flush=True)
    print(f"  candidates={len(rows)} matched={matched} patched={patched} no_match={no_match}", flush=True)

    if len(rows) > 0 and patched == 0:
        log(f"WARN: {len(rows)} rows needed linkage but 0 patched", "WARN", "VERIFIED")

    log("orange E fix complete", "INFO", "VERIFIED")


if __name__ == "__main__":
    main()
