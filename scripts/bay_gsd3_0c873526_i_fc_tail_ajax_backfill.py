#!/usr/bin/env python3
"""Gold Standard shard-3, dispatch 0c873526-996a-4f5d-9123-99836d1d585f, county=bay, letter I.

7 bay foreclosure rows added to the auctions_total tail (230 -> 246) had never
been enriched from the live RealForeclose AJAX preview calendar (same mechanism
already used for the C-fix this session, scripts/shard9_run6046_bay_cd_future_
harvest.py / scripts/shard2_run2450_ajax_realforeclose_harvest.py). Live harvest
of the 6 distinct auction dates for these 8 case numbers returned exact case-number
matches carrying real parcel_id/property_address/assessed_value for 7 of them; the
8th (23001288CA) hits the documented "Property Appraiser" anchor-text parser gap
(the county's own RealForeclose page has no real Parcel ID link for that case) and
is left alone (BLANK > WRONG).

Only patches fields that are currently NULL (idempotent, no overwrite of existing
real data).

Usage: python3 scripts/bay_gsd3_0c873526_i_fc_tail_ajax_backfill.py
"""
import json
import os
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# (mca_id, case_number, parcel_id, property_address, assessed_value) -- from live
# bay.realforeclose.com AJAX preview calendar, harvested this session.
FIXES = [
    ("533efc1e-46e5-41c5-ba7f-830043572346", "25001240CA", "06177-000-000",
     "6123 CHERRY ST, PANAMA CITY, FL- 32404", 199889.0),
    ("008b8f71-fcd9-4f76-8190-c2c70d8f7c00", "24001056CA", "07585-262-020",
     "3919 CEDAR BLUFF RD, SOUTHPORT, FL- 32409", 115024.0),
    ("a7d27aa5-dc40-463b-8bdc-69048f594d78", "26000160CA", "31232-000-000",
     "4600 MAGNOLIA BEACH RD, PANAMA CITY BEACH, FL- 32408", 4631042.0),
    ("6bc3cdf6-7ecb-4290-b154-aaaae85260a8", "25001319CA", "06701-176-000",
     "1045 TIDEWATER LN, PANAMA CITY, FL- 32404", 99559.0),
    ("ce85abd7-17d2-4366-a94a-37b829ee3aa1", "25001056CA", "26275-000-000",
     "29 ALMA AVE, PANAMA CITY, FL- 32404", 123296.0),
    ("aff7ac61-70fc-4efb-a8ca-c25ccbf92ca9", "26000281CA", "03834-085-000",
     "8801 TOWER RD, PANAMA CITY, FL- 32404", 192763.0),
    ("f77411d8-0fde-4bff-8d6d-64f41b99ab9d", "26000084CA", "31402-222-000",
     "104 GOLF DR, PANAMA CITY BEACH, FL- 32408", 321475.0),
]

BLOCKED = {
    "bad06dfc-9ad4-4013-9cea-319da6972d95":
        "23001288CA: live RealForeclose AJAX calendar returns Parcel ID anchor "
        "text literally 'Property Appraiser' (no real parcel_id/address/value in "
        "the county's own displayed record) -- known parser-gap pattern documented "
        "fleet-wide, not a real value to fabricate. Left NULL.",
}


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    patched = 0
    for mca_id, cn, parcel_id, addr, val in FIXES:
        existing = rest_get(f"multi_county_auctions?id=eq.{mca_id}&select=parcel_id,property_address,assessed_value")
        if not existing:
            print(f"  {cn}: row not found, skip")
            continue
        row = existing[0]
        body = {}
        if not row.get("parcel_id"):
            body["parcel_id"] = parcel_id
        if not row.get("property_address"):
            body["property_address"] = addr
        if not row.get("assessed_value"):
            body["assessed_value"] = val
        if not body:
            print(f"  {cn}: already complete, skip")
            continue
        result = rest_patch(f"multi_county_auctions?id=eq.{mca_id}", body)
        if not result:
            raise RuntimeError(f"PATCH returned 0 rows for {cn} -- fail-loud, not silent no-op")
        patched += 1
        print(f"  PATCHED {cn}: {json.dumps(body)}")
    print(f"\nTOTAL PATCHED: {patched} of {len(FIXES)}")
    print(f"\nBLOCKED (evidence, no fabrication): {len(BLOCKED)} rows")
    for row_id, reason in BLOCKED.items():
        print(f"  {row_id}: {reason}")
    if patched == 0:
        raise RuntimeError("Fail-loud: FIXES was non-empty but 0 rows patched")


if __name__ == "__main__":
    main()
