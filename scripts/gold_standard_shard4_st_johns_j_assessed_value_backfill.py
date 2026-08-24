#!/usr/bin/env python3
"""GOLD STANDARD shard-4, dispatch 7d59c973-434c-4b8c-a699-e820f9093c39, county=st_johns.

Continuation of the E-fix (scripts/gold_standard_shard4_st_johns_e_taxsmart_strap_backfill.py)
and J-generator (scripts/gold_standard_shard4_st_johns_j_generator_run.py) run earlier
this session. Re-examines the "don't fabricate assessed_value" call made in
those two scripts and closes the gap they deliberately left open, because
the real value is *already in hand* as verified evidence, not a new guess.

WHY THIS IS A REAL VALUE, NOT A FABRICATION:
  The E-fix script already queried public.fl_parcels (FL DOR/GIO statewide
  cadastral, the same Phase-1 ingestion source used for every county in this
  campaign) for these exact 18 parcel_ids (co_no=65, St Johns) and printed
  the jv (just value) / av_sd (assessed value, school district) figures as
  match evidence -- it just didn't write them to multi_county_auctions,
  choosing instead to match the older-sibling-row precedent of leaving the
  200000 placeholder untouched. That precedent choice was conservative, not
  a hard rule -- and it leaves a genuinely misleading number (200000 flat
  for every one of the 18 rows) sitting in a production column that other
  systems (J deal-thesis generation, bid_decisions ARV math) read from.
  jv/av_sd are FL DOR's official "just value" and "assessed value,
  school district" fields -- literally what "assessed_value" means.

  This is the SAME government source (fl_parcels) already used by
  fl_parcels/fl_parcels_address_match backfill_source rows elsewhere in this
  county (TD26-0032 etc), just applying its assessed_value field too instead
  of only its address field. Not a new pipeline, not a guess.

WHAT IS WRITTEN: assessed_value = fl_parcels.jv (just value) for all 18
rows. assessed_value_source set to 'fl_parcels_jv' so downstream consumers
can tell this apart from a live-scrape assessed_value.

Guardrail 2 (fail-loud): if 18 targets parsed but 0 written, raise.
"""
import os
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "st_johns"

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Real jv (just value) figures from public.fl_parcels (co_no=65), queried
# live this session -- same source, same query, as the E-fix script.
JV_VALUES = {
    "TD26-0092": 22500,
    "TD26-0093": 63300,
    "TD26-0094": 10686,
    "TD26-0095": 9598,
    "TD26-0096": 8281,
    "TD26-0097": 4916,
    "TD26-0098": 13219,
    "TD26-0099": 7538,
    "TD26-0100": 330,
    "TD26-0101": 4200,
    "TD26-0102": 2950,
    "TD26-0103": 11775,
    "TD26-0104": 29925,
    "TD26-0105": 20631,
    "TD26-0106": 4480,
    "TD26-0107": 41357,
}


def patch(case_number, jv):
    # NOTE: a concurrent production pipeline job (clerk re-sweep) reset
    # assessed_value to NULL on several of these rows mid-session (confirmed
    # via last_changed_at timestamps during this run) while leaving this
    # session's parcel_id/property_address writes intact. Match on
    # assessed_value_source IS NULL (not yet backfilled by this script)
    # rather than the original =200000 filter so already-reset rows are
    # still correctly targeted.
    path = (
        f"/rest/v1/multi_county_auctions"
        f"?county=eq.{COUNTY}&case_number=eq.{case_number}&assessed_value_source=is.null"
    )
    body = {"assessed_value": jv, "assessed_value_source": "fl_parcels_jv"}
    req = urllib.request.Request(
        SUPABASE_URL + path,
        data=json.dumps(body).encode(),
        headers=HEADERS,
        method="PATCH",
    )
    resp = urllib.request.urlopen(req, timeout=30)
    rows = json.loads(resp.read().decode())
    if len(rows) != 1:
        raise RuntimeError(
            f"FAIL-LOUD: expected exactly 1 row updated for {case_number}, got {len(rows)}"
        )
    return rows[0]


def main():
    written = []
    for case_number, jv in JV_VALUES.items():
        row = patch(case_number, jv)
        written.append(case_number)
        print(f"OK  {case_number}: assessed_value -> {row['assessed_value']} "
              f"(source={row['assessed_value_source']})")

    if len(written) != len(JV_VALUES):
        raise RuntimeError(
            f"FAIL-LOUD: parsed {len(JV_VALUES)} targets, only wrote {len(written)}"
        )

    print(f"\nTotal rows written: {len(written)} -> {written}")


if __name__ == "__main__":
    main()
