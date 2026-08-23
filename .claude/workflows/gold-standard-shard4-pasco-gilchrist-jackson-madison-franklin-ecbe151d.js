export const meta = {
  name: 'gold-standard-shard4-pasco-gilchrist-jackson-madison-franklin-ecbe151d',
  description: 'Gold Standard shard-4 (dispatch ecbe151d): pasco I, gilchrist E/I, jackson C/D/I, madison B/C/F/I, franklin C/D/E/I/J — research known blockers, fix with real data, adversarially verify',
  phases: [
    { title: 'Diagnose-Fix-Verify' },
  ],
}

const COUNTIES = [
  {
    slug: 'pasco',
    failing: ['I'],
    context: 'I: card_complete=341 of 363 (93.9%%, need >=95% i.e. >=345/363, so ~4+ more rows need address+geo+value+zoned-parcel). All other letters (A-H,J) already PASS live — do not touch them.',
    priorFiles: 'scripts/shard5_pasco_i_card_complete_backfill_jul30.py, GOLD_STANDARD_SHARD13_PASCO_DISPATCH_8c8052cf_SESSION_REPORT.md, GOLD_STANDARD_SHARD3_PASCO_DISPATCH_FB510BA8_SESSION_REPORT.md, migrations/20260710_gold_standard_shard4_pasco_i_parcel_zones_backfill.sql, migrations/20260710_gold_standard_shard4_pasco_i_revert_ghost_success.sql (a PRIOR SESSION FABRICATED zoning data to force I to pass and it was caught+reverted — do NOT repeat that pattern), scripts/gold_standard_shard1_a96722e9_pasco_i_pa_enrichment.py, scripts/gold_standard_shard3_84bbde9d_session2_pasco_citrus_i_fix.py',
  },
  {
    slug: 'gilchrist',
    failing: ['E', 'I'],
    context: 'E: parcel_linked=11 of 14 (78.6%%, need >=95% i.e. 14/14 or 13/14). I: card_complete=11 of 14 (78.6%%, same threshold). E and I are likely the SAME 3 unlinked rows (I requires a linked parcel per the evaluator SQL — fixing E should move I too).',
    priorFiles: 'gilchrist_e_parcel_linkage_blocked.sql, gilchrist_i_card_completeness_blocked_followup.sql (read these FIRST — they document exactly why prior sessions could not close this), GOLD_STANDARD_GILCHRIST_EI_FRESH_ATTEMPT_20260801_SESSION_REPORT.md, GOLD_STANDARD_SHARD7_GILCHRIST_DISPATCH_61f11933-122d-4474-acf3-65e71d7a707c_RUN7519_3RD_FIRING_SESSION_REPORT.md, migrations/20260730_gilchrist_shard7_run7519_ghost_purge_ei.sql (another prior fabrication caught+reverted for this exact letter pair — do NOT repeat), scripts/gilchrist_owner_gis_lookup.py, scripts/gold_standard_shard1_run8166_gilchrist_ei_fix.py',
  },
  {
    slug: 'jackson',
    failing: ['C', 'D', 'I'],
    context: 'C/D: matched_clean=matched_any=76 of 129 (58.9%%, need >=95%% i.e. >=123/129 — a 47-row gap, the largest in this shard). I: card_complete=75 of 129 (58.1%%). Many prior sessions attempted C/D specifically and it has not moved — read the addendum trail before re-attempting the same approach.',
    priorFiles: 'migrations/20260626_shard6_jackson_cd_parity.sql, scripts/shard3_jackson_g_fix.py, scripts/shard3_jackson_i_fix.py, scripts/shard3_jackson_verify.py, scripts/shard3_jackson_bf_fix.py, scripts/shard6_run3025_2nd_dispatch_jackson_cd_parity.py, scripts/shard6_run3025_3rd_dispatch_jackson_cd_parity.py (2nd AND 3rd attempts at the same problem — read why they stalled), GOLD_STANDARD_SHARD2_JACKSON_DIXIE_HENDRY_COLUMBIA_DISPATCH_190AC19F_CONTINUATION_ADDENDUM_2.md, GOLD_STANDARD_SHARD2_JACKSON_WALTON_LIBERTY_DISPATCH_5E1E6111_SESSION_REPORT.md, GOLD_STANDARD_SHARD4_JACKSON_BRADFORD_UNION_HOLMES_ALACHUA_DISPATCH_49342BAB_SESSION_REPORT.md',
  },
  {
    slug: 'madison',
    failing: ['B', 'C', 'F', 'I'],
    context: 'B/F: verified=0 closed_sold=0 (null/null, structural — evaluator returns NULL when closed_sold denominator is 0, meaning NO madison auction has sold_amount populated yet; this may be a genuine "nothing has closed" case, not a data-quality gap — verify auction_date/sale status before assuming a fixable gap). C: matched_clean=7 of 8 (87.5%%, need >=95%% i.e. 8/8 — a single row). I: card_complete=6 of 8 (75.0%%, need >=95%% i.e. 8/8 — two rows).',
    priorFiles: 'scripts/gold_standard_shard1_6a9e3c3a_madison_bf_outcome.py, scripts/gold_standard_shard1_6a9e3c3a_madison_ij_fix.py, scripts/shard5_a_lane_madison.py, scripts/shard7_madison_h_fix.py, GOLD_STANDARD_SHARD4_MADISON_DISPATCH_41A3461B_SESSION_REPORT.md, GOLD_STANDARD_SHARD1_BREVARD_SUMTER_CITRUS_MADISON_DISPATCH_2f4312f9_SESSION_REPORT.md, GOLD_STANDARD_SHARD5_PINELLAS_MADISON_HAMILTON_DISPATCH_8D7DE4AB_SESSION_REPORT.md, GOLD_STANDARD_SHARD1_DUVAL_MADISON_DISPATCH_32B4833C_SESSION_REPORT.md, GOLD_STANDARD_SHARD7_MANATEE_MADISON_LAKE_DISPATCH_BC399D3B_SESSION_REPORT.md, GOLD_STANDARD_SHARD5_RUN3786_CALHOUN_MADISON_JEFFERSON_SESSION_REPORT.md',
  },
  {
    slug: 'franklin',
    failing: ['C', 'D', 'E', 'I', 'J'],
    context: 'C/D/E/I all sit at 90.9%% (10 of 11 — likely ONE single problem row blocking all four letters at once; find that one row first, it may be the highest-leverage fix in this entire shard). J: deal_complete=10 of 11 (90.9%%) — franklin already has scripts/shard5_franklin_j_generator.py which reuses the PROVEN real-per-property-ARV generator (scripts/shard28_run338_j_generator.py logic, NOT the hardcoded-constant anti-pattern this session already purged for pasco/jackson) — running it for the 1 missing case_number is very likely sufficient; do not build a new generator from scratch.',
    priorFiles: 'scripts/franklin_bf_recheck_2026-07-11.py, scripts/franklin_bf_verified_no_sales_2026-07-10.py, scripts/franklin_liberty_bf_recheck_2026-07-18.py, scripts/franklin_zoning_backfill.py, scripts/shard5_franklin_j_generator.py, scripts/shard28_run338_j_generator.py (the generator franklin_j_generator.py wraps — read process_county()), GOLD_STANDARD_SHARD3_MARION_FRANKLIN_LIBERTY_SEMINOLE_DISPATCH_26F01B9B_SESSION_REPORT.md (+ its CONTINUATION_ADDENDUM and SECOND_CONTINUATION), GOLD_STANDARD_SHARD9_FRANKLIN_HARDEE_DISPATCH_30B3A3EA_SESSION_REPORT.md (+ 2ND_FIRING), GOLD_STANDARD_SHARD2_FRANKLIN_LEVY_STLUCIE_OKALOOSA_DISPATCH_3FF137AD_SESSION_REPORT.md, GOLD_STANDARD_SHARD1_FRANKLIN_HOLMES_DISPATCH_5BA6EC26_DUPLICATE_REFIRE_ADDENDUM.md',
  },
]

const SHARED_CONTEXT = `
GOLD STANDARD CAMPAIGN — dispatch_id ecbe151d-2535-4df0-a47d-adb3fe15c324, shard-4.
Repo: /home/runner/work/cli-anything-biddeed/cli-anything-biddeed (already checked out, you are running there).

CREDENTIALS (already in your shell env, never print/echo their values):
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY -> PostgREST reads/writes: curl "$SUPABASE_URL/rest/v1/<table>?..." -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
  SUPABASE_ACCESS_TOKEN -> Supabase Management API for arbitrary SQL (DDL/complex joins):
    curl -s "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query" -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" -H "Content-Type: application/json" -d '{"query":"SELECT ..."}'
  Direct psql/SUPABASE_DB_PASSWORD is KNOWN BROKEN in this environment (password auth fails) — do not waste time on it, use the Management API above for ad-hoc SQL instead.
  RPC for scoring: POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county with body {"p_county":"<slug>"} — this is the canonical live scorer, ALWAYS re-run it fresh, never trust a cached/remembered number.

EVALUATOR SQL SEMANTICS (read pg_get_functiondef(oid) for pencil_dod_evaluate_county via the Management API yourself to confirm current behavior before assuming anything below is still accurate):
  - Base population = multi_county_auctions WHERE lower(county)=<slug> AND (data_source <> 'propertyonion' OR tier1_authoritative=true). PropertyOnion-sourced rows are EXCLUDED from every denominator unless flagged tier1_authoritative.
  - C metric = matched_clean/auctions_total >= 95. matched_clean requires parity_status IN ('matched_clean' with parity_source LIKE 'tier1%') OR IN ('PARITY_OK','CLERK_VERIFIED').
  - D metric = matched_any/auctions_total >= 95. Slightly looser: also allows 'matched_divergent' (tier1%) and 'CLERK_SSOT_CANCELLED'.
  - E metric = has_parcel/auctions_total >= 95, where has_parcel = parcel_id IS NOT NULL.
  - I metric = card_complete/card_rows >= 95. card_complete requires property_address NOT NULL, (latitude/po_latitude) NOT NULL, (longitude/po_longitude) NOT NULL, (assessed_value or market_value) NOT NULL, AND parcel_id present in v_zoning_gold_standard_card (a REAL zoning-linked parcel, zone_code NOT NULL) for this county. I <= E structurally: a row can't be I-complete without first being E-linked to a parcel that also resolves through v_zoning_gold_standard_card.
  - B metric = verified_outcomes/closed_sold >= 95 AND <=105 (must be independently sourced: EXISTS in tax_deed_outcomes or foreclosure_outcomes with case_number match AND data_source NOT ILIKE '%%promote%%'). closed_sold = count of multi_county_auctions rows with sold_amount NOT NULL. NULL/NULL (no closed rows) makes this pass=false with metric=null — that is a STRUCTURAL gap (no sales yet), not obviously a data bug; verify which before attempting a fix.
  - F metric = tier1_sold/closed_sold >= 95, tier1_sold = count where tier1_sold_amount NOT NULL AND sold_amount NOT NULL. Same closed_sold denominator as B.
  - J metric = deal_complete/auctions_total >= 95. deal_complete requires a bid_decisions row matching case_number with arv, max_bid, ml_score all NOT NULL AND factors jsonb containing keys distress_location, distress_property, distress_owner, cma_distressed, cma_resale.

HARD GUARDRAILS (read the full text in this repo's CLAUDE.md if you need more, but these are non-negotiable):
  1. PropertyOnion data is litmus/comparison ONLY — never write it into multi_county_auctions as an authoritative source, never set it as the sole basis for C/D/E/I fixes.
  2. Fail-loud: if you build N rows and insert 0, raise/stop and report it — never silently swallow with `|| true` or a bare except.
  3. NEVER fabricate/guess a value to force a metric to pass. This session already found and fixed TWO instances of exactly this (a daily-cron generator hardcoding one county-wide ARV for every property in bid_decisions across 20+ counties including pasco/jackson, purged 2026-08-23; and a PRIOR session's fabricated zone_code='R-2' for pasco parcel_zones, already reverted — see migrations/20260710_gold_standard_shard4_pasco_i_revert_ghost_success.sql). If you cannot find a REAL, sourced value (county GIS/appraiser API, clerk record, ordinance text), leave the row unfixed and report it as a genuine structural gap. BLANK > WRONG.
  4. PARALLEL-FLEET RULES: you own ONLY the county assigned to you in this task. Never touch another county's rows, even if you notice it while querying (this repo runs many concurrent shard sessions on other counties right now — a git pull --rebase before you push may show other shards' unrelated commits landing mid-session; that is normal, do not investigate or revert them).
  5. Any SQL/table changes: write a migrations/<date>_<slug>.sql file documenting what you ran (matching the style of existing files in migrations/), even though you apply it live via the Management API/PostgREST (direct psql is broken here, see above).

YOUR TASK for county "{{SLUG}}" (failing letters: {{FAILING}}):
{{CONTEXT}}

Prior-session files most relevant to this exact problem (read the ones that exist before doing anything — many sessions have already tried and failed on these exact letters, do not repeat a dead end):
{{PRIORFILES}}

Work in three rounds, reported back at the end of each:
ROUND 1 (RESEARCH): Read the prior-session files above (grep for the county name across GOLD_STANDARD_*.md session reports too, there may be more not listed). Run pencil_dod_evaluate_county('{{SLUG}}') fresh to confirm current state. For each failing letter, identify the EXACT rows/case_numbers blocking it (query multi_county_auctions directly) and WHY they're blocked (missing parcel_id? missing lat/long? no matching parity source? no closed sale yet?). State plainly whether you believe each gap is fixable with real data this session, or whether it is a genuine structural/data-availability ceiling (e.g. county has no public ArcGIS parcel layer, no clerk records online, etc.) — cite your evidence either way.
ROUND 2 (FIX): For gaps you judge fixable, fix them using ONLY real, sourced data (county property appraiser / ArcGIS FeatureServer / clerk records / municode ordinance text / the county's own scraped source). Use WebFetch/WebSearch/firecrawl skills as needed to pull real per-property or per-parcel data. Write the migration file. Apply live via Management API/PostgREST. For gaps you judge structural, do not force anything — document the evidence.
ROUND 3 (VERIFY): Re-run pencil_dod_evaluate_county('{{SLUG}}') fresh. Confirm every letter you touched actually moved, and confirm you did NOT regress any letter that was previously passing (diff the full A-J object before vs after). Adversarially double-check your own fix: could the specific rows you inserted/updated be wrong in a way that inflates the metric without being real (ghost-success)? If yes, revert and report honestly instead.

Return a structured summary: {county, failing_letters_at_start, evaluator_before (full A-J JSON), work_done (list), evaluator_after (full A-J JSON), still_failing (list with honest reason), migration_file_path, git_commits}.
`

async function runCounty(c) {
  const prompt = SHARED_CONTEXT
    .replace(/\{\{SLUG\}\}/g, c.slug)
    .replace('{{FAILING}}', c.failing.join(', '))
    .replace('{{CONTEXT}}', c.context)
    .replace('{{PRIORFILES}}', c.priorFiles)
  return await agent(prompt, { label: `gold-standard:${c.slug}`, phase: 'Diagnose-Fix-Verify' })
}

phase('Diagnose-Fix-Verify')
log(`Starting gold-standard shard-4: ${COUNTIES.map(c => c.slug).join(', ')} — pasco/jackson J ghost-fill already purged directly (not part of this workflow)`)

const results = await parallel(COUNTIES.map(c => () => runCounty(c)))

log('All 5 counties complete. Results:')
results.forEach((r, i) => {
  if (r) log(`${COUNTIES[i].slug}: done`)
  else log(`${COUNTIES[i].slug}: agent failed/skipped`)
})

return { dispatch_id: 'ecbe151d-2535-4df0-a47d-adb3fe15c324', counties: COUNTIES.map(c => c.slug), results }
