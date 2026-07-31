#!/usr/bin/env python3
"""
Gold Standard shard-9 (dispatch 255f0be0) — highlands G regression fix.

The 2nd-firing highlands-I ULTRALOOP fix created jurisdiction_id=1654
("Highlands County", unincorporated) and 4 new zoning_districts (R1/R1A/AU/B1)
plus 45 parcel_zones rows to close the I gap (real, adversarially-verified:
82.6% -> 98.5%, all 45 parcels confirmed via live spatial point-in-polygon
against the county's own Municipal_Boundary ArcGIS layer to be genuinely
unincorporated, not Sebring/Lake Placid/Avon Park despite mailing address).

That fix had a side effect: it regressed G (zoning density/FAR/pk1000
coverage) from PASS 99.5% to FAIL 0.0%, because the 4 new districts had no
zone_standards rows, and v_zoning_gold_standard_kpi_v3's applicability
defaults treat an unmatched/unstandardized district as APPLICABLE-but-empty
rather than N/A — so adding 45 parcels with zero standards coverage dragged
the countywide average to zero.

This script documents (idempotent re-apply) the fix: real, ordinance-cited
zone_standards for all 4 districts, sourced directly from the Highlands
County Land Development Regulations PDF (fetched and parsed with pypdf,
784 pages, specific sections confirmed verbatim by an independent
adversarial-verify subagent before this was treated as shipped):

  R1 (id 13183) / R1A (id 13185): Sec. 12.05.210.E min lot 10,000 sq ft
    (Sec. 12.05.211: R-1 uses identical standards to R-1A) ->
    max_density_du_acre = 43,560 / 10,000 = 4.36. far_regulated=false,
    pk1000_regulated=false (single-family residential; Sec 12.05.210.F uses
    max lot coverage 50%, not FAR; Table 3 prices single-family parking
    per-bedroom, not per-1000sf).
  AU (id 13186): Sec. 12.05.200.G.1 min lot 5 acres for all uses ->
    max_density_du_acre = 1/5 = 0.20. far_regulated=false,
    pk1000_regulated=false (agricultural district, no FAR/commercial-parking
    concept in this LDR).
  B1 (id 13184): Sec. 12.05.240.I.2 "Up to 0.80 [FAR] for other commercial
    uses" (0.70 for office) -> max_far=0.80. density_regulated=false
    (commercial, not residential). parking_per_1000sf=2.5 — INFERRED, not a
    single stated per-district ratio; derived from Table 3 (Sec 12.10.200)
    "Retail Shop or Store (not otherwise listed) and Department Stores: 1
    space per 400 sq ft" = 2.5/1000sf, chosen as representative of B-1's
    primary permitted use (general retail/personal service).

Live result confirmed by adversarial-verify subagent: G restored to PASS
99.6% (density=99.6 far=100.0 pk1000=100.0), all 10 highlands letters (A-J)
PASS. gold_standard_ultraloop_audit row inserted (county_slug=highlands,
letter=G, survived=true).
"""
import os
import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
HEADERS_MIN = {**HEADERS, "Prefer": "return=minimal"}

LDR_SOURCE = ("https://cms2.revize.com/revize/highlandscountyfl/departments/"
              "development_services/planning/LDRS%20thru%20Ord%2021-22-28%20(6-21-22)%20ADA.pdf")

DISTRICTS = {
    13183: {  # R1
        "flags": {"density_regulated": True, "far_regulated": False, "pk1000_regulated": False},
        "standards": {"max_density_du_acre": 4.36, "max_far": None, "parking_per_1000sf": None,
                       "ordinance_section": "Sec. 12.05.211 (R-1, same as R-1A) x Sec. 12.05.210.E min lot 10,000sf -> 43560/10000; "
                                             "F: max lot coverage 50% (no FAR concept, single-family uses lot coverage not FAR)",
                       "confidence_score": 0.9},
    },
    13185: {  # R1A
        "flags": {"density_regulated": True, "far_regulated": False, "pk1000_regulated": False},
        "standards": {"max_density_du_acre": 4.36, "max_far": None, "parking_per_1000sf": None,
                       "ordinance_section": "Sec. 12.05.210.E min lot 10,000sf -> 43560/10000; "
                                             "F: max lot coverage 50% (no FAR concept, single-family uses lot coverage not FAR)",
                       "confidence_score": 0.9},
    },
    13186: {  # AU
        "flags": {"density_regulated": True, "far_regulated": False, "pk1000_regulated": False},
        "standards": {"max_density_du_acre": 0.20, "max_far": None, "parking_per_1000sf": None,
                       "ordinance_section": "Sec. 12.05.200.G.1 min lot 5 acres for all uses -> 1 DU per 5 acres "
                                             "(agricultural district, no FAR/parking-per-1000sf concept applies)",
                       "confidence_score": 0.9},
    },
    13184: {  # B1
        "flags": {"density_regulated": False, "far_regulated": True, "pk1000_regulated": True},
        "standards": {"max_density_du_acre": None, "max_far": 0.80, "parking_per_1000sf": 2.5,
                       "ordinance_section": "Sec. 12.05.240.I.2 max FAR 0.80 (other commercial uses, 0.70 for office); "
                                             "parking INFERRED from Table 3 Sec 12.10.200 Retail Shop or Store "
                                             "(not otherwise listed): 1 space/400sf = 2.5/1000sf, representative of "
                                             "B-1's primary retail/personal-service use",
                       "confidence_score": 0.7},
    },
}


def main():
    client = httpx.Client(timeout=60)
    for district_id, cfg in DISTRICTS.items():
        client.patch(f"{SUPABASE_URL}/rest/v1/zoning_districts", headers=HEADERS_MIN,
                     params={"id": f"eq.{district_id}"}, json=cfg["flags"])

        existing = client.get(f"{SUPABASE_URL}/rest/v1/zone_standards", headers=HEADERS,
                              params={"zoning_district_id": f"eq.{district_id}", "select": "id"})
        rows = existing.json() if existing.status_code == 200 else []
        body = {"zoning_district_id": district_id, "source_url": LDR_SOURCE, **cfg["standards"]}
        if rows:
            client.patch(f"{SUPABASE_URL}/rest/v1/zone_standards", headers=HEADERS_MIN,
                         params={"id": f"eq.{rows[0]['id']}"}, json=body)
        else:
            client.post(f"{SUPABASE_URL}/rest/v1/zone_standards", headers=HEADERS_MIN, json=body)
        print(f"district {district_id}: applied")

    r = client.post(f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", headers=HEADERS,
                    json={"p_county": "highlands"})
    print(r.json().get("G"))


if __name__ == "__main__":
    main()
