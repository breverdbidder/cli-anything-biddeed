#!/usr/bin/env python3
"""GOLD STANDARD miami_dade, letter G — pk1000/FAR applicability + FAR backfill
for the 4 zone_code rows that had NO zoning_districts row at all (district_id
NULL), which caused v_zoning_district_applicability's LEFT JOIN to fall back
to COALESCE(...,true) in v_zoning_gold_standard_kpi_v3 -- i.e. these 4 parcels
were being counted as "pk1000-applicable" purely because no classification
row existed, not because their real land use is genuinely parking/FAR
regulated.

Real ordinance research this session (all sourced, no guessing):

1. Palmetto Bay E-1 -- CONFIRMED "One Acre Estate Single Family District"
   per Palmetto Bay's own Official Zoning Map / Code Div. 30-50 Zoning
   Districts. Pure single-family estate residential -> not FAR/pk1000
   regulated. Fixed by inserting a correctly-categorized zoning_districts
   row (category='residential', name matches the 'estate'/'single' regex);
   the view's default logic then correctly computes far_applicable=false,
   pk1000_applicable=false with ZERO guessed numbers.

2. Sweetwater RM-15 -- CONFIRMED "Low Density Multifamily Residential
   District" per the City of Sweetwater's own Official Zoning Map
   (cityofsweetwater.fl.gov/DocumentCenter/View/119). Pure multifamily
   residential (no commercial component) -> not FAR/pk1000 regulated.
   Same fix pattern as E-1: category='residential' row inserted, view
   auto-computes far_applicable=false, pk1000_applicable=false.

3. Miami Beach MXE -- CONFIRMED "Mixed Use Entertainment District",
   Miami Beach Code of Ordinances Chapter 142, Division 13, Sec. 142-545
   (Development regulations): "All uses -- 2.0 [FAR] Except convention
   hotel development (as set forth in section 142-841) -- 3.5". Real,
   genuine mixed-use commercial district -> far_applicable/pk1000_applicable
   both correctly TRUE. max_far=2.0 backfilled with real citation.
   parking_per_1000sf LEFT NULL: Sec. 130-32 (off-street parking, parking
   district no. 1) gives a use-differentiated schedule (retail ~3.33/1000sf,
   office ~2.5/1000sf, restaurants per-seat) but this session could not
   confirm live which parking district MXE's Ocean Drive/Collins Ave
   parcels actually fall under -- NOT guessed, genuinely unresourced this
   session.

4. Hialeah RDD -- CONFIRMED via live search + Ordinance No. 2016-32 PDF
   (hialeahfl.gov/DocumentCenter/View/312) that RDD = "Residential
   Development District" (NOT "Redevelopment" as originally assumed),
   established for "unified mixed-use development consisting of
   residential and commercial/retail uses" (Hialeah Heights annexation
   area). This settles the code's real meaning but the ordinance found is
   a site-specific rezoning/development-agreement approval, not Chapter 98's
   RDD development-standards text (setbacks/FAR/parking). Could not locate
   the live Chapter 98 RDD standards section (Municode/elaws blocked,
   Firecrawl out of credits) within this session's budget.
   LEFT UNRESOLVED -- not guessed, genuinely unresourced this session.

Net effect on v_zoning_gold_standard_kpi_v3 (county=miami_dade):
  pk1000: 8 applicable / 50.0% pass  ->  6 applicable / 66.7% pass
  far:    22 applicable / 81.8% pass ->  20 applicable / 95.0% pass
  density: unchanged (98.1%)
Letter G remains FAIL (pk1000 66.7% still binding) -- genuine partial
progress, not a full fix. Hialeah RDD and Miami Beach MXE parking are the
2 residual pk1000-applicable-but-NULL rows for a future session.

Usage: python3 scripts/gold_standard_miami_dade_g_pk1000_far_district_backfill_20260830.py
"""
import os
import time
import httpx

REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]

# (jurisdiction_id, code, name, category, ordinance_section)
DISTRICT_INSERTS = [
    (1329, "E-1", "One Acre Estate Single Family District", "residential",
     "Palmetto Bay Official Zoning Map / Code of Ordinances Div 30-50 Zoning Districts"),
    (1059, "RM-15", "Low Density Multifamily Residential District", "residential",
     "City of Sweetwater Official Zoning Map (cityofsweetwater.fl.gov/DocumentCenter/View/119)"),
    (960, "MXE", "Mixed Use Entertainment District", "mixed-use",
     "Miami Beach Code of Ordinances Sec. 142-545, Div. 13 (Ch. 142, Zoning Districts and Regulations)"),
]

# (jurisdiction_id, code) -> max_far, source_url, ordinance_section, confidence
STANDARDS_INSERTS = [
    (960, "MXE", 2.0,
     "https://library.municode.com/fl/miami_beach/codes/code_of_ordinances?nodeId=SPBLADERE_CH142ZODIRE_ARTIIDIRE_DIV13MXMIUSENDI_S142-545DERE",
     "Miami Beach Code Sec. 142-545 (Development regulations, MXE district) -- all uses max FAR 2.0, "
     "except convention hotel development per Sec. 142-841 (FAR 3.5)", 0.75),
]


def mgmt_sql(query: str, retries=3):
    h = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json",
         "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) curl-client"}
    last_exc = None
    for attempt in range(retries):
        try:
            r = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                            headers=h, json={"query": query}, timeout=120)
            if r.status_code == 201:
                return r.json()
            last_exc = Exception(f"STATUS {r.status_code}: {r.text[:800]}")
        except Exception as e:
            last_exc = e
        time.sleep(2 * (attempt + 1))
    raise last_exc


def sql_str(v):
    return "'" + str(v).replace("'", "''") + "'"


def main():
    juris_to_district_id = {}
    for jur_id, code, name, category, ord_section in DISTRICT_INSERTS:
        result = mgmt_sql(f"""
          INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section)
          VALUES ({jur_id}, {sql_str(code)}, {sql_str(name)}, {sql_str(category)}, {sql_str(ord_section)})
          ON CONFLICT (jurisdiction_id, code) DO UPDATE SET
            name = EXCLUDED.name, category = EXCLUDED.category, ordinance_section = EXCLUDED.ordinance_section
          RETURNING id;
        """)
        did = result[0]["id"]
        juris_to_district_id[(jur_id, code)] = did
        print(f"  zoning_districts ({jur_id}, {code}) -> id={did}, category={category}")

    for jur_id, code, max_far, source_url, ord_section, confidence in STANDARDS_INSERTS:
        did = juris_to_district_id.get((jur_id, code))
        if did is None:
            check = mgmt_sql(f"SELECT id FROM zoning_districts WHERE jurisdiction_id={jur_id} AND code={sql_str(code)};")
            did = check[0]["id"]
        mgmt_sql(f"""
          INSERT INTO zone_standards (zoning_district_id, max_far, source_url, ordinance_section, confidence_score)
          VALUES ({did}, {max_far}, {sql_str(source_url)}, {sql_str(ord_section)}, {confidence})
          ON CONFLICT (zoning_district_id) DO UPDATE SET
            max_far = EXCLUDED.max_far, source_url = EXCLUDED.source_url,
            ordinance_section = EXCLUDED.ordinance_section, confidence_score = EXCLUDED.confidence_score;
        """)
        print(f"  zone_standards district_id={did}: max_far={max_far}")

    print("Done. Hialeah RDD and Miami Beach MXE parking_per_1000sf left "
          "unresolved -- genuinely unresourced this session, not guessed.")


if __name__ == "__main__":
    main()
