export const meta = {
  name: 'gold-standard-shard9-columbia-run7177',
  description: 'Gold Standard shard-9 columbia (dispatch b5ef98e4, loop run 7177): 3rd firing on this dispatch — B/F outcome discovery for 7 now-past-due cases via civitek OCRS + browser leads, I Fort White zoning fresh recheck, A tax-deed/realtaxlien fresh recheck, adversarial verify',
  phases: [
    { title: 'Research', detail: 'parallel browser-capable agents, one per new angle' },
    { title: 'Verify', detail: 'independent refuter per positive lead' },
  ],
}

const CASE_CONTEXT = `
Gold Standard campaign, shard-9, county columbia ONLY (dispatch b5ef98e4-2451-463c-bf3f-5bca27e5c4b7, loop run 7177).
Live baseline (VERIFIED via pencil_dod_evaluate_county('columbia') just now, matches this session's brief exactly):
6/10. Passing: C=100(matched_clean=15) D=100(matched_any=15) E=100(parcel_linked=15) G=100(density=100)
H=18.4h(SLA48h) J=100(deal_complete=15). Failing: A=0(fc=15 td=0), B=null(verified=0 closed_sold=0),
F=null(tier1_sold=0 closed_sold=0), I=93.3(card_complete=14 of 15).
Do NOT touch C/D/E/G/H/J -- they already pass cleanly. Do NOT touch any county other than columbia.

THIS IS THE THIRD FIRING on this exact dispatch/problem. Two prior sessions (2026-07-27, see
GOLD_STANDARD_SHARD9_COLUMBIA_DISPATCH_FD02926F_RUN6871_SESSION_REPORT.md and its
_CONTINUATION_ADDENDUM.md, both in repo root -- READ THESE YOURSELF before starting) exhaustively confirmed
A/B/F/I blocked via ~10+ independent methods and 2 rounds of adversarial refuters. Re-verified fresh at the
start of THIS session (2026-07-29): columbiaclerk.com/tax-deed-sales/ = HTTP 403 (Cloudflare), still blocked.
columbiafl.realtaxlien.com = HTTP 403, still blocked. civitekflorida.com/ocrs/county/12/index.xhtml = HTTP 200
(reachable), consistent with prior finding that the OCRS *page* loads but the *search action* was Turnstile-
gated when tested for a different county (bradford, county 04) two days ago. Columbia's own OCRS gating has
NOT yet been tested with a real interactive browser -- that is this session's genuinely new angle for B/F.

EXHAUSTED DEAD ENDS (do NOT re-try, confirmed dead by direct fresh reproduction across 2 prior sessions):
  - columbiaclerk.com (tax-deed-sales, foreclosures, official-records paths) -- Cloudflare 403 via curl (3 UAs),
    WebFetch, headless Chromium dump-dom (worked on 2026-07-05, no longer works), Python urllib (also hits a
    SECOND block layer, WP Defender AntiBot Global Firewall). Firecrawl scrape was HTTP 402 (no credits) two
    sessions ago -- if credits are now available, a fresh Firecrawl attempt is fine (not exhausted), but if it
    hits the same Cloudflare JS-challenge timeout pattern seen on other blocked clerk sites in this campaign
    (see bradfordclerk.com precedent), do not keep retrying that specific tool/mode.
  - gis.columbiacountyfla.com Zoning_Atlas (point + polygon query) -- zero features for parcel 33-6S-16-04023-000
    / STRAP 04023000166S33 (Fort White, incorporated -- county GIS only covers unincorporated).
  - gis11.cama.io ColumbiaCounty_Features/MapServer/21 "County Zoning" -- also zero features for the same parcel
    (independently re-confirmed this session: MapServer/21 no longer resolves at all, HTTP 500 "service not
    found" -- the CAMA vendor's schema appears to have changed; worth one fresh discovery pass on the current
    MapServer layer list, but do not assume the old layer-21 zoning data still exists there).
  - Fort White's own LDC ordinance text (Article 2, Ordinance 174-2013) -- district table + dimensional
    standards only, no street/subdivision-keyed boundary description that would let you determine THIS parcel's
    zone from the ordinance alone.
  - Zoneomics.com -- no free address lookup, paid report required, no budget authorization.
  - civitekflorida.com OCRS search action -- CONFIRMED Turnstile-gated for county 04 (bradford) two days ago
    (server round-trip to challenges.cloudflare.com/.../pat/... returned HTTP 401, form cleared, visible
    "Verify you are human" checkbox appeared). NOT yet tested for county 12 (columbia) specifically -- Civitek
    is multi-tenant and per-county Turnstile config CAN differ; this is a genuinely open question, test it
    fresh, do not assume it is identical.
  - Wayback Machine CDX for columbiaclerk.com/tax-deed-sales/ -- most recent snapshot 2024-11-10, shows 2024
    parcels only, no 2025/2026 data (checked 2 days ago; a fresh CDX query costs nothing and dates may have
    added a newer snapshot since -- worth one more check, low cost).
  - FL DOR statewide tax-cert-sale PDF (floridarevenue.com) confirmed Columbia's 2026 lien pipeline active at
    columbiafl.realtaxlien.com, bidding started 2026-05-13 -- but that portal itself is 403-blocked (re-confirmed
    fresh this session), so it does not supply a live deed-application count.

NEW GROUND FOR THIS SESSION (genuinely untried):
  1. B/F: use a real interactive browser (browser-use or firecrawl-browser Skill) against
     civitekflorida.com/ocrs/county/12/index.xhtml (note: county 12 = columbia, NOT 04). Use the anonymous
     public-access option (never the attorney-login option). Search each of these 7 case numbers (all now
     past their auction_date as of today 2026-07-29 with sold_amount still NULL): 2025-499-CA, 2025-396-CA,
     2025-103-CA, 2023-492-CA, 2023-79-CA, 2025-2196-CC, 2025-501-CA. Try both hyphenated and CAAXMX/CCAXMX
     suffixed formats. If the search action itself hits a Turnstile challenge (like bradford's), report that
     plainly and STOP -- do not attempt to solve/bypass it. If it does NOT hit a Turnstile challenge (genuinely
     possible -- per-county config can differ), read the docket for each case: look for Certificate of Title,
     Certificate of Disbursements, Final Judgment amount, Notice of Sale results, or an entry stating
     cancelled/continued/redeemed. A postponement to a new date is a valid, reportable finding too -- do not
     fabricate a sold amount for a sale that did not happen.
  2. I: Fort White parcel 33-6S-16-04023-000 (STRAP 04023000166S33), 357 SW AMIEL CT, owner LAND HAND OUTDOORS
     LLC. Do a fresh discovery pass on gis11.cama.io's CURRENT MapServer layer list (the old layer/21 zoning
     reference is stale -- HTTP 500 now) to see if zoning moved to a different layer number under a schema
     change, rather than assuming it is gone. Also try a plain WebSearch/firecrawl-search for "Fort White
     Florida zoning map parcel lookup" or "Town of Fort White planning department contact" to find either a
     newer digitized zoning source or a public contact/email that could supply a real zone code (record the
     contact for a human follow-up if found -- do not fabricate a code).
  3. A: fresh CDX check on web.archive.org for columbiaclerk.com/tax-deed-sales/ for any snapshot newer than
     2024-11-10, and a fresh attempt at columbiafl.realtaxlien.com with a real interactive browser (not just
     curl) in case a real browser clears whatever is producing the 403 (report plainly if it still hard-blocks
     in a real browser -- do not force it).
`

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... headers apikey: $SUPABASE_SERVICE_ROLE_KEY,
  Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY. NEVER echo/print/log the header value itself.
- Live arbitrary SQL: POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query, headers
  Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json, body {"query": "<sql>"}. Build
  JSON with a real encoder (python3 -c "import json; ..." to a temp file, curl --data-binary @file) -- do not
  hand-quote. Direct psql/pooler connections are known to fail password auth in this sandbox; use the
  Management API / REST exclusively.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county body
  {"p_county":"columbia"} -- your before/after proof. B passes ONLY in the 95-105%% band. F needs
  tier1_sold_amount AND sold_amount both non-null on the same row.
- Skills available via the Skill tool: "browser-use" and "firecrawl-browser" for real interactive browser
  sessions (JS execution, form fills, clicks). "firecrawl-scrape"/"firecrawl-search"/WebSearch for static
  content and general search.
- gh CLI is authenticated. Repo root is the current working directory, on main.

Hard rules (from the campaign brief and this repo's CLAUDE.md -- follow exactly):
- You own ONLY columbia. Never touch any other county's rows.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as independent/verified.
- Fail-loud invariant: if you find zero real data, report it as blocked/residual. NEVER fabricate a case
  number, sold amount, date, zone code, or party name, and NEVER reuse another row's/parcel's numbers as a
  stand-in. This campaign has zero tolerance for ghost-success (see the QUARANTINED Fort White zoning migration
  from a prior columbia session -- a guessed zone code that was correctly never applied).
- Every claim you return must be tagged VERIFIED (you ran the request and are pasting real output/evidence),
  UNTESTED, or INFERRED (say why).
- Do NOT attempt to solve or bypass any CAPTCHA/Turnstile challenge. If one blocks you, report it and stop
  that angle.
- Do not run public.gold_standard_loop(), gold_standard_certify(), or modify cron jobs 109/111/115 or any
  gold-standard-loop-* job.
`

phase('Research')
const LEADS = [
  {
    key: 'civitek_ocrs_columbia',
    prompt: `You are working Gold Standard shard-9, county columbia, inside the cli-anything-biddeed repo (already checked out, on main).\n\n${CASE_CONTEXT}\n\n${RECIPE}\n\nYOUR SPECIFIC JOB: pursue NEW GROUND #1 ONLY (civitekflorida.com/ocrs/county/12/index.xhtml, the anonymous public option, for columbia's 7 past-due cases listed above). Use the "browser-use" or "firecrawl-browser" Skill to drive the search form interactively -- do NOT use plain curl/WebFetch, this form requires real JS/form interaction. Test whether the search action itself hits a Turnstile challenge for county 12 specifically (do not assume it does just because bradford's county 04 did). If blocked, report exactly what you observed (network trace, HTTP codes, visible challenge). If NOT blocked, search each of the 7 case numbers and extract any sale-outcome docket entries.\n\nReturn { lead: "civitek_ocrs_columbia", found: boolean, turnstile_blocked: boolean, sale_results: array of {case_number, winning_bid, sale_date, outcome, evidence_text} for any case with real docket evidence, confidence: "VERIFIED"|"UNTESTED"|"INFERRED", notes: string }.`,
  },
  {
    key: 'fortwhite_zoning_recheck',
    prompt: `You are working Gold Standard shard-9, county columbia, inside the cli-anything-biddeed repo (already checked out, on main).\n\n${CASE_CONTEXT}\n\n${RECIPE}\n\nYOUR SPECIFIC JOB: pursue NEW GROUND #2 ONLY (Fort White zoning for parcel 33-6S-16-04023-000 / STRAP 04023000166S33). First, do a fresh discovery pass on gis11.cama.io's CURRENT MapServer layer list for the Columbia County Property Appraiser CAMA vendor (list services/layers, don't assume layer/21 zoning still exists -- it now 500s). If you find a live zoning layer under a new number/service, query it for this parcel's exact geometry/STRAP. Second, search for a genuine, current, free way to get Fort White's zoning designation for this parcel (Town of Fort White planning department contact info, any newer digitized zoning map, any GIS portal not yet checked). Do NOT write anything to parcel_zones or any table yourself -- research and report only; a fix will only be applied after this finding is adversarially verified.\n\nReturn { lead: "fortwhite_zoning_recheck", found: boolean, verified_zone_code: string|null, source_url: string|null, evidence: string, confidence: "VERIFIED"|"UNTESTED"|"INFERRED", notes: string }.`,
  },
  {
    key: 'taxdeed_recheck',
    prompt: `You are working Gold Standard shard-9, county columbia, inside the cli-anything-biddeed repo (already checked out, on main).\n\n${CASE_CONTEXT}\n\n${RECIPE}\n\nYOUR SPECIFIC JOB: pursue NEW GROUND #3 ONLY (letter A -- tax deed lane). Check web.archive.org's CDX API for columbiaclerk.com/tax-deed-sales/ for any snapshot newer than 2024-11-10. Separately, use the "browser-use" or "firecrawl-browser" Skill (a real browser, not curl) against columbiafl.realtaxlien.com and columbiaclerk.com/tax-deed-sales/ to see if JS execution clears whatever is producing the 403 for either site. If both remain hard-blocked even in a real browser, report that plainly as confirmed-dead -- do not force it or attempt any bypass. Do NOT insert any auction row yourself even if you find current data -- research and report only.\n\nReturn { lead: "taxdeed_recheck", found: boolean, current_listings: array|null, evidence: string, confidence: "VERIFIED"|"UNTESTED"|"INFERRED", notes: string }.`,
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
    },
    required: ['lead', 'found'],
    additionalProperties: true,
  },
})))

const positiveLeads = findings.filter(Boolean).filter(f => f.found)
log(`Research complete: ${findings.filter(Boolean).length}/${LEADS.length} leads returned, ${positiveLeads.length} claim a positive find.`)

phase('Verify')
let verifications = []
if (positiveLeads.length > 0) {
  verifications = await parallel(positiveLeads.map((f) => () => agent(
    `Independently verify this claimed Gold Standard columbia finding. You did NOT do this research -- be skeptical, your only job is to try to refute it.\n\n` +
    `Claimed finding: ${JSON.stringify(f)}\n\n${CASE_CONTEXT}\n\n${RECIPE}\n\n` +
    `Your job: re-visit the exact same source yourself, independently, right now (use "browser-use"/"firecrawl-browser" fresh -- do not just trust the pasted evidence). Confirm: (a) case/parcel/property identity matches exactly, ` +
    `(b) any sale amount, zone code, or listing is real primary-source content, not inferred/guessed/AVM-derived, (c) the source is genuinely independent (not PropertyOnion-derived). Default to refuted=true if you cannot independently reproduce the exact same evidence.\n\n` +
    `Return { lead: string, refuted: boolean, refutation_reason: string|null, confirmed_finding: object|null, survives: boolean }.`,
    {
      label: `verify:${f.lead}`,
      phase: 'Verify',
      schema: {
        type: 'object',
        properties: {
          lead: { type: 'string' },
          refuted: { type: 'boolean' },
          refutation_reason: {},
          confirmed_finding: {},
          survives: { type: 'boolean' },
        },
        required: ['lead', 'refuted', 'survives'],
      },
    }
  )))
}

return { findings, verifications }
