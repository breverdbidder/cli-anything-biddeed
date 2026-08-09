-- Adversarial refuter audit rows for union county B/F investigation
-- Independent verification session, 2026-08-09
-- Diagnosis claim: closed_sold=0 is genuine structural accrual block (unionclerk.com
-- Cloudflare-403, both RealAuction subdomains 403, Civitek OCRS Turnstile/JSF-form
-- blocked, no case-level sale results via WebSearch).
-- Refuter verdict: SURVIVED. Independent re-verification via fresh pencil_dod_evaluate_county,
-- fresh WebSearch with different terms, direct WebFetch (403 confirmed independently),
-- floridacourtaccess.org, UniCourt, taxdeedsales.com (dead JS-redirect stub),
-- civitekflorida.com OCRS JSF form (landing page reachable but requires stateful
-- PrimeFaces AJAX interaction untraversable via curl/WebFetch), and Wayback Machine
-- (zero archived snapshots of the foreclosure-sales page) all found ZERO evidence of
-- a missed sale. Both open case numbers (63-2025-CA-0053, 63-2024-CA-0047) confirmed
-- genuinely upcoming (auction_date > CURRENT_DATE). Tax deed case UNION-TD-CERT223
-- correctly resolved as redeemed (not sold), sourced from unionclerk_official, not
-- PropertyOnion.

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
(
  NULL,
  'native',
  'union',
  'B',
  'union B (verified_outcomes/closed_sold) fails with closed_sold=0 — genuine structural accrual block: unionclerk.com Cloudflare-403 on all subpaths, RealAuction subdomains 403, Civitek OCRS Turnstile/JSF-blocked, no case-level sale results found anywhere.',
  jsonb_build_object(
    'fresh_pencil_dod_evaluate_county', jsonb_build_object('B', jsonb_build_object('pass', false, 'detail', 'verified=0 closed_sold=0', 'metric', null)),
    'db_check_case_dates', 'SELECT case_number, auction_date, auction_date > CURRENT_DATE, auction_status FROM multi_county_auctions WHERE county=union AND sale_type=foreclosure -> 63-2025-CA-0053 (2026-08-13, upcoming, is_future=true), 63-2024-CA-0047 (2026-10-15, upcoming, is_future=true)',
    'db_check_foreclosure_outcomes', 'SELECT DISTINCT county FROM foreclosure_outcomes WHERE case_number ILIKE %0053% OR %0047% -> only bay/broward/duval/hillsborough/orange/palm_beach/pinellas/santa_rosa/sarasota/seminole/volusia; ZERO union rows (broad substring match confirms no false negative)',
    'db_check_tax_deed_outcomes', 'SELECT * FROM tax_deed_outcomes WHERE case_number ILIKE %UNION% -> 1 row UNION-TD-CERT223 outcome=redeemed data_source=unionclerk_official:tier1_live_20260711 (not PropertyOnion, correctly not counted as sold)',
    'websearch_1', 'query: "63-2025-CA-0053" Union County Florida -> no case-level result, only generic unionclerk.com foreclosure-sales page + unrelated case 63-2025-CA-0063',
    'websearch_2', 'query: "63-2024-CA-0047" Union County Florida foreclosure -> no case-level result, generic listing aggregators only',
    'websearch_3', 'query: unionclerk.com foreclosure sale case numbers sold amount -> no match, unrelated county PDFs returned',
    'websearch_4', 'query: Union County FL clerk civil case search cancelled continued -> floridacourtaccess.org and UniCourt surfaced but neither has case-level lookup for these numbers',
    'websearch_5', 'query: Union County Florida foreclosure sale results August 2026 Lake Butler -> only generic market-trend aggregator pages, no case-level outcome',
    'webfetch_independent', 'WebFetch https://unionclerk.com/departments-services/court-services/foreclosure-sales/ -> HTTP 403 Forbidden (independently reproduces diagnosis agents finding via different tool call)',
    'webfetch_floridacourtaccess', 'WebFetch https://floridacourtaccess.org/union-county -> confirms no direct case lookup, recommends contacting clerk directly, notes Union Countys records are less accessible online than larger counties',
    'ocrs_form_probe', 'curl to civitekflorida.com/ocrs/county/63/ returns HTTP 200 landing page (Public/Attorney/Registered/Party access options) but is a PrimeFaces JSF form requiring stateful AJAX POST with ViewState token; attempted POST reproduction returned the same landing page (untraversable via curl without full JS browser session) -- consistent with prior sessions Turnstile-blocked characterization at the practical/functional level',
    'taxdeedsales_com', 'curl https://www.taxdeedsales.com/florida/union-county -> 114-byte client-side JS redirect stub to /lander, dead end, no data',
    'wayback_machine', 'curl archive.org/wayback/available for unionclerk.com foreclosure-sales page -> archived_snapshots: {} (zero snapshots exist, cannot cross-check historical page state)',
    'conclusion', 'No missed sale found after independent multi-source effort using different search terms/tools than the diagnosis agent. Structural block claim CONFIRMED to survive adversarial review.'
  ),
  true
),
(
  NULL,
  'native',
  'union',
  'F',
  'union F (tier1_sold/closed_sold) fails with closed_sold=0 for the same root cause as B — no closed/sold foreclosure or tax-deed cases exist in Union County live data beyond the correctly-redeemed tax deed cert; structural accrual block, not a scraper bug.',
  jsonb_build_object(
    'fresh_pencil_dod_evaluate_county', jsonb_build_object('F', jsonb_build_object('pass', false, 'detail', 'tier1_sold=0 closed_sold=0', 'metric', null)),
    'shared_evidence_with_letter_B', 'F and B share the same closed_sold=0 denominator (count of sold_amount IS NOT NULL among Union auctions); since B was independently re-verified as a genuine structural block (see letter B row, same audit batch), F fails for the identical root cause -- no fabrication path exists because there is no candidate sold row to even mis-tag as tier1',
    'db_check_sold_amount_column', 'SELECT case_number, sold_amount FROM multi_county_auctions WHERE lower(county)=union -> all 3 rows have sold_amount=null (UNION-TD-CERT223 redeemed not sold, two foreclosure cases upcoming not yet auctioned)',
    'conclusion', 'No missed sale found. F structural-block claim CONFIRMED to survive adversarial review, consistent with and dependent on the B finding.'
  ),
  true
);
