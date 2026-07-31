# Gold Standard Shard-3 — hillsborough / alachua / dixie

dispatch_id: e2353eb4-f852-4723-b4b4-aab3cf9c1987
chat_session: architect-20260731T080000
loop run: 7622
mode: ULTRALOOP fallback (manual Task/Workflow fan-out — no `/effort ultracode` menu available in this
environment; recorded as `ultraloop_mode='fallback'` per protocol)

## Scoreboard (live, VERIFIED via `pencil_dod_evaluate_county`, all queries run this session)

### hillsborough — 10/10, UNCHANGED, no action taken
Certified under an active `gold_standard_cert_scope` freeze (snapshot_at
2026-06-24T00:02:01.322442+00:00, rationale "SUMMIT #8144 beta-6-county"). Scoped evaluation is byte-identical
to the brief and to a fresh unscoped-vs-scoped comparison run at session start:
```
A PASS 362 [fc=529 td=362]        F PASS 100.0 [tier1_sold=187 closed_sold=187]
B PASS 100.0 [verified=187/187]   G PASS 95.6  [density=95.6 pk1000=100.0]
C PASS 100.0 [matched_clean=891]  H PASS 0.6   [hours since last_seen]
D PASS 100.0 [matched_any=891]    I PASS 96.7  [card_complete=862 of 891]
E PASS 97.2  [parcel_linked=866]  J PASS 100.0 [deal_complete=891]
```
The unscoped live view shows I dipping to 93.6% (938-row denominator, backfill accrual since the snapshot) —
per Evaluator V6 rules this does **not** move the certified score; denominators are frozen. No work needed,
no files touched for this county this session.

### alachua — 8/10, UNCHANGED (E, I confirmed still genuinely blocked)
```
BEFORE: E FAIL 82.8 [parcel_linked=48]     I FAIL 82.8 [card_complete=48 of 58]
AFTER:  E FAIL 82.8 [parcel_linked=48]     I FAIL 82.8 [card_complete=48 of 58]
```
Byte-identical before/after. Fresh re-verification (not a carry-over — re-ran the AJAX docid harvest, the
ArcGIS owner-match query, and the qpublic probe live this session) confirms the exact same 10-row gap
diagnosed 8 hours earlier this same day (commit `8b992c3b`): 8 rows with empty Clerk docid, 1 row with an
unresolvable 2-parcel ArcGIS owner-match ambiguity, 1 row spanning a "MULTIPLE PARCEL" legal description.
Zero rows writable without fabrication. One new lever attempted (FL GIO Statewide Cadastral OWN_NAME query as
an independent disambiguator) — timed out, inconclusive, worth retrying next session.
Migration: `supabase/migrations/20260731c_shard3_alachua_ei_freshness_recheck_no_change.sql`
Audit: `gold_standard_ultraloop_audit` ids **11591** (E, survived=true), **11592** (I, survived=true).

### dixie — 8/10, I MOVED (0.0% → 94.1%, still FAIL by 2 rows), C/D UNCHANGED
```
BEFORE: I FAIL 0.0  [card_complete=0 of 34]     C FAIL 73.5 [matched_clean=25]   D FAIL 73.5 [matched_any=25]
AFTER:  I FAIL 94.1 [card_complete=32 of 34]    C FAIL 73.5 [matched_clean=25]   D FAIL 73.5 [matched_any=25]
```
**I fix (real, adversarially verified):** root cause was missing geo/value on 32 of 34 rows (zoning-side card
substrate was already fine — 32 parcels correctly zone-linked via jurisdiction "Cross City"). Backfilled
`latitude`/`longitude`/`assessed_value` (and `property_address` for the one row missing it) for all 32 target
rows via a **live direct query against the FL GIO Statewide Cadastral ArcGIS FeatureServer** (`CO_NO=25` for
Dixie, dash-stripped `PARCEL_ID`) — bypassing our internal `fl_parcels` mirror, which has zero Dixie rows
(never ingested; a pre-existing, separately-documented dead end). 32/32 parcels returned an exact single
ArcGIS match; all 32 written. Zero fabrication: refuter independently spot-checked 33/33 rows for distinct
lat/lon (explicitly checking for the county-centroid-placeholder failure mode a prior session caught and
purged here — none found), and re-verified one clustered-value sample (9 rows sharing JV=6500, confirmed as
genuinely distinct adjacent platted lots, not a placeholder) against the live ArcGIS source to full decimal
precision. Residual 2/34 gap is genuinely structural and out of this fix's scope (one row has no parcel_id at
all; one row's parcel is simply absent from `v_zoning_gold_standard_card` — fixing that requires
parcel_zones/zoning_districts work, explicitly barred from this task).
Migration: `supabase/migrations/20260731b_shard3_dixie_i_arcgis_geo_value_backfill.sql`
Audit: `gold_standard_ultraloop_audit` id **11586** (I, survived=true).

**C/D (no change, reconfirmed):** the 9-row gap (6 `DIXIE-SYNTH-` tax-deed rows tagged
`parity_scope='archive_no_source_truth'`, 1 past-due foreclosure case `15-2023-CA-57` now 10 days past sale
with no disposition anywhere on dixieclerk.com, 2 genuinely-future cases correctly excluded) has been worked
by many independent prior sessions and remains blocked on a confirmed Cloudflare-Turnstile-gated Official
Records search (out of bounds to bypass). This session's fresh angle — a direct Firecrawl API scrape to get
past WebFetch's static-HTML limitation on dixieclerk.com's tax-deed page — hit a genuine `HTTP 402
insufficient credits` wall, not a workaround. Structural ceiling remains 32/34 = 94.1% even in the best case.
Migration: `supabase/migrations/20260731_shard3_dixie_cd_freshness_recheck_no_change.sql`
Audit: ids **11558/11559** (fix-agent's own logged check) and **11588** (+11589 for D, refuter's independent
re-confirmation) — all survived=true.

## Also verified live (flag, not fixed — out of this shard's letter targets)
**dixie J is a known live ghost-success**, unrelated to this session's work: `bid_decisions` rows for dixie
case_numbers show only 7 distinct (arv, max_bid) pairs across 2,754 rows — a shared placeholder pattern from
the mechanical comps job (`gen_valuations_comps_batch`, cron 109), already flagged by a prior session
(`20260727c_shard7_dixie_ij_new_source_search_no_change.sql`) as ghost and never resolved (same root cause as
the pre-fix I gap: `fl_parcels` has zero Dixie rows, so no real per-parcel comps can be produced). J still
numerically PASSes (100%) in `pencil_dod_evaluate_county` because the SQL evaluator does not itself detect
placeholder patterns — that is exactly what the ULTRALOOP audit layer is for. **Do not certify dixie based on
J's raw PASS** without treating this as an open, unresolved ghost-success. Per guardrails, cron 109 was not
touched and no fix was attempted this session (out of scope for this shard).

## Concurrency note
14 `summit_chat_dispatch` rows fired simultaneously at 2026-07-31T08:00:00Z (this shard is one of them). Per
PARALLEL-FLEET RULES, `public.gold_standard_loop()` / `gold_standard_certify()` were **not** run — only
per-county `pencil_dod_evaluate_county` calls, scoped to this shard's 3 counties.

## Files this session
- `supabase/migrations/20260731_shard3_dixie_cd_freshness_recheck_no_change.sql`
- `supabase/migrations/20260731b_shard3_dixie_i_arcgis_geo_value_backfill.sql`
- `supabase/migrations/20260731c_shard3_alachua_ei_freshness_recheck_no_change.sql`
- This report.

## Next-session priorities
1. **dixie I**: 32/34 is the honest ceiling until `v_zoning_gold_standard_card` gets a link for
   `27-10-13-5568-0000-0480` (parcel_zones/zoning_districts work, separate letter G/I substrate task) and/or
   `15-2025-CA-46` acquires a parcel_id.
2. **dixie J**: real fix requires either the broken `ingest_county.py` CI secret (cross-cutting, not
   shard-scoped) or populating `fl_parcels` for Dixie by some other path — until then J stays ghost.
3. **alachua E/I**: retry the FL GIO Statewide Cadastral `OWN_NAME` disambiguation lever with a longer
   timeout/off-peak — it timed out both attempts this session without confirming or refuting.
4. **dixie C/D**: structural ceiling 94.1% unless Civitek OCRS Turnstile is ever resolved by the owner
   (out of bounds for an agent session) or dixieclerk.com starts publishing outcomes.
