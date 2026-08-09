-- Architect triage #18374 -- brevard, letter I (card_complete) mechanical backfill.
--
-- Live re-diagnosis of the 1,151-row I gap (card_rows=7244, card_complete=6093,
-- 84.1%) confirms the 2026-07-30 shard-4 session's finding (dispatch
-- 09f985fc, GOLD_STANDARD_SHARD4_BREVARD_DISPATCH_09F985FC_SESSION_REPORT.md):
-- the residual is dominated by a genuine, source-confirmed data-availability
-- wall, not a scraping/pipeline gap.
--
-- Fresh gap-composition breakdown this session (7244 card_rows fetched and
-- evaluated client-side against the exact evaluator predicate in
-- pencil_dod_evaluate_county, matched the live RPC's 6093/7244 exactly before
-- any write):
--   989 rows: property_address IS NULL only (everything else already present)
--        -- 50/50 randomly sampled rows independently re-confirmed via
--        -- sample_properties.address = 'UNKNOWN' (or blank) at the FL GIO/DOR
--        -- cadastral source, matched by tax_account = parcel_id. Zero
--        -- fabricable population. Same conclusion as 2026-07-28 and
--        -- 2026-07-30 sessions, now on a fresh independent sample.
--   ~120 rows: parcel_id present but not found in v_zoning_gold_standard_card
--        (by parcel_id OR tax_account) AND not found in parcel_zones or
--        sample_properties either -- genuinely no zoning-substrate linkage
--        exists in this DB for these parcel_ids. Not mechanically fixable
--        from data already present.
--   ~40 rows: various combinations of no_geo/no_value/no_parcel_id with no
--        real address at all -- same structural wall as the 989-row bucket.
--
-- Only 2 rows were legitimately mechanically enrichable this session, both
-- traced to sample_properties (already-populated FL GIO/DOR ingestion table,
-- joined by tax_account = multi_county_auctions.parcel_id):
--
--   1. id=0fb73de8-fe6c-4161-a656-4455d2773d58 (parcel_id 2426611): had
--      address+value+zoned-parcel already, missing latitude/longitude only.
--      sample_properties has no centroid_lat/centroid_lon for this parcel but
--      does have a full ring-polygon (`geometry`). Derived centroid = simple
--      average of the polygon's vertex coordinates (14 vertices, small urban
--      lot at 205 Palmetto Ave, Merritt Island) -> lat=28.359062461836427,
--      lng=-80.69578836467001.
--   2. id=346d463b-ddfd-457b-83ba-7405d1b74994 (parcel_id 2107356): had
--      address+geo+zoned-parcel already, missing assessed_value only.
--      sample_properties.land_value=44000.0 + building_value=87120.0 =
--      131120.0 -- same land_value+building_value=assessed_value derivation
--      pattern already used elsewhere in this pipeline.
--
-- Applied live via PostgREST scoped PATCH (per-row `?id=eq.<uuid>`, not bulk
-- upsert-by-id -- the 2026-07-30 session documented that Postgres validates
-- NOT NULL constraints on the full implicit INSERT row before resolving
-- ON CONFLICT, even for rows that only take the UPDATE branch). Recorded here
-- as the equivalent SQL for the audit trail; already applied at the time this
-- file lands.
--
-- RESULT: card_complete moved 6093 -> 6095 (+2, exactly matching the 2 rows
-- patched). Rounds to the same 84.1% at 1 decimal. No regression on any other
-- letter (A,B,C,D,E,F,G,H,J unchanged, all PASS).
--
-- NOT fixed, and why (genuine structural blockers, not attempted further):
--   - 989-row UNKNOWN-address bucket: no legitimate address exists at either
--     of the two independently-checked authoritative sources (per the
--     2026-07-30 session's live dual-source re-scrape, and this session's
--     fresh 50-row random re-sample against sample_properties, 50/50 confirm
--     UNKNOWN). Fabricating a placeholder was rejected -- would reproduce the
--     ghost-success pattern this project has purged repeatedly.
--   - ~120-row parcel_id_unzoned bucket: parcel_id present but absent from
--     both v_zoning_gold_standard_card and the raw parcel_zones/
--     sample_properties tables under either parcel_id or tax_account key --
--     no linkage data exists anywhere in this DB to backfill from.
--   - New external scraping infra (bcpao.us Cloudflare-gated site, per-case
--     AcclaimWeb lookups for no-parcel rows) explicitly out of scope for this
--     session per the task brief.

UPDATE public.multi_county_auctions
SET latitude = 28.359062461836427, longitude = -80.69578836467001
WHERE id = '0fb73de8-fe6c-4161-a656-4455d2773d58'
  AND lower(county) = 'brevard';

UPDATE public.multi_county_auctions
SET assessed_value = 131120.0
WHERE id = '346d463b-ddfd-457b-83ba-7405d1b74994'
  AND lower(county) = 'brevard';
