export const meta = {
  name: 'gold-standard-shard2-charlotte-stlucie-okaloosa-taylor-9160a21e',
  description: 'Gold Standard shard-2 (dispatch 9160a21e): taylor E/C/D/I/J parcel-id fix + B/F outcome discovery, okaloosa C/D/I parity-stamp for 4 fresh consolidated cases, charlotte+st_lucie C structural-ceiling reconfirm — ULTRALOOP diagnose/fix/adversarial-verify',
  phases: [
    { title: 'Fix' },
    { title: 'Verify' },
  ],
}

const COMMON_PREAMBLE = `
You are working the BidDeed.AI Gold Standard campaign, dispatch_id=9160a21e-3e88-4f96-b88c-19e8692e24cd.
This is a NON-INTERACTIVE session — nobody will read questions you print. Execute, don't ask.

DB ACCESS: direct psql is DOWN for this session (known, documented constraint — do not waste time
re-diagnosing it). Use Supabase PostgREST instead. Env vars already set in your shell:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, REALFORECLOSE_EMAIL, REALFORECLOSE_PASSWORD, REALFORECLOSE_USERNAME
Read pattern:
  curl -s "$SUPABASE_URL/rest/v1/multi_county_auctions?county=eq.<c>&select=*" \\
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
Write pattern (PATCH by id):
  curl -s -X PATCH "$SUPABASE_URL/rest/v1/multi_county_auctions?id=eq.<uuid>" \\
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \\
    -H "Content-Type: application/json" -H "Prefer: return=representation" \\
    -d '{"parcel_id":"...", "parity_status":"...", ...}'
Verify pattern (per-county letter scoreboard, run BEFORE and AFTER any write):
  curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county" \\
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \\
    -H "Content-Type: application/json" -d '{"p_county":"<c>"}'
If PostgREST returns a transient 521/502, retry once after a few seconds before concluding it's down.

GUARDRAILS (hard, non-negotiable):
- NEVER fabricate parcel_id, sold_amount, winning_bidder, or parity_status. Every write must trace to a
  named, live, real source you actually fetched this session (clerk site, county GIS, property appraiser,
  recorded court document). If you can't verify, leave the field null and report blocked=true with the
  reason — BLANK > WRONG.
- PropertyOnion (PO / po_* fields) is litmus ONLY — never write PO-derived values into parity_status,
  parcel_id, sold_amount, or winning_bidder.
- Do not touch pencil_dod_evaluate_county, cron jobs 109/111/115, or the gold-standard-loop-* scoring jobs.
- Tag every claim VERIFIED (you ran the query/fetch yourself, evidence attached) / UNTESTED / INFERRED.
- Do not modify any other county's rows. Do not modify multi_county_auctions.county for any row without
  overwhelming evidence — if you find a miscategorized row, report it, don't silently move it.

Return your findings via the required structured schema. Be honest: blocked=true with a clear reason is a
GOOD outcome if the true blocker is a data ceiling, not a failure to report.
`

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    county: { type: 'string' },
    letters_targeted: { type: 'array', items: { type: 'string' } },
    claim: { type: 'string', description: 'One sentence: what changed and why it should move the metric' },
    writes_made: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          table: { type: 'string' }, row_id: { type: 'string' },
          fields_changed: { type: 'string' }, source_evidence: { type: 'string' },
        },
      },
    },
    before_metric_json: { type: 'string' },
    after_metric_json: { type: 'string' },
    confidence: { type: 'string', enum: ['VERIFIED', 'UNTESTED', 'INFERRED'] },
    blocked: { type: 'boolean' },
    blocked_reason: { type: 'string' },
  },
  required: ['county', 'letters_targeted', 'claim', 'confidence', 'blocked'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    survived: { type: 'boolean' },
    reasoning: { type: 'string' },
    live_recheck_metric: { type: 'string', description: 'Result of you independently re-running pencil_dod_evaluate_county' },
    fabrication_risk_found: { type: 'boolean' },
  },
  required: ['survived', 'reasoning'],
}

const streams = [
  {
    key: 'taylor_e_parcel_fix',
    label: 'taylor:E/C/D/I/J',
    prompt: COMMON_PREAMBLE + `
TASK: taylor county, row id 3582a069-131f-4f87-9cbd-20a3fedbde5e, case_number "25-245 CA", is the ONLY
row in taylor with parity_status=null AND parcel_id=null (auctions_total=14, this row is the sole gap
behind C=92.9%, D=92.9%, E=92.9%, I=92.9%, J=92.9% — fixing this one row is expected to flip all five to
100% since taylor's I/J evaluator logic is structurally gated on E's parcel linkage per project docs).

ALREADY ESTABLISHED THIS SESSION (do not re-derive, just verify and apply):
- Fetched https://taylorclerk.com/uploads/2026/08/25-245-CA.pdf (the case's own Notice of Foreclosure
  Sale + recorded Final Judgment, Book 945 Page 617-620, Instrument 260004523, recorded 08/27/2026,
  Circuit Court Case No. 25000245CAAXMX). It states:
    TAX ID: 09912-001
    Legal description: THE SOUTH 85 FEET OF THE NORTH 1/2 OF LOTS 1 AND 2, BLOCK 68, STEINHATCHEE
      SUBDIVISION, PLAT BOOK 1 PAGE 26, Taylor County FL
    Plaintiff: PennyMac Loan Services, LLC   Defendant: Christopher Lasiter
    Total judgment: $394,895.56 (already matches our judgment_amount/opening_bid on file — good sign
      the row is otherwise correctly scraped, only parcel_id/parity/geo are missing)
    Sale date: 2026-10-01, 11:00 AM, at the courthouse, 108 N Jefferson St, Perry FL 32347

YOUR JOB:
1. Re-fetch the PDF yourself to independently confirm TAX ID 09912-001 (don't just trust this brief).
2. Try to confirm parcel 09912-001 exists via Taylor County Property Appraiser (search for their site —
   likely taylorpa.net or similar; try their GIS/search) or the FL GIO statewide cadastral API
   (scripts/ingest_county.py has the FL GIO pattern if useful — Taylor co_no lookup) for
   address/lat/long/assessed_value. This is a bonus enrichment, not a blocker — if the county appraiser
   site is unreachable, the tax ID from the recorded Final Judgment is ALREADY sufficient authoritative
   evidence for parcel_id; proceed to step 3 either way.
3. PATCH the row (id 3582a069-131f-4f87-9cbd-20a3fedbde5e): set parcel_id='09912-001', parity_status
   to whatever value correctly represents "matched via authoritative recorded court document" per the
   existing convention other taylor rows use (look at the other 13 taylor rows' parity_status values —
   they use 'PARITY_OK' and 'matched_clean' — pick consistently with how similarly-sourced rows in this
   county are classified; do NOT invent a new status string), parity_source describing the source (e.g.
   'clerk_recorded_judgment'), owner_name='Christopher Lasiter', property_address if you found a real
   one via appraiser/GIO, and any lat/long/assessed_value you verified.
   IMPORTANT: also correct the mislabeled 'plaintiff' field if it currently holds the defendant's name
   instead of PennyMac Loan Services — check first, fix only if genuinely wrong.
4. Run pencil_dod_evaluate_county for taylor BEFORE (already known from this session's brief) and AFTER
   your write. Report both JSON blobs verbatim.
5. If parcel 09912-001 cannot be independently corroborated by any second source, you may still apply the
   fix (the recorded Final Judgment is itself an authoritative legal record, re-fetched by you), but set
   confidence to VERIFIED with source_evidence citing the PDF specifically, not INFERRED.
`,
  },
  {
    key: 'taylor_bf_outcomes',
    label: 'taylor:B/F',
    prompt: COMMON_PREAMBLE + `
TASK: taylor county B (verified independent outcomes) and F (tier1 sold-amount) are both null/0 —
0 closed_sold, 0 verified — even though 10 of taylor's 14 auction rows have auction_date already in the
past relative to today (2026-09-01): foreclosure cases 25-217 CA (2026-07-30), 25-196 CA (2026-07-23),
25-218 CA (2026-07-16), 25-014 CA (2026-08-11), 26-042 CA (2026-08-27), 25-210 CA (2026-08-27); tax-deed
cases TDA 26-026 (2026-07-20), TDA 26-028 (2026-07-20), TDA 26-032 (2026-08-17), TDA 26-031 (2026-08-17).
None of these are marked closed/sold yet — a real sale outcome (Certificate of Title recorded, or tax
deed issued, with sale/winning-bid amount) needs to be discovered from an INDEPENDENT source (not
PropertyOnion) for canon compliance.

ALREADY CHECKED THIS SESSION (don't repeat):
- taylorclerk.com/departments/foreclosure-sales/ and /departments/tax-deeds/ (the live WordPress feeds
  scripts/clerk_ssot/parsers/taylor.py uses) only show CURRENT/UPCOMING listings — past-due cases fall
  off the list entirely, no historical archive there. The tax-deeds Vue widget is currently empty (no
  <tax-deed-sales> element rendered) — likely because zero tax deeds are CURRENTLY scheduled, not a
  scraper bug.
- https://pubrecords.taylorclerk.com/PublicInquiry/Search.aspx?Type=Name — likely the Taylor Clerk's
  Official Records index (Certificates of Title get recorded there) — returned HTTP 403 to a plain curl
  fetch (probable bot-protection / requires a real browser session or specific headers).
- https://taylorclerk.com/departments/tax-deeds-surplus/ exists (a "surplus funds" list, which would
  only have entries for tax deeds that already SOLD for more than owed) but was empty/inconclusive on a
  raw-HTML grep — worth a real look, it's structurally the kind of page that only lists CLOSED sales.

YOUR JOB — try these in order, stop as soon as one works and gives you real per-case sale results:
1. Retry pubrecords.taylorclerk.com with the WebFetch tool or the firecrawl-scrape skill (both handle
   JS/bot-protected pages better than raw curl) — search by defendant name or case number for each of
   the 10 cases above, looking for a recorded Certificate of Title (foreclosure) or Tax Deed (tax sale)
   with a sale/consideration amount.
2. Check https://taylorclerk.com/departments/tax-deeds-surplus/ properly (render it, don't just grep raw
   HTML) for the 4 TDA cases — surplus entries imply the deed sold above the minimum bid, which is itself
   evidence of a closed sale with an amount.
3. Try myfloridacounty.com/official_records/ (linked from taylorclerk.com) — many small FL clerks
   contract their official records index to this statewide vendor.
4. As a last resort, try the browser-use skill to drive pubrecords.taylorclerk.com interactively.
5. For EACH case where you find a real recorded outcome: PATCH the multi_county_auctions row with
   sold_amount (or tier1_sold_amount if that's the convention other verified taylor rows use — check),
   tier1_sale_status, winning_bidder if disclosed, and a data_source string identifying this as an
   independent clerk-recorded outcome (NOT PropertyOnion-derived) — follow the B canon requirement that
   the outcome source be INDEPENDENT.
6. If genuinely blocked (all sources 403/unreachable even via WebFetch/firecrawl/browser-use), report
   blocked=true with exactly which URLs and error codes you hit — this is an acceptable, honest outcome
   given taylor's tiny population; do not fabricate anything to force a pass.
7. Run pencil_dod_evaluate_county for taylor before/after and report both verbatim, even if you made zero
   writes.
`,
  },
  {
    key: 'okaloosa_cdi_fix',
    label: 'okaloosa:C/D/I',
    prompt: COMMON_PREAMBLE + `
TASK: okaloosa county C=92.9%, D=92.9%, I=92.9% (all three fail on the exact same 6 rows with
parity_status=null, out of 85 total auctions).

ALREADY ESTABLISHED THIS SESSION (verified via live query + prior scripts in this repo):
- 2 rows are KNOWN DEAD ENDS, already investigated in a prior session (scripts/okaloosa_parcel_gis_enrich.py
  docstring, 2026-07-19): case '2024-CA-000470' (id 86fd8a0f-53ff-4ccb-9104-90069762e466, auction_date
  2026-08-19, foreclosure) has NO property_address to match on at all; case '2024-TDD-000089' (id
  46039562-77f6-4429-883a-4410d2882cb2, same auction_date, tax_deed) has no parcel_id/APN to match on.
  Both are past-due now. Spend at most 15 minutes independently re-confirming these are still genuinely
  unmatchable (try okgis.myokaloosa.com ArcGIS parcel layer by owner-name search if the case data has a
  name; try the okaloosa clerk site for the case number itself) — if still dead, report blocked=true for
  these two specifically and move on. Do NOT force a match.
- The other 4 rows are a HIGH-VALUE, LIKELY-EASY fix: a single consolidated lawsuit (base case
  2025-CA-002286) split into 4 sub-cases -F, -F3, -F4, -F5, auction_date 2026-09-02 (imminent — 1 day out
  from today 2026-09-01), each ALREADY has a parcel_id and opening_bid=100.0 populated (scraped from a
  live source already) but parity_status is null (never ran through the clerk parity/tier1 pipeline):
    2025-CA-002286-F  (id 7613dcbe-c0b7-4292-b254-d511142f2912) parcel 17-3N-21-37000-001-0100, "Lot 50 Delaware PLANTATIONS SUBDIVISION"
    2025-CA-002286-F3 (id a30d6c61-6a36-4771-aa6d-c90c4f3df1c0) parcel 30-2S-21-42840-00D-0311, "Condominium Unit D-311, SUMMER BREEZE"
    2025-CA-002286-F4 (id c67ba672-d8c2-43a8-b557-7f7e3ac3cdbb) parcel 17-3N-21-37000-001-0240, "Lot 24 UNRECORDED DELAWARE PLANTATION SUBDIVISION PHASE TWO"
    2025-CA-002286-F5 (id e8da14d5-984c-45fd-872e-24dac7ee7cf8) parcel 08-3N-21-37000-005-0011, legal
      description text reads "...WALTON COUNTY, FLORIDA" — FLAG: this may be a data quality issue (wrong
      county assignment, or a genuine cross-referenced legal description quirk in the original filing).
      INVESTIGATE THIS SPECIFICALLY before writing anything for -F5: pull the actual case record/notice
      for 2025-CA-002286-F5 (okaloosa.realforeclose.com using REALFORECLOSE_EMAIL/PASSWORD env creds,
      same login flow as scripts/okaloosa_stub_case_lookup.py) and confirm independently whether this
      case is really an Okaloosa County circuit court case (case numbers are county-specific in FL) with
      a parcel that happens to sit near/reference Walton County in its legal description, vs. a genuine
      miscategorization that should not be in our okaloosa table at all. Report your finding either way;
      do not silently change county on this row without being certain.

YOUR JOB:
1. Use REALFORECLOSE_EMAIL/REALFORECLOSE_PASSWORD (already in env) with the login+FNC=LOAD/FNC=UPDATE
   pattern from scripts/okaloosa_stub_case_lookup.py or scripts/realauction_winner_harvest.py to pull
   live case data for all 4 -F/-F3/-F4/-F5 cases from okaloosa.realforeclose.com, auction 09/02/2026.
2. For each of the 4, if the live clerk record confirms the case/parcel exists and matches what's on file,
   PATCH parity_status appropriately (use the same status other okaloosa rows carry for a clean clerk
   match — check a few passing okaloosa rows' parity_status/parity_source values first and stay
   consistent), set parity_source, parity_checked_at semantics as the schema requires.
3. Resolve the -F5 Walton-County flag per the investigation above before writing it.
4. For the 2 known dead-end rows, do a light re-check only; report blocked=true if still unmatchable.
5. Run pencil_dod_evaluate_county for okaloosa before/after, report both verbatim.
`,
  },
  {
    key: 'charlotte_c_ceiling_reconfirm',
    label: 'charlotte:C',
    prompt: COMMON_PREAMBLE + `
TASK: charlotte county C=58.8% (matched_clean=180 of 306), the ONLY failing letter (9/10). This has
ALREADY been investigated and confirmed as a structural, non-fixable ceiling TWICE: once 2026-08-16-ish
and again 2026-08-29 (scripts/charlotte_c_run20260829_systemic_investigation_ceiling_reconfirmed.py in
this repo — read it in full first). Finding: the entire C-gap is CLERK_SSOT_CANCELLED rows (currently 113
of 306, up from 112 three days ago — genuinely cancelled foreclosure sales, correctly excluded from C's
passing set by the evaluator's own design, which deliberately treats CLERK_SSOT_CANCELLED as matched_any
(D) but not matched_clean (C)). This is a canon-level tension (documented in
GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md, read that too), not a per-county bug,
and per that finding's own recommendation this needs OWNER sign-off on a canon change (Option A/B/C), not
continued per-county re-investigation burning session budget.

YOUR JOB (light-touch, do NOT attempt to "fix" C — there is no fix available at the county level):
1. Confirm current live count: query charlotte rows grouped by parity_status, confirm CLERK_SSOT_CANCELLED
   count and the delta since the Aug 29 investigation (112 -> current). If the count grew, spot-check the
   1-2 NEWEST such rows (highest created_at/updated_at) against charlotte.realforeclose.com or the
   Charlotte Clerk's own source to confirm they really are cancelled (not a new bug pattern) — same
   verification method the Aug 29 script used. Do not spot-check more than 3 rows; this is a freshness
   spot-check, not a full re-audit.
2. Make ZERO writes to parity_status/matched_clean-affecting fields — this letter has no legitimate lever
   at the county level. If your spot-check finds something that ISN'T genuinely cancelled (a real bug),
   that changes everything — investigate further and fix that specific row, but this is not expected.
3. Report your claim as: "C remains structurally capped, reconfirmed" with confidence VERIFIED (you
   re-checked live), blocked=true, blocked_reason citing the canon tension and the prior investigation.
4. Run pencil_dod_evaluate_county for charlotte, report the JSON verbatim (before==after expected).
`,
  },
  {
    key: 'stlucie_c_ceiling_reconfirm',
    label: 'st_lucie:C',
    prompt: COMMON_PREAMBLE + `
TASK: st_lucie county C=80.7% (matched_clean=201 of 249), the ONLY failing letter (9/10). This has ALREADY
been investigated and confirmed as a structural, non-fixable ceiling: scripts/gold_standard_shard1_6a9e3c3a_stlucie_c_parity_fix.py
(2026-08-16, read it in full first) found the C-gap is entirely CLERK_SSOT_CANCELLED rows (35 at that time,
now 47 — up notably) + 1 matched_divergent multi-parcel case (2025CA001832, left untouched pending new
evidence per an even earlier 2026-08-06 session). Same canon-level tension documented in
GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md as charlotte's — read that file too.

The CLERK_SSOT_CANCELLED count growing from 35 to 47 (35% increase) since the last check is a genuine
delta worth a real look, not just charlotte's incremental +1 — verify these are still correct.

YOUR JOB (light-touch, do NOT attempt to change canon or force a match):
1. Confirm current live parity_status breakdown for st_lucie (matched_clean, PARITY_OK,
   CLERK_SSOT_CANCELLED, matched_divergent counts). Compare to the 2026-08-16 baseline (matched_clean=123
   tier1 + 62 PARITY_OK=185, CLERK_SSOT_CANCELLED=35, matched_divergent=1, total=221 then; now total=249).
2. Spot-check up to 5 of the NEWEST CLERK_SSOT_CANCELLED rows (by created_at/updated_at) against
   acclaimweb.stlucieclerk.gov/TributeWeb/ (the St Lucie Clerk's own tax-deed system,
   scripts/clerk_ssot/parsers/st_lucie.py uses this) or the St Lucie foreclosure clerk source, to confirm
   they're genuinely cancelled and this isn't a new over-flagging bug given the notable growth.
3. Separately, take one real look at case 2025CA001832 (the matched_divergent multi-parcel case) with
   fresh eyes — it's the one row in this county that was EXPLICITLY left open pending new evidence, not
   confirmed dead. If you can find new evidence resolving it cleanly, that's a legitimate 1-row C fix.
4. Make writes ONLY if you find (a) a genuinely misclassified CLERK_SSOT_CANCELLED row, or (b) new
   evidence resolving 2025CA001832. Otherwise zero writes.
5. Report claim, confidence, blocked status honestly. Run pencil_dod_evaluate_county before/after,
   report verbatim.
`,
  },
]

phase('Fix')
const fixResults = await parallel(streams.map((s) => () =>
  agent(s.prompt, { label: s.label, phase: 'Fix', schema: FIX_SCHEMA })
))

log(`Fix phase complete: ${fixResults.filter(Boolean).length}/${streams.length} streams returned`)

phase('Verify')
const verified = await parallel(
  fixResults.map((r, i) => {
    if (!r) return () => Promise.resolve(null)
    return () =>
      agent(
        `Adversarially verify this Gold Standard campaign claim for county "${r.county}", letters ${JSON.stringify(r.letters_targeted)}.

CLAIM: ${r.claim}
CONFIDENCE TAGGED BY CLAIMANT: ${r.confidence}
BLOCKED: ${r.blocked} ${r.blocked_reason || ''}
WRITES CLAIMED: ${JSON.stringify(r.writes_made || [])}
BEFORE METRIC: ${r.before_metric_json || 'not provided'}
AFTER METRIC: ${r.after_metric_json || 'not provided'}

Your ONLY goal is to try to REFUTE this claim. You did not write this claim and have no stake in it being
true. Using the same Supabase PostgREST access (env vars SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY already
set — same curl patterns as any other DB task in this project):
1. Independently re-run pencil_dod_evaluate_county for county "${r.county}" RIGHT NOW and compare to the
   claimed after_metric_json. If they don't match, or don't match the direction claimed, REFUTE.
2. If writes_made lists any row IDs, pull those rows fresh from multi_county_auctions and confirm the
   fields actually changed to what's claimed, and that the cited source_evidence is a real, checkable,
   named source (not vague/invented). If a field looks fabricated, guessed, or PropertyOnion-derived where
   an independent source was required (letters B/F specifically), REFUTE.
3. If the claim is "blocked, no writes made" — verify that's true (spot check the county still shows the
   same live metric as reported) and that the stated reason is plausible given what you can independently
   observe; a well-documented honest blocker SURVIVES (this is a pass condition, not a failure).
4. Default to refuted=true (survived=false) if you are genuinely uncertain — the burden of proof is on
   the claim, per this project's Sentinel-correct-by-default convention.
Report survived (true only if the claim holds up), your reasoning, and the live_recheck_metric JSON you
personally ran.`,
        { label: `verify:${streams[i].label}`, phase: 'Verify', schema: VERDICT_SCHEMA }
      ).then((v) => ({ ...r, stream: streams[i].key, verdict: v }))
  })
)

const survived = verified.filter(Boolean).filter((v) => v.verdict?.survived)
const refuted = verified.filter(Boolean).filter((v) => v.verdict && !v.verdict.survived)

log(`Verify phase complete: ${survived.length} survived, ${refuted.length} refuted`)

return { fixResults, verified, survived, refuted }
