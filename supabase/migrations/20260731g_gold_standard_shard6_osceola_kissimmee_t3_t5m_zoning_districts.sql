-- GOLD STANDARD SHARD-6 (santa_rosa/osceola, dispatch 091fb9f9, 2nd firing on this dispatch same day)
-- County: osceola, criterion G (density/far/pk1000 gap)
-- Session: 2026-07-31T08:00Z chat_session architect-20260731T080000
--
-- ROOT CAUSE (CONFIRMED, live ordinance fetch this session):
-- v_zoning_gold_standard_kpi_v3 join-misses 3 osceola parcels (2x Kissimmee T3,
-- 1x Kissimmee T5-M, jurisdiction_id=957) because NO zoning_districts row exists
-- for code='T3' or code='T5-M' under jurisdiction 957 at all (verified: the 51
-- existing rows for jurisdiction 957 are whole-ToC "Uncategorized" sections, not
-- per-zone-code district rows). The join-miss defaults these 3 parcels to
-- applicable=true with NULL standards in ALL of density/far/pk1000, dragging
-- down all three sub-metrics simultaneously (this is why the 8cfc21d7 migration
-- from earlier the same morning was a no-op: its UPDATE ... WHERE code IN
-- ('T3','T5-M',...) matched zero rows, since those codes never existed as rows).
--
-- LIVE ORDINANCE RESEARCH (CONFIRMED via Municode public content API, not
-- WebFetch/Firecrawl which have been blocked 5 firings running on this letter):
--   ClientID 2866 (Kissimmee) resolved via api.municode.com/Clients/name
--   ProductID 15261 (Code of Ordinances) via api.municode.com/ClientContent/2866
--   JobID 462754 (Supp. No. 5, current as of Ord. 3113, Feb 4 2025) via
--     api.municode.com/Jobs/latest/15261
--   Full live text of Chapter 14-5 (Form-Based Code) pulled via
--     api.municode.com/CodesContent?jobId=462754&nodeId=PTIIILADECO_CH14-5FOSECO&productId=15261
--
-- Table 5-2 (Transect Zone Dimensional Standards, section 14-5-6) lists, for
-- every transect zone (T1/T3/T4-R/T4-O/T5-M/T5-U/T6/SD): setbacks, frontage
-- buildout, lot width/depth, max block perimeter, impervious surface %, min/max
-- building height, ground floor elevation/ceiling height, allowed encroachments.
-- It contains NO FAR column and NO density (du/acre) column for any transect
-- zone -- Kissimmee's form-based code regulates intensity via building form
-- (height + lot coverage + setbacks), not a numeric FAR or density cap.
-- CONFIRMED, full table dumped and reviewed row-by-row this session.
--
-- Section 14-5-9.B.1 explicitly states: "Parking shall be provided for each use
-- in accordance with the minimum requirements outlined by use in chapter 14-7"
-- -- i.e. parking in the FBC is governed by land USE (Ch.14-7 Table 7-2, a
-- citywide use-based ratio table), not by transect zone. There is no single
-- zone-level parking_per_1000sf value in the ordinance for T3 or T5-M; a real
-- value would require verified per-parcel use classification, which these 3
-- parcels do not yet have (INFERRED best-effort ruled out this session; left
-- NULL / pk1000_regulated unset rather than fabricate a representative ratio,
-- since evidence for the parcels' actual use was inconclusive from address/
-- assessed-value alone).
--
-- LIVE EFFECT (measured via v_zoning_gold_standard_kpi_v3 before/after, same
-- session): density_applicable_parcels 44->41, pct_density_of_applicable
-- 90.9->97.6 (density sub-metric now clears the 95% gate). far_applicable_
-- parcels 4->1 (3 genuinely non-applicable parcels removed). pk1000_applicable
-- 14->11, pct_pk1000_of_applicable 64.3->81.8 (still below 95%, structural gap
-- elsewhere in osceola, not addressed by this migration).
-- Letter G remains FAIL overall (min(density,far,pk1000) still dragged down by
-- far=0.0% on the single remaining unresolved parcel, and pk1000=81.8% -- both
-- of which are broader problems this migration does not claim to fix).
--
-- Applied live via Supabase REST API (service-role key) 2026-07-31 -- this file
-- documents the change already applied; psql direct connection was unavailable
-- in this session's sandbox (password auth failure), consistent with prior
-- sessions' pattern of applying via PostgREST/service-role script and
-- committing the migration for repo history.
--
-- IDEMPOTENT: guarded by NOT EXISTS.

BEGIN;

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated)
SELECT 957, 'T3', 'T3 - General Urban Zone', 'Transect Zone (Form-Based Code)',
       'Kissimmee LDC Chapter 14-5 Form-Based Code, Table 5-2 Transect Zone Dimensional Standards',
       'Kissimmee LDC Ch. 14-5-6, Table 5-2', false, false
WHERE NOT EXISTS (
    SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 957 AND code = 'T3'
);

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated)
SELECT 957, 'T5-M', 'T5-M - Urban Center Zone (Multifamily)', 'Transect Zone (Form-Based Code)',
       'Kissimmee LDC Chapter 14-5 Form-Based Code, Table 5-2 Transect Zone Dimensional Standards',
       'Kissimmee LDC Ch. 14-5-6, Table 5-2', false, false
WHERE NOT EXISTS (
    SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 957 AND code = 'T5-M'
);

INSERT INTO public.zone_standards (zoning_district_id, source_url, ordinance_section, confidence_score)
SELECT zd.id,
       'https://api.municode.com/CodesContent?jobId=462754&nodeId=PTIIILADECO_CH14-5FOSECO&productId=15261',
       'Kissimmee LDC Table 5-2 (Ch. 14-5-6, Site Standards) -- CONFIRMED live fetch 2026-07-31: T3 row lists front/side/rear setbacks, frontage buildout, lot standards, min/max building height (14ft min, 3 stories max); no FAR or density (du/acre) column exists for any transect zone in this table -- density/intensity is form-controlled via height+lot coverage+setbacks, not a numeric cap. Ch.14-5-9.B.1: parking is regulated by land use per Ch.14-7 Table 7-2 (use-based ratios), not by transect zone -- no single zone-level parking_per_1000sf value exists in the ordinance for T3; left NULL pending per-parcel use verification.',
       0.95
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 957 AND zd.code = 'T3'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

INSERT INTO public.zone_standards (zoning_district_id, source_url, ordinance_section, confidence_score)
SELECT zd.id,
       'https://api.municode.com/CodesContent?jobId=462754&nodeId=PTIIILADECO_CH14-5FOSECO&productId=15261',
       'Kissimmee LDC Table 5-2 (Ch. 14-5-6, Site Standards) -- CONFIRMED live fetch 2026-07-31: T5-M row lists front/side/rear setbacks, frontage buildout, lot standards, min/max building height (22ft min, 5 stories +3 bonus max); no FAR or density (du/acre) column exists for any transect zone in this table -- density/intensity is form-controlled via height+lot coverage+setbacks, not a numeric cap. Ch.14-5-9.B.1: parking is regulated by land use per Ch.14-7 Table 7-2 (use-based ratios), not by transect zone -- no single zone-level parking_per_1000sf value exists in the ordinance for T5-M; left NULL pending per-parcel use verification.',
       0.95
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 957 AND zd.code = 'T5-M'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

COMMIT;

-- NEXT SESSION: 1 far-applicable parcel remains (zone_code='RS-2', jurisdiction_id=
-- 1186 Osceola County, parcel_id=062629000000, inserted into parcel_zones this
-- morning by the shard6_santarosa_osceola_091fb9f9_i_real_gis_fix script). This
-- session searched Osceola County LDC (jobId=478316, productId=15810) Article
-- 3.2.2 (Residential District Descriptions) live and could NOT find a district
-- currently named "RS-2" -- current single-family codes are ARE/US/US-M/LDR,
-- current multi-family codes include MDR/MDR-M/HDR (full names not yet
-- resolved to a code-to-code crosswalk). RS-2 may be a legacy/pre-rewrite code,
-- a St.Cloud-style code misassigned to Osceola County jurisdiction_id=1186, or
-- a genuine current code this session's TOC search missed. Do not guess a
-- crosswalk -- verify against the GIS parcel source that assigned it, then
-- either correct the jurisdiction_id or find the matching current district.
-- pk1000_applicable=11, pct_pk1000_of_applicable=81.8% (9/11) is now the
-- binding constraint for G overall (needs many more real per-1000sf values
-- across other osceola zone codes, not just T3/T5-M -- broader effort).
