#!/usr/bin/env python3
"""GOLD STANDARD lee I fix (stage 4), 2026-08-29 session, continuation of stage 3
(gold_standard_shard5_lee_20260829_i_round2_zone_link.py). Live re-measured after
stage 3: I = 400/448 (89.3%), FAIL (gate 95% / 426 rows). G = 97.0, PASS.

Residual after stage 3: 16 rows (14 no-parcel_id, 2 parcel_id-but-no-address).

Of the 14 no-parcel_id rows: 11 have NEITHER parcel_id NOR property_address (fully
blank rows -- unresolvable via ArcGIS address lookup, genuinely unfillable without a
new upstream source; left alone). 3 have an address but no parcel_id:
  26-CA-000071  "11100 ORANGE RIVER BLVD"        -> exact SITENUMBER+SITESTREET
  26-CA-000056  "616 MAPLE AVE N"                -> exact SITENUMBER+SITESTREET
  25-CA-006255  "7127 ALMENDRO TER 4"            -> exact SITENUMBER+SITESTREET+unit
A 4th, 24-CC-004249 "16300 PINE RIDGE RD LOT X18" (mobile-home-park lot format), was
searched (SITENUMBER=16300 and SITESTREET LIKE '%PINE RIDGE%') and returned NO
STRAP with a matching SITENUMBER -- genuinely unresolvable via this method, left
alone, not fabricated.

For the 3 resolved rows, looked up the live Lee County Property Appraiser Parcels
FeatureServer (https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/
Lee_County_Parcels/FeatureServer/0/query) by SITENUMBER (+SITESTREET/unit
disambiguation), confirmed SITEADDR echoes our stored property_address exactly
(no ambiguity), and derived:
  - parcel_id in our TRS-block-parcelnum.unit convention from the matched STRAP
  - latitude/longitude via polygon centroid (same method as prior geo backfill
    script, card-completeness only, not used for spatial zoning joins)
  - assessed_value from the ASSESSED field
  - zone_code from ZONING, cross-checked against existing zoning_districts rows
    for jurisdiction_id=630 ("Lee County (Unincorporated)" -- matches the same
    jurisdiction confirmed for other Lehigh Acres / unincorporated parcels this
    session): all 3 codes (AG-2, RS-1, RM-2) already have existing
    zoning_districts rows (ids 11214, 11108, 11208) -- SAFE to link.

METHOD: PATCH multi_county_auctions (parcel_id/latitude/longitude/assessed_value)
first (zero G-regression risk, pure multi_county_auctions write), THEN insert
parcel_zones in one batch and re-check pencil_dod_evaluate_county('lee') G;
revert the parcel_zones batch only (not the multi_county_auctions patch, which
carries no G risk) on any regression, same guardrail as prior stages.
"""
import os
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Generated directly from live ArcGIS SITENUMBER/SITESTREET lookup (see docstring).
ROWS = [
    {
        "id": "8cf27065-79b2-49cc-b7c3-9befb10a689f",  # case 26-CA-000071
        "parcel_id": "01-44-25-01-00015.0000",
        "latitude": 26.678756, "longitude": -81.774598,
        "assessed_value": 204989,
        "jurisdiction_id": 630, "zone_code": "AG-2", "zone_name": "Agricultural",
    },
    {
        "id": "0da461a8-d4ad-48ae-b47e-b81fbce1c08b",  # case 26-CA-000056
        "parcel_id": "28-44-27-L2-09034.0230",
        "latitude": 26.623926, "longitude": -81.616124,
        "assessed_value": 319132,
        "jurisdiction_id": 630, "zone_code": "RS-1",
        "zone_name": "Residential Single-Family Low Density",
    },
    {
        "id": "f6493226-b755-485f-b9ab-ea0bc2a6ad7a",  # case 25-CA-006255
        "parcel_id": "14-45-24-37-000Q0.0040",
        "latitude": 26.561991, "longitude": -81.874474,
        "assessed_value": 140766,
        "jurisdiction_id": 630, "zone_code": "RM-2",
        "zone_name": "Residential Multiple Low Density",
    },
]


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


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

    for r in ROWS:
        patch_body = {"parcel_id": r["parcel_id"], "latitude": r["latitude"],
                       "longitude": r["longitude"], "assessed_value": r["assessed_value"]}
        rest_patch(f"multi_county_auctions?id=eq.{r['id']}", patch_body)
        print(f"  PATCHED multi_county_auctions id={r['id']} parcel_id={r['parcel_id']}")

    zone_rows = [{"parcel_id": r["parcel_id"], "jurisdiction_id": r["jurisdiction_id"],
                  "zone_code": r["zone_code"], "zone_name": r["zone_name"],
                  "source": "lee_20260829_i_round2_nopid_backfill_arcgis"} for r in ROWS]
    try:
        resp = rest_post("parcel_zones", zone_rows)
    except Exception as e:
        print(f"parcel_zones BATCH FAILED: {e}")
        return
    inserted_ids = [r["id"] for r in resp] if isinstance(resp, list) else []
    print(f"parcel_zones inserted={len(inserted_ids)} of {len(zone_rows)}")

    ev = evaluate()
    g_after = ev["G"]["metric"]
    print(f"POST-INSERT: G={g_after} (was {g_before}) I={ev['I']['metric']} ({ev['I']['detail']})")

    if g_after < g_before:
        print(f"G REGRESSION DETECTED ({g_before} -> {g_after}). Reverting parcel_zones batch only.")
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
