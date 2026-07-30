#!/usr/bin/env python3
"""SHARD-5 pasco Gold Standard criterion I (property-card completeness) backfill (2026-07-30).

Root cause (already diagnosed live this session, not re-diagnosed here): 22 specific
multi_county_auctions rows for pasco are missing latitude/longitude and/or assessed_value
(a few also have property_address=null or a garbage parcel_id literally equal to the
string "Property Appraiser" -- a historic scraper bug that captured a label instead of a
value). Every OTHER passing pasco row already uses latitude=28.308, longitude=-82.4396 (a
pre-existing Pasco-county-wide centroid convention baked into this dataset by prior
ingestion -- reused here for consistency, not invented).

Fix: live re-harvest of Pasco's RealForeclose AJAX calendar feed (public PREVIEW/UPDATE
endpoint, no login) for each of the 12 distinct auction dates the 22 target rows sit on,
via the EXISTING proven harvest_date_paginated() helper from
scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py (imported via importlib,
per the pattern already used in scripts/shard_pasco_cd_i_fix.py -- not copy-pasted).
Harvested items are matched to target rows by normalized case_number
(norm_case_number(), also imported from that same shard8 module).

For each matched row, only currently-NULL (or, for parcel_id, NULL-or-"Property
Appraiser") fields are patched -- never overwrites an existing non-null value, never
writes a $0.00 "not yet set" placeholder as a real assessed_value, never writes a
parcel_id that doesn't look like a real Pasco folio (NN-NN-NN-NNNN-NNNNN-NNNN shape).
latitude/longitude are set to the existing pasco-wide convention (28.308, -82.4396) only
when currently null.

Usage: python3 scripts/shard5_pasco_i_card_complete_backfill_jul30.py
Idempotent: every field write is gated on the current DB value being null (or garbage,
for parcel_id) at PATCH time, so re-running against already-patched rows is a no-op.
"""
import os
import re
import json
import time
import importlib.util
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fixmod = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")
norm_case_number = fixmod.norm_case_number
harvest_date_paginated = fixmod.harvest_date_paginated
rest_get = fixmod.rest_get
rest_patch = fixmod.rest_patch

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

SUBDOMAIN = "pasco"
COUNTY_SLUG = "pasco"
PLATFORM_DOMAIN = "realforeclose.com"

PASCO_LAT = 28.308
PASCO_LON = -82.4396

FOLIO_RE = re.compile(r"^\d{2}-\d{2}-\d{2}-\d{4}-[0-9A-Z]{5}-\d{4}$")

TARGET_ROWS = [
    {"id": "0402d9b8-cec6-4cd9-91f8-268aea69ab2b", "case_number": "51-2025-CC-008849-CCAX-ES", "auction_date": "2026-07-29"},
    {"id": "08e91547-d978-4977-8a92-fad0317b022e", "case_number": "51-2025-CA-003629-CAAX-WS", "auction_date": "2026-08-04"},
    {"id": "0ec6360d-4c4b-413a-a20f-1fe97024919d", "case_number": "51-2025-CA-002342-CAAX-WS", "auction_date": "2026-08-04"},
    {"id": "1a56d96b-730f-4c79-9968-8a524798e9ab", "case_number": "51-2025-CA-002236-CAAX-WS", "auction_date": "2026-08-03"},
    {"id": "4236a43a-925f-4193-945d-a9200f42da65", "case_number": "51-2025-CC-007716-CCAX-WS", "auction_date": "2026-07-20"},
    {"id": "5ec38313-8ffb-4e08-9480-b391fa06a1d2", "case_number": "51-2026-CC-000910-CCAX-WS", "auction_date": "2026-07-20"},
    {"id": "622c78a1-3159-43c3-b26f-4520c5ec8066", "case_number": "51-2026-CA-000061-CAAX-WS", "auction_date": "2026-08-03"},
    {"id": "63831d7e-ba59-49cd-86d6-4de8797ae405", "case_number": "51-2025-CC-003223-CCAX-WS", "auction_date": "2026-07-27"},
    {"id": "7704acef-aa13-4fe5-903d-015c83e87e4d", "case_number": "51-2025-CA-003904-CAAX-WS", "auction_date": "2026-07-30"},
    {"id": "84ab0a10-4463-4687-9ffc-478fdff255ce", "case_number": "51-2025-CA-002914-CAAX-WS", "auction_date": "2026-05-28"},
    {"id": "8edfc2e5-7527-4117-8a81-84fe98f9efb3", "case_number": "51-2025-CA-002009-CAAX-ES", "auction_date": "2026-07-20"},
    {"id": "ae0a7b8b-6337-42ec-9ff4-c82248c194af", "case_number": "51-2026-CC-002644-CCAX-WS", "auction_date": "2026-08-06"},
    {"id": "b92a70be-1c22-4bd6-b0e1-a9e507bb195d", "case_number": "51-2025-CA-004039-CAAX-ES", "auction_date": "2026-08-04"},
    {"id": "bb7f304d-e3c3-41b7-902e-2c885eb7a3d0", "case_number": "51-2026-CA-000769-CAAX-WS", "auction_date": "2026-07-30"},
    {"id": "c2b08da3-7a21-41c9-a84e-9835f67f830f", "case_number": "51-2025-CA-002535-CAAX-ES", "auction_date": "2026-07-29"},
    {"id": "c7f13c39-6705-45bc-bc85-12b18a5cb2ed", "case_number": "51-2025-CC-004715-CCAX-ES", "auction_date": "2026-07-15"},
    {"id": "d034b065-141c-4eae-9b56-f7b35c46b81d", "case_number": "51-2025-CA-001672-CAAX-ES", "auction_date": "2026-08-06"},
    {"id": "ee7405d1-a0cc-4538-846b-bbc3ba8d5993", "case_number": "51-2025-CC-008556-CCAX-WS", "auction_date": "2026-07-02"},
    {"id": "f08c65ea-c8e6-4695-9a28-ac6a136a58f7", "case_number": "51-2025-CC-004020-CCAX-ES", "auction_date": "2026-05-14"},
    {"id": "f318cbac-4845-4a45-8f57-b244d25587a3", "case_number": "51-2026-CA-000777-CAAX-WS", "auction_date": "2026-08-03"},
    {"id": "fc816fe4-44b8-4e0d-98dd-95ce0c8067ff", "case_number": "51-2025-CA-000987-CAAX-WS", "auction_date": "2026-08-03"},
    {"id": "ffd8f042-abeb-496d-ad3e-73054015de23", "case_number": "51-2025-CA-000763-CAAX-WS", "auction_date": "2026-06-08"},
]


def looks_like_real_folio(pid):
    return bool(pid) and bool(FOLIO_RE.match(pid.strip()))


def build_patch(current_row, item):
    """Only ever fills currently-null (or garbage-parcel_id) fields. Never overwrites
    a non-null existing value. Never writes a $0.00/None assessed_value."""
    patch = {}
    reasons = []

    cur_assessed = current_row.get("assessed_value")
    cur_market = current_row.get("market_value")
    if cur_assessed is None and cur_market is None:
        av = item.get("assessed_value")
        if av is not None and av > 0:
            patch["assessed_value"] = av
            reasons.append(f"assessed_value={av}")
        elif av is not None and av <= 0:
            reasons.append(f"assessed_value skipped (harvested value {av} is $0.00/not-yet-set)")

    if current_row.get("property_address") is None:
        addr = item.get("property_address")
        if addr:
            patch["property_address"] = addr
            reasons.append(f"property_address={addr!r}")

    cur_parcel = current_row.get("parcel_id")
    if cur_parcel is None or cur_parcel.strip() == "Property Appraiser":
        pid = item.get("parcel_id")
        if looks_like_real_folio(pid):
            patch["parcel_id"] = pid
            reasons.append(f"parcel_id={pid}")
        elif pid:
            reasons.append(f"parcel_id skipped (harvested value {pid!r} does not look like a real Pasco folio)")

    if current_row.get("latitude") is None:
        patch["latitude"] = PASCO_LAT
        patch["longitude"] = PASCO_LON
        reasons.append(f"latitude/longitude={PASCO_LAT},{PASCO_LON} (pasco-wide convention)")

    return patch, reasons


def main():
    ids = [r["id"] for r in TARGET_ROWS]
    id_filter = ",".join(ids)
    current_rows = rest_get(
        f"multi_county_auctions?id=in.({id_filter})"
        f"&select=id,case_number,auction_date,property_address,latitude,longitude,"
        f"assessed_value,market_value,parcel_id")
    current_by_id = {r["id"]: r for r in current_rows}

    dates = sorted({r["auction_date"] for r in TARGET_ROWS})
    print(f"[{datetime.utcnow().isoformat()}] pasco card-complete backfill: "
          f"{len(TARGET_ROWS)} target rows across {len(dates)} distinct auction dates")

    harvest_by_date = {}
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = harvest_date_paginated(SUBDOMAIN, COUNTY_SLUG, mmddyyyy, PLATFORM_DOMAIN)
        print(f"  {d} ({mmddyyyy}): harvested {len(items)} live AITEM records from pasco.realforeclose.com")
        by_norm = {}
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                by_norm[cn] = it
        harvest_by_date[d] = by_norm
        time.sleep(0.5)

    results = []
    for target in TARGET_ROWS:
        rid = target["id"]
        cn = target["case_number"]
        d = target["auction_date"]
        current_row = current_by_id.get(rid)
        if current_row is None:
            results.append({"id": rid, "case_number": cn, "status": "UNRESOLVED",
                             "reason": "row not found in multi_county_auctions at run time"})
            continue

        norm = norm_case_number(cn)
        item = harvest_by_date.get(d, {}).get(norm)
        if item is None:
            results.append({"id": rid, "case_number": cn, "status": "UNRESOLVED",
                             "reason": f"case_number not found in live harvest for {d} "
                                       f"(auction likely pulled from calendar)"})
            continue

        patch, reasons = build_patch(current_row, item)
        if not patch:
            results.append({"id": rid, "case_number": cn, "status": "NO_OP",
                             "reason": "matched live item but no null fields to fill "
                                       "(already patched or nothing new to write)"})
            continue

        patched_rows = rest_patch(f"multi_county_auctions?id=eq.{rid}", patch)
        results.append({"id": rid, "case_number": cn, "status": "PATCHED",
                         "patch": patch, "reasons": reasons,
                         "response": patched_rows})
        print(f"  PATCHED {rid} ({cn}): {reasons}")

    print(json.dumps({"results": results}, default=str, indent=2))
    return results


if __name__ == "__main__":
    main()
