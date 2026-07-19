-- GTM-22J shard-8 (dispatch 4569d5ab, run5153): santa_rosa + putnam G fix.
--
-- ROOT CAUSE (verified live 2026-07-19 via ULTRALOOP research+adversarial-verify
-- fan-out): both counties' G metric was pinned to a false 0%/50% FAR score
-- because v_zoning_district_applicability's default heuristic
-- (far_applicable = category IN ('commercial','industrial') AND name !~ 'pud')
-- incorrectly assumed the ONE far-applicable-by-default commercial district in
-- each county actually regulates floor area ratio. Live ordinance text says
-- otherwise:
--   * Gulf Breeze, FL C-1 Commercial District (Sec. 21-161/162/163, Div. 8):
--     only permitted uses / height (35 ft) / setback (15 ft) sections exist;
--     no FAR section anywhere in the division. Confirmed via two independent
--     fetches (workflow research agent + adversarial verifier, both against
--     the same live zoneomics.com Gulf Breeze code mirror).
--   * Palatka, FL C-2 Intensive Commercial District (Sec. 94-149(f)): schedule
--     of standards explicitly lists "Maximum Density: Not applicable" and
--     gives height/impervious-surface/yard figures but no FAR line at all.
--     Confirmed via direct WebFetch of the same ordinance section.
-- zoning_districts.far_regulated is the existing override column for exactly
-- this situation (NULL falls back to the category heuristic); setting it
-- false removes these two districts' single applicable parcel from the FAR
-- denominator instead of fabricating a FAR value that the ordinance does not
-- contain.
--
-- Santa Rosa also had a density gap (93.2%, need >=95%) driven by 7 parcels
-- across 6 districts missing max_density_du_acre. Of those, 3 districts
-- (Milton R-1, R-1A, R-U) have a directly-quoted minimum lot area in the
-- City of Milton Unified Development Code (Article 6, Table 6.2.1 / 6.4.1),
-- verified via WebFetch of the city's own hosted PDF. This migration derives
-- max_density_du_acre = 43,560 / min_lot_area_sqft for those three districts
-- only -- the SAME method already used for the existing Interlachen R-1A/R-2
-- rows in this table (43560/7500=5.81 already matches two live passing rows),
-- not a guessed figure. The remaining 3 parcels (Gulf Breeze R-C, Jay RM,
-- Jay RM-A) could not be sourced from any live ordinance text this session
-- (Town of Jay is not on municode; Gulf Breeze R-C's municode page 403'd and
-- had no lot-area data in the mirror) and are left NULL -- density still
-- clears the >=95% threshold without them (100/103 = 97.1%).

BEGIN;

-- Gulf Breeze C-1: no FAR standard in the ordinance (Div. 8 has only permitted
-- uses / height / setback sections) -- correct the applicability flag.
UPDATE zoning_districts
SET far_regulated = false
WHERE id = 5563 AND code = 'C-1';

-- Palatka C-2: ordinance schedule explicitly states "Maximum Density: Not
-- applicable" and lists no FAR standard -- correct the applicability flag.
UPDATE zoning_districts
SET far_regulated = false
WHERE id = 5645 AND code = 'C-2';

-- Milton R-1: min lot area 7,500 sf (Table 6.2.1) -> 43560/7500 = 5.81 du/acre
UPDATE zone_standards
SET max_density_du_acre = 5.81
WHERE zoning_district_id = 11522 AND max_density_du_acre IS NULL;

-- Milton R-1A: min lot area 9,000 sf (Table 6.2.1) -> 43560/9000 = 4.84 du/acre
UPDATE zone_standards
SET max_density_du_acre = 4.84
WHERE zoning_district_id = 11523 AND max_density_du_acre IS NULL;

-- Milton R-U: min lot area (SF) 7,000 sf (Table 6.4.1) -> 43560/7000 = 6.22 du/acre
UPDATE zone_standards
SET max_density_du_acre = 6.22
WHERE zoning_district_id = 11521 AND max_density_du_acre IS NULL;

COMMIT;
