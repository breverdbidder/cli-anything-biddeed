-- GOLD STANDARD shard-9 (dispatch 20a33672), 4th firing 2026-07-20
-- Two corrective actions applied live during this session (both already
-- applied directly via the Management API; this file documents them for
-- the repo record and so a future db reset/replay reproduces the same
-- live state).

-- ============================================================================
-- BROWARD LETTER G — self-inflicted regression fix (caught same session)
-- Adding 3 new parcel_zones rows (RS-6/RM-10/RS-4, jurisdiction 628,
-- unincorporated Broward) for the new deedauction-harvested tax deed
-- parcels used zone_code values with NO matching zoning_districts row.
-- v_zoning_gold_standard_kpi_v3's applicability join defaults an unmatched
-- district to far_applicable=true/pk1000_applicable=true (COALESCE(...,
-- true)) with max_far/parking NULL -- which flipped G from PASS(100.0) to
-- FAIL(far=0.0, pk1000=0.0) the moment those 3 rows existed. Real zoning
-- codes, real source (Broward County Urban Planning Division "ZoningOfficial"
-- ArcGIS layer, Code of Ordinances Ch. 39, effective 2024-01-30), real
-- max_density_du_acre values (6/10/4 units per acre, straight from the
-- layer's own DESCRIPTION field) -- not fabricated, just needed the district
-- + standards rows that make the applicability view classify them the same
-- way as every other single/multi-family residential code in this dataset
-- (far/parking not applicable, density applicable).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, effective_date, far_regulated, pk1000_regulated, density_regulated)
VALUES
  (628, 'RS-6', 'One Family Detached, 6 units per acre', 'residential', 'Broward County Code of Ordinances Ch. 39', '2024-01-30', false, false, true),
  (628, 'RM-10', 'Multiple Family, 10 units per acre', 'residential', 'Broward County Code of Ordinances Ch. 39', '2024-01-30', false, false, true),
  (628, 'RS-4', 'One Family Detached, 4 units per acre', 'residential', 'Broward County Code of Ordinances Ch. 39', '2024-01-30', false, false, true)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, effective_date, confidence_score)
SELECT d.id, v.dens, 'https://bcgishub.broward.org/server/rest/services/PSD/ZoningOfficial/FeatureServer/2',
       'Broward County Code of Ordinances Ch. 39', '2024-01-30', 0.95
FROM zoning_districts d
JOIN (VALUES ('RS-6', 6.0), ('RM-10', 10.0), ('RS-4', 4.0)) AS v(code, dens) ON v.code = d.code
WHERE d.jurisdiction_id = 628
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- Real zoning for the 3 unincorporated-Broward deedauction parcels (sourced
-- from the same official ArcGIS layer, queried live by FOLIO).
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
VALUES
  ('504205050430', 628, 'RS-6', 'One Family Detached, 6 units per acre', 'broward_zoningofficial_arcgis_bmsd_2026-07-20', '2024-01-30'),
  ('504205100010', 628, 'RM-10', 'Multiple Family, 10 units per acre', 'broward_zoningofficial_arcgis_bmsd_2026-07-20', '2024-01-30'),
  ('504113040670', 628, 'RS-4', 'One Family Detached, 4 units per acre', 'broward_zoningofficial_arcgis_bmsd_2026-07-20', '2024-01-30')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- LETTER J — SYSTEMIC bid_decisions FABRICATION, discovered by independent
-- ULTRALOOP adversarial refuter (fresh-context Agent, did not write any of
-- this session's fixes) during survival-vote review of the alachua J claim
-- below, then confirmed live and extended to a fleet-wide duplicate-cluster
-- sweep. THIS IS THE MOST IMPORTANT FINDING OF THE SESSION.
--
-- alachua: 5 rows had NO parcel_id yet carried a deal thesis --
--   - 2 rows (01 2025 CA 001928, 01 2025 CA 003287; created 2026-06-19,
--     pipeline_run_id NULL): byte-identical arv=100000.00/max_bid=40000.00/
--     ml_score=0.7500 despite real judgment_amount $223K vs $1.11M.
--   - 3 rows (01 2025 CA 003110/003156/01 2026 CC 000399; created
--     2026-07-10, pipeline_run_id=SHARD14-2a2b2667-J-v1): arv = exactly
--     judgment_amount * 1.4 (verified to 2 decimals on all 3) -- formulaic,
--     no property ever identified.
-- Then the refuter found a THIRD, larger alachua batch this session had
-- missed: 14 more rows (created 2026-06-26 16:19:33, single batch,
-- pipeline_run_id NULL), byte-identical arv=210000.00/max_bid=90500.00/
-- ml_score=0.7500 across real judgment_amount ranging $7,024-$3,995,806 --
-- WITH real parcel_id present on every row, so the earlier "parcel_id IS
-- NULL" guard alone does not catch this pattern.
--
-- That third batch's discovery prompted a full duplicate-value-cluster
-- sweep of BOTH counties' currently-qualifying (per pencil_dod's exact J
-- formula) bid_decisions rows. alachua came back clean after the above 19
-- were removed. broward did not: 157 of 620 previously-"qualifying" rows
-- (i.e. rows that were making broward's J read 95.1% PASS) belong to 41
-- distinct duplicate (arv,max_bid,ml_score) clusters -- the largest being
-- arv=350000.00/max_bid=220000.00/ml_score=0.5800 shared by 60 rows across
-- 31 different real judgment amounts, and arv=50000.00/max_bid=0.00/
-- ml_score=0.5200 shared by rows whose real per-parcel assessed_value
-- differs (spot-checked: $25,870-$49,710) yet arv/max_bid never varied --
-- max_bid of exactly $0.00 on every row is not a real Shapira-formula
-- output. All created 2026-06-19 11:12-11:16 UTC, tiered flat-default
-- fallback values keyed by an ml_score confidence bucket (0.40/0.52/0.58),
-- not a real per-property analysis.
--
-- A broader (out-of-scope) query found this exact pattern recurring
-- ~2,909 times for the arv=260000/max_bid=157000/ml_score=0.40 triple alone
-- across the WHOLE bid_decisions table (not just broward/alachua) -- this is
-- almost certainly a fleet-wide issue inflating other shards' J metrics the
-- same way it inflated broward's. Flagged for the AI Architect / next
-- session to dispatch a fleet-wide remediation; NOT fixed here, since
-- PARALLEL-FLEET RULES restrict this session to broward + alachua only.
--
-- Net effect: broward J flips from a fabricated PASS(95.1%) to an honest
-- FAIL(71.0%, deal_complete=463 of 652). alachua J stays FAIL, now at
-- 82.4% -> honestly recomputed to 42/51 after removing all 19 fabricated
-- rows (was reading a fabricated 92.2% before this session touched it).
DELETE FROM bid_decisions
WHERE county_slug = 'alachua'
  AND case_number IN ('01 2025 CA 001928', '01 2025 CA 003287',
                       '01 2025 CA 003110', '01 2025 CA 003156', '01 2026 CC 000399',
                       '01 2025 CA 000484', '01 2025 CA 001356', '01 2025 CA 001487',
                       '01 2025 CA 001517', '01 2025 CA 002675', '01 2025 CA 002972',
                       '01 2025 CA 003027', '01 2025 CA 003277', '01 2025 CA 003575',
                       '01 2025 CC 003291', '01 2025 CC 005145',
                       'TD 2026-017', 'TD 2026-018', 'TD 2026-019');

-- broward: purge every currently-qualifying row that is a member of a
-- duplicate (arv,max_bid,ml_score) cluster of size >= 2 within broward's
-- current scope (idempotent: re-running after the rows are gone is a no-op
-- since the qualifying/clusters CTEs will just come back empty).
WITH scoped AS (
  SELECT * FROM multi_county_auctions
  WHERE lower(county) = 'broward'
    AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true)
),
qualifying AS (
  SELECT bd.id, bd.arv, bd.max_bid, bd.ml_score
  FROM bid_decisions bd
  JOIN scoped mca ON mca.case_number = bd.case_number
  WHERE bd.county_slug = 'broward'
    AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL AND bd.ml_score IS NOT NULL
    AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property' AND bd.factors ? 'distress_owner'
    AND bd.factors ? 'cma_distressed' AND bd.factors ? 'cma_resale'
),
clusters AS (
  SELECT arv, max_bid, ml_score FROM qualifying GROUP BY 1, 2, 3 HAVING count(*) >= 2
)
DELETE FROM bid_decisions bd
USING clusters c
WHERE bd.id IN (SELECT id FROM qualifying q WHERE q.arv = c.arv AND q.max_bid = c.max_bid AND q.ml_score = c.ml_score);
