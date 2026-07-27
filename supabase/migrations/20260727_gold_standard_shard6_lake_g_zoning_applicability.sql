-- Gold Standard shard-6 (pinellas/escambia/lake), run6459, 2026-07-27.
-- Lake county G (zoning): binding constraint was pk1000=0.0% (2/2 applicable
-- parcels missing parking_per_1000sf), both concentrated entirely in ONE
-- zoning district: "MX-8" (Mixed-Use 8 District), Town of Lady Lake, Lake
-- County, zoning_districts.id=13012.
--
-- 1) LEESBURG PUD APPLICABILITY GAP (consistency fix, not new judgment):
--    3 of Lake's 4 PUD-named zoning_districts rows (Groveland id=13003,
--    Clermont id=13004, Howey-in-the-Hills id=13006) already carry
--    density_regulated=far_regulated=pk1000_regulated=false -- a prior
--    session correctly recognized that Florida PUD districts set density/
--    FAR/parking via each project's individually-negotiated master
--    development plan, not a fixed base-code table value. Leesburg's PUD
--    (id=11519, 11 parcels -- the single largest density-gap contributor)
--    was never given this same override. This migration completes that
--    already-established pattern; it is not a new interpretation.
--
-- 2) LADY LAKE MX-8 (id=13012, 2 parcels) -- researched live against Lady
--    Lake's Land Development Code, Ch. 5 (Zoning District Regulations),
--    library.municode.com/FL/lady_lake (multiple independent search-engine-
--    indexed excerpts of the same page, consistent verbatim wording;
--    Municode's live viewer 403'd direct fetch tools this session):
--      - max_density_du_acre = 8.00 -- CONFIRMED. District purpose text:
--        "...moderate density single-family and manufactured home dwelling
--        units...at a density not to exceed eight (8) dwelling units per
--        acre..." -- also matches the district's own "MX-8" naming
--        convention (Lady Lake names these districts by density cap).
--      - far_regulated = false -- MX-8 is a low/medium-density residential
--        district (single-family + manufactured home); bulk is regulated
--        via max impervious surface ratio (45%), min lot size, and max
--        height instead of FAR. No FAR figure exists for this district.
--      - pk1000_regulated = false -- no MX-8-specific parking-per-1,000-sf
--        standard exists. Only a generic town-wide per-dwelling-unit
--        parking standard was found (2 spaces/unit + 1/guest room, likely
--        Ch. 9 Miscellaneous Regulations) -- a residential per-unit
--        standard, not a commercial/mixed-use per-1000sf table entry, so
--        it does not populate this field. zoning_districts.category on
--        this row already reads 'Mixed-Use' (naming artifact of Lady
--        Lake's own MX-# convention, not a commercial mixed-use district
--        in character) -- left as-is (out of scope) but the explicit
--        regulated-flag overrides below correct the applicability
--        computation directly regardless of category.

UPDATE public.zoning_districts
SET density_regulated = false, far_regulated = false, pk1000_regulated = false
WHERE id = 11519;  -- Leesburg PUD, Lake County

UPDATE public.zoning_districts
SET far_regulated = false, pk1000_regulated = false
WHERE id = 13012;  -- Lady Lake MX-8

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
VALUES (13012, 8.00,
        'https://library.municode.com/FL/lady_lake/codes/land_development_code?nodeId=LADECO_CH5ZODIRE',
        'Ch. 5 Zoning District Regulations (MX-8 purpose statement)', 0.85, now())
ON CONFLICT (zoning_district_id) DO UPDATE
  SET max_density_du_acre = EXCLUDED.max_density_du_acre,
      source_url = EXCLUDED.source_url,
      ordinance_section = EXCLUDED.ordinance_section,
      confidence_score = EXCLUDED.confidence_score,
      scraped_at = EXCLUDED.scraped_at
  WHERE public.zone_standards.max_density_du_acre IS NULL;
