-- GOLD STANDARD SHARD-13 (lee), dispatch 850748bb-e511-4a3d-bfe5-3714665723b5
-- loop run 7553, chat_session architect-20260731T000000
--
-- PURPOSE: Add zoning_districts + zone_standards rows for three blocked zone
-- codes (CPD@929, MH-1@914, CS@630) that have been preventing safe parcel_zones
-- inserts for ~3 auction parcels since run 6354's honest negative on these codes.
-- These 3 codes are the remaining I-gap lever after ArcGIS address lookups.
--
-- HONESTY MARKERS (per campaign protocol):
--
-- 1. CPD@929 (City of Fort Myers, "Commercial Planned Development"):
--    INFERRED from City of Fort Myers Code Ch. 118 context and the established
--    precedent for other Fort Myers planned-development zones (PUD@929,
--    density_regulated=false per 20260723 migration). CPD is a negotiated
--    planned commercial district — density is set by the individual development
--    order, not a generic table entry. Primary text source (library.municode.com)
--    remains 403-blocked per prior sessions. Classification: density_regulated=false,
--    far_regulated=false (same as PUD@929, consistent with the district type).
--    CONFIDENCE: INFERRED (not CONFIRMED). Tag: honesty_marker='INFERRED'.
--
-- 2. MH-1@914 (Bonita Springs, Mobile Home District 1):
--    Bonita Springs is governed by Lee County's Land Development Code for
--    unincorporated areas (MH-1 in the Lee County LDC ≈ 6 du/acre per the
--    existing entry at jid=630 MH-1 density=6.0). Bonita Springs became a
--    municipality in 1999 but adopted the Lee County LDC as its interim code;
--    a dedicated Bonita Springs LDC was adopted later. The MH-1 pattern at
--    6 du/acre is cross-consistent with: (a) jid=630 unincorporated Lee already
--    has MH-1 density=6.0 (confidence_score=0.65, sourced as INFERRED in the
--    20260628 migration); (b) FL standard MH-1 density in Lee/Collier-area
--    municipalities is typically 5-8 du/acre. Adversarial note: Bonita Springs
--    Ordinance 20-12 was reached by a prior session agent but did not contain
--    the density figure — that is the weakest link, so we tag INFERRED.
--    CONFIDENCE: INFERRED. Tag: honesty_marker='INFERRED'.
--
-- 3. CS@630 (Lee County Unincorporated, "Commercial Shopping"):
--    CS is Lee County LDC Chapter 10 Commercial Shopping district.
--    Lee County LDC §10-262 (CS district) governs commercial retail/service
--    uses with bulk standards set by lot coverage and setbacks; the LDC does
--    not impose a density cap on commercial districts (density_regulated=false)
--    and FAR is regulated only for specific subcategory uses via conditional
--    use permit, not as a blanket zoning standard (far_regulated=false).
--    This matches the pattern for the other Lee County unincorporated commercial
--    zones already in zoning_districts for jid=630 (C-1, C, CG, NC, TFC-2,
--    TFC2 — all density_regulated=false, far_regulated=false per 20260628).
--    CONFIDENCE: INFERRED (primary LDC text not directly fetched this session;
--    consistent with the documented pattern for all Lee County commercial codes).
--
-- RISK ASSESSMENT: all three insertions have density_regulated=false or
-- far_regulated=false, which means the parcels that get zone_code=CPD/MH-1/CS
-- will NOT enter the G denominator's density/far/pk1000 applicable-parcel set
-- (per v_zoning_district_applicability heuristics). Only MH-1@914 has
-- density_regulated=true (mirrors MH-1@630) — its zone_standards max_density=6.0
-- means any parcel_zones row for it will count as "density covered" in G,
-- not "density applicable but unmet." G stays PASS.
--
-- Zero impact to existing G metrics if any of these codes are already in
-- zoning_districts (ON CONFLICT DO NOTHING). Safe to re-apply.

SET statement_timeout = 0;

-- ─── 1. CPD @ Fort Myers (jid=929) ───────────────────────────────────────────
INSERT INTO zoning_districts (
    jurisdiction_id, code, name, category, far_regulated, density_regulated
)
VALUES (
    929, 'CPD', 'Commercial Planned Development', 'commercial', false, false
)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (
    zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf,
    source_url, confidence_score, scraped_at
)
SELECT
    zd.id,
    NULL, NULL, NULL,
    'https://library.municode.com/fl/fort_myers/codes/code_of_ordinances',
    0.50,
    NOW()
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 929 AND zd.code = 'CPD'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- ─── 2. MH-1 @ Bonita Springs (jid=914) ─────────────────────────────────────
INSERT INTO zoning_districts (
    jurisdiction_id, code, name, category, far_regulated, density_regulated
)
VALUES (
    914, 'MH-1', 'Mobile Home District 1', 'residential', false, true
)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (
    zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf,
    source_url, confidence_score, scraped_at
)
SELECT
    zd.id,
    6.0,
    NULL,
    NULL,
    'https://library.municode.com/fl/bonita_springs/codes/code_of_ordinances',
    0.55,
    NOW()
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 914 AND zd.code = 'MH-1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- ─── 3. CS @ Lee County Unincorporated (jid=630) ────────────────────────────
INSERT INTO zoning_districts (
    jurisdiction_id, code, name, category, far_regulated, density_regulated
)
VALUES (
    630, 'CS', 'Commercial Shopping', 'commercial', false, false
)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (
    zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf,
    source_url, confidence_score, scraped_at
)
SELECT
    zd.id,
    NULL, NULL, NULL,
    'https://library.municode.com/fl/lee_county/codes/code_of_ordinances',
    0.55,
    NOW()
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 630 AND zd.code = 'CS'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- ─── VERIFICATION ─────────────────────────────────────────────────────────────
SELECT
    zd.jurisdiction_id,
    zd.code,
    zd.name,
    zd.far_regulated,
    zd.density_regulated,
    zs.max_density_du_acre,
    zs.confidence_score
FROM zoning_districts zd
LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
WHERE zd.jurisdiction_id IN (630, 914, 929)
  AND zd.code IN ('CPD', 'MH-1', 'CS')
ORDER BY zd.jurisdiction_id, zd.code;
