export const meta = {
  name: 'gold-standard-shard6-bradford-run7177',
  description: 'Gold Standard shard-6 bradford (dispatch f68d2ec5, loop run 7177): B/F sale-outcome discovery for case 25000457CAAXMX via new OCRS + browser-based leads, adversarial verify',
  phases: [
    { title: 'Research', detail: 'parallel browser-capable agents, one per new lead' },
    { title: 'Verify', detail: 'independent refuter per positive lead' },
  ],
}

const CASE_CONTEXT = `
Gold Standard campaign, shard-6, county bradford (dispatch f68d2ec5-b6ba-4201-8d33-3c2083e0fce3).
Live baseline (VERIFIED via pencil_dod_evaluate_county('bradford') just now, matches this session's brief exactly):
8/10. Passing: A=1(fc=4 td=1, documented-blocked, tax deed lane genuinely empty per clerk PDF -- do not touch),
C=100(matched_clean=5) D=100(matched_any=5) E=100(parcel_linked=5) G=100(density=100) H=9h I=100(card_complete=5 of 5)
J=100(deal_complete=5). Failing: B=null(verified=0 closed_sold=0), F=null(tier1_sold=0 closed_sold=0).
Do NOT touch A/C/D/E/G/H/I/J -- they already pass cleanly. This is a single-lever B/F fix.

THE LEVER: all 5 bradford rows are auction_status='upcoming'. Four have future auction_date (2026-08-13 x2,
2026-08-20, 2026-09-09). ONE, case 25000457CAAXMX, has auction_date=2026-07-16 -- 13 days in the past as of today
(2026-07-29) -- yet is still 'upcoming' with sold_amount=null. Case detail: 2025-CA-000457, VyStar Credit Union v.
Unknown Heirs of Debra Ilene Hunter, property 18737 CHARLOTTE AVE, BROOKER, FL 32622, parcel_id 00273-0-01000.
This is a foreclosure (sale_type='foreclosure', case format CAAXMX = circuit civil). closed_sold in the evaluator
= count(sold_amount IS NOT NULL); with zero rows having sold_amount, B and F are both structurally null/FAIL until
this ONE case's real sale outcome is found and written in.

EXHAUSTED DEAD ENDS (4 prior sessions today+recently, dispatches 42aac1fb, d07c1eba x2, c475a06d x2 -- documented
in supabase/migrations/20260725_gold_standard_shard5_bradford_i_bf_residual_confirmation.sql,
20260725c_..._bf_3rd_reconfirm.sql, 20260725d_..._bf_4th_reconfirm_ori_turnstile.sql -- READ these files yourself
for full detail before starting). DO NOT RE-TRY these -- confirmed dead by direct fresh reproduction each time:
  - bradfordclerk.com/tax-deeds-and-foreclosure-sales/ and /foreclosures/ and /official-records/ -- Cloudflare
    "Just a moment..." 403 challenge via plain curl AND WebFetch, reproduced multiple sessions.
  - Firecrawl static scrape of bradfordclerk.com -- was HTTP 402 (no credits) in prior sessions; RE-VERIFIED this
    session credits ARE available now (no longer 402) but the scrape now returns HTTP 408 SCRAPE_TIMEOUT even with
    waitFor=8000/timeout=60000 -- the Cloudflare JS challenge does not resolve within Firecrawl's own scrape budget.
    Do not keep retrying plain firecrawl-scrape on this URL -- it is a dead end via that specific tool/mode.
  - bctelegraph.com legal notices checked THROUGH the 7-23-26 issue -- pre-sale notice found (confirms case detail
    above), no post-sale/certificate-of-title notice as of that issue.
  - surplusindex.com/bradford-county-florida-excess-funds-list/ -- HTTP 404.
  - Wayback Machine CDX for bradfordclerk.com -- only captures the Cloudflare challenge page, dead.
  - bradford.realforeclose.com / realtaxdeed.com -- confirmed NOT a RealAuction client, redirects to generic
    marketing site. Do not re-probe RealAuction subdomains.
  - officialrecords.bradfordclerk.com (guessed subdomain) -- DNS resolution failure.
  - myfloridacounty.com/orisearch/04 -- search form loads, but every POST search submission hits a Cloudflare
    Turnstile human-verification challenge via plain curl/WebFetch. Do NOT attempt to solve/bypass a CAPTCHA --
    if a REAL interactive browser session (see NEW LEADS below) also hits an actual Turnstile challenge requiring
    interactive human solving, stop and report it blocked; do not try adversarial bypass techniques.
  - gz.floridapa.com/mapserver/ -- undocumented CGI, unrelated to sale outcomes anyway (was for I/E parcel lookup,
    already resolved by a different method).
  - records.bradfordco.org/PSI/ -- redirects to /PSI/auth, login-gated (checked fresh this session, HTTP 302 to
    auth). Do not pursue -- same login-gated category as OCRS-guess, not the anonymous one below.

NEW LEADS (found fresh this session via Firecrawl search -- genuinely untried by any prior bradford session):
  1. https://www.civitekflorida.com/ocrs/county/04/ -- "Bradford County OCRS", page text explicitly states
     "This option allows for anonymous access to court records" (distinct from the Attorney-of-Record login option
     also listed on the same page -- use ONLY the anonymous/public option, never attempt the attorney login).
     Verified fresh this session: HTTP 200, real JSF/PrimeFaces search application (not Cloudflare-blocked), a
     completely different vendor/domain than bradfordclerk.com or the myfloridacounty ORI guess. This is a
     genuine, live, government-operated Florida court-records search portal (Civitek is a known FL clerk-records
     SaaS vendor) -- using it to search a real, already-public case number for its own docket entries is exactly
     the kind of authorized public-records lookup this campaign's B/F playbook calls for, not any kind of scraping
     violation. This form is JSF-based with ViewState/AJAX postbacks -- plain curl cannot drive it usably; use a
     real browser automation tool (the "browser-use" or "firecrawl-browser" Skill) to load the page, search for
     case number "2025-CA-000457" (try both with and without dashes, and try "25000457CAAXMX" if the first format
     yields nothing), and read the docket for any post-sale filing: Certificate of Title, Certificate of
     Disbursements, Final Judgment amount, Notice of Sale results, or a docket entry explicitly stating the sale
     was cancelled/continued/redeemed. If postponed/continued to a new date, that is ALSO a valid, useful, real
     finding (report the new sale date; do not fabricate a sold amount for a sale that didn't happen).
  2. Bradford County's own tax-deeds-and-foreclosure-sales page (bradfordclerk.com, Cloudflare-blocked to static
     tools) is documented (pipeline.counties.notes, VERIFIED 2026-07-03) to link out to a Box.com folder named
     "FORECLOSURE SALE LIST", refreshed periodically by clerk staff -- Box.com folders are typically NOT
     Cloudflare-protected the way the parent site is. No prior session's residual-confirmation migrations mention
     actually reaching this Box.com link -- it appears genuinely untried, likely because reaching it first requires
     rendering the blocked parent page. Use a real browser automation tool (same Skill as above) to load
     bradfordclerk.com/tax-deeds-and-foreclosure-sales/ with full JS execution (a real browser may clear the
     Cloudflare JS challenge where curl/plain Firecrawl scrape cannot -- if it also hard-blocks in a real browser,
     report that plainly, do not force it), locate the Box.com link, follow it, and check the resulting document
     for case 25000457CAAXMX / property "18737 Charlotte Ave" / party "Debra Ilene Hunter" or "VyStar Credit Union".
`

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... headers apikey: $SUPABASE_SERVICE_ROLE_KEY,
  Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY. NEVER echo/print/log the header value itself -- reference the
  env var in the command, do not paste the resolved secret into any file, comment, or tool output.
- Live arbitrary SQL: POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query, headers
  Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json, body {"query": "<sql>"}. Build the
  JSON with a real encoder (python3 -c "import json; ..." to a temp file, curl --data-binary @file) -- do not
  hand-quote. direct psql/psycopg2 pooler connections are known to fail password auth in this environment; use
  the Management API / REST exclusively.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county body
  {"p_county":"bradford"} -- your before/after proof. B passes ONLY in the 95-105%% band. F needs tier1_sold_amount
  AND sold_amount both non-null on the same row.
- Skills available via the Skill tool: "browser-use" and "firecrawl-browser" for real interactive browser sessions
  (JS execution, form fills, clicks) -- use one of these for the JSF OCRS search and the Box.com link discovery.
  "firecrawl-scrape"/"firecrawl-search" for simple static content only (already tried and dead-ended on
  bradfordclerk.com directly, per context above -- do not keep retrying static scrape on that specific URL).
- FIRECRAWL_API_KEY is present and has credit (verified fresh this session -- no longer HTTP 402).
- gh CLI is authenticated. Repo root is the current working directory (worktree-isolated copy, on main).

Hard rules (from the campaign brief and this codebase's CLAUDE.md -- follow exactly):
- You own ONLY bradford, case 25000457CAAXMX. Never touch any other bradford row or any other county.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as independent/verified.
- Fail-loud invariant: if you find zero real data, report it as blocked/residual. NEVER fabricate a case number,
  sold amount, date, or party name, and NEVER reuse another row's/parcel's numbers as a stand-in. This exact
  county has a documented double-revert history of fabricated I-values (see
  supabase/migrations/20260703_shard13_polk_cd_realforeclose_matches_bradford_i_honesty_fix.sql and its revert in
  20260710_shard_bradford_i_refabrication_stop_and_e_appraiser_lookup.sql) -- zero tolerance, do not repeat it here.
- Every claim you return must be tagged VERIFIED (you ran the request and are pasting real output/evidence),
  UNTESTED, or INFERRED (say why).
- Do NOT attempt to solve or bypass any CAPTCHA/Turnstile challenge. If one blocks you, report it and stop that
  angle.
- Do not run public.gold_standard_loop(), gold_standard_certify(), or modify cron jobs 109/111/115 or any
  gold-standard-loop-* job.
`

phase('Research')
const LEADS = [
  {
    key: 'civitek_ocrs',
    prompt: `You are working Gold Standard shard-6, county bradford, inside the cli-anything-biddeed repo (already checked out, on main).\n\n${CASE_CONTEXT}\n\n${RECIPE}\n\nYOUR SPECIFIC JOB: pursue NEW LEAD #1 ONLY (the civitekflorida.com/ocrs/county/04/ anonymous OCRS search) for case 25000457CAAXMX / 2025-CA-000457. Use the "browser-use" or "firecrawl-browser" Skill to drive the search form interactively. Try both case-number formats. If you reach real docket results, extract: case status, any Certificate of Title / Certificate of Disbursements / sale-result entry, winning bid / sale amount if present, sale date if changed, and the exact docket entry text as evidence. If the anonymous option itself turns out to be login-gated in practice (contrary to its own page text) or hits a CAPTCHA, report that plainly and stop -- do not try the attorney-login path or any bypass.\n\nReturn { lead: "civitek_ocrs", found: boolean, sale_result: {winning_bid, sale_date, outcome, party_names} | null, evidence: string (exact text/screenshot description + URL), confidence: "VERIFIED"|"UNTESTED"|"INFERRED", notes: string }.`,
  },
  {
    key: 'box_foreclosure_list',
    prompt: `You are working Gold Standard shard-6, county bradford, inside the cli-anything-biddeed repo (already checked out, on main).\n\n${CASE_CONTEXT}\n\n${RECIPE}\n\nYOUR SPECIFIC JOB: pursue NEW LEAD #2 ONLY (the Box.com "FORECLOSURE SALE LIST" doc linked from bradfordclerk.com/tax-deeds-and-foreclosure-sales/). Use the "browser-use" or "firecrawl-browser" Skill for full JS rendering (a real browser may get past the Cloudflare challenge where curl/plain firecrawl-scrape could not -- confirm this fresh, don't assume). If you reach the page, locate the Box.com link, follow it, and search the document for case 25000457CAAXMX, property "18737 Charlotte Ave, Brooker, FL 32622", or parties "VyStar Credit Union" / "Debra Ilene Hunter". If the page is still hard-blocked even in a real browser session, report that plainly as confirmed-dead (don't force it) and, opportunistically only, try a plain web search (WebSearch or firecrawl-search) for "Bradford County Florida foreclosure sale list Box.com" or "bradfordclerk.com foreclosure sale list" to see if the Box.com folder URL is indexed/discoverable independently of the blocked parent page.\n\nReturn { lead: "box_foreclosure_list", found: boolean, sale_result: {winning_bid, sale_date, outcome, party_names} | null, evidence: string (exact text + URL), confidence: "VERIFIED"|"UNTESTED"|"INFERRED", notes: string }.`,
  },
]

const findings = await parallel(LEADS.map((lead) => () => agent(lead.prompt, {
  label: `research:${lead.key}`,
  phase: 'Research',
  schema: {
    type: 'object',
    properties: {
      lead: { type: 'string' },
      found: { type: 'boolean' },
      sale_result: {},
      evidence: { type: 'string' },
      confidence: { type: 'string' },
      notes: { type: 'string' },
    },
    required: ['lead', 'found', 'evidence'],
  },
})))

const positiveLeads = findings.filter(Boolean).filter(f => f.found)
log(`Research complete: ${findings.filter(Boolean).length}/${LEADS.length} leads returned, ${positiveLeads.length} claim a positive find.`)

phase('Verify')
let verifications = []
if (positiveLeads.length > 0) {
  verifications = await parallel(positiveLeads.map((f) => () => agent(
    `Independently verify this claimed Gold Standard bradford B/F finding for case 25000457CAAXMX. You did NOT do this research -- be skeptical.\n\n` +
    `Claimed finding: ${JSON.stringify(f)}\n\n${CASE_CONTEXT}\n\n${RECIPE}\n\n` +
    `Your job: re-visit the exact same source yourself, independently, right now (use "browser-use" or "firecrawl-browser" fresh -- do not just trust the pasted evidence). Confirm: (a) the case number/property/party match exactly, ` +
    `(b) the sale amount and outcome are real docket/document content, not inferred or guessed, (c) the source is genuinely independent (not PropertyOnion-derived, not a third-party AVM estimate standing in for an official amount -- ` +
    `this county has a documented history of exactly that failure mode, e.g. an Auction.com Cotality AVM estimate was correctly rejected in a prior session for this same reason). Return ` +
    `{ lead: string, refuted: boolean, refutation_reason: string|null, confirmed_sale_result: object|null, survives: boolean }.`,
    {
      label: `verify:${f.lead}`,
      phase: 'Verify',
      schema: {
        type: 'object',
        properties: {
          lead: { type: 'string' },
          refuted: { type: 'boolean' },
          refutation_reason: {},
          confirmed_sale_result: {},
          survives: { type: 'boolean' },
        },
        required: ['lead', 'refuted', 'survives'],
      },
    }
  )))
}

return { findings, verifications }
