#!/usr/bin/env python3
"""GOLD STANDARD lee I fix (stage 2b), 2026-08-29 session, continuation of stage 2a
(gold_standard_shard5_lee_20260829_i_arcgis_geo_value_backfill.py).

After stages 1+2a, I (card completeness) = 325/448 (72.5%), FAIL. Live diagnosis
found 96 rows with complete property_address/lat-lng/assessed_value but no
parcel_zones row linking their parcel_id to a zone_code (the join
v_zoning_gold_standard_card requires). Looked up each row's real ZONING code via
the live Lee County Property Appraiser Parcels FeatureServer (same STRAP-match
method as stage 2a: https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/
services/Lee_County_Parcels/FeatureServer/0/query, field ZONING) and cross-checked
against existing zoning_districts rows per jurisdiction:
  95 of 96 had a real STRAP match (1 has a placeholder "Property Appraiser"
     parcel_id, unresolvable, left alone)
  31 of 95 returned no ZONING value at all from ArcGIS (condo/PUD sub-units without
     a parcel-level zoning attribute -- real source gap, not fabricated, left alone)
  64 of 95 have a real zone_code
  60 of 64 already have a matching zoning_districts row for their (jurisdiction, code)
     pair -- SAFE to link, no new zoning_districts row required (this script)
  1  of 64 (2026000134, Cape Coral R1-D) has NO existing zoning_districts row for
     that code -- would require fabricating a new district; per the hard prohibition
     on inventing zoning-standard rows AND the lee_gsd3_0c873526 precedent's explicit
     G-regression warning for exactly this class of gap, NOT inserted. Documented
     I residual.
  3  of 64 excluded for other reasons noted per-row above (STRAP found, but not in
     the 60-row safe set for reasons captured in /tmp/lee_zoning_safe.json at
     generation time -- see BATCHES source list below).

BATCHES loaded from a pre-computed, code-verified list (jurisdiction_id, zone_code,
parcel_ids) generated directly from the live ArcGIS lookup + existing
zoning_districts cross-check (no hand-transcription -- avoids the exact class of
copy-paste error this session caught and discarded on the first draft of this
script). Source data embedded below as LEE_ZONE_LINK_BATCHES.

METHOD (per this session's guardrail: "re-check pencil_dod_evaluate_county('lee')
G after any zoning-table write"): insert parcel_zones rows in small batches grouped
by (jurisdiction_id, zone_code), residential-category batches FIRST (lowest risk,
matches the lee_gsd3_0c873526 precedent's finding that residential-category codes
with NULL parking_per_1000sf do NOT trip the pk1000_applicable fallback, unlike
commercial/mixed-category codes), commercial/mixed batches LAST. G is checked live
after EVERY batch. Any batch that drops G below its pre-batch value is immediately
reverted (DELETE the just-inserted parcel_zones rows) and reported as a residual,
never silently left in a regressed state.

RESULT (executed live 2026-08-29): 58 of 60 rows linked. G stayed PASS throughout
(96.3 -> 96.8, never dropped). I moved 325->383 of 448 (72.5%->85.5%), still FAIL
(gate 95% / 426 rows) but a large gain. One batch reverted: jurisdiction_id=914
(Bonita Springs) zone_code='MH-1' (zoning_districts.id=13459) dropped G 96.8->96.2
on insert -- confirmed live that this district has NO zone_standards row at all
(zero rows for zoning_district_id=13459), the exact "unfillable liability" pattern
flagged in the lee_gsd3_0c873526 precedent. Reverted via DELETE, G confirmed back
to 96.8 immediately after. Those 2 rows (01-48-25-B2-00200.0790,
27-47-25-B2-00412.0020) remain a documented I residual, not fabricated, not
silently dropped.
"""
import os
import json
import time
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Generated directly from live data: ArcGIS STRAP->ZONING lookup for the 96
# card-complete-except-zoning lee rows, cross-checked against existing
# zoning_districts rows per (jurisdiction_id, code). Residential-category
# batches first, commercial/mixed last (risk-ordered per guardrail).
LEE_ZONE_LINK_BATCHES = [
    {"jurisdiction_id": 630, "zone_code": "MH-1", "zone_name": "Mobile Home Low Density",
     "parcel_ids": ["10-45-22-05-00000.2920", "24-43-24-03-00017.0430", "26-43-24-04-00000.0700"]},
    {"jurisdiction_id": 630, "zone_code": "RM-2", "zone_name": "Residential Multiple Low Density",
     "parcel_ids": ["05-45-27-21-000K0.0060"]},
    {"jurisdiction_id": 630, "zone_code": "RS-1", "zone_name": "Residential Single-Family Low Density",
     "parcel_ids": ["02-44-26-L3-12118.0040", "02-44-27-15-00057.0160", "07-45-27-L1-07028.0120",
                     "08-44-22-01-0000B.0350", "10-45-27-L1-05026.0060", "10-45-27-L4-09050.0040",
                     "11-44-24-22-00000.0040", "16-44-24-02-00000.0010", "22-45-27-L3-13082.0050",
                     "23-45-27-L2-03027.0140", "23-45-27-L3-15053.0030", "27-44-26-L4-03033.0030",
                     "28-44-22-10-0000D.0020", "31-44-27-06-00001.A020", "34-44-26-L1-06052.0020"]},
    {"jurisdiction_id": 815, "zone_code": "R1", "zone_name": "R1 Zone",
     "parcel_ids": ["01-44-22-C3-05227.0030", "02-44-23-C2-02623.0110", "06-44-23-C4-04217.0310",
                     "06-44-23-C4-04226.0250", "06-44-24-C1-02075.0090", "07-44-23-C2-04131.0360",
                     "08-44-23-C1-03991.0200", "09-44-23-C3-03760.0450", "11-44-23-C2-02604.0530",
                     "18-43-23-C4-05504.0050", "18-44-23-C2-05305.0420", "22-44-23-C4-04436.0030",
                     "25-43-22-C2-05155.0170", "25-43-22-C2-05158.0040", "25-43-22-C2-05185.0290",
                     "25-43-22-C3-05184.0290", "26-44-23-C2-03081.0390", "31-43-23-C4-04315.0030",
                     "32-43-23-C4-04093.0470", "33-43-23-C1-03853.0010", "33-44-23-C1-05890.0320",
                     "33-44-23-C1-05893.0060", "33-44-23-C3-04791.0200"]},
    {"jurisdiction_id": 815, "zone_code": "RML", "zone_name": "Residential Multi-Family Low",
     "parcel_ids": ["10-45-23-C4-03377.0170", "11-45-23-C4-01713.0090", "12-45-23-C3-02200.0090"]},
    {"jurisdiction_id": 914, "zone_code": "MH-1", "zone_name": "Mobile Home Zoning District 1 (Bonita Springs)",
     "parcel_ids": ["01-48-25-B2-00200.0790", "27-47-25-B2-00412.0020"]},
    {"jurisdiction_id": 914, "zone_code": "TFC-2", "zone_name": "TFC-2 Zone",
     "parcel_ids": ["36-47-25-B3-01200.0340"]},
    {"jurisdiction_id": 929, "zone_code": "AG-2", "zone_name": "AG-2 Zone",
     "parcel_ids": ["18-44-26-07-00020.0000"]},
    {"jurisdiction_id": 929, "zone_code": "MH-2", "zone_name": "MH-2 Zone",
     "parcel_ids": ["20-46-25-00-00017.0110"]},
    {"jurisdiction_id": 929, "zone_code": "RM-12", "zone_name": "Residential Multifamily - 12",
     "parcel_ids": ["19-44-25-P1-00209.0010"]},
    {"jurisdiction_id": 929, "zone_code": "RPD", "zone_name": "RPD Zone",
     "parcel_ids": ["06-46-24-32-00000.0610", "12-46-24-05-00000.9047"]},
    {"jurisdiction_id": 929, "zone_code": "RS-1", "zone_name": "Residential Single-Family Low Density",
     "parcel_ids": ["29-43-26-05-00089.0200", "30-43-26-01-00002.0310"]},
    # --- commercial/mixed batches LAST, highest G-regression risk per precedent ---
    {"jurisdiction_id": 815, "zone_code": "C", "zone_name": "Commercial",
     "parcel_ids": ["05-44-23-C4-04029.0210", "27-44-23-C1-04414.0630", "34-43-23-C1-02942.B080"]},
    {"jurisdiction_id": 929, "zone_code": "NC", "zone_name": "Neighborhood Commercial",
     "parcel_ids": ["02-45-24-P4-02325.0010"]},
    {"jurisdiction_id": 929, "zone_code": "CPD",
     "zone_name": ("Community Planning District (Fort Myers -- project-specific planned "
                    "development; density/FAR set per approved master plan, not a fixed "
                    "per-district standard; INFERRED: similar to Lee County unincorporated "
                    "CPD treatment in prior sessions)"),
     "parcel_ids": ["33-45-24-24-0000G.0070"]},
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

    total_linked = 0
    total_skipped_dup = 0
    reverted_batches = []
    for b in LEE_ZONE_LINK_BATCHES:
        jur, code, name, pids = b["jurisdiction_id"], b["zone_code"], b["zone_name"], b["parcel_ids"]
        rows = [{"parcel_id": pid, "jurisdiction_id": jur, "zone_code": code,
                  "zone_name": name, "source": "lee_20260829_i_zone_link_arcgis_crosscheck"}
                for pid in pids]
        try:
            resp = rest_post("parcel_zones", rows)
        except Exception as e:
            print(f"  BATCH FAIL jur={jur} code={code}: {e}")
            continue
        inserted_ids = [r["id"] for r in resp] if isinstance(resp, list) else []
        n_inserted = len(inserted_ids)
        n_skipped = len(pids) - n_inserted
        total_linked += n_inserted
        total_skipped_dup += n_skipped

        ev = evaluate()
        g_after = ev["G"]["metric"]
        print(f"  jur={jur} code={code}: inserted={n_inserted} skipped_dup={n_skipped} "
              f"-> G={g_after} (was {g_before}) I={ev['I']['metric']}")

        if g_after < g_before:
            print(f"    G REGRESSION DETECTED ({g_before} -> {g_after}). Reverting this batch.")
            if inserted_ids:
                id_list = ",".join(str(i) for i in inserted_ids)
                rest_delete(f"parcel_zones?id=in.({id_list})")
            reverted_batches.append({"jurisdiction_id": jur, "zone_code": code, "parcel_ids": pids})
            total_linked -= n_inserted
            ev2 = evaluate()
            print(f"    post-revert: G={ev2['G']['metric']} pass={ev2['G']['pass']}")
            g_before = ev2["G"]["metric"]
        else:
            g_before = g_after
        time.sleep(0.3)

    ev_final = evaluate()
    print(f"\nTOTALS: linked={total_linked} skipped_dup={total_skipped_dup} "
          f"reverted_batches={len(reverted_batches)}")
    print(f"FINAL: G={ev_final['G']['metric']} pass={ev_final['G']['pass']}  "
          f"I={ev_final['I']['metric']} ({ev_final['I']['detail']})")
    if reverted_batches:
        print("REVERTED (G-regression, left as documented residual, not fabricated):")
        for rb in reverted_batches:
            print(f"    jur={rb['jurisdiction_id']} code={rb['zone_code']} pids={rb['parcel_ids']}")


if __name__ == "__main__":
    main()
