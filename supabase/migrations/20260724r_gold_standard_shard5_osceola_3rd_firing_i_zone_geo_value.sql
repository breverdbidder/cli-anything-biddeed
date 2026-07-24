-- Gold Standard Shard-5 osceola, dispatch ac5f5206, 3rd firing.
-- Live-verified via ULTRACODE workflow (5 research agents + independent adversarial
-- refuters, one per finding). Only refuted=false, non-HYPOTHESIS findings applied.
--
-- APPLIED (6 of 8 I-letter candidates; both G-letter candidates that survived refutation
-- were HYPOTHESIS-confidence, not written -- see session addendum):
--   case 19892023  / 112529181100010210 -> RA-3 (Kissimmee, cw.kissimmee.gov Zoning_Districts/10)
--   case 19952023  / 112529235700010830 -> RA-3 (Kissimmee, same source)
--   case 36212023  / 212529181600       -> T5-M (Kissimmee; county-layer PARCELNO ambiguous
--                                          between 2 stacked records, but the Kissimmee zoning
--                                          DISTRICT match is a spatial point-in-polygon result
--                                          independent of which stacked record is "the" parcel,
--                                          so the truncated 12-digit id -- already mca's stored
--                                          value -- is used directly, no update needed)
--   case 52962018  / 262630061300011010 -> R-3 (Saint Cloud, arcgisweb.stcloud.org). Only this
--                                          ONE of 4 cases sharing truncated parcel_id 262630061300
--                                          has a precisely-confirmed address match (3433 Allegra
--                                          Cir) this session; the other 3 (48482022/52562018, no
--                                          address at all; 53252018, 3630 Allegra Cir, address
--                                          digits do not match either confirmed sibling parcel's
--                                          address on record) are left untouched -- not fabricated.
--   case "2011 CA 003872 MF" / 072530272401950380 -> PD (Osceola unincorp., jurisdiction 1186)
--   case "2019 CA 000153 MF" / 3026315130000D0070 -> E-1 (Osceola unincorp., jurisdiction 1186)
--
-- DECLINED (refuted by independent adversarial agent, not written):
--   case 31152023 / 182529227600011636 -> SRPUD claim: raw GIS data independently confirmed
--     clean by the refuter, but the refuter's verdict was refuted=true on a provenance
--     objection (finding not yet present in a PRIOR session's committed artifacts -- true of
--     any brand-new finding, arguably a category error). Per ULTRALOOP protocol ("a claim
--     ships ONLY if it survives refutation... Sentinel/refuter is correct by default, burden
--     of proof on whoever disagrees" -- CLAUDE.md SHIP GATE), this session does NOT override
--     the refutation despite disagreeing with its reasoning. Flagged for next session to
--     re-run verification with a cleaner refuter prompt that doesn't conflate "new work" with
--     "must already appear in an older document".
--   case 8642023 / 052529152400 -> MUPUD claim: refuted on a real, substantive concern -- the
--     truncated 12-digit "parcel" is a shared prefix across 24 condo units + 1 COMM parcel with
--     no confirmed case-to-specific-unit linkage. Correctly declined, consistent with prior
--     sessions' handling of ambiguous truncated-parcel matches.
--
-- G-letter (Kissimmee T3/SRPUD FAR-density codification, St Cloud R-3 max_density_du_acre):
--   ALL THREE research findings from this firing were held back -- T3 "not codified" and
--   St Cloud R-3 "max_density_du_acre=10" were REFUTED (T3 on an unlocated supporting
--   citation despite the primary Table 5-2 evidence checking out; St Cloud R-3 on an
--   unresolved Oct-2025 comprehensive-plan/zoning-update cycle the refuter could not rule
--   out as amending this section). SRPUD "not codified" survived refutation but only at
--   HYPOTHESIS confidence (both the researcher and refuter explicitly flagged no Playwright/
--   browser-rendering tool was available in this sandbox to read the primary Municode text
--   directly). None of the three meet this campaign's bar for a production zoning_districts
--   write (established precedent: PD/PMUD/STRPD/AC/CR/CT/RMH were all CONFIRMED against
--   directly-read ordinance text). G gets zero writes this firing -- 4th correct decline in
--   this campaign, not a new fabrication risk. Next session should retry with a browser-
--   rendering-capable tool to upgrade SRPUD to CONFIRMED and resolve the T3/St-Cloud gaps.

BEGIN;

-- Precision parcel_id updates (case_number+county scoped, 1 row each)
UPDATE public.multi_county_auctions SET parcel_id = '112529181100010210'
  WHERE county = 'osceola' AND case_number = '19892023' AND parcel_id = '112529181100';

UPDATE public.multi_county_auctions SET parcel_id = '112529235700010830'
  WHERE county = 'osceola' AND case_number = '19952023' AND parcel_id = '112529235700';

UPDATE public.multi_county_auctions SET parcel_id = '262630061300011010'
  WHERE county = 'osceola' AND case_number = '52962018' AND parcel_id = '262630061300';

UPDATE public.multi_county_auctions SET parcel_id = '072530272401950380'
  WHERE county = 'osceola' AND case_number = '2011 CA 003872 MF' AND parcel_id = 'OSC-293392A6D6A9';

UPDATE public.multi_county_auctions SET parcel_id = '3026315130000D0070'
  WHERE county = 'osceola' AND case_number = '2019 CA 000153 MF' AND parcel_id = 'OSC-DF43CD8C61B2';

-- Geo + value backfill for the 2 previously address-only OSC- rows (COALESCE-guarded,
-- does not overwrite any pre-existing value)
UPDATE public.multi_county_auctions
SET latitude = COALESCE(latitude, 28.340083100638548),
    longitude = COALESCE(longitude, -81.36592494157402),
    assessed_value = COALESCE(assessed_value, 401100),
    market_value = COALESCE(market_value, 412100)
WHERE county = 'osceola' AND case_number = '2011 CA 003872 MF';

UPDATE public.multi_county_auctions
SET latitude = COALESCE(latitude, 28.188940678218014),
    longitude = COALESCE(longitude, -81.24380477849465),
    assessed_value = COALESCE(assessed_value, 128517),
    market_value = COALESCE(market_value, 425400)
WHERE county = 'osceola' AND case_number = '2019 CA 000153 MF';

-- Real zone_code linkage, idempotent (skip if already present)
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT * FROM (VALUES
  ('112529181100010210', 957::int,  'RA-3',  'RA-3 (Single Family Residential)', 'ac5f5206_osceola_3rd_firing/kissimmee_gis_live_verified'),
  ('112529235700010830', 957::int,  'RA-3',  'RA-3 (Single Family Residential)', 'ac5f5206_osceola_3rd_firing/kissimmee_gis_live_verified'),
  ('212529181600',       957::int,  'T5-M',  'T5-M (Mixed-Use Center)',          'ac5f5206_osceola_3rd_firing/kissimmee_gis_live_verified'),
  ('262630061300011010', 894::int,  'R-3',   'Multi-Family Dwelling District',   'ac5f5206_osceola_3rd_firing/stcloud_gis_live_verified'),
  ('072530272401950380', 1186::int, 'PD',    'Plan Development',                 'ac5f5206_osceola_3rd_firing/osceola_county_gis_live_verified'),
  ('3026315130000D0070', 1186::int, 'E-1',   'Estate',                           'ac5f5206_osceola_3rd_firing/osceola_county_gis_live_verified')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);

COMMIT;
