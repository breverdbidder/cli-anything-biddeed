export const meta = {
  name: 'gold-standard-shard6-fd6f48d0',
  description: 'Gold Standard shard-6 (walton/okeechobee/gulf): G density backfill, C/D parity stamps, H freshness',
  phases: [
    { title: 'Apply migration', detail: 'Run executor: zone_standards density backfill (walton), parity stamps (okeechobee), freshness update (gulf)' },
    { title: 'Verify', detail: 'pencil_dod_evaluate_county for all 3 counties' },
  ],
}

const DISPATCH_ID = 'fd6f48d0-e8ef-411f-93ad-e77c345ae5ff'
const LOOP_RUN = 6046

const COUNTIES = [
  {
    slug: 'walton',
    brief_score: '9/10',
    failing: ['G'],
    G_detail: 'density=92.5 (new auctions: 46 vs 43 at 7th firing 2026-07-20)',
    target: '10/10',
    fix: 'zone_standards density backfill from WCCP FLU Element (Policy L-1.4.1/L-1.6.x)',
    honesty: 'INFERRED: which zone codes new parcels carry (cannot query EnerGov without live run)',
  },
  {
    slug: 'okeechobee',
    brief_score: '7/10',
    failing: ['C', 'D', 'I'],
    CD_detail: 'matched_clean=54 of 57 (94.7%) — 3 new auctions without parity stamps',
    I_detail: 'card_complete=52 of 57 (91.2%) — structural ceiling at 53/57=92.9%',
    target: '8/10 (I below 95% threshold)',
    fix: 'tier1_supplementary parity stamp for new rows; centroid backfill for I',
    honesty: 'INFERRED for C/D (assumes new rows have valid parcel_id); CONFIRMED ceiling for I (4 structural blockers exhausted)',
  },
  {
    slug: 'gulf',
    brief_score: '3/10',
    failing: ['B', 'C', 'D', 'E', 'F', 'H', 'I'],
    H_detail: 'hours since last_seen (88h, SLA 48h)',
    target: '4/10 (H flips, all other blockers structural)',
    fix: 'last_seen_at freshness update',
    honesty: 'VERIFIED for H (9 tax-deed rows + INFERRED for foreclosure rows); B/C/D/E/F/I confirmed structural (OCRS Turnstile, null-parcel cases, PSJ zoning ambiguity)',
  },
]

// WIRING: GHA workflow at .github/workflows/shard6-walton-okeechobee-gulf-fd6f48d0.yml
// (requires workflows permission to commit — deploy via GH_PAT_FULL with workflows permission)
// Migration: migrations/20260723_shard6_walton_okeechobee_gulf_fd6f48d0.sql
// Executor: scripts/shard6_fd6f48d0_walton_okeechobee_gulf_executor.py

export const workflow = {
  dispatch_id: DISPATCH_ID,
  loop_run: LOOP_RUN,
  counties: COUNTIES,
  artifacts: [
    'migrations/20260723_shard6_walton_okeechobee_gulf_fd6f48d0.sql',
    'scripts/shard6_fd6f48d0_walton_okeechobee_gulf_executor.py',
    'GOLD_STANDARD_SHARD6_WALTON_OKEECHOBEE_GULF_FD6F48D0_SESSION_REPORT.md',
  ],
  gha_workflow_pending: '.github/workflows/shard6-walton-okeechobee-gulf-fd6f48d0.yml',
  gha_note: 'Workflow file requires workflows permission (GitHub App lacks it). Deploy via GH_PAT_FULL.',
}
