-- GTM-22j shard-6 (dispatch 1f302343, 2nd firing): hillsborough G regression fix, part 2
-- Continuation of 20260719n. Two more classification-only fixes (no fabricated numeric
-- values), applied live and re-verified before this file was written:
--
-- 1. Pre-existing "PD"/"PD-A" zoning_districts rows (631/867/961) already had
-- far_regulated/pk1000_regulated implicitly false via category default, but
-- density_regulated was unset (NULL), defaulting density_applicable=true even though
-- these rows had far/pk1000 correctly excluded for the same underlying reason: Planned
-- Development sets density per individual development order, not a single ordinance-wide
-- number. This one fix (119 of the ~180-parcel density gap) took density from 79.3%/85.4%
-- to 95.6% -- PASS.
--
-- 2. Hillsborough County's own Comprehensive Plan text (verified live via web search
-- against planhillsborough.org before this migration was written) shows FAR is governed
-- by Future Land Use category (RES-1/RES-12/AM/A/AR/AE/P etc.), not by base zoning
-- district, for at least the residential/agricultural FLU categories -- and Hillsborough's
-- own Part 6.11 parking standards are set per USE TYPE, not per zoning district. This is a
-- structural mismatch with a flat max_far/parking_per_1000sf-per-zoning-district model, not
-- a "couldn't find the number" gap, so CG/CN (631, unincorporated Hillsborough County only)
-- are marked not-regulated at the district level. This evidence is specific to Hillsborough
-- County's own comprehensive plan text; it was NOT extended to Tampa's CN or Plant City's
-- C-1 (different jurisdictions, weaker/inconclusive evidence this session -- see residual
-- note below).
--
-- RESIDUAL (NOT fixed, BLANK > WRONG): far_applicable_parcels for hillsborough is now down
-- to exactly 2, both pre-existing rows this session did not create -- City of Tampa CN
-- (zoning_districts.id=1861) and Plant City C-1 (id=1772) -- neither has a max_far value.
-- This session made a genuine, good-faith attempt to source real values (Tampa Code Ch.27
-- Sec.27-156 Table 4-2, Plant City Code Sec.102-620-equivalent for C-1) and hit: Municode
-- WAF 403 on direct fetch, an Angular SPA shell with no server-rendered content when fetched
-- via curl with a browser UA, and search results that only ever surface Plant City's C-2
-- Sec.102-620 FAR section, never a C-1 equivalent (suggestive that C-1 may genuinely lack a
-- FAR section, but this is absence-of-evidence, not a confirmed absence -- not applied).
-- G is PASS on density (95.6) and pk1000 (100.0, unblocked as a side effect of fix #2 --
-- the same 2 residual parcels already had real pre-existing parking_per_1000sf=4.00 values)
-- but still FAILS overall (LEAST includes far=0.0) until a future session sources real
-- max_far for these exact 2 parcels' districts, or a primary-source citation confirms FAR is
-- genuinely not regulated for them either. Also flagged for that future session: Plant City
-- C-1's existing parking_per_1000sf=4.00 value carries confidence_score=0.00 in the live
-- DB (source_url points at Plant City Municode but with no ordinance_section) -- looks like
-- a placeholder from an earlier session, not touched here (outside this session's scope,
-- not introduced by this session), but worth a dedicated audit pass.

UPDATE public.zoning_districts
SET density_regulated = false
WHERE (jurisdiction_id, code) IN (
  (631, 'PD'), (867, 'PD'), (867, 'PD-A'), (961, 'PD')
)
AND density_regulated IS DISTINCT FROM false;

UPDATE public.zoning_districts
SET far_regulated = false, pk1000_regulated = false
WHERE jurisdiction_id = 631 AND code IN ('CG', 'CN')
AND (far_regulated IS DISTINCT FROM false OR pk1000_regulated IS DISTINCT FROM false);
