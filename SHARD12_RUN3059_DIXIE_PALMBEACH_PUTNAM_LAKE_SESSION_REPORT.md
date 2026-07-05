# SHARD-12 run3059 (dixie / palm_beach / putnam / lake) — ULTRALOOP re-audit, zero letters flipped

dispatch_id: `2a410706-e983-4830-ab87-00708ce9ed77`
session: architect-20260705T000000
mode: ultracode Workflow tool (5 agents: 4 adversarial refuters fanned in parallel + 1 open investigator), logged `ultraloop_mode='native'`

## Method

Read the current failing letters for all four assigned counties directly from `pencil_dod_evaluate_county`, then read the evaluator function body (`pg_get_functiondef`) to understand exactly what C/D/E/I measure. Grepped git history and `supabase/migrations/` for each county's prior C/D work before touching anything — all four had already been through one or more ghost-success purge/re-audit cycles in the last 2 days (2026-07-03 through 2026-07-04). Ran a Workflow with one adversarial-refuter subagent per county's structural-ceiling claim (independent live queries, not trusting my own diagnosis), plus one open investigator on putnam's letter I (the one letter without a prior documented structural block).

## Verdicts (live, 2026-07-05T03:41Z)

**dixie C/D — SURVIVED.** 21/32 (65.6%), FAIL. Residual gap = 10 rows with synthetic `DIXIE-SYNTH-*` case numbers (auction_status mostly `cancelled`, zero corresponding row in `tax_deed_outcomes`/`foreclosure_outcomes` — independently re-checked, still zero) + 1 upcoming case that hasn't sold. Re-ran `refresh_parity_tier1_outcomes('dixie')` live: zero change. Matches the 2026-07-03/07-04 audited ceiling exactly.

**palm_beach C/D — SURVIVED (after adjudicating a contested refuter finding).** 430/688 (62.5%) and 442/688 (64.2%), FAIL. The refuter initially flagged 23 `upcoming` (unsold) rows matched via `refresh_palm_beach_parity_v2()` → `realforeclose_aids` as ghost-success, on the grounds that `realforeclose_aids` has no sold_amount/outcome column. I ran a second-order check before accepting that: canon and the evaluator SQL define C/D as *listing/case parity* (parity_status + parity_source only — no reference to sold_amount anywhere in the C/D computation), a distinct check from B/F (which explicitly require `tax_deed_outcomes`/`foreclosure_outcomes`). `realforeclose_aids` is confirmed genuinely independently-harvested (`scripts/realforeclose_aids_paginated_harvest.py`, real `case_clerk_url`/`parcel_assessor_url` pointing at `erec.mypalmbeachclerk.com`/`pbcpao.gov`), not a mirror of `multi_county_auctions`. **Broward currently PASSES C at 99.1% relying on the identical mechanism** (`refresh_broward_parity_v1`, uncontested across many prior sessions) — accepting the refuter's objection would retroactively invalidate an already-shipped, currently-passing county score. Verdict: the refuter's specific claim does not survive; no purge applied; the gap remains honestly 269 upcoming auctions (246 unmatched, structurally unmatchable pre-sale) out of 688 total, non-upcoming rows already 100% matched.

Flagged, not actioned (out of this session's scope): only 62 of 166 mca↔realforeclose_aids join pairs for palm_beach are exact case-number matches, the rest via fuzzy-substring or parcel-id-only branches — a fleet-wide matching-confidence question for `refresh_palm_beach_parity_v2`/`refresh_broward_parity_v1`, independent of upcoming-vs-closed status, worth a dedicated session.

**putnam C/D — SURVIVED.** 6/238 (2.5%), FAIL. Independently re-derived the 6-row ceiling (5 `tax_deed_outcomes` + 1 net-new `foreclosure_outcomes` match, union = 6, exact match to live DB). Separately confirmed the 217 rows tagged `parity_source='clerk_official_court_format'` have **zero** corroboration in `tax_deed_outcomes`, `foreclosure_outcomes`, or `realforeclose_aids` (exact and normalized case_number) — that classification (migration `20260619_shard2_putnam_cd_h_fix.sql`) was applied purely by string pattern (`case_number NOT LIKE 'PO-%'`), never by an actual cross-reference. Renaming these to a tier1-prefixed source (as was done for gulf/levy in `20260628_parity_source_tier1_prefix_17counties.sql` — putnam was correctly NOT included in that batch) would inflate C/D from 2.5% to ~93.7% with zero new verification work. **Not done.**

**putnam I — investigated, no fix exists this session.** 220/238 (92.4%), FAIL. 9 rows lack parcel_id entirely (no address data — previously diagnosed structural block, `20260704_shard5_gulf_i_regression_refix_putnam_cd_purge_e_fix.sql`). A further 6 rows have all 4 basic card fields (address/geo/value) but are absent from `v_zoning_gold_standard_card`: all 6 `parcel_id`s resolve correctly under the documented `fl_parcels.co_no = fl_counties.co_no + 10` offset (no offset bug), but 3 sit in Interlachen/Crescent City/East Palatka (zero `zoning_districts`/`parcel_zones` rows exist for those jurisdictions at all) and 3 sit in Palatka, which has a working but tiny partial ingestion (224 zoned parcels out of ~15,039 raw Palatka parcels in `fl_parcels`) that simply hasn't swept these 3 yet. No one-row fix exists; this needs new zoning-ingestion work (Phase 3/4 of the county-expansion pipeline), matching the fleet-wide G/I pattern already documented in CLAUDE.md.

**lake B/C/D/E/F — SURVIVED, zero drift from the 2026-07-03 audit.** All 97 in-scope lake auctions are `upcoming`/`cancelled` with zero `sold_amount` anywhere (B, F correctly null/FAIL — genuinely no closed sales exist yet). C=2/97 (2.1%), D=18/97 (18.6%) via `tier1_po_mca_match_lake_20260703`; the 38 `lake_pa_fieldmap_owner_name_v1` rows remain correctly un-promoted — re-confirmed the underlying "unsafe owner-name fuzzy matching" finding with a fresh live collision (two distinct cases/plaintiffs sharing the address `2205 PINK GRAPEFRUIT TRL` and near-identical owner name). E=67/97 (69.1%): 28 unlinked rows come from `lake_clerk_foreclosure_calendar_v1`, which never captures `property_address` (nothing to geocode), plus 2 synthetic test fixtures. Re-flagged (not actioned, needs Ariel's confirmation per the prior session's note): `LAKE-TD-SYNTH-SHARD6-001` is still sitting in `tax_deed_outcomes`, unlinked to any MCA row.

## BEFORE/AFTER (identical — zero drift, live `pencil_dod_evaluate_county`, 2026-07-05T03:41Z)

| county | before (brief) | after (this session) |
|---|---|---|
| dixie | 8/10 (C,D fail) | 8/10 (C,D fail) — unchanged |
| palm_beach | 8/10 (C,D fail) | 8/10 (C,D fail) — unchanged |
| putnam | 7/10 (C,D,I fail) | 7/10 (C,D,I fail) — unchanged |
| lake | 4/10 (B,C,D,E,F,I fail) | 4/10 (B,C,D,E,F,I fail) — unchanged |

12 rows logged to `gold_standard_ultraloop_audit` (dispatch_id above, `ultraloop_mode='native'`), all `survived=true`, refreshing the evidence window for all four counties' failing letters.

## No DDL/data changes this session

All actions were read-only verification via the Supabase Management API (`https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query`) and REST RPC, plus one canonical, idempotent `refresh_parity_tier1_outcomes()` re-invocation per county (confirmed no-op via before/after evaluator diff). No `multi_county_auctions`/outcome-table rows were modified. This documents those live actions per HARD GUARDRAIL #3.
