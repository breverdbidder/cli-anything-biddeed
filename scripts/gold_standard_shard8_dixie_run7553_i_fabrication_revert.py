#!/usr/bin/env python3
"""
GOLD STANDARD shard-8 (brevard/dixie), dispatch_id c6b5fdd6-b4a0-4da7-aa46-f104f222ac7d, loop run 7553.

Root cause (VERIFIED live, 2026-07-31): 32 of dixie's 34 multi_county_auctions rows shared
an identical placeholder signature -- property_address='DIXIE COUNTY, FL', latitude=29.5839,
longitude=-83.1702, assessed_value=134615.38 -- a residual of the fabrication incident this
same county had reverted on 2026-07-10 (migrations/20260710_gold_standard_shard8_dixie_
fabrication_revert_completion.sql). That migration explicitly deferred cleaning up the 30
DIXIE-SYNTH-* auction-listing rows themselves ("out of scope per the original script,
flagged there as BLOCKED/deferred for a dedicated full-county revert") -- this script is
that dedicated revert, discovered independently while working letter I this session.

This fabrication was inflating letter I (property card completeness): dixie showed
card_complete=32 of 34 (94.1%) resting almost entirely on the fake placeholder, not real
per-parcel data. parcel_id was NOT part of the fabrication (it is derived from real
dixieclerk.com cert data, confirmed real for all 32 rows) -- only property_address,
latitude, longitude, assessed_value, and market_value were fake, and only those fields
are touched here.

Effect (live, VERIFIED via pencil_dod_evaluate_county('dixie')):
  I: 94.1% (32 of 34) -> 0.0% (0 of 34) -- an honest regression, not a bug. This also
  revealed that even the 2 rows with fully real, cross-verified data (15-2025-CA-10,
  15-2025-CA-46, enriched this same session via FL DOR Cadastral + Dixie Tax Collector)
  do NOT count as card_complete -- proving I's real gate for dixie is zoning-parcel
  linkage (the v_zoning_gold_standard_card join), not address/geo/value completeness.
  Dixie zoning-parcel coverage is the actual next lever for I, not further address
  enrichment. G reporting 100% for dixie despite this needs re-investigation -- likely a
  denominator-scoping artifact in v_zoning_gold_standard_kpi_v3, not real parcel coverage.
  C/D/E/F/G/H/J unaffected (E/parcel_id was not touched; C/D depend on parity_status only).

This script is idempotent: the exact-match filter (all four placeholder values) matches
zero rows once already reverted.

Usage: python3 scripts/gold_standard_shard8_dixie_run7553_i_fabrication_revert.py
"""
import json
import os
import urllib.parse
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

FILTER = {
    "county": "eq.dixie",
    "property_address": "eq.DIXIE COUNTY, FL",
    "latitude": "eq.29.5839",
    "longitude": "eq.-83.1702",
    "assessed_value": "eq.134615.38",
}

REVERT_FIELDS = {
    "property_address": None,
    "latitude": None,
    "longitude": None,
    "assessed_value": None,
    "market_value": None,
}


def main():
    assert SUPABASE_KEY, "SUPABASE_SERVICE_ROLE_KEY required"
    qs = urllib.parse.urlencode(FILTER, safe="(),.")
    req = urllib.request.Request(
        f"{BASE}/multi_county_auctions?{qs}",
        data=json.dumps(REVERT_FIELDS).encode(),
        headers=HEADERS,
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        updated = json.loads(resp.read().decode())
    print(f"Reverted fabricated placeholder fields on {len(updated)} rows:")
    for row in updated:
        print(" ", row.get("case_number"))


if __name__ == "__main__":
    main()
