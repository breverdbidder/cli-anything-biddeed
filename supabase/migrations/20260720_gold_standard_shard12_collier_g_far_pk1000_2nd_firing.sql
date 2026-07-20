-- Gold Standard shard-12 (dispatch 9d04299e), 2nd firing -- collier G residual gap
-- (FAR + parking for C-1/C-4/C-5/Industrial), applied live via Supabase Management
-- API (direct psql auth is broken in this environment -- stale SUPABASE_DB_PASSWORD,
-- matching every prior shard session's documented pattern).
--
-- CONTEXT: the 2026-07-19 firing of this same dispatch fixed I (fail->pass) and
-- partially fixed G (density sub-metric only: PUD/RMF-12/VR flagged density_regulated
-- =false, RT given a real density value). It explicitly left "G -- FAR + parking for
-- C-1/C-4/C-5/I" as the #1 item for a future session, after exhausting elaws.us (503),
-- library.municode.com (Angular SPA shell, no server-rendered text), collier.gov PDFs
-- (403), Firecrawl (402, insufficient credits), and Wayback availability API (no
-- snapshot found for the elaws.us URL specifically).
--
-- THIS SESSION: independently reconfirmed all of the above are still dead (elaws.us
-- still 503, municode still JS-shell, collier.gov still 403, Firecrawl still 402).
-- Found two genuinely NEW paths via a 3-strategy research + adversarial-verification
-- workflow: (1) Municode's underlying JSON API (api.municode.com/CodesContent),
-- reachable directly even though the library.municode.com viewer itself is a dead
-- SPA shell -- serves the live, current LDC text (confirmed current via "Ord. No.
-- 24-05" citation); (2) a Wayback Machine snapshot of the actual archived Collier LDC
-- ordinance PDF (ordinance-200441-pages-301600.pdf, 2004 codification, snapshot
-- 20251221043346) that the narrower single-URL availability-API check in the prior
-- session's search had missed.
--
-- BEFORE this migration (verified live 2026-07-20 via
-- SELECT public.pencil_dod_evaluate_county('collier')):
--   G: pass=false, density=84.4 far=0.0 pk1000=0.0 (metric = LEAST = 0.0)
--   far/pk1000_applicable_parcels = 9 (C-1=1, C-4=6, C-5=1, I=1), 0% filled on both

-- 1) C-1 (id=11684) FAR -- CONFIRMED via api.municode.com Sec 4.02.01 Table 2 AND
--    independently via the Wayback-archived 2004 ordinance PDF (same Table 2,
--    2 independent fetches, 2 independent refuters, both HTTP 200, visual read of
--    the rendered table matched verbatim in both). C-1 row's Floor Area Ratio (%)
--    cell reads literally "None" -- same explicit non-numeric marker used
--    consistently across every genuinely-unregulated row in this table (GC, A, E,
--    C-1, C-2, C-3, I, BP, CON, P, CF all show "None"; only C-4/C-5 differ, see
--    the SKIPPED section below for why those do NOT get the same treatment).
UPDATE zoning_districts
   SET far_regulated = false
 WHERE id = 11684; -- C-1, Commercial Professional

-- 2) I / Industrial (id=11689) FAR -- CONFIRMED, same evidentiary tier as C-1:
--    Table 2 row for "I" reads Height=50, Distance=A, Min Floor Area=1,000,
--    Floor Area Ratio (%)=None. Independently re-verified twice (api.municode.com
--    live fetch + Wayback 2004 ordinance PDF visual read), no caveats, no
--    use-specific exceptions muddying this row (unlike C-4/C-5's Hotels/Destination
--    resort entries).
UPDATE zoning_districts
   SET far_regulated = false
 WHERE id = 11689; -- I, Industrial

-- 3) Parking (pk1000) -- CONFIRMED false (not district-regulated) for ALL FOUR
--    target districts: C-1 (11684), C-4 (11685), C-5 (11686), I (11689).
--    Sec 4.05.04 Table 17 "Parking space requirements" is organized ENTIRELY by
--    land-use category (Office, Retail shop or store, Shopping center, Restaurant
--    subtypes, Industrial use/activity manufacturing, Warehouse/wholesale, ~90 rows
--    total) -- there is zero row anywhere in this table keyed to a zoning district
--    code. This was independently re-confirmed by 4 separate refuters, each doing a
--    full visual read of all 6 table pages (rendered from the Wayback-archived PDF,
--    since text-layer extraction was garbled/unreliable on this scanned ordinance),
--    not just trusting the researcher's claim. A parcel's actual parking requirement
--    in Collier depends on what USE is built on it, not which of these 4 districts
--    it sits in -- our schema's one-value-per-zoning-district model does not map
--    onto how this county's code is actually structured. This is a genuine
--    "not regulated at the district level" finding, not a suppressed/fabricated
--    number -- distinct from the C-4/C-5 FAR case below, where a real per-use value
--    DOES exist in the district's own table row (just not as one district-wide
--    figure).
UPDATE zoning_districts
   SET pk1000_regulated = false
 WHERE id IN (11684, 11685, 11686, 11689); -- C-1, C-4, C-5, I

-- ============================================================================
-- SKIPPED (left as-is / still applicable-but-missing) -- do not fabricate.
-- ============================================================================
--
-- C-4 (id=11685) and C-5 (id=11686) FAR: a "not_regulated" claim for both was
--   surfaced by one research strategy and INITIALLY accepted by its paired
--   refuter for C-4, but a second, more rigorous refuter independently working the
--   IDENTICAL C-5 row (same table, same PDF, same columns -- C-4 and C-5 have byte-
--   for-byte the same FAR-column pattern) caught and REFUSED it: the FAR cell for
--   both C-4 and C-5 is NOT blank/"None" like the genuinely-unregulated rows --
--   it contains real populated values ("Hotels .60" / "Destination resort .80"),
--   with no footnote marker tying them to some other implicit district-wide figure.
--   That means FAR *is* regulated for C-4/C-5, just per-use rather than as one
--   district-wide number our schema can hold -- treating it as "not_regulated"
--   would have discarded real regulatory data under a category-error label that
--   does not actually apply here (unlike the genuine category errors correctly
--   rejected in the 2026-07-19 session, e.g. an Activity-Center-overlay FAR value
--   mistakenly generalized to a base district). Given the direct contradiction
--   between the two refuter verdicts on an identical fact pattern, the more
--   rigorous, better-evidenced (footnote-marker check, sibling-row comparison)
--   REFUSED verdict is treated as authoritative for BOTH C-4 and C-5, overriding
--   the other refuter's acceptance. max_far stays NULL for both, far_regulated
--   left untouched (defaults to true via the commercial/industrial category
--   heuristic in v_zoning_district_applicability) -- an honest residual gap, not a
--   fixed value and not a flag flip.
--
-- This is why G still fails after this migration: far_applicable_parcels shrinks
-- (9 -> 7, since C-1/I's 2 parcels move to N/A) but the 2 remaining
-- far-applicable districts (C-4=6 parcels, C-5=1 parcel) still have zero FAR
-- values filled, so pct_far_of_applicable stays 0.0%, which remains the binding
-- constraint in LEAST(density, far, pk1000).

-- AFTER this migration (verify live via
-- SELECT public.pencil_dod_evaluate_county('collier')):
--   pk1000_applicable_parcels expected to drop from 9 to 0 (all 4 target districts
--   now N/A) -- pct_pk1000_of_applicable becomes NULL, which Postgres's LEAST()
--   ignores (does not auto-pass G; LEAST(density, far) still binds on far=0.0%).
--   far_applicable_parcels expected to drop from 9 to 7 (C-1's 1 + I's 1 parcel
--   move to N/A); pct_far_of_applicable stays 0.0% (C-4/C-5 still unfilled).
--   G expected to remain pass=false -- this migration is an honest data-quality
--   correction (accurate applicability, real citations, dead paths not re-chased),
--   not a fix that flips the letter to pass.
