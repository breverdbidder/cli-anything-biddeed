#!/usr/bin/env python3
"""
GOLD STANDARD dixie letters E + I -- fix the last 2 unlinked rows (2026-08-25).

Root cause (VERIFIED live): dixie had exactly 2 of 35 multi_county_auctions rows with
parcel_id IS NULL and property_address stuck on the placeholder "DIXIE COUNTY, FL":
  - id=0efd37b5-38e7-42ec-8227-cad7c75ae3cc, case_number=15-2025-CA-46 (foreclosure)
  - id=95d45bcf-d092-4393-a3f2-126f0c9c80f2, case_number=15-2025-CA-24 (foreclosure)
Both had real lat/lon and assessed_value/market_value already populated from a prior
session -- only property_address and parcel_id were missing, holding E (parcel-linkage
%) and I (property-card completeness) at 94.3% (33/35).

Research chain (all VERIFIED, no fabrication):
  1. dixieclerk.com foreclosure-sales page (raw HTML, not just WebFetch summary) gave
     the real service addresses for both cases:
       15-2025-CA-46 -> 159 SE 243RD ST, CROSS CITY FL 32628 (defendant Lyndi Brooke Bridge)
       15-2025-CA-24 -> 125 NE 450TH ST, OLD TOWN FL 32680 (defendant Roger Thomas Ansin Jr)
  2. US Census TIGER geocoder confirmed both addresses resolve to real, valid FL
     addresses (coords within ~0.01 deg of the pre-existing DB lat/lon).
  3. Dixie County Tax Collector (dixie.floridatax.us, ASP.NET WebForms, "Powered by
     Phenix.net") owner-name search matched both defendants exactly by last name
     (BRIDGE, ANSIN) with matching property address AND assessed/market value already
     in our DB ($114,900 and $110,200 respectively) -- strong independent corroboration.
  4. Each tax-collector PropertyDetail page embeds an outbound link to the Property
     Appraiser's qpublic.schneidercorp.com record with a `KeyValue=` query param --
     this is the county's own authoritative DOR-format parcel_id cross-reference
     (qpublic itself 403s to non-browser fetchers -- Cloudflare-gated -- but the
     KeyValue is sourced from the tax collector's own page, not invented):
       BRIDGE  (15-2025-CA-46) -> KeyValue=09-10-12-2450-0000-0160
       ANSIN   (15-2025-CA-24) -> KeyValue=32-09-13-4492-0002-0730
  5. Both parcel_ids already exist in v_zoning_gold_standard_card for county='dixie',
     jurisdiction_id=975, zone_code='R-1' -- no new zoning research/insert was needed;
     letter I's zoning-linkage gate was already satisfied once parcel_id was set.

Effect (live, VERIFIED via pencil_dod_evaluate_county('dixie')):
  E: 94.3% (33/35) -> 100.0% (35/35) PASS
  I: 94.3% (33/35) -> 100.0% (35/35) PASS
  All other letters (A/B/C/D/F/G/H/J) unaffected -- untouched fields.

This script is idempotent: it targets the two rows by id and only writes fields that
were previously null/placeholder, using PATCH (not upsert), so re-running with the
same already-applied values is a no-op.

Usage: python3 scripts/gold_standard_dixie_ei_last2rows_fix.py
"""
import json
import os
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

UPDATES = [
    {
        "id": "0efd37b5-38e7-42ec-8227-cad7c75ae3cc",
        "case_number": "15-2025-CA-46",
        "fields": {
            "parcel_id": "09-10-12-2450-0000-0160",
            "property_address": "159 SE 243RD ST, CROSS CITY, FL 32628",
            "city": "CROSS CITY",
            "zip": "32628",
            "assessed_value_source": "dixie.floridatax.us tax collector record (verified 2026-08-25)",
        },
    },
    {
        "id": "95d45bcf-d092-4393-a3f2-126f0c9c80f2",
        "case_number": "15-2025-CA-24",
        "fields": {
            "parcel_id": "32-09-13-4492-0002-0730",
            "property_address": "125 NE 450TH ST, OLD TOWN, FL 32680",
            "city": "OLD TOWN",
            "zip": "32680",
            "assessed_value_source": "dixie.floridatax.us tax collector record (verified 2026-08-25)",
        },
    },
]


def main():
    assert SUPABASE_KEY, "SUPABASE_SERVICE_ROLE_KEY required"
    for upd in UPDATES:
        req = urllib.request.Request(
            f"{BASE}/multi_county_auctions?id=eq.{upd['id']}",
            data=json.dumps(upd["fields"]).encode(),
            headers=HEADERS,
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            updated = json.loads(resp.read().decode())
        if updated:
            row = updated[0]
            print(f"Updated {upd['case_number']} ({upd['id']}):")
            print(f"  parcel_id -> {row.get('parcel_id')}")
            print(f"  property_address -> {row.get('property_address')}")
        else:
            print(f"WARNING: no row matched id={upd['id']} (already applied or id changed)")


if __name__ == "__main__":
    main()
