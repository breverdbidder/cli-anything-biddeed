#!/usr/bin/env python3
"""GOLD STANDARD lee I fix (stage 3), 2026-08-29 session, continuation of stage 2b
(gold_standard_shard5_lee_20260829_i_zone_link.py). Live re-measured after stage 2b:
I = 383/448 (85.5%), FAIL (gate 95% / 426 rows). G = 96.8, PASS.

Live re-diagnosis of the 65-row residual (replicating pencil_dod_evaluate_county's
tier1-eligible cohort: is_operational=true AND (data_source != 'propertyonion' OR
data_source IS NULL), exactly 448 rows matching auctions_total) found:
  14  rows with NO parcel_id at all (unresolvable via this method, see stage 4 notes)
  2   rows with parcel_id but NO property_address (unresolvable via this method)
  38  rows with property_address + lat/lng + assessed_value/market_value ALL present,
      but parcel_id NOT linked in v_zoning_gold_standard_card (missing from
      parcel_zones, or zone_code null)

TRANSFORM DISCOVERY (this session): the prior "strip -/. from parcel_id" transform
does NOT cover Lehigh Acres / block-numbering-scheme parcels. Live cross-check of
this session's confirmed-successful parcel_zones rows
(source=lee_20260829_i_zone_link_arcgis_crosscheck) against the live ArcGIS
FeatureServer showed the naive strip works ONLY when our parcel_id's block segment
is ALREADY alphanumeric (e.g. "C3", "L3", "B2", "P1" -- these pass through
unmodified). For parcel_ids with a purely NUMERIC block segment (e.g. "02", "03",
"06"), the naive strip produces zero ArcGIS matches: verified live for
16-44-27-02-00008.0030 -> stripped "16442702000080030" returns 0 features, AND a
wildcard STRAP LIKE '164427%' scan shows this TRS has NO plain-numeric block STRAPs
at all (only L1/L2/L3/L4 and "99" blocks exist) -- confirming the numeric block code
in our parcel_id and the letter block code in ArcGIS's STRAP are NOT the same
namespace / not string-transformable (no fixed numeric->letter mapping: e.g.
"02" appeared as L3 for one parcel and as L1/L4 for others in the same TRS). There
is no deterministic transform; only an independent identifier (property_address)
correctly recovers the correct feature.

RESOLUTION METHOD (this script's source data): address-based ArcGIS lookup
(SITENUMBER exact + SITESTREET exact/fallback unit-suffix match against
property_address) against https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/
rest/services/Lee_County_Parcels/FeatureServer/0/query, fields STRAP/ZONING/
SITEADDR/SITENUMBER/SITESTREET. Of the 38-row gap:
  23  resolved to exactly one ArcGIS feature via SITENUMBER+SITESTREET exact match
  14  resolved to exactly one feature via SITENUMBER + unit-suffix fallback (all are
      condo/PUD sub-units on multi-unit STRAP families e.g. "144423C3001002060")
  1   (parcel_id literally "Property Appraiser", a placeholder value) unresolvable

Of the 23 exact matches:
  3   returned no/empty ZONING from ArcGIS (Sanibel T2/T3/T4 STRAPs -- real source
      gap, condo/PUD-style sub-parcels on the island, left alone, not fabricated)
  2   (27-47-25-B2-00412.0020, 01-48-25-B2-00200.0790) are the EXACT SAME 2 rows
      the prior script (gold_standard_shard5_lee_20260829_i_zone_link.py) already
      inserted and reverted -- jurisdiction_id=914 (Bonita Springs) zone_code
      "MH-1" has ZERO zone_standards rows (confirmed dead end, would drop G if
      re-inserted). NOT re-attempted per task instructions.
  1   (07-45-24-C2-05300.0100, Cape Coral, ZONING="R1-D") has NO existing
      zoning_districts row for (jurisdiction_id=815, code="R1-D") -- only a plain
      "R1" district exists (id=11226). Per the hard prohibition on inventing new
      zoning_districts rows, NOT inserted. Documented I residual.
  17  have a real ZONING value (16x RS-1, 1x RM-2) AND an existing matching
      zoning_districts row for (jurisdiction_id=630 "Lee County (Unincorporated)",
      code) -- SAFE to link, same low-risk residential-category pattern that
      caused zero G-regression in the prior stage's RS-1/RM-2 batches under the
      same jurisdiction_id=630.

All 14 condo/PUD unit matches returned ZONING=None/empty from ArcGIS -- verified
this is a structural gap (checked the building's own "common element" parent STRAP
e.g. 034724W10560000CE, also ZONING=None), not a lookup failure. Real source gap,
left alone.

METHOD: insert parcel_zones rows in ONE batch (all 17 rows share the same
jurisdiction_id=630, low-risk residential codes already proven safe in stage 2b).
Re-check pencil_dod_evaluate_county('lee') G immediately after; revert on any
regression (same guardrail as stage 2b).
"""
import os
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Generated directly from live ArcGIS address-lookup + zoning_districts cross-check
# (see docstring). All jurisdiction_id=630, both codes already have existing
# zoning_districts rows (RS-1 id=11108, RM-2 id=11208).
LEE_ROUND2_ZONE_LINK_ROWS = [
    {"parcel_id": "16-44-27-02-00008.0030", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "28-44-27-03-00011.0200", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "11-45-26-07-00072.0170", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "24-44-27-04-00015.0090", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "05-45-26-06-00001.0310", "jurisdiction_id": 630, "zone_code": "RM-2",
     "zone_name": "Residential Multiple Low Density"},
    {"parcel_id": "29-44-27-07-00028.013B", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "06-44-27-03-00239.0060", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "18-44-27-06-00021.0070", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "18-44-27-07-00028.0100", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "20-44-27-01-00002.0220", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "24-44-27-01-00003.0040", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "25-44-27-08-00032.0220", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "24-44-27-06-00024.0210", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "12-45-26-06-00063.0100", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "24-44-27-10-00040.0200", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "25-44-27-11-00043.0240", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "18-44-27-06-00021.0120", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
]


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=ignore-duplicates,return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_delete(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", method="DELETE",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                                           "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def evaluate():
    body = json.dumps({"p_county": "lee"}).encode()
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                                  data=body, method="POST",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                                           "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    ev0 = evaluate()
    g_before = ev0["G"]["metric"]
    print(f"BASELINE: G={g_before} pass={ev0['G']['pass']}  I={ev0['I']['metric']} ({ev0['I']['detail']})")

    rows = [{**r, "source": "lee_20260829_i_round2_zone_link_arcgis_address_match"}
            for r in LEE_ROUND2_ZONE_LINK_ROWS]

    try:
        resp = rest_post("parcel_zones", rows)
    except Exception as e:
        print(f"BATCH FAILED: {e}")
        return

    inserted_ids = [r["id"] for r in resp] if isinstance(resp, list) else []
    n_inserted = len(inserted_ids)
    n_skipped = len(rows) - n_inserted
    print(f"inserted={n_inserted} skipped_dup={n_skipped}")

    ev = evaluate()
    g_after = ev["G"]["metric"]
    print(f"POST-INSERT: G={g_after} (was {g_before}) I={ev['I']['metric']} ({ev['I']['detail']})")

    if g_after < g_before:
        print(f"G REGRESSION DETECTED ({g_before} -> {g_after}). Reverting entire batch.")
        if inserted_ids:
            id_list = ",".join(str(i) for i in inserted_ids)
            rest_delete(f"parcel_zones?id=in.({id_list})")
        ev2 = evaluate()
        print(f"post-revert: G={ev2['G']['metric']} pass={ev2['G']['pass']}  I={ev2['I']['metric']}")
    else:
        print("No G regression. Batch kept.")

    ev_final = evaluate()
    print(f"\nFINAL: G={ev_final['G']['metric']} pass={ev_final['G']['pass']}  "
          f"I={ev_final['I']['metric']} ({ev_final['I']['detail']})")


if __name__ == "__main__":
    main()
