-- SHARD-8 run2886 addendum (same dispatch_id 0b518e79-822d-473f-ae19-1362c72bf9be)
-- Companion to 20260704_shard8_run2886_martin_cd_pa_certificate_of_title_fix.sql.
--
-- HONEST REGRESSION FOUND AND FIXED: after applying the companion migration,
-- refresh_parity_tier1_outcomes('martin') was run per instructions (canonical
-- tier1 matcher). Its first step resets parity_status=NULL for EVERY martin
-- row currently in a terminal auction_status ('redeemed','completed','sold',
-- 'cancelled','canceled') before re-matching against foreclosure_outcomes /
-- tax_deed_outcomes. That reset is county-wide, not scoped to the 6 rows this
-- shard touched -- it also wiped 3 pre-existing cancelled rows
-- (24000956CAAXMX, 25000363CAAXMX, 25002912CCAXMX) that were already
-- auction_status='cancelled' before this session and had SOME parity_status
-- set by an earlier, non-tier1 mechanism (parity_source was NULL/legacy on
-- inspection), but no backing row in foreclosure_outcomes/tax_deed_outcomes
-- to be re-matched against. Net effect measured live: D (matched_any) went
-- 44.8%->37.9%, a real drop caused by invoking the canonical function, not
-- by this shard's own case-number fixes (those only ever added matches).
--
-- FIX: independently verify these 3 cancelled cases via the same real
-- pamartinfl.gov Sale History source used in the companion migration, then
-- backfill foreclosure_outcomes so the canonical matcher has something real
-- to match them against instead of leaving them orphaned by its own reset.
-- auction_status was NOT changed for these 3 -- it was already 'cancelled'
-- before this session and remains so; only the missing outcomes-table
-- backing is added.
--
--   24000956CAAXMX  auction 2026-04-07  parcel 34-38-42-053-002-00190-3
--     Sale History shows only a 2023 NC-Quit Claim Deed ($100) -- no 2026
--     recording of any kind (no CoT, no market deed). Consistent with
--     cancellation (case never reached a sale); does not independently
--     prove *why* it was cancelled, but corroborates that no sale occurred.
--     https://www.pamartinfl.gov/app/search/pcn/34-38-42-053-002-00190-3
--   25000363CAAXMX  auction 2026-05-14  parcel 19-38-41-002-000-00952-0
--     Personal Representative's Deed recorded 2026-04-30 (14 days BEFORE
--     the scheduled 2026-05-14 auction), $290,000, grantor "REGO ROBERT A
--     ESTATE", Doc #3184525, Bk/Pg 3565/511 -- an estate sale that resolved
--     the property before the foreclosure auction could occur. No CoT
--     recorded for this parcel at all.
--     https://www.pamartinfl.gov/app/search/pcn/19-38-41-002-000-00952-0
--   25002912CCAXMX  auction 2026-04-28  parcel 48-38-41-180-015-54550-0
--     Quit Claim Deed recorded 2026-03-29 (30 days BEFORE the scheduled
--     2026-04-28 auction), $100 nominal, grantor "HAMLIN ISABEL KILLEEN",
--     Doc #3178696, Bk/Pg 3558/1697 -- a pre-auction transfer, no CoT
--     recorded for this parcel at all.
--     https://www.pamartinfl.gov/app/search/pcn/48-38-41-180-015-54550-0
--
-- All 3: outcome='cancelled' (matches existing, unmodified auction_status),
-- winning_bid left NULL (no sale occurred), data_source tag distinguishes
-- this from the CoT-backed 'sold' rows in the companion migration since the
-- evidence standard here is weaker (absence of a CoT + a pre-auction deed,
-- not a direct sale-price confirmation) -- tagged with ':INFERRED' suffix
-- per HONESTY PROTOCOL to reflect that the cancellation *reason* is
-- inferred from deed timing, even though the cancelled *status* itself was
-- already independently on record in our own DB before this session.

INSERT INTO foreclosure_outcomes (
  case_number, county, sale_type, auction_date, final_judgment, winning_bid,
  outcome, property_address, parcel_id, data_source, source_url
) VALUES
  ('24000956CAAXMX', 'martin', 'foreclosure', '2026-04-07', 119788.67, NULL,
   'cancelled', '6917 SE DELEGATE ST, HOBE SOUND, FL- 33455', '34-38-42-053-002-00190-3',
   'martin_pa_sale_history:shard8_run2886:INFERRED',
   'https://www.pamartinfl.gov/app/search/pcn/34-38-42-053-002-00190-3'),
  ('25000363CAAXMX', 'martin', 'foreclosure', '2026-05-14', 248339.33, NULL,
   'cancelled', '3693 SW WHISPERING SOUND DR', '19-38-41-002-000-00952-0',
   'martin_pa_sale_history:shard8_run2886:INFERRED',
   'https://www.pamartinfl.gov/app/search/pcn/19-38-41-002-000-00952-0'),
  ('25002912CCAXMX', 'martin', 'foreclosure', '2026-04-28', 17628.60, NULL,
   'cancelled', '5455 SE SCHOONER OAKS WAY, STUART, FL- 34997', '48-38-41-180-015-54550-0',
   'martin_pa_sale_history:shard8_run2886:INFERRED',
   'https://www.pamartinfl.gov/app/search/pcn/48-38-41-180-015-54550-0')
ON CONFLICT (case_number, county, auction_date) DO UPDATE SET
  outcome        = EXCLUDED.outcome,
  parcel_id      = EXCLUDED.parcel_id,
  data_source    = EXCLUDED.data_source,
  source_url     = EXCLUDED.source_url,
  enriched_at    = now();

-- Re-run the canonical tier1 matcher for martin to pick up these 3 backfills
-- (no auction_status change needed -- they were already 'cancelled').
SELECT * FROM refresh_parity_tier1_outcomes('martin');

-- VERIFICATION QUERY (run after apply):
-- SELECT public.pencil_dod_evaluate_county('martin');
