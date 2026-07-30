export const meta = {
  name: 'gold-standard-shard9-gulf-run7519-3rd-firing',
  description: 'Gold Standard shard-9 gulf 3rd firing on dispatch 0ba2502a: confirm no drift at 9/10, fan out for genuinely new levers on failing letter I, regression-check the 9 passing letters, adversarially verify any new claim',
  phases: [
    { title: 'Discover' },
    { title: 'Verify' },
  ],
}

phase('Discover')
log('gulf is at 9/10 per live pencil_dod_evaluate_county query (I fails at 85.7%, capped by a documented Port St Joe zoning dead end). Fanning out to check for genuinely new levers before closing out.')

const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    found_new_lever: { type: 'boolean' },
    summary: { type: 'string' },
    evidence: { type: 'string' },
    confidence_label: { type: 'string', enum: ['CONFIRMED', 'HYPOTHESIS', 'UNKNOWN'] },
  },
  required: ['found_new_lever', 'summary', 'evidence', 'confidence_label'],
}

const REGRESSION_SCHEMA = {
  type: 'object',
  properties: {
    anomaly_found: { type: 'boolean' },
    details: { type: 'string' },
    letters_checked: { type: 'array', items: { type: 'string' } },
  },
  required: ['anomaly_found', 'details', 'letters_checked'],
}

const [portStJoeFinding, regressionCheck, auditFreshness] = await Promise.all([
  agent(`You are working the BidDeed.AI Gold Standard fleet campaign, shard-9, county=gulf, dispatch 0ba2502a-8ac3-408e-9fb0-255fae137aaf. This is a re-check, NOT a re-derivation. Repo root has mgmt_sql.py (usage: python3 mgmt_sql.py 'SELECT ...') which runs SQL against the live Supabase project via the Management API using env var SUPABASE_ACCESS_TOKEN (already set).

CONTEXT (already established across 4+ prior sessions, most recently 2026-07-30 ~17:44Z, do NOT re-derive): letter I (property-card completeness) for gulf is capped at 12/14 (85.7%), below the 95% threshold. The 2 remaining incomplete rows are parcels 05762000R and 05004050R. Both sit inside City of Port St Joe limits per Gulf County GIS layer 40 (Land Use, Type=Municipal) at arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer (71 layers enumerated exhaustively — only layer 7 "City Limits of Port St Joe" and layer 40 "Land Use" exist; NO dedicated Port St Joe zoning-classification layer). The city's own zoning map is a scanned/vector-text PDF with real text labels (R-1, R-1A, R-2A, R-2B, R-3, C-1, C-1A, C-2, PU, PUD) but NO georeferencing binding labels to specific parcels. The documented resolution path is a human phone call to City of Port St Joe Planning (850-229-8261) — out of your reach.

YOUR TASK: do a FRESH check for whether anything has genuinely changed that would unlock this without a phone call. Specifically:
1. Web search for "City of Port St Joe Florida zoning map GIS" and "Port St Joe Florida planning department online zoning lookup" — look for a NEW georeferenced/queryable zoning layer, not the same PDF already documented.
2. Check cityofportstjoe.com (or its current live domain, search if unsure) for a GIS/planning portal.
3. Re-enumerate arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer's layer list (a plain GET to the MapServer endpoint with f=json) to confirm no new Port St Joe zoning layer has been added since the last check.
4. If you find any real lead, verify it actually resolves parcel 05762000R or 05004050R specifically to a zoning classification — do not report found_new_lever=true on a generic/PDF-only source, that has already been ruled out.

Report found_new_lever=true ONLY if you find an actual new, queryable, georeferenced source that resolves one or both parcels. Otherwise found_new_lever=false. Tag your summary with a Honesty Protocol confidence_label (CONFIRMED/HYPOTHESIS/UNKNOWN). Be honest — "nothing new found" is a completely acceptable and expected outcome, do not stretch weak evidence into a false positive.`,
    { label: 'discover:port-st-joe-zoning', phase: 'Discover', schema: FINDING_SCHEMA }),

  agent(`You are an independent regression auditor for the BidDeed.AI Gold Standard fleet campaign, county=gulf, dispatch 0ba2502a-8ac3-408e-9fb0-255fae137aaf. Repo root has mgmt_sql.py (usage: python3 mgmt_sql.py 'SELECT ...') running SQL against the live Supabase project (SUPABASE_ACCESS_TOKEN already set in env). Run: SET statement_timeout = 0; then SELECT public.pencil_dod_evaluate_county('gulf');

The most recent known-good state (2026-07-30 ~17:44Z, a few hours ago) was: A pass(5) B pass(100.0) C pass(100.0) D pass(100.0) E pass(100.0) F pass(100.0) G pass(100.0) H pass(<48h) I fail(85.7, card_complete=12 of 14) J pass(100.0) — 9/10, auctions_total=14.

YOUR TASK: independently re-verify this is still true RIGHT NOW via the live query, and additionally cross-check at least letters B (verified_outcomes vs closed_sold — must be in the 95-105% band per campaign rules, not just nominally 100%), C/D (matched counts must be 14 of 14, not a rounding artifact), and E (parcel_linked count) against raw counts on multi_county_auctions / foreclosure_outcomes / tax_deed_outcomes for county='gulf', not just trusting the evaluator function's output. Look specifically for: denominator changes (auctions_total should still be 14 — if it changed, new rows may have been scraped and could shift any letter), double-counting, or any letter that regressed from its last-known value. Report anomaly_found=true if you find ANY discrepancy between the live evaluator output and your independent raw-count cross-check, or if any letter regressed. List every letter you actually checked in letters_checked.`,
    { label: 'discover:regression-check', phase: 'Discover', schema: REGRESSION_SCHEMA }),

  agent(`Query the live Supabase project (mgmt_sql.py in repo root, usage: python3 mgmt_sql.py 'SELECT ...', SUPABASE_ACCESS_TOKEN already set) for: SELECT letter, survived, max(created_at) as latest FROM public.gold_standard_ultraloop_audit WHERE county_slug='gulf' GROUP BY letter, survived ORDER BY letter;

Report, for county=gulf, which of the 10 letters (A-J) have at least one survived=true audit row, and how recent the newest one is for each letter (compute age in days from the latest created_at using the DB's own now() in the same query, e.g. via a second query: SELECT letter, max(created_at), now() - max(created_at) as age FROM public.gold_standard_ultraloop_audit WHERE county_slug='gulf' AND survived=true GROUP BY letter). This is informational only — no DB writes, no code changes. Report as anomaly_found=true only if you find a letter that currently PASSES on the live scoreboard (per SELECT public.pencil_dod_evaluate_county('gulf')) but has ZERO survived=true audit rows ever (meaning its pass status is unaudited, not merely stale) — flag that as a details string. Otherwise anomaly_found=false. List letters_checked as all 10 letters.`,
    { label: 'discover:audit-freshness', phase: 'Discover', schema: REGRESSION_SCHEMA }),
])

log(`Port St Joe lever: found_new_lever=${portStJoeFinding?.found_new_lever}. Regression check: anomaly_found=${regressionCheck?.anomaly_found}. Audit freshness: anomaly_found=${auditFreshness?.anomaly_found}.`)

phase('Verify')

let leverVerdict = null
if (portStJoeFinding?.found_new_lever) {
  leverVerdict = await agent(`Adversarially refute this claim about gulf county (BidDeed.AI Gold Standard campaign, letter I): "${portStJoeFinding.summary}" Evidence offered: "${portStJoeFinding.evidence}". Your ONLY goal is to break this claim. Independently re-derive it from scratch — do not trust the transcription. Check whether the source is genuinely georeferenced/queryable (not a scanned PDF or generic text mention), and whether it actually resolves parcel 05762000R or 05004050R specifically in Gulf County, Florida (City of Port St Joe). Default to refuted=true on any gap, ambiguity, or inability to independently reproduce. Use mgmt_sql.py in the repo root (SUPABASE_ACCESS_TOKEN already set) if you need to cross-check against multi_county_auctions or parcel_zones.`,
    { label: 'verify:port-st-joe-lever', phase: 'Verify', schema: { type: 'object', properties: { refuted: { type: 'boolean' }, reasoning: { type: 'string' } }, required: ['refuted', 'reasoning'] } })
}

let regressionVerdict = null
if (regressionCheck?.anomaly_found) {
  regressionVerdict = await agent(`A regression auditor flagged a possible anomaly on gulf county's Gold Standard scoreboard: "${regressionCheck.details}" (letters checked: ${JSON.stringify(regressionCheck.letters_checked)}). Independently re-run SELECT public.pencil_dod_evaluate_county('gulf'); (mgmt_sql.py in repo root, SUPABASE_ACCESS_TOKEN set) and your own raw-count cross-checks against multi_county_auctions/foreclosure_outcomes/tax_deed_outcomes to confirm or refute whether this is a real anomaly needing a fix, or a false alarm. Default to treating it as real (refuted=false, meaning the anomaly stands) unless you can positively rule it out.`,
    { label: 'verify:regression-anomaly', phase: 'Verify', schema: { type: 'object', properties: { refuted: { type: 'boolean' }, reasoning: { type: 'string' } }, required: ['refuted', 'reasoning'] } })
}

return {
  gulf_metric_before_session: '9/10 (I fails at 85.7%)',
  port_st_joe_finding: portStJoeFinding,
  port_st_joe_verify: leverVerdict,
  regression_check: regressionCheck,
  regression_verify: regressionVerdict,
  audit_freshness: auditFreshness,
}
