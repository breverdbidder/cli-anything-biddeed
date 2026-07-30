export const meta = {
  name: 'gold-standard-shard8-okeechobee-run7519-ed344dc4',
  description: 'Gold Standard shard-8 okeechobee (dispatch ed344dc4, loop run 7519): adversarial verify of a dedup fix for 10 mislabeled sale_type duplicate rows that moved C/D/I to PASS',
  phases: [
    { title: 'Verify', detail: 'independent refuter, fresh context' },
    { title: 'AuditLog', detail: 'write gold_standard_ultraloop_audit rows' },
  ],
}

const DISPATCH_ID = 'ed344dc4-9b86-4f5a-97af-26ea782adcbe'

const CLAIM = `
CLAIM (made by a prior agent in this session, NOT you -- be skeptical and re-derive everything yourself):

County: okeechobee. Before (VERIFIED live via SELECT public.pencil_dod_evaluate_county('okeechobee') at session start):
{"A":{"pass":true,"metric":25,"detail":"fc=25 td=51"},"B":{"pass":true,"metric":100,"detail":"verified=6 closed_sold=6"},
"C":{"pass":false,"metric":86.8,"detail":"matched_clean=66"},"D":{"pass":false,"metric":86.8,"detail":"matched_any=66"},
"E":{"pass":true,"metric":100,"detail":"parcel_linked=76"},"F":{"pass":true,"metric":100,"detail":"tier1_sold=6 closed_sold=6"},
"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0},
"I":{"pass":false,"metric":85.5,"detail":"card_complete=65 of 76"},
"J":{"pass":true,"metric":100,"detail":"deal_complete=76"},"auctions_total":76}

Root cause claimed: multi_county_auctions had 76 rows for okeechobee but only 66 DISTINCT case_number values -- i.e. exactly
10 case_numbers were duplicated. For each duplicated case_number there were two rows: (a) an older row, correctly containing
real, already-verified data (property_address, latitude, longitude, assessed_value, parity_status='matched_clean',
parity_source LIKE 'tier1%' e.g. 'tier1:shard8_run_ac288257_ajax_harvest:foreclosure:2026-08-06'), but mislabeled
sale_type='foreclosure' even though the case_number carries Florida's 'TD' (tax deed docket) prefix; and (b) a newer row
(created 2026-07-30 16:35 UTC, data_source NULL, parity_status NULL, missing address/lat/lon) correctly labeled
sale_type='tax_deed' but otherwise a blank duplicate scaffold row. The 10 case_numbers: 2026TD038, 2026TD039, 2026TD040,
2026TD045, 2026TD046, 2026TD047, 2026TD048, 2026TD051, 2026TD067, 2026TD071.

Claimed fix (already executed live against Supabase project mocerqjnksmhcjzxrewo, NOT a draft -- verify it actually
happened): for each of the 10 pairs, DELETE the blank tax_deed-labeled duplicate row, then UPDATE the older data-rich row's
sale_type from 'foreclosure' to 'tax_deed' (both operations scoped by county='okeechobee' and exact id, inside one
transaction). Deleted ids: ad55c33c-4789-4c6b-a726-b43be20502fe, 4d76412f-a072-4d1d-9c81-3c84a1a00437,
0838f639-f18d-4293-be80-0824299fa8bf, 3ce7f1c0-fee0-4f93-bf09-4ad61070088f, f8499ad9-effa-4ea6-9e8e-619a7be52ab0,
2be4766e-a83b-49c6-8e85-4225a7bdfcbd, 462bbf76-a2d7-4027-9751-6f885b2ea8c9, 568feb16-6bb7-4b3f-9dbc-c69900d3a5e6,
3ae69a15-867e-47f8-acba-a1a377a4a97f, 1af2a45c-df83-461c-9d9d-15433c51280f. Relabeled (foreclosure->tax_deed) ids:
0b4485d7-14c2-4b0d-ac68-570f38e21a5c, 56b0b086-85b8-45f1-833b-edd1007520d2, 92ab9212-c703-43dd-b5cd-5f0ea48d93cf,
4e663b11-0c3e-4364-8c50-849296837144, cacf2126-99fd-4c2d-a3bf-60227c96e366, e2dbc581-1686-4afc-a768-8e26fc37e6db,
21a32dc2-ef35-4106-9e06-7154a69fb1f7, 52092e61-ab25-4bfd-b011-da04bf354640, 428cdc3c-2ef5-4a98-aa8b-ed15913d5ad7,
a9834e75-7771-4986-a2a8-a89a1ff776a4. No property_address, latitude, longitude, or assessed_value was written by hand --
every surviving value already existed on the row that was kept (it was already tier1-verified in a prior session via the
okeechobee.realforeclose.com AJAX foreclosure harvest, confirmed by all 10 pairs sharing an identical opening_bid between
their two rows, strong evidence they are the same underlying sale double-seeded with two sale_type labels).

Claimed after (paste-in from same RPC, run immediately after the fix):
{"A":{"pass":true,"metric":15,"detail":"fc=15 td=51"},"B":{"pass":true,"metric":100,"detail":"verified=6 closed_sold=6"},
"C":{"pass":true,"metric":100,"detail":"matched_clean=66"},"D":{"pass":true,"metric":100,"detail":"matched_any=66"},
"E":{"pass":true,"metric":100,"detail":"parcel_linked=66"},"F":{"pass":true,"metric":100,"detail":"tier1_sold=6 closed_sold=6"},
"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0.1},
"I":{"pass":true,"metric":98.5,"detail":"card_complete=65 of 66"},
"J":{"pass":true,"metric":100,"detail":"deal_complete=66"},"auctions_total":66}

Residual gap disclosed (NOT claimed fixed): one further row, case_number 2026TD050 (id adc8301b-d58f-4bd0-a300-f35d0239d82a,
parcel_id 1-25-37-35-0070-00060-1760), already had parity_status='matched_clean' and assessed_value but is still missing
property_address/latitude/longitude. FL GIO Statewide Cadastral (services9.arcgis.com .../Florida_Statewide_Cadastral/
FeatureServer/0) was queried for this parcel_id (dash-stripped format, confirmed as the correct format because it
successfully returned a feature for a DIFFERENT okeechobee parcel, 1-35-37-35-0020-00000-0650 -> CO_NO=57 in FL GIO's own
numbering, NOT the fl_counties.co_no=47 our internal table has -- a real, noted discrepancy) and returned zero features for
2026TD050's parcel. This one row was left incomplete and reported as an honest residual rather than fabricated -- I is still
98.5%, comfortably above the 95% threshold.

KNOWN RECURRING RISK (found separately this session, cross-referencing OTHER concurrent audit rows on this same dispatch):
pg_cron job 204 ('gold-calendar-parity-cycle', every 5 min -> promote_upcoming_tier1_cards -> biddeed.flow_card_to_mca) has
repeatedly re-inserted this exact kind of duplicate (TD-numbered case, sale_type wrongly derived as 'foreclosure') across at
least 3 prior sessions. biddeed.flow_card_to_mca's live definition already contains a regex-based fix (dated 2026-07-30 in
its own comment) deriving sale_type from '^[0-9]{4}TD[0-9]+$' before falling back to platform-based logic. Post-fix
durability check this session: count(*)=66, count(DISTINCT case_number)=66, max(created_at)=2026-07-28 06:11:28+00 --
i.e. despite the cron running every 5 minutes, no NEW row has been created for okeechobee since 2026-07-28, meaning the
cron is reconciling to existing rows (UPDATE path) not creating fresh duplicates (INSERT path). Re-verify this durability
claim yourself too -- do not assume it still holds by the time you run.
`

const RECIPE = `
Environment (already available):
- Live SQL: python3 mgmt_sql.py "SELECT ..." from repo root (cli-anything-biddeed, on main) -- this runs against
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query using SUPABASE_ACCESS_TOKEN. Prefix heavy
  queries with "SET statement_timeout = 0;". This is the SAME tool the fix agent used -- use it yourself, don't take
  its word for anything.
- REST API also available: \${SUPABASE_URL}/rest/v1/<table> with headers apikey/Authorization: Bearer
  $SUPABASE_SERVICE_ROLE_KEY.
- pencil_dod_evaluate_county('okeechobee') is the canonical scoring RPC -- call it fresh, do not reuse the pasted JSON.
- FL GIO Statewide Cadastral: https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query
  -- PARCEL_ID values in this service have NO dashes (confirmed working format this session).

Your job -- ADVERSARIAL VERIFY, per this campaign's ULTRALOOP protocol (docs/ULTRALOOP-SSOT.md): you did NOT write this
fix. Try to break the claim. Specifically:
1. Run pencil_dod_evaluate_county('okeechobee') RIGHT NOW yourself. Confirm auctions_total=66 (not 76, not something else,
   and NOT 88 -- 88 would mean the pg_cron-204 duplicate-reseed risk noted above has recurred), and confirm C, D, I
   actually show pass=true with the metrics claimed above (allow for H's metric drifting slightly since it's a live clock,
   and V2_LITMUS which is informational-only).
2. Row-count sanity: query multi_county_auctions WHERE county='okeechobee' and confirm (a) exactly 66 rows now exist,
   (b) count(DISTINCT case_number) = 66 (i.e. genuinely no more duplicates), (c) none of the 10 case_numbers listed above
   have MORE than one row, (d) max(created_at) is still 2026-07-28 or earlier -- if it's newer, the reseed cron has fired
   again and this claim no longer survives.
3. Ghost-success check: for at least 4 of the 10 relabeled ids, independently query multi_county_auctions by id and
   confirm property_address, latitude, longitude, and assessed_value are non-null AND look like real Okeechobee, FL data
   (real street format, lat ~26.9-27.6 / lon ~-81.3--80.6 bounding box for Okeechobee County). Do NOT trust that they are
   real just because the claim says so.
4. Confirm the 10 deleted ids are actually gone (SELECT ... WHERE id IN (...) should return zero rows).
5. Regression check on the OTHER letters: confirm B stays at exactly 100 (95-105 band, critical-three), and that A, E, F,
   G, H, J did not silently break as a side effect of the total dropping from 76 to 66. Pay particular attention to J
   (deal_complete) since bid_decisions is keyed by case_number, not row id -- confirm deal_complete/auctions_total is still
   >=95% and ideally still 100% as claimed.
6. Spot-check the residual claim: query case_number='2026TD050' yourself and confirm it is STILL incomplete (this campaign's
   hard guardrail bans ghost-success -- if someone quietly "fixed" it with a fabricated address, that is a violation, not a
   bonus; equally if it turns out it WAS fixable and simply wasn't tried hard enough, note that as a residual finding for
   the next session, but do not fabricate a value yourself either).
7. INSERT one row per letter you adjudicate (C, D, I at minimum; optionally A/E/F/J if you want to record the
   regression-check) into public.gold_standard_ultraloop_audit via REST POST to \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit
   with service-role headers. Columns: dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used
   Workflow-tool subagent fan-out, not native /effort ultracode), county_slug ('okeechobee'), letter, claim (short text
   describing what you're adjudicating), refuter_evidence (jsonb -- your actual query results, not a summary), survived
   (boolean -- true only if your independent re-check confirms the claim held).

Hard rules: you own ONLY okeechobee, do not touch any other county's rows. Do NOT run public.gold_standard_loop() or
gold_standard_certify() -- other shards may be mid-session, per the campaign's parallel-fleet rules. Do NOT modify cron
jobs 109/111/115 or any gold-standard-loop-* scoring job. Do NOT touch bid_decisions. If you find ANY discrepancy between
the claim and live reality, report refuted=true with the exact evidence -- do not soften it. If pg_cron job 204's reseed
bug has recurred, that is a valid refutation of durability even if the underlying fix logic is still correct -- report it
plainly and note it as the priority item for the next session (do not attempt to disable or modify cron 204 yourself
without further diagnosis; it is not one of the explicitly protected jobs but a live cron change is a bigger action than
this verify pass should take unilaterally).

Return: { county: 'okeechobee', refuted: boolean, refutation_reasons: [...], fresh_evaluation: <full JSON from the RPC>,
row_count_check: {...}, ghost_success_spotcheck: [...], deleted_ids_confirmed_gone: boolean, residual_confirmed: boolean,
audit_rows_inserted: number, survives: boolean }
`

phase('Verify')
const verified = await agent(
  `You are independently auditing a claimed Gold Standard fix for county "okeechobee" in the cli-anything-biddeed repo (checked out on main, repo root is cwd). You did not write this fix -- be skeptical and re-derive everything from live data yourself.\n\n${CLAIM}\n\n${RECIPE}`,
  {
    label: 'verify:okeechobee',
    phase: 'Verify',
    schema: {
      type: 'object',
      properties: {
        county: { type: 'string' },
        refuted: { type: 'boolean' },
        refutation_reasons: { type: 'array', items: { type: 'string' } },
        fresh_evaluation: {},
        row_count_check: {},
        ghost_success_spotcheck: { type: 'array', items: {} },
        deleted_ids_confirmed_gone: { type: 'boolean' },
        residual_confirmed: { type: 'boolean' },
        audit_rows_inserted: { type: 'number' },
        survives: { type: 'boolean' },
      },
      required: ['county', 'refuted', 'fresh_evaluation', 'survives'],
    },
  }
)

return { verified }
