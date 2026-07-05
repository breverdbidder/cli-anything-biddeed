-- SHARD-1 (brevard, gilchrist, sarasota, flagler, liberty) — run 3059 (Gold Standard daily session)
-- dispatch_id: de295275-1e36-4809-a813-97bc4a6b897c
-- Session: architect-20260705T000000
--
-- APPLIED LIVE via PostgREST table PATCH (no DDL — SUPABASE_DB_PASSWORD auth fails against
-- every reachable pooler/direct host in this sandbox, and no exec_sql/exec RPC exists in the
-- live schema; consistent with the same finding recorded in
-- 20260703_shard1_miami_dade_matcher_reinvoke_flagler_fabrication_revert.sql two days earlier).
-- This file is the historical record of the one REST-executable UPDATE applied this session,
-- plus a durable log of four proposed fixes that were adversarially verified and REFUTED before
-- shipping — so no future session re-derives and re-attempts them.
--
-- ═══════════════════════════════════════════════════════════════════════════
-- METHOD: ULTRACODE workflow, 4 independent refuter subagents (one per county),
-- each given fresh read-only Supabase REST access and told to try to BREAK the
-- proposed fix using independent queries. All 4 proposals were REFUTED before
-- any write was made. Findings logged to gold_standard_ultraloop_audit
-- (5 rows, this dispatch_id).
-- ═══════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════
-- PART 1 — GILCHRIST: ghost-success purge (APPLIED, the only real change this session)
-- ═══════════════════════════════════════════════════════════════════════════
-- Gilchrist's reported C/D of 60.0% (3/5 matched_clean) was itself partly a ghost-success.
-- Of the 3 "matched_clean" rows, only 1 (case 26-0005-TD, auction_status='completed',
-- parity_source='tier1_tax_deed_outcome', sold_amount=5050) is genuinely outcome-backed.
-- The other 2 (case 212025CA000035CAAXMX, case 212025CA000069CAAXMX) carry
-- parity_source='tier1_realforeclose_gilchrist', auction_status='upcoming', sold_amount=NULL,
-- and have ZERO rows in tax_deed_outcomes or foreclosure_outcomes -- an auction that hasn't
-- happened cannot have a verified outcome. This is the identical signature already caught and
-- reverted fleet-wide for miami_dade (333 rows, 20260704_shard4_miami_dade_cd_systemic_ghost_success_revert.sql)
-- and leon (31 rows, 20260703_shard_leon_cd_ghost_success_honesty_fix.sql). The canonical
-- refresh_parity_tier1_outcomes() function structurally excludes auction_status='upcoming' from
-- ever becoming matched_clean, confirming these 2 rows could never have been produced by the
-- current matcher and were a stale hand-promotion from an earlier session.
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('gilchrist'):
--   C: 60.0% (matched_clean=3) FAIL -> 20.0% (matched_clean=1) FAIL (honest number; pass/fail
--      status unchanged, both were already below the 95% threshold)
--   D: 60.0% (matched_any=3)   FAIL -> 20.0% (matched_any=1)   FAIL (same)
--   A/B/E/F/G/H/I/J unaffected, still PASS (8/10 unchanged).

UPDATE multi_county_auctions
SET parity_status = NULL,
    parity_source = NULL,
    updated_at = now()
WHERE lower(county) = 'gilchrist'
  AND id IN ('80ec5ac5-c97a-4238-b32d-3cff89779894', '598aae70-206f-426d-abff-60bc96019319')
  AND parity_status = 'matched_clean'
  AND parity_source = 'tier1_realforeclose_gilchrist'
  AND sold_amount IS NULL
  AND auction_status = 'upcoming';
-- 2 rows reverted (idempotent: guard ensures re-running after this fix is a no-op)

-- ═══════════════════════════════════════════════════════════════════════════
-- PART 2 — SARASOTA: proposed C/D fix REFUTED, NOT applied (no write)
-- ═══════════════════════════════════════════════════════════════════════════
-- Proposed: promote 37 unmatched rows (all auction_status='upcoming', zero PropertyOnion
-- coverage confirmed) to matched_clean via parity_source='tier1_sarasota_direct'.
-- REFUTED: all 37 rows are upcoming auctions with no outcome-table backing -- same
-- structural impossibility as gilchrist. Sarasota's existing 165 matched_clean rows are
-- legitimate (produced by the real canonical refresh_parity_tier1_outcomes() matcher, not a
-- relabel). This exact 81.3% gap was already independently diagnosed one day earlier
-- (20260704_shard14_duval_sarasota_holmes_union_ultraloop_run3025.sql) as a genuine, current
-- hard ceiling with no fixable gap today -- correctly left alone (BLANK > WRONG) rather than
-- forced. NO ACTION TAKEN. Separately flagged (not remediated): 1,111 sarasota
-- multi_county_auctions rows carry data_source='propertyonion', a HARD GUARDRAIL violation
-- ("PropertyOnion = litmus ONLY. Never ingest as a data source.") -- these are correctly
-- excluded from the evaluator's 203-row denominator so they do not corrupt the scoreboard, but
-- they are dead contamination sitting in production and should be cleaned up in a dedicated
-- session (out of scope here: 1,111-row DELETE needs its own review, not a same-session
-- side-effect of a parity fix).

-- ═══════════════════════════════════════════════════════════════════════════
-- PART 3 — FLAGLER: proposed C/D restoration REFUTED, NOT applied (no write)
-- ═══════════════════════════════════════════════════════════════════════════
-- ROOT CAUSE CONFIRMED (informational, no fix shipped): on 2026-07-04T16:29:22Z, a bug in
-- refresh_parity_tier1_outcomes() (its reset step unconditionally nulled parity_status/source
-- for every closed-status row in a county regardless of what wrote it) wiped the 117-row
-- 2026-07-03 promotion (20260703_shard2_flagler_parity_fix.sql, tier1_flagler_direct). The bug
-- was already patched going forward by 20260704_shard13_run3025_2nd_dispatch_refresh_parity_snapshot_fix.sql,
-- but flagler's wiped data was never restored -- all 134 rows currently sit at
-- parity_status=NULL/parity_source=NULL.
--
-- Proposed fix (re-apply the identical July 3 promotion logic) was REFUTED:
--   1. 27 of 134 flagler rows carry parity_po_id/po_market_value/po_sold_amount (real
--      PropertyOnion linkage) -- the "zero PropertyOnion coverage" premise is false at the
--      substantive level. The codebase's own precedent (20260702_shard8_clay_holmes_cd_parity_fix.sql)
--      requires excluding parity_po_id-populated rows from any tier1-direct promotion; the
--      July 3 logic never did this.
--   2. 81 of the 117 originally-promoted rows are auction_status='upcoming' -- matched_clean is
--      definitionally impossible for an auction that hasn't happened, the same structural
--      defect found in gilchrist/sarasota.
--   3. The tier1_flagler_direct label itself was flagged as suspect BEFORE the July 3 fix ran:
--      20260703_shard1_miami_dade_matcher_reinvoke_flagler_fabrication_revert.sql (10:34 UTC,
--      ~6h earlier the same day) found flagler's entire B/F outcome dataset (30 tax_deed_outcomes
--      rows) fabricated via self-referential COALESCE writes, reverted it, and explicitly flagged
--      the pre-existing 17 tier1_flagler_direct rows as "a pure string relabel with no underlying
--      independent-match logic... flagged, not silently fixed." The July 3 16:12 fix extended
--      this already-flagged-suspect label to 117 more rows the same day.
--   4. tax_deed_outcomes and foreclosure_outcomes are BOTH entirely empty for flagler (0 rows
--      each) -- there is no real independent outcome data to match against today. B and F
--      correctly remain FAIL.
-- NO ACTION TAKEN -- flagler's current 0%/0%/FAIL/FAIL honest state is correct and was left
-- alone. Real path forward (documented, not attempted this session): flagler.realtaxdeed.com
-- and flagler.realforeclose.com both return HTTP 200 to a plain fetch as of 2026-07-05 (the
-- 2026-07-03 "403 bot-blocked" finding is now stale) but only serve the RealAuction generic
-- login shell without RealAuction-authenticated credentials (none available in this
-- environment) or the FNC=UPDATE preview-diff endpoint. flaglerclerk.com (separate from
-- RealAuction, the county's own site) returns HTTP 403 to a plain fetch (WAF/Cloudflare),
-- consistent with the prior finding -- a genuine headless-render bypass (Playwright+chromium,
-- per the working precedent in scripts/shard9_union_clerk_realdata_ingest.py) is the viable next
-- step but was not attempted this session (no browser binaries provisioned in this sandbox;
-- deferred to a session budgeted for that setup cost).

-- ═══════════════════════════════════════════════════════════════════════════
-- PART 4 — LIBERTY: proposed C/D fix REFUTED, NOT applied (no write)
-- ═══════════════════════════════════════════════════════════════════════════
-- Proposed: promote liberty's sole row (case 24-CA-22, auction_status='upcoming') to
-- matched_clean via parity_source='tier1_liberty_direct'. REFUTED: same structural
-- impossibility (upcoming auction, no outcome-table backing) plus liberty has a documented
-- FULL FABRICATION HISTORY (20260702_shard1b_liberty_full_fabrication_deletion.sql deleted 4
-- wholesale-synthetic rows a prior session inserted purely to hit a gold-standard score target,
-- with 11 prior audit rows having incorrectly survived=true on that fabricated data before being
-- caught) -- making liberty a high-risk county for any further parity_status promotion without a
-- real outcome join. NO ACTION TAKEN.
--
-- SEPARATE FINDINGS (informational, no fix required/possible this session):
--   A (fc=1 td=0, FAIL): live re-fetch of https://libertyclerk.com/courts/tax-deeds/ confirms
--     the page's own body text states "There are no properties on the list of tax deeds at this
--     time" -- a genuine, verified data ceiling (zero active tax deed sales exist for this
--     county right now), not a scraper defect. scripts/shard_liberty_clerk_scraper.py correctly
--     parses both the foreclosure-sales page (1 row found) and the tax-deeds page (0 rows,
--     correctly empty) as of 2026-07-05.
--   G/I (FAIL): fl_counties shows liberty total_parcels=0, gis_endpoint=NULL -- zero
--     parcel/zoning ingestion has ever run for this county. This is the same fleet-wide gap
--     already diagnosed for every county except brevard (only brevard has zoning substrate
--     loaded) -- out of scope for a single-county fix.
--   B/F (metric=null, FAIL): liberty's only auction has not occurred yet (auction_date
--     2026-07-21) -- closed_sold=0, so the metric is structurally unmeasurable until the sale
--     happens. Not fixable today.

-- ═══════════════════════════════════════════════════════════════════════════
-- FINAL STATE (live pencil_dod_evaluate_county, 2026-07-05, this session):
--   brevard:   10/10 PASS (unchanged, re-verified only, not touched)
--   gilchrist:  8/10 (C=20.0% FAIL, D=20.0% FAIL -- corrected from a false 60.0%/60.0%)
--   sarasota:   8/10 (C=81.3% FAIL, D=81.3% FAIL -- unchanged, correctly left alone)
--   flagler:    6/10 (B/C/D/F FAIL -- unchanged, correctly left alone)
--   liberty:    3/10 (A/B/C/D/F/G/I FAIL -- unchanged, correctly left alone)
-- 5 rows written to gold_standard_ultraloop_audit (dispatch_id
-- de295275-1e36-4809-a813-97bc4a6b897c) per CERTIFY GATE: 1 survived=true (the gilchrist
-- purge), 4 survived=false (the four refuted promotions, logged so no future session
-- re-derives and re-attempts them without new evidence).
