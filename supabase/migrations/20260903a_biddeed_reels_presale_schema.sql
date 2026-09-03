-- BidDeed Reels v3 (issue #19761): PRE-SALE (calendar) reels + deal pages.
--
-- Additive-only on top of v1/v2's winnerdata.biddeed_reels (issues
-- #19736/#19752). New columns support presale rows built from
-- v_upcoming_auctions_ssot BEFORE the auction happens, distinct from v1/v2's
-- postsale rows (built AFTER a sale is captured, keyed off sold_amount).
--
-- The existing unique(case_number, county) constraint
-- (biddeed_reels_case_number_county_key, verified live via pg_constraint)
-- would collide once the SAME case_number/county gets a presale row before
-- the auction and a postsale row after it -- replaced with the 3-column
-- unique the issue asks for so both phases can coexist for one case.

begin;

alter table winnerdata.biddeed_reels
  add column if not exists phase           text not null default 'postsale'
    check (phase in ('presale','postsale')),
  add column if not exists opening_bid     numeric,
  add column if not exists judgment_amount numeric,
  add column if not exists days_to_auction integer,
  add column if not exists presale_rank    numeric;

alter table winnerdata.biddeed_reels
  drop constraint if exists biddeed_reels_case_number_county_key;

alter table winnerdata.biddeed_reels
  add constraint biddeed_reels_case_county_phase_key unique (case_number, county, phase);

create index if not exists biddeed_reels_phase_auction_date_idx
  on winnerdata.biddeed_reels(phase, auction_date);

comment on column winnerdata.biddeed_reels.phase is
  'presale = built before the auction from v_upcoming_auctions_ssot (issue #19761, T1). postsale = built after a sale from auction_buyer_sightings (v1/v2, issues #19736/#19752). Default postsale preserves every pre-existing row''s meaning unchanged.';
comment on column winnerdata.biddeed_reels.presale_rank is
  'issue #19761 T4 ranking score for presale rows only -- see rank_presale_score() in scripts/biddeed_reels_lib.py for the formula. Unrelated to the existing rank_score column, which is v1/v2 postsale-only.';
comment on column winnerdata.biddeed_reels.days_to_auction is
  'auction_date minus the date this row was last (re)computed -- snapshot at render time, not a live countdown (issue #19761 T5 runs this pipeline at auction_date = today+2, so this is normally 2 on first render).';

commit;
