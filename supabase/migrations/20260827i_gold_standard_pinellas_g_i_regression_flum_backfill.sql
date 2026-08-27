-- Gold Standard pinellas letter G regression fix (caused by the same-session letter I
-- fix that added 14 new parcel_zones rows, 2026-08-27 18:17-18:24 UTC, linking
-- previously-unlinked auction parcels to real zone codes via live municipal ArcGIS
-- zoning lookups). That I fix was independently adversarially verified as legitimate
-- (real GIS lookups, not fabricated) but it regressed G from PASS 95.6% to FAIL 0.0%
-- (density=94.3 far=0.0 pk1000=0.0) because several of the newly-referenced
-- zoning_districts rows had no far_regulated/density_regulated/pk1000_regulated
-- classification and/or no zone_standards row at all.
--
-- VIEW LOGIC (confirmed live via v_zoning_district_applicability, cross-referenced
-- against its documented CREATE OR REPLACE VIEW DDL in
-- 20260718s_gold_standard_shard12_okeechobee_pk1000_regulated_override_column.sql,
-- the latest of the two migrations that author this view's DDL):
--   far_applicable      = far_regulated IF NOT NULL ELSE category IN
--                          (commercial,industrial,mixed-use) AND name !~ 'pud'
--   pk1000_applicable    = pk1000_regulated IF NOT NULL ELSE same commercial/
--                          industrial/mixed-use-non-PUD fallback
--   density_applicable   = density_regulated IF NOT NULL ELSE
--                          (category IN (commercial,industrial) -> false, ELSE true)
-- v_zoning_gold_standard_kpi_v3's own pj CTE additionally does
-- COALESCE(a.far_applicable, true) / COALESCE(a.pk1000_applicable, true) whenever a
-- parcel_zones.zone_code has NO matching zoning_districts row at all (LEFT JOIN miss),
-- forcing "applicable" for genuinely unresolvable codes -- same fleet-wide pattern
-- documented in 20260718f (seminole) and 20260827 (lake groveland PUD) sessions.
--
-- THE 12 (jurisdiction_id, code) PAIRS TOUCHED BY THE I-FIX (all pinellas):
--   635/R-4, 635/RM, 814/NS-1, 814/NT-1, 814/NTM-1, 856/MDR, 959/R-6, 1094/B,
--   1096/RM-15, 1097/RM, 898/R-5, 898/T-1
--
-- STATUS PER PAIR AFTER LIVE INVESTIGATION (all category=residential except 1094/B
-- which is genuinely Commercial):
--   814/NS-1, 814/NT-1, 814/NTM-1 (St Petersburg), 856/MDR (Clearwater),
--   1096/RM-15 (Treasure Island): ALREADY had real max_density_du_acre (+FAR for
--   856/1096) from prior sessions (2026-07-31 / 2026-08-09). NOT TOUCHED this
--   migration -- already satisfied, no write needed.
--
--   635/R-4 (Pinellas County Unincorp, zoning_districts.id=13607): Sec. 138-351
--   defers density to the underlying FLUM category (confirmed via WebFetch of
--   pinellascounty.elaws.us Sec. 138-385.1, which lists only lot/setback/height for
--   R-4, no du/ac figure). Real parcel 163035883800000370 (6100 32nd St N, St
--   Petersburg) spatially confirmed on Residential Medium (RM) FLUM land via TWO
--   independent live ArcGIS REST point-in-polygon queries: egis.pinellas.gov/gis/
--   rest/services/PublicWebGIS/Landuse_Zoning/MapServer/0 (LANDUSECODE=RM) AND
--   egis.pinellas.gov/gis/rest/services/AGO/PPC_Data/MapServer/17 (PLAN_MAP_CATEGORY=
--   Residential Medium) -- both agree. Zoning layer 1 cross-check at the same
--   coordinate confirms ZONECLASS=R-4 (coordinate verified reliable, not a
--   placeholder geocode). FLUM C&R-8 (Residential Medium): 15 du/ac.
--   WRITTEN: zone_standards.max_density_du_acre = 15.00 (new row, id=6390).
--
--   635/RM (Pinellas County Unincorp, zoning_districts.id=13264): real parcel
--   152701290550001080's stored coordinate ("WOOD DOVE AVE, TARPON SPRINGS" -- a
--   street-only geocode, no house number) is UNRELIABLE: the zoning layer at that
--   exact point returns ZONECLASS=RPD (not RM) and the FLUM layer returns
--   PLAN_MAP_CATEGORY=Preservation (not a residential density category) -- same
--   "known fabricated-placeholder coordinate" pattern already flagged in
--   20260807h_gold_standard_shard5_5d40a513_pinellas_i_gis_zone_backfill.sql and
--   20260809c_architect_triage_pinellas_g_flum_density_backfill.sql (which
--   explicitly left 635/RM as an unresolved residual for the same reason).
--   NOT WRITTEN. Genuinely still blocked -- needs a real parcel geocode fix (e.g.
--   Clerk docket cross-reference) before FLUM lookup can be trusted for this row.
--
--   959/R-6 (Safety Harbor, zoning_districts.id=2544): LDC Sec. 25.06(D)(1):
--   "Maximum Density = Per underlying Plan Category" (same FLUM-deferred pattern,
--   confirmed via WebFetch of zoneomics.com/code/safety-harbor-FL/chapter_3). Real
--   parcel 162821111520110100 (49 Birch Creek Dr, Safety Harbor) spatially confirmed
--   on Residential Low Medium (RLM) FLUM land via AGO/PPC_Data/MapServer/17. FLUM
--   C&R-7 (Residential Low Medium): 10 du/ac.
--   WRITTEN: zone_standards.max_density_du_acre = 10.00 (UPDATE existing row id=147).
--
--   1094/B (Indian Rocks Beach, zoning_districts.id=2559): genuinely Commercial
--   category, own ordinance-stated figures (NOT FLUM-deferred). Sec. 110-131(6)(e)(3):
--   "The maximum density is 18 units per acre for permanent dwelling units" (used).
--   Sec. 110-131(6)(h): "Maximum floor area ratio in the B business district for
--   non-residential use is 0.55." Confirmed via WebFetch of zoneomics.com mirror
--   (municode.com blocks direct fetch with HTTP 403, consistent with prior sessions).
--   parking_per_1000sf INTENTIONALLY LEFT NULL: a retail-parking figure ("1 space
--   per 200 sq ft" / 5.0 per 1000sf equivalent) appeared only in an unconfirmed
--   WebSearch snippet without a verifiable section citation after multiple good-faith
--   WebFetch/WebSearch attempts (municode blocked, zoneomics chapter pages returned
--   only table-of-contents navigation for the parking article, PDF ordinance text
--   extraction did not surface it). Per BLANK > WRONG this is NOT written as a real
--   value. This parcel's category (Commercial, non-PUD) makes it genuinely
--   pk1000_applicable=true under the view's formula, so it remains counted as
--   "applicable but missing" for the pk1000 sub-metric -- an honest residual, not
--   hidden.
--   WRITTEN: zone_standards.max_density_du_acre = 18.00, max_far = 0.55 only
--   (new row, id=6391). NOTE: this district's own category='Commercial' makes
--   density_applicable=false under the view's formula (density fallback excludes
--   commercial/industrial) -- the density value is written for completeness/audit
--   trail but is not counted in the density sub-metric; harmless.
--
--   1097/RM (St Pete Beach): NO zoning_districts row existed at all for this
--   jurisdiction/code (St Pete Beach had never been touched by zoning ingestion
--   before the same-session I-fix). LDC Div. 12 Sec. 12.6: "The maximum residential
--   density permitted in the RM Residential District shall not exceed 15 units per
--   acre." Sec. 12.11: FAR 0.50 applies only to non-residential uses within the
--   district (RM's primary use is residential, governed by density not FAR --
--   far_regulated=false). Sec. 23.5 (Div. 23 Off-Street Parking and Loading):
--   residential parking = "2 per unit" -- a per-dwelling-unit standard, not
--   per-1,000sf (pk1000_regulated=false). Confirmed via WebFetch of zoneomics.com/
--   code/st-pete-beach-FL/chapter_14 and stpetebeach.elaws.us/code/ldc_div23_sec23.5
--   (municode.com blocks direct fetch).
--   WRITTEN: new zoning_districts row (id=14259, category=residential,
--   far_regulated=false, pk1000_regulated=false) + new zone_standards row
--   (id=6392, max_density_du_acre=15.00, parking_per_unit=2.00).
--
--   898/R-5 (Pinellas Park, zoning_districts.id=2519): Code Sec. 18-1513.2 (Density
--   Regulations): "A maximum of fifteen (15) dwelling units per net acre (du/a)
--   shall be permitted in the R-5 Multi-Family Residential District." Confirmed via
--   WebFetch of zoneomics.com mirror.
--   WRITTEN: zone_standards.max_density_du_acre = 15.00 (new row, id=6393).
--
--   898/T-1 (Pinellas Park, zoning_districts.id=2521): T-1's own purpose statement
--   (confirmed via WebSearch of zoneomics.com/code/pinellas-park-FL/chapter_13)
--   states the district is "appropriate for areas designated on the Official Land
--   Use Plan Map as Residential Low Medium, Residential Medium, Transportation/
--   Utility and Community Redevelopment District" -- density is FLUM-deferred, same
--   pattern as unincorporated Pinellas County and Safety Harbor. Real parcel
--   163029287820000071 (8115 61st St N, Pinellas Park) spatially confirmed on
--   Residential Low Medium (RLM) FLUM land via AGO/PPC_Data/MapServer/17. FLUM
--   C&R-7 (Residential Low Medium): 10 du/ac.
--   WRITTEN: zone_standards.max_density_du_acre = 10.00 (new row, id=6394).
--
-- LIVE BEFORE (verified via rpc/pencil_dod_evaluate_county('pinellas') at session
-- start, matching the dispatch brief exactly):
--   G: {"pass":false,"metric":0.0,"detail":"density=94.3 far=0.0 pk1000=0.0"}
--
-- LIVE AFTER (re-ran rpc/pencil_dod_evaluate_county('pinellas') immediately after
-- all writes):
--   G: {"pass":false,"metric":0.0,"detail":"density=95.7 far=100.0 pk1000=0.0"}
--   density 94.3 -> 95.7 (now individually >=95% threshold, fixed via 635/R-4 +
--     959/R-6 + 898/T-1 real FLUM-sourced values), far 0.0 -> 100.0 (fully fixed,
--     the only far-applicable gap parcel was 1094/B, now resolved). pk1000 remains
--     0.0 because 1094/B is the sole pk1000-applicable pinellas parcel and its real
--     parking-per-1000sf value could not be confirmed after a genuine good-faith
--     search (see honesty note above) -- NOT fabricated. G's overall metric is
--     LEAST(density,far,pk1000) so it remains FAIL until either 1094/B's real
--     parking figure is found, or 635/RM's parcel geocode is fixed and it turns out
--     not to affect pk1000 (RM is residential, pk1000 N/A -- would not help this
--     axis; 635/RM only affects density, not pk1000).
--   Letters A-F, H, I, J: unchanged (re-verified in the same closing call), no
--   regression caused by this migration.
--
-- RESIDUALS FOR A FUTURE SESSION (explicit, not hidden):
--   1. 635/RM density -- needs a real (non-placeholder) parcel geocode before FLUM
--      lookup can be trusted; current stored lat/lon is unreliable (street-only
--      geocode, cross-checks fail on both zoning and FLUM layers).
--   2. 1094/B parking_per_1000sf -- needs a confirmed municode/zoneomics section
--      citation for Indian Rocks Beach's B-district off-street parking schedule;
--      municode.com blocks direct fetch, zoneomics chapter pages for the parking
--      article did not surface the table content via WebFetch this session.

BEGIN;

-- (1) 635/R-4 (Pinellas County Unincorporated)
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT 13607, 15.00,
  'https://plan.pinellas.gov/wp-content/uploads/2021/08/PLANPinellas_FLUM_CR.pdf',
  'Pinellas County Code Sec. 138-351 (density governed by underlying FLUM category, not the zoning-district text itself). Real parcel 163035883800000370 spatially confirmed on Residential Medium (RM) FLUM land via two independent live ArcGIS REST queries (egis.pinellas.gov PublicWebGIS/Landuse_Zoning/MapServer/0 and AGO/PPC_Data/MapServer/17, both agree); zoning layer cross-check at the same point confirms ZONECLASS=R-4 (coordinate verified reliable). FLUM C&R-8 (Residential Medium): 15 du/ac max. GS-PINELLAS-G-8DA482B6-2ND.',
  0.80
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 13607);

-- (2) 959/R-6 (Safety Harbor)
UPDATE zone_standards
SET max_density_du_acre = 10.00,
    source_url = 'https://plan.pinellas.gov/wp-content/uploads/2021/08/PLANPinellas_FLUM_CR.pdf',
    ordinance_section = 'Safety Harbor LDC Sec. 25.06(D)(1): Maximum Density = Per underlying Plan Category (FLUM-deferred). Real parcel 162821111520110100 (49 Birch Creek Dr, Safety Harbor) spatially confirmed on Residential Low Medium (RLM) FLUM land via egis.pinellas.gov AGO/PPC_Data/MapServer/17. FLUM C&R-7 (Residential Low Medium): 10 du/ac max. GS-PINELLAS-G-8DA482B6-2ND.',
    confidence_score = 0.75
WHERE zoning_district_id = 2544 AND max_density_du_acre IS NULL;

-- (3) 1094/B (Indian Rocks Beach) -- density + FAR only; pk1000 intentionally NOT written
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score)
SELECT 2559, 18.00, 0.55,
  'https://www.zoneomics.com/code/indian-rocks-beach-FL/chapter_3',
  'Indian Rocks Beach Code Sec. 110-131(6)(e)(3): max density 18 units/acre (permanent dwelling units). Sec. 110-131(6)(h): max FAR 0.55 (non-residential use). parking_per_1000sf intentionally left NULL -- no section-confirmed figure found after a good-faith search; per BLANK > WRONG not fabricated. GS-PINELLAS-G-8DA482B6-2ND.',
  0.70
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 2559);

-- (4) 1097/RM (St Pete Beach) -- zoning_districts row did not exist at all
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, far_regulated, pk1000_regulated)
SELECT 1097, 'RM', 'RM Residential District', 'residential',
  'St. Pete Beach LDC Division 12 RM Residential District. far_regulated=false: Sec. 12.11 FAR of 0.50 applies only to non-residential uses within the district, not the primary residential use. pk1000_regulated=false: Sec. 23.5 residential parking = 2 spaces per unit (per-dwelling-unit standard, not per-1,000sf). GS-PINELLAS-G-8DA482B6-2ND.',
  false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1097 AND code = 'RM');

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, parking_per_unit, source_url, ordinance_section, confidence_score)
SELECT zd.id, 15.00, 2.00,
  'https://www.zoneomics.com/code/st-pete-beach-FL/chapter_14',
  'St. Pete Beach LDC Div. 12 Sec. 12.6: max residential density 15 units/acre. Sec. 23.5: residential parking 2 spaces/unit. GS-PINELLAS-G-8DA482B6-2ND.',
  0.80
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1097 AND zd.code = 'RM'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- (5) 898/R-5 (Pinellas Park)
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT 2519, 15.00,
  'https://www.zoneomics.com/code/pinellas-park-FL/chapter_13',
  'Pinellas Park Code Sec. 18-1513.2 (Density Regulations): 15 dwelling units per net acre max in the R-5 Multi-Family Residential District. GS-PINELLAS-G-8DA482B6-2ND.',
  0.85
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 2519);

-- (6) 898/T-1 (Pinellas Park)
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT 2521, 10.00,
  'https://plan.pinellas.gov/wp-content/uploads/2021/08/PLANPinellas_FLUM_CR.pdf',
  'Pinellas Park T-1 Manufactured Home Subdivision District purpose statement: "appropriate for areas designated ... as Residential Low Medium, Residential Medium, Transportation/Utility and Community Redevelopment District" -- FLUM-deferred. Real parcel 163029287820000071 (8115 61st St N, Pinellas Park) spatially confirmed on Residential Low Medium (RLM) FLUM land via egis.pinellas.gov AGO/PPC_Data/MapServer/17. FLUM C&R-7 (Residential Low Medium): 10 du/ac max. GS-PINELLAS-G-8DA482B6-2ND.',
  0.75
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 2521);

COMMIT;

-- VERIFICATION (run after apply):
-- SELECT rpc/pencil_dod_evaluate_county('pinellas');
-- Expected G detail: density~95.7 far=100.0 pk1000=0.0 (still FAIL overall, LEAST-
-- bound by the one unresolved 1094/B parking figure -- see residuals above).
