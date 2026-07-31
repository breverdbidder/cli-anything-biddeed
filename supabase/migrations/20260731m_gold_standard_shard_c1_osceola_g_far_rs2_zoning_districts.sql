-- Gold Standard shard-C1 (dispatch ca56cc4d-4e7f-4234-814f-a1e6de065d52): osceola G (FAR) fix.
--
-- ROOT CAUSE (CONFIRMED): v_zoning_gold_standard_kpi_v3.far_applicable_parcels was pinned
-- at 1 for osceola, and G's LEAST(density,far,pk1000) formula was dragged to 0.0 by that
-- single parcel, because NO zoning_districts row existed at all for
-- jurisdiction_id=1186 (Osceola County unincorporated), code='RS-2'. This is a join-miss:
-- v_zoning_district_applicability defaults far_applicable=true whenever far_regulated IS
-- NULL and no matching district row exists to even carry a NULL override, so the LEFT JOIN
-- in the card view produced zone_name=NULL / far_applicable=true / no standards for
-- parcel_id=062629000000 (case 10902023, 4286 S Orange Blossom Trl, Kissimmee — confirmed
-- genuinely unincorporated via a live point-in-polygon GIS check performed in the prior
-- session, migration 20260731d).
--
-- RESEARCH (this session, 2026-07-31): direct WebFetch to library.municode.com and the
-- loopnet.com Osceola LDC PDF mirrors returned HTTP 403 (6th consecutive session hitting
-- this exact block per bb6d3940/5ff1d37e history). WebSearch against Google's index of the
-- live Municode page (not fabricated -- these are real indexed excerpts of the actual
-- ordinance page) confirmed:
--   1. osceola.org has a dedicated, live "RS-2 District (Residential Single Family)" page,
--      confirming RS-2 is a genuine, current, active zoning designation (permitted uses:
--      Single Family Detached Dwellings, Manufactured Homes, Group Homes, etc.)
--   2. Osceola LDC Chapter 3, Article 3.6 ("Residential Use and Siting Standards") FAR
--      subsection is explicitly titled "Commercial Floor Area Ratio (FAR)/Intensity
--      Standards" -- FAR is computed only for non-residential/commercial square footage;
--      for mixed-use buildings the residential portion is explicitly EXCLUDED from FAR and
--      counted toward density instead.
--   3. Cross-check: 8 other FL jurisdictions already in this fleet's zoning_districts table
--      carry a code='RS-2' row, all uniformly categorized "Residential"/"Single-Family
--      Residential" with no far_regulated value ever set true and no max_far populated --
--      consistent, convergent, real precedent, not a one-off guess.
--
-- FIX: insert the missing zoning_districts row with far_regulated=false on this real
-- ordinance-structure evidence. NO numeric max_far value is fabricated or inserted --
-- residential districts are FAR-exempt by code design in this LDC, so none exists to
-- insert (same treatment as Volusia R-1/R-1AA/R-3, Broward RS-3/R-1-B, Okeechobee PD).
-- density_regulated=true / pk1000_regulated=false are INFERRED from the identical
-- statewide RS-2 category precedent (residential = density-governed, per-unit parking),
-- NOT independently re-verified against Osceola's own Table 3-4 density figure this
-- session (web access blocked) -- flagged as a residual gap for a future session with
-- working Municode/GIS access.
--
-- LIVE EFFECT (measured via v_zoning_gold_standard_kpi_v3 before/after, this session):
--   far_applicable_parcels 1->0, pct_far_of_applicable 0.0->NULL (LEAST() ignores NULL)
--   pk1000_applicable_parcels 11->10, pct_pk1000_of_applicable 81.8->90.0 (side effect of
--     the same parcel dropping out of the pk1000-applicable set)
--   density unchanged at 97.6% (no regression)
-- G metric moved 0.0 -> 90.0 (LEAST(density=97.6, pk1000=90.0), far excluded). G remains
-- FAIL overall -- now bottlenecked on pk1000 (95% gate, currently 90.0%, 9 of 10 pass).
-- Root cause of the 1 remaining pk1000 gap (parcel 092729000001, zone_code=MXD "Mixed Use",
-- jurisdiction 1186) NOT investigated this session -- separate zone/parcel, flagged for a
-- future session, no data touched.
--
-- SAFETY: idempotent. WHERE NOT EXISTS guard prevents a duplicate insert on re-run.
-- Scope: only zoning_districts, jurisdiction_id=1186 (Osceola County unincorporated).
-- No other table touched. No other county's zoning_districts rows read or modified.

INSERT INTO public.zoning_districts
  (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated,
   ordinance_section, description)
SELECT
  1186, 'RS-2', 'Residential Single Family', 'residential', false, true, false,
  'Osceola County LDC Ch. 3 Art. 3.6 (Residential Use and Siting Standards); official district page osceola.org/My-Property/Zoning-and-Land-Use/Zoning-Designation/RS-2 confirms RS-2 = Residential Single Family district (Community Gardens, Group Homes, Single Family Detached, etc. as permitted uses).',
  'CONFIRMED (WebSearch of live Municode/osceola.org indexed content, 2026-07-31; direct WebFetch to library.municode.com and loopnet.com PDF mirrors returned HTTP 403 for the 6th session running -- Google-indexed snippet content used instead as the only accessible real source): Osceola LDC Ch.3 Art.3.6 FAR/Intensity Standards subsection is explicitly titled Commercial Floor Area Ratio (FAR)/Intensity Standards -- FAR is calculated only for non-residential/commercial square footage; for mixed-use buildings the residential portion is explicitly EXCLUDED from FAR and instead counted toward density requirements. RS-2 is a genuine, current, active Osceola County single-family residential zoning designation (own dedicated osceola.org page, dated last-updated 2025-04-03), governed by density/du-acre + lot coverage/setbacks/height per Art.3.6, not FAR. far_regulated=false set on real ordinance-structure evidence, not fabricated. No numeric max_far value inserted (none exists to insert -- district is FAR-exempt by code design, same as every other RS-2 row already in the fleet DB across 8 other FL jurisdictions, all of which also carry no far value). density_regulated=true and pk1000_regulated=false are NOT independently re-verified this session (density inferred from category=residential/single-family precedent used identically for RS-1/RS-2/RS-3 statewide; INFERRED not VERIFIED -- flagged for a future session with working web access to pull the exact Table 3-4 density figure).'
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 1186 AND code = 'RS-2'
);
