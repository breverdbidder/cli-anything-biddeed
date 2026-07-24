-- Gold Standard shard-8 suwannee, 2nd session today (dispatch 15bb3eb1-ecb1-4e92-b2a9-684b372f0d1d)
--
-- Context: the day's 1st suwannee session (be0fd55f / 7daa017f) already shipped A (0->PASS,
-- fc=4 td=9) and J (0->100%, 13/13 real Shapira V14 per-property inference), live-reverified
-- by this session before touching anything (pencil_dod_evaluate_county('suwannee') matched the
-- prior session's claimed after-state exactly, no drift). This session targeted the two
-- remaining failing letters, B and F, both structurally gated on closed_sold=0 (all 13 suwannee
-- auction rows have sold_amount IS NULL -- nothing has posted a sale result yet).
--
-- NEW WORK THIS SESSION (not a repeat of the 4666/4667 tax-deed checks already done 2026-07-11,
-- 07-18, 07-19, 07-20, 07-24 session 1):
--   1. Case 25-CA-197 (auction_date 2026-07-23, YESTERDAY relative to this session) is the one
--      row in the 13-row suwannee set with a past auction date that had never been checked for
--      a posted result -- it was only inserted into multi_county_auctions by TODAY'S 1st session.
--   2. Ran an ultracode Workflow (2 parallel investigate agents, adversarial-refuter gate wired
--      for any positive claim) to check for a sale result on 25-CA-197 and to attempt
--      disambiguating the held-back "David Thomas" (25-CA-200) A-residual.
--   3. Investigation flagged a possible case_number/defendant mismatch (25-CA-197 vs 25-CA-170)
--      against the county's authoritative docx list. Independently re-queried
--      multi_county_auctions directly (not trusting the agent's characterization) and confirmed
--      the DB pairing is actually CORRECT: 25-CA-170=Saavedra (sale 7/28, still future),
--      25-CA-197=Dowdy (sale 7/23, past) -- no data-integrity bug, the agent's own prompt (mine)
--      had the pairing backwards, caught before any fix was attempted.
--   4. No sale result exists for either case in any source checked (suwgov.org docx list,
--      suwannee-search.gsacorp.io parcel deed/transfer history for Saavedra's parcel -- last
--      instrument still a 2010 QCD, no Suwannee civil docket search exists to check Dowdy's
--      case). closed_sold=0 stands; B and F correctly remain FAIL.
--   5. David Thomas (25-CA-200) disambiguation: located the correct tool
--      (myfloridacounty.com/orisearch/61, supports party-name search across Lis
--      Pendens/Judgment/Certificate of Title) but submission is blocked by a Cloudflare Turnstile
--      CAPTCHA that cannot be solved without an interactive browser. This is a tooling/access
--      limitation, not a confirmed absence of public data -- flagged for a session with
--      browser-automation available, not force-resolved by guessing among the 3 candidates.
--
-- No multi_county_auctions rows changed. No sold_amount/tier1_sold_amount fabricated.
--
-- gold_standard_ultraloop_audit: 2 new rows (B, F; both survived=true, dispatch_id above),
-- applied live via Supabase Management API before this file was committed -- included below
-- verbatim as the historical record. Re-running this INSERT would duplicate rows; it is NOT
-- idempotent and is not intended to be re-applied by `supabase db push`.

INSERT INTO gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived) VALUES
('15bb3eb1-ecb1-4e92-b2a9-684b372f0d1d','native','suwannee','B',
 '5th independent re-check (2026-07-24, session 2 of the day): confirmed case_number/defendant pairing in multi_county_auctions is CORRECT (25-CA-170=Saavedra/14127 CR 252, sale 7/28 future; 25-CA-197=Dowdy/608 Savannah St NW, sale 7/23 already past) -- ruling out a data-integrity bug as an explanation for B=0. Checked suwgov.org live docx sale list (revised 7/20), the Property Appraiser deed/transfer history for Saavedra''s parcel 08767000011 (last instrument 2010 QCD, no 2025/26 transfer), and confirmed no Suwannee civil docket search exists to find a result for Dowdy''s sale either. No posted sale result exists for either case. verified=0/closed_sold=0 stands; correctly FAIL, not a scraper bug.',
 '{"web_sources_checked":["suwgov.org/wp-content/uploads/Foreclosure-List-2-1-12.docx","suwannee-search.gsacorp.io/api/livesearch/Saavedra","suwannee-search.gsacorp.io/parcel/3203S13E08767000011","suwannee-search.gsacorp.io/api/livesearch/Dowdy","suwgov.org/court-services/foreclosures/"],"db_cross_check":"multi_county_auctions case_number/owner_name pairing independently confirmed correct, no bug found","confidence_tag":"VERIFIED"}'::jsonb,
 true),
('15bb3eb1-ecb1-4e92-b2a9-684b372f0d1d','native','suwannee','F',
 'Direct consequence of B finding (2026-07-24, session 2): closed_sold=0 stands, so tier1_sold cannot exist. No lever this session.',
 '{"basis":"F is structurally gated on B/closed_sold; same evidence set as B row this session","confidence_tag":"VERIFIED"}'::jsonb,
 true);
