-- Gold Standard shard-12 (dispatch 704e70a0, okeechobee/st_johns continuation)
-- Adds pk1000_regulated override column, mirroring the existing far_regulated /
-- density_regulated pattern on zoning_districts, so a district can be marked
-- "parking not zoning-regulated" (e.g. negotiated-per-project PD) without
-- fabricating a parking_per_1000sf value.
--
-- SAFETY: additive column, defaults NULL everywhere. v_zoning_district_applicability
-- CASE WHEN pk1000_regulated IS NOT NULL THEN pk1000_regulated ELSE <prior formula> END
-- preserves prior behavior for every existing row until explicitly overridden.
-- Verified live (2026-07-18): full v_zoning_gold_standard_kpi_v3 snapshot across all
-- 67 counties byte-identical before/after the view CREATE OR REPLACE, prior to setting
-- any override value.
--
-- Then sets pk1000_regulated=false for okeechobee's PD (Planned Development, id 11442),
-- matching the same real-ordinance finding already used for its far_regulated=false
-- override (Sec. 2.04.17 confirms PD parking, like FAR, is negotiated per-project with
-- no fixed ratio — see prior session commit 4c1fbd9c/2f49d2af).
--
-- Live effect: okeechobee G pk1000 metric 50.0% -> 100.0% (pk1000_applicable_parcels 2->1,
-- the PD parcel now correctly excluded rather than counted against with a NULL value).
-- G remains FAIL overall (still bottlenecked on density=39.1%), tracked separately.

ALTER TABLE zoning_districts ADD COLUMN IF NOT EXISTS pk1000_regulated boolean;

CREATE OR REPLACE VIEW v_zoning_district_applicability AS
 SELECT id AS district_id,
    jurisdiction_id,
    code,
    name,
    lower(COALESCE(category, ''::text)) AS category_norm,
        CASE
            WHEN lower(COALESCE(category, ''::text)) = 'residential'::text AND lower(name) ~ '(single|two[ -]?family|duplex|mobile|manufactured|rural|estate)'::text AND lower(name) !~ '(multi|multiple)'::text THEN 'single_two_family'::text
            WHEN lower(COALESCE(category, ''::text)) = 'residential'::text AND lower(name) ~ '(multi|multiple|apartment)'::text THEN 'multi_family'::text
            WHEN lower(COALESCE(category, ''::text)) = 'residential'::text THEN 'residential_other'::text
            WHEN lower(COALESCE(category, ''::text)) = ANY (ARRAY['commercial'::text, 'industrial'::text]) THEN 'commercial_industrial'::text
            ELSE 'other'::text
        END AS subtype,
        CASE
            WHEN far_regulated IS NOT NULL THEN far_regulated
            ELSE (lower(COALESCE(category, ''::text)) = ANY (ARRAY['commercial'::text, 'industrial'::text, 'mixed-use'::text])) AND lower(name) !~ 'pud'::text
        END AS far_applicable,
        CASE
            WHEN pk1000_regulated IS NOT NULL THEN pk1000_regulated
            ELSE (lower(COALESCE(category, ''::text)) = ANY (ARRAY['commercial'::text, 'industrial'::text, 'mixed-use'::text])) AND lower(name) !~ 'pud'::text
        END AS pk1000_applicable,
        CASE
            WHEN density_regulated IS NOT NULL THEN density_regulated
            WHEN lower(COALESCE(category, ''::text)) = ANY (ARRAY['commercial'::text, 'industrial'::text]) THEN false
            ELSE true
        END AS density_applicable
   FROM zoning_districts d;

UPDATE zoning_districts
   SET pk1000_regulated = false,
       ordinance_section = COALESCE(ordinance_section, 'Sec. 2.04.17')
 WHERE id = 11442 AND code = 'PD' AND jurisdiction_id = 943;
