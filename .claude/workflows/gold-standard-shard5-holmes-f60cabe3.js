export const meta = {
  name: 'gold-standard-holmes-f60cabe3',
  description: 'Holmes County B/C/D/F final-avenue sweep + adversarial verify (dispatch f60cabe3)',
  phases: [
    { title: 'Discover' },
    { title: 'Verify' },
  ],
}

const BLOCKED_CASES = [
  { case_number: 'TD#2023-225', parcel_id: '0811.04-001-000-041.000', address: 'Bonifay, FL 32425' },
  { case_number: 'TD#2023-496', parcel_id: '1316.00-000-000-022.000', address: 'Bonifay, FL 32425' },
  { case_number: 'TD#2023-185', parcel_id: '0607.00-000-000-005.000', address: 'Bonifay, FL 32425' },
  { case_number: 'TD#2023-584', parcel_id: '1327.04-000-000-002.000', address: 'Bonifay, FL 32425' },
  { case_number: 'TD#2020-589', parcel_id: '1327.04-001-002-096.000', address: 'Bonifay, FL 32425' },
]

const CONTEXT = `
You are working GOLD STANDARD dispatch f60cabe3-6c9e-4d95-aaf1-4a82aa983eea for Holmes County, FL
(a small rural panhandle county in the cli-anything-biddeed foreclosure/tax-deed intelligence platform).
Holmes is at 6/10 on the pencil_dod canon (A,E,G,H,I,J pass; B,C,D,F fail).

B/F fail because zero of 13 multi_county_auctions rows have sold_amount populated (closed_sold=0),
so the ratio is undefined (metric=null). C/D fail because 5 of 13 rows (the blocked cases below) have
parity_status=null -- they no longer appear on the live holmesclerk.com listing (rolled off / sale
already happened) and no independent source has confirmed a disposition for them.

Blocked cases (all 5 need EITHER a real sold_amount+data_source written to tax_deed_outcomes/
foreclosure_outcomes with an INDEPENDENT (non-PropertyOnion, non-"*promote*") data_source, OR a
parity_status='matched_clean'/'matched_divergent' with parity_source starting 'tier1'):
${JSON.stringify(BLOCKED_CASES, null, 2)}

EXHAUSTIVELY CONFIRMED DEAD ENDS -- DO NOT RE-ATTEMPT, DO NOT REPORT THESE AS "NEW":
- holmesclerk.com/courts/foreclosures-tax-deeds/{foreclosures,tax-deeds,lands-available-for-taxes}/ --
  forward-looking notice board only, explicitly states "there are no sales scheduled at this time",
  zero results/disposition/archive page exists anywhere on the site.
- myfloridacounty.com/orisearch/30 (Holmes Official Records Index search) -- Cloudflare Turnstile wall
  on the search POST (sitekey 0x4AAAAAAA64PTBePmuGbrkR), confirmed dead live as recently as 2026-07-31.
- civitekflorida.com/ocrs/county/30 (Civitek OCRS, linked from holmesclerk.com's own "SEARCH COURT
  RECORDS" button) -- also Turnstile-gated (sitekey 0x4AAAAAAAR0Af-5MfzdbO3p), and even if reachable its
  Case Search tab requires a Year+CourtType+Sequence# circuit-civil schema that does not fit TD# tax-deed
  identifiers anyway.
- qpublic.net/holmes and qpublic.schneidercorp.com -- Cloudflare 403 / JS challenge.
- holmescountytaxcollector.com/Property/search -- reachable (not gated), but only returns tax-roll
  STATUS codes (e.g. 'TD'=pending application), no disposition/dollar/winning-bidder field.
- GovEase.com -- generic marketing shell for all paths tried, no evidence Holmes uses it as an auction
  vendor (no outbound link from holmesclerk.com to any 3rd-party vendor at all).
- Firecrawl (map/scrape/browser) -- account confirmed at ZERO credits again just now (2026-08-01,
  fresh HTTP check, "Insufficient credits" on a trivial /v1/scrape of example.com). Any plan requiring
  Firecrawl is a dead end this session -- do not attempt it, do not assume credits refreshed.
- floridapublicnotices.com (checked 2026-08-01 via its HAL-JSON API) -- only publishes the F.S. 197.512
  PRE-SALE application notice, never a post-sale-result notice. Confirmed no post-sale notice exists for
  any of the 5 blocked cases.
- archive.org Wayback Machine -- zero captures of holmesclerk.com after 2026-03-14 (predates all 5 sale
  dates) and zero captures of any XHR/JSON API endpoint ever for this domain (client-side-only Vue SPA).
- qpublic.net/fl/holmes/ (URL variant, checked 2026-08-01) -- also Cloudflare-gated.
- clerkecertify.com (checked 2026-08-01) -- receipt/QR-code authenticity verifier only, cannot search by
  parcel/case, cannot surface unknown dispositions.

HARD RULE: if you hit a CAPTCHA, Cloudflare Turnstile, "verify you are human" challenge, or any other
active bot-detection wall on ANY site (known or newly discovered), DO NOT attempt to solve, bypass, or
work around it in any way (no third-party solver, no headless-browser stealth tricks, no manual
token-fetch). Simply record it as blocked and move on. This is a hard ethical boundary, not a
resourcing constraint -- treat it exactly like a dead end.

HARD RULE: never fabricate a sold_amount, parcel match, or disposition. BLANK > WRONG. If you find
nothing verifiable, say so plainly -- that is a valid and expected outcome (12+ prior sessions over 3
weeks reached exactly this conclusion).

DB access: Supabase Management API at https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
via POST with {"query": "<sql>"} body, header "Authorization: Bearer $SUPABASE_ACCESS_TOKEN". REST API
at $SUPABASE_URL/rest/v1/<table> with apikey + Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY headers
for row-level reads/writes. Both env vars are available in your shell.
`

phase('Discover')
const findings = await parallel([
  () => agent(`${CONTEXT}

YOUR TASK: given every listed dead end above is now confirmed exhausted, look for a genuinely NEW avenue
not listed above -- e.g. a Holmes County Commission meeting-minutes archive (tax deed sale results are
sometimes read into the record), a newspaper legal-notice archive distinct from floridapublicnotices.com,
or any other public disposition source for the 5 blocked cases. Do not re-attempt anything in the dead-end
list. If you can find no genuinely new avenue to try, say so plainly and stop -- do not pad the report.

Try real HTTP requests (curl-equivalent). Report exactly what you found for each of the 5 cases: either
a genuine disposition (sold, cancelled, redeemed) with a source URL and evidence, or "nothing found" with
the specific URLs/queries you tried. Do not write anything to the database yet -- that happens in the
Verify phase after adversarial review. Return your findings as structured text: one paragraph per case
number, and an overall found_new_lever true/false verdict.`, { phase: 'Discover', label: 'new-avenue-sweep' }),

  () => agent(`${CONTEXT}

YOUR TASK: re-verify Firecrawl credit status live (fresh HTTP check, not cached) and, if credits are
available, attempt a Firecrawl-rendered fetch of myfloridacounty.com/orisearch/30 or
civitekflorida.com/ocrs/county/30 for the 5 blocked cases -- JS rendering via a paid service is a
different technique than a bare curl and might legitimately get further (this is NOT solving a CAPTCHA,
it's using a different HTTP client; if it still hits an active Turnstile/CAPTCHA challenge, stop
immediately per the hard rule above, do not attempt to solve it). If Firecrawl is still at zero credits,
say so and stop -- do not pad the report.

Return structured findings with a found_new_lever true/false verdict. Do not write to the database.`, { phase: 'Discover', label: 'firecrawl-credit-recheck' }),
])

log(`Discover phase complete. found_new_lever signals: ${findings.filter(Boolean).map(f => (f.match(/found_new_lever[:\s]*(true|false)/i) || [,'unknown'])[1]).join(', ')}`)

phase('Verify')
const hasNewLever = findings.filter(Boolean).some(f => /found_new_lever[:\s]*true/i.test(f))

let verifyResults = []
if (hasNewLever) {
  verifyResults = await parallel(findings.filter(Boolean).map((f, i) => () =>
    agent(`${CONTEXT}

A discovery agent produced this finding for Holmes County B/C/D/F research. Your ONLY job is to
adversarially try to REFUTE it: re-fetch the exact same URLs/sources independently from scratch, check
whether the claimed evidence actually supports a real, usable database write (a genuine sold_amount from
an independent non-PropertyOnion source, or a genuine case-number/parcel match). Default to refuted=true
if you cannot independently reproduce the evidence or if it's ambiguous/low-confidence. Do not trust the
finding's prose -- verify the underlying facts yourself.

FINDING TO VERIFY:
${f}

Return your verdict as refuted=true/false with your own independent evidence.`, { phase: 'Verify', label: `refute-${i}` })
  ))
} else {
  log('No new lever found -- skipping Verify (nothing positive to refute).')
}

return { findings, hasNewLever, verifyResults }

// NOTE for the next session running this file: this is a template for the NEXT firing on this exact
// gap. Before re-running, update the dead-end list above with anything this run's agents newly ruled
// out (the two Discover prompts are already scoped to avoid re-treading the 2026-08-01 dead-end list).
// If two consecutive runs both find found_new_lever=false with no new avenue even attempted (not just
// re-confirmed), treat holmes B/C/D/F as fully exhausted and stop scheduling autonomous sessions against
// it until a human-in-the-loop step (Firecrawl credits funded, or manual courthouse contact) changes the
// facts on the ground.
