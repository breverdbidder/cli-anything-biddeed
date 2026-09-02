export const meta = {
  name: 'gold-standard-shard2-calhoun-okaloosa-charlotte-holmes-54730e95',
  description: 'Gold Standard shard-2 (dispatch 54730e95): charlotte D tax-deed-result recheck, okaloosa I FL-GIO card backfill, calhoun C light structural reconfirm, holmes B/C/D/F freshness recheck on 2 past-due parcels — ULTRALOOP fix + adversarial verify',
  phases: [
    { title: 'Fix' },
    { title: 'Verify' },
  ],
}

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    county: { type: 'string' },
    letter: { type: 'string' },
    wrote_changes: { type: 'boolean' },
    writes: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          table: { type: 'string' },
          filter: { type: 'string' },
          fields_set: { type: 'string' },
        },
        required: ['table', 'filter', 'fields_set'],
      },
    },
    evidence: { type: 'string', description: 'exact URLs fetched, HTTP status, and quoted content proving the claim' },
    claim_summary: { type: 'string' },
    honesty_tag: { type: 'string', enum: ['VERIFIED', 'UNTESTED', 'INFERRED', 'ASSUMED', 'UNKNOWN'] },
    blocked_reason: { type: 'string' },
  },
  required: ['county', 'letter', 'wrote_changes', 'claim_summary', 'honesty_tag'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    survived: { type: 'boolean' },
    reasoning: { type: 'string' },
  },
  required: ['survived', 'reasoning'],
}

const COMMON = `
Environment: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set in your shell env. Use PostgREST:
  Read:  curl -s "$SUPABASE_URL/rest/v1/<table>?<filters>&select=..." -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
  Write: curl -s -X PATCH "$SUPABASE_URL/rest/v1/<table>?<filters>" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "Content-Type: application/json" -H "Prefer: return=representation" -d '{...}'
Never use curl -v (dumps the auth header). Never echo/print the key value itself.
If a request returns {"code":"55P03",...} (lock timeout — other shards are writing concurrently), retry up to 4 times with a short sleep (5-10s) between attempts before giving up.
HARD GUARDRAILS: PropertyOnion is litmus-only, never a write source. Never fabricate a match/value/status. Fail loud — if the live source doesn't confirm something, report it blocked, do not guess. Never touch gadsden/broward/other counties' rows. Only touch the county+case_numbers named below.
Tag every claim VERIFIED (you personally observed the proof this session) / UNTESTED / INFERRED / ASSUMED / UNKNOWN.
`

async function fixCharlotteD() {
  return agent(`${COMMON}
You are working Charlotte County, criterion D (parity "matched_any" coverage), currently 293/309 = 94.8% FAIL (need >=95%, i.e. >=294/309 — just ONE more row flips it to PASS).

Live DB snapshot already pulled this session (do not re-derive, start from here):
- 10 Charlotte tax-deed cases from YESTERDAY's (2026-09-01) auction have zero tier1 data and parity_status=null: 26-0239, 26-0242, 26-0245, 26-0248, 26-0251, 26-0254, 26-0256, 26-0257, 26-0258, 26-0266. table multi_county_auctions, county=charlotte, sale_type=tax_deed.
- 1 rescheduled foreclosure case 26-0178 (orig auction_date 2026-08-25), tier1_sale_status='RESCHEDULED' as of 2026-08-25 — check if a new sale date has since appeared.
- A prior session (2026-08-31) established the precedent pattern for this exact county: when a live, authoritative sale-result source confirms SOLD, write parity_status='matched_clean', parity_source='tier1:charlotte_shard2_54730e95_<date>:<note>' (cite your own real source), tier1_sale_status='SOLD', tier1_authoritative=true, tier1_verified_at=<now, ISO8601 UTC>. When a source confirms CANCELED/REDEEMED, write parity_status='CLERK_SSOT_CANCELLED' instead (this counts toward matched_any but not matched_clean — that's fine for D).
- Charlotte's realforeclose-style foreclosure portal is known 403-blocked to this runner's egress (documented, don't re-try it for these tax-deed cases — tax deeds in Florida typically run on a SEPARATE platform, often realtaxdeed.com or the clerk's own tax-deed sales page. Find Charlotte's actual tax-deed result source live — check charlotteclerk.com, realtaxdeed.com/index.cfm?county=charlotte or similar, and Charlotte County Clerk's own tax deed sales results page. If ALL avenues are blocked/gated, say so plainly with the exact URLs and error codes — do not force a write.

Task:
1. Find and fetch Charlotte's real tax-deed sale RESULTS source (not just the calendar) live.
2. For each of the 10 case numbers above, determine if a real disposition (SOLD with amount, CANCELED, REDEEMED, or still pending) is posted. Match by case number.
3. For every case with a genuine, cited disposition, write the appropriate multi_county_auctions PATCH per the precedent pattern above (also set sold_amount if you found a real winning-bid dollar figure and the case is SOLD — this also helps F).
4. Separately check case 26-0178 for a new scheduled date; if a new authoritative status exists, apply the same pattern; otherwise leave untouched.
5. Do NOT touch any of the other 293 rows already counted (matched_clean/CLERK_SSOT_CANCELLED) — verify count is still 309 total, unchanged, after your writes.

Return via the required schema. In claim_summary state the before/after row counts you personally observed. wrote_changes=true only if you actually PATCHed at least one row with a real cited disposition.`, { phase: 'Fix', label: 'fix:charlotte:D', schema: FIX_SCHEMA })
}

async function fixOkaloosaI() {
  return agent(`${COMMON}
You are working Okaloosa County, criterion I (property card completeness: address+geo+value+zoned parcel), currently 79/85 = 92.9% FAIL (need >=95%, i.e. >=81/85 — 2 more rows flips it to PASS).

Live DB snapshot already pulled this session (start from here, table multi_county_auctions, county=okaloosa):
- 2024-CA-000470 (foreclosure, auction_date 2026-08-19, past-due): property_address, lat, lng, assessed_value, parcel_id ALL null. Prior fleet notes call this and its sibling "genuinely outside GIS coverage" / a likely true data ceiling — but has NOT been re-checked from the Okaloosa Property Appraiser's own site (only ArcGIS was tried before). Try https://www.okaloosapa.com (Okaloosa County Property Appraiser) name/case search or parcel search directly, live, this session, as the one new lever. If it's genuinely a dead end, say so plainly with URLs/errors — do not force a write.
- 2024-TDD-000089 (tax_deed, auction_date 2026-08-19, past-due): same all-null gap. Same treatment.
- 2025-CA-002286-F (auction_date 2026-09-02, TODAY): has property_address='1008 BAYSHORE DR' and lat/lng already, but assessed_value is null. parcel_id='17-3N-21-37000-001-0100'.
- 2025-CA-002286-F3 (parcel_id='30-2S-21-42840-00D-0311'): has partial address, missing lat/lng/assessed_value.
- 2025-CA-002286-F4 (parcel_id='17-3N-21-37000-001-0240'): has partial address, missing lat/lng/assessed_value.
- 2025-CA-002286-F5 (parcel_id='08-3N-21-37000-005-0011'): has partial address, missing lat/lng/assessed_value.

Task:
1. For the 4 "2025-CA-002286-F*" rows: query the FL GIO Statewide Cadastral ArcGIS FeatureServer (https://gis.floridados.gov or the FL GIO cadastral REST endpoint used fleet-wide — query by PARCELID, Okaloosa's CO_NO — verify the correct CO_NO for Okaloosa County live rather than assuming a number) for centroid latitude/longitude and JV (just/assessed value). This is the SAME reference pipeline used for Brevard/other counties in this fleet — real government cadastral data, not fabrication.
2. Write real lat/lng/assessed_value for whichever of the 4 rows the FeatureServer returns real data for. Do NOT guess or interpolate — only write what the API actually returns for that exact parcel_id.
3. For the 2 all-null rows, try the Okaloosa PA site as described above; only write if you get a real hit.
4. Getting even 2 of these 6 rows to full completeness (address+geo+value, they already have parcel_id except the first 2) flips I to PASS.

Return via the required schema, listing exactly which case_numbers you completed and which remain genuinely blocked with evidence.`, { phase: 'Fix', label: 'fix:okaloosa:I', schema: FIX_SCHEMA })
}

async function fixCalhounC() {
  return agent(`${COMMON}
You are working Calhoun County, criterion C (parity "matched_clean"), currently 8/9 = 88.9% FAIL.

This is a SINGLE-ROW block: case_number='546 OF 2024' (tax_deed), multi_county_auctions, county=calhoun, currently parity_status='CLERK_SSOT_CANCELLED', parity_source='calhoun_clerk_taxdeeds_wpapi_20260814_reconfirm_empty_feed'. This exact row/finding has ALREADY been independently re-investigated and reconfirmed as a genuine clerk-confirmed cancellation at least 3 separate times in prior sessions (dispatches d3ebfbe4, f6a6977d, 8389b490) — every time concluding it's a canon-level structural ceiling: matched_clean by design permanently excludes CLERK_SSOT_CANCELLED rows (same rule as Charlotte/Gadsden C), and with only 9 total rows, the math (8/9=88.9%) cannot reach 95% while this one row is excluded, and even a NEW matched-clean row added to the denominator makes it worse short-term (9/10=90%) — Calhoun needs the denominator to grow past ~20 auctions with only this 1 exclusion before 95% becomes arithmetically reachable at all, OR an owner-level canon change (tracked in GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md).

Given 3+ prior confirmations, DO NOT re-run the full investigation. Do ONLY a light freshness recheck:
1. Fetch calhounclerk.com's tax-deed listing/results live, confirm case '546 OF 2024' still shows as cancelled/no-sale (or check if a genuine sale outcome has since posted — that would be a materially new fact worth reporting).
2. Query multi_county_auctions for county=calhoun to confirm total row count is still 9 (i.e., no new auction has been ingested that would change the denominator math above). If the total has changed, recompute whether 95% is now arithmetically reachable and say so.
3. Do NOT write anything unless you find genuinely new information (e.g., the case actually sold, or the denominator changed materially). If nothing changed, report wrote_changes=false and state this is a reconfirmed structural ceiling (4th+ time), not a new session's fresh finding.

Return via the required schema.`, { phase: 'Fix', label: 'fix:calhoun:C', schema: FIX_SCHEMA })
}

async function fixHolmesBCDF() {
  return agent(`${COMMON}
You are working Holmes County, criteria B (verified independent outcomes, currently null/0 closed_sold=0 FAIL), C (68.8%, matched_clean=11/16 FAIL), D (68.8%, matched_any=11/16 FAIL), F (null, tier1_sold=0/0 FAIL).

CRITICAL CONTEXT — read before doing anything: Holmes B/C/D/F has been independently investigated and reconfirmed a genuine structural dead end in 18+ prior sessions (most recently dispatch 4cb27213, 2026-08-25). ALL of the following levers are EXHAUSTED — do NOT re-attempt them, they have already failed repeatedly with fresh live re-checks each time: holmesclerk.com site search by case number or defendant surname (tried, zero results every time), holmescountytaxcollector.com (zero tax-deed hyperlinks exist on the site), myfloridacounty.com/orisearch and civitekflorida.com/ocrs (Cloudflare Turnstile-gated, out of bounds per hard rule against bypassing CAPTCHA), tax-deeds/lands-available-for-taxes pages (both self-report "no sales at this time").

The ONE genuinely new thing to check this session: two Holmes foreclosure rows had auction_date=2026-08-27 with auction_status='scheduled' as of the last check (2026-08-25, BEFORE that date). Today is 2026-09-02 — 6 days AFTER that scheduled sale date. This is a fresh opportunity that did not exist in any prior session:
- case_number='PARCEL-0531.03-003-028-007.000', parcel_id='0531.03-003-028-007.000'
- case_number='HOLMES-LEGACY-3ca8afb6-fe6d-4c71-bf8a-51df49eebfc3', parcel_id='0936.01-004-00C-008.000'

Task:
1. Fetch https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/ live (and any results/archive page it links to) and check specifically whether either of these 2 parcel IDs now shows a real sale disposition (sold amount, cancelled, redeemed) now that their sale date has passed.
2. If you find a genuine disposition with a real dollar amount for either: write to multi_county_auctions (sold_amount, auction_status) AND insert an independent-source row to foreclosure_outcomes (data_source citing 'holmes_clerk_direct:shard2_54730e95_<date>', outcome, winning_bid) — this is a genuinely new INDEPENDENT closed-sale outcome, which moves B and F together (and C/D if the case_number matches cleanly).
3. If the page still shows no disposition (case still pending/rescheduled, or page unchanged), report that plainly — do not force a write. This is expected and acceptable per BLANK > WRONG.
4. Do not touch case_number='HOLMES-LEGACY-123a1bd5-...' (the permanently-unmatchable placeholder-case-number row) or any of the TD#* tax-deed cases (auction dates 2026-07-xx, already exhaustively checked) — those are correctly documented as closed dead ends, not in scope for this session.

Return via the required schema honestly — a "still blocked" result for this letter is a legitimate, valuable outcome, not a failure.`, { phase: 'Fix', label: 'fix:holmes:BCDF', schema: FIX_SCHEMA })
}

const TASKS = [
  { key: 'charlotte:D', run: fixCharlotteD },
  { key: 'okaloosa:I', run: fixOkaloosaI },
  { key: 'calhoun:C', run: fixCalhounC },
  { key: 'holmes:BCDF', run: fixHolmesBCDF },
]

const results = await pipeline(
  TASKS,
  t => t.run(),
  async (fixResult, t) => {
    if (!fixResult) return { task: t.key, fix: null, verify: null }
    if (!fixResult.wrote_changes) {
      log(`${t.key}: no write claimed (${fixResult.honesty_tag}) — skipping verify`)
      return { task: t.key, fix: fixResult, verify: null }
    }
    const verify = await agent(`${COMMON}
You are an independent adversarial refuter. You did NOT write the following claim — your ONLY job is to try to break it. Default to refuted=false only if you can independently re-derive the same conclusion using your own fresh queries/fetches (different from just trusting the claimant's report).

CLAIM to verify (county=${t.key.split(':')[0]}, letter(s)=${t.key.split(':')[1]}):
${JSON.stringify(fixResult, null, 2)}

Independently:
1. Re-query the exact tables/rows named in "writes" via PostgREST live — confirm the fields actually changed and match what was claimed.
2. Re-fetch the exact URL(s) cited in "evidence" yourself, live — confirm the cited content is real and actually supports the claim (not misread, not stale, not a different case number).
3. Check for fabrication red flags: does the parity_source/data_source string cite a real, checkable source? Is there any unexplained mismatch between the claimed evidence and what you independently observe?
4. Re-run SELECT public.pencil_dod_evaluate_county('${t.key.split(':')[0]}') via the RPC endpoint (retry on 55P03 lock timeout) and confirm the relevant letter's metric actually moved in the direction claimed.

Report survived=true only if your OWN independent re-derivation confirms the claim. Report survived=false if anything doesn't check out, with specifics.`, { phase: 'Verify', label: `verify:${t.key}`, schema: VERIFY_SCHEMA })
    return { task: t.key, fix: fixResult, verify }
  }
)

return results
