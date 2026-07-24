# Gold Standard shard-10: alachua — session report
(dispatch `a36233a1-0145-43b9-a8f0-75acc7594181`, loop run 6253, chat session `architect-20260724T160000`)

## Result: alachua 4/10 -> 7/10 live, verified

```
BEFORE: A pass B pass C fail(83.9) D fail(83.9) E fail(85.7) F fail(87.5) G pass H pass I fail(71.4) J fail(83.9)
AFTER:  A pass B pass C pass(100)  D pass(100)  E fail(76.8) F pass(100)  G pass H pass I fail(71.4) J fail(83.9)
```

Full before/after JSON pasted below (### SQL VERIFICATION).

## F: fixed (87.5% -> 100%)

Case `01 2025 CA 002830` carried `sold_amount=174416.2` while its `auction_date` was
2026-08-27 (34 days in the future of this session) and its `foreclosure_outcomes` row
(`data_source=realforeclose:alachua:shard5_run581`) had `winning_bid IS NULL` — no backing
outcome anywhere. Live-reharvested `alachua.realforeclose.com`'s own AJAX calendar for
8/27/2026 (`scripts/shard2_run2450_ajax_realforeclose_harvest.py`) and confirmed the case is
genuinely still listed upcoming with no sale-result field at all — ruling out a hendry-style
genuine dual-source conflict (there is no second live source claiming this case already sold).
The value also doesn't match judgment_amount/opening_bid/assessed_value/market_value on the
same row, ruling out a simple column-aliasing bug. Nulled `sold_amount` (not fabricated a
matching tier1 value). Verified live post-fix: `tier1_sold=7 closed_sold=7`.

## E: honest correction, not a fix (85.7% -> 76.8%)

Found `parcel_id='Property Appraiser'` — RealForeclose's own link-text placeholder, not a real
ID (already flagged as a known bad value by `scripts/shard14_run121fa7c3_alachua_e_i_diagnosis.py`)
— literally stored on 6 alachua rows. E's reported 85.7% (48/56) was silently inflated by these
6 ghosts. Root cause: these rows predate the `_clean_parcel()` validation added to
`.github/scripts/calendar_sweep_mca.py` in commit `8e13f266` ("v3.0"); because the sweep's
`columns=`-scoped upsert only writes fields *present* in the current scrape and never
force-nulls an absent field, stale pre-v3.0 garbage is never cleared by later (correctly
behaving) sweep runs.

- `01 2024 CA 001683`: RESTORED to `02975-002-000`, the previously real-verified value from
  `scripts/shard10_run3645_alachua_e_parcel_backfill.py` (ArcGIS PublicParcel FeatureServer
  unique match on a recorded judgment's grantee name). This fix had silently reverted to the
  ghost placeholder since that script ran — re-applied, not re-derived.
- `01 2025 CA 002830`: `parcel_id` nulled; `latitude`/`longitude` also nulled — `29.6516`/
  `-82.3248` is a shared county-centroid fallback (confirmed carried by **40** separate alachua
  rows, i.e. not a real per-property geocode). `property_address` and `assessed_value` kept
  (row-unique values — real scraped data, not part of the same fallback).
- `01 2025 CA 001634`, `01 2025 CA 003156`, `01 2023 CA 004261`, `01 2024 CC 005935`:
  `parcel_id` nulled, no real replacement found this session (BLANK > WRONG, not fabricated).

Net: E moved from a ghost-inflated 85.7% to a true 76.8% (43/56). **This is a regression in the
reported number and an improvement in its truthfulness** — the pre-fix 85.7% was never real,
and per the ULTRALOOP protocol's own stated purpose (catching exactly this class of anomaly),
disclosing and correcting it is the deliverable, not a setback to be hidden.

Residual: 13 rows genuinely lack parcel_id. Of these, 7 were live-reconfirmed this session
(`isol.alachuaclerk.org` docid empty on RealForeclose's own AJAX payload for all 7 target
auction dates) as having no clerk cross-reference document yet, and 1 (`01 2025 CA 003287`) is
a confirmed multi-parcel case with no single correct parcel_id assignable without fabrication —
both dead ends matching the prior diagnosis exactly, not re-litigated further.

## C/D: fixed (83.9% -> 100% each)

9 rows had `parity_status IS NULL` (6) or a non-tier1 `parity_source`
(`realforeclose_aids_patch`, 3) — both fail the evaluator's `parity_source LIKE 'tier1%'`
predicate regardless of match quality. Forked
`scripts/gold_standard_shard6_polk_cd_i_ajax_harvest.py` (itself forked from
shard11/leon, shard2/palmbeach, shard4/leon — an established pattern shipped by multiple prior
shard sessions and never reverted per git log) as
`scripts/gold_standard_shard10_alachua_cd_ajax_harvest_run6253.py`, re-harvested
`alachua.realforeclose.com`'s live AJAX calendar for each target row's own auction_date
(2026-08-11, 2026-08-18, 2026-08-27, 2026-09-01 — all confirmed live 2026-07-24), exact-matched
by normalized case_number, and promoted all 9/9 matches (every target case is genuinely present
on the live calendar) to `parity_status='matched_clean'`,
`parity_source='tier1:shard10_run6253_alachua_ajax_harvest:<sale_type>:<date>'`. No
PropertyOnion data touched — RealForeclose is the primary source these rows were already
scraped from, re-confirmed live against the county's own site.

## I / J: confirmed genuinely blocked, not attempted further

- I (`card_complete=40/56`, need 53/56): bounded by the same 13 E-unlinked rows (card requires
  `parcel_id` resolvable in `v_zoning_gold_standard_card` with a real `zone_code`) — per the
  documented dependency chain (I <= E by construction), I cannot move further until real parcel
  linkage exists for those rows. Not attempted (would require the same clerk-cross-reference
  documents confirmed absent above).
- J (`deal_complete=47/56`, need 53/56): of the 9 pre-existing gap rows, 3 (`01 2025 CA 003156`,
  `01 2023 CA 004261`, `01 2024 CC 005935`) have no `parcel_id` **and** no
  `assessed_value`/`market_value`, so
  `scripts/gold_standard_shard9_broward_alachua_j_generator_real.py`'s `real_arv()` has no real
  ARV input to use for them; the other 6 J-gap rows are the same 6 still-unlinked-E rows. Did
  not run the generator (confirmed it would be a no-op for all 9 — verified by inspecting its
  `real_arv()` fallback chain against these rows' actual column values, not assumed).

## ULTRALOOP audit trail

`ultraloop_mode='fallback'` (this session ran manual fan-out diagnosis/fix/self-adversarial-
check rather than a spawned workflow — bounded interactive session, not a fresh /effort
ultracode menu). 4 rows logged to `gold_standard_ultraloop_audit`
(dispatch `a36233a1-0145-43b9-a8f0-75acc7594181`), one per letter (F, E, C, D), each
`survived=true` with the raw-query evidence quoted in `refuter_evidence`. Self-adversarial pass
performed on each claim before logging (see refuter_evidence text) — in particular, verified the
F case wasn't a hendry-style genuine dual-source conflict before nulling it, and verified the
C/D fix pattern (exact-match against the primary RealForeclose source, not PropertyOnion) is the
same convention multiple prior shard sessions shipped and which has never been reverted.

### SQL VERIFICATION

```
BEFORE (public.pencil_dod_evaluate_county('alachua'), 2026-07-24T16:0x:xxZ):
{"A":{"pass":true,"metric":3,"detail":"fc=53 td=3"},
 "B":{"pass":true,"metric":100,"detail":"verified=8 closed_sold=8"},
 "C":{"pass":false,"metric":83.9,"detail":"matched_clean=47"},
 "D":{"pass":false,"metric":83.9,"detail":"matched_any=47"},
 "E":{"pass":false,"metric":85.7,"detail":"parcel_linked=48"},
 "F":{"pass":false,"metric":87.5,"detail":"tier1_sold=7 closed_sold=8"},
 "G":{"pass":true,"metric":97.9,"detail":"density=97.9 far= pk1000="},
 "H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":71.4,"detail":"card_complete=40 of 56"},
 "J":{"pass":false,"metric":83.9,"detail":"deal_complete=47 ..."},
 "county":"alachua","auctions_total":56}

AFTER (public.pencil_dod_evaluate_county('alachua'), 2026-07-24T16:2xZ):
{"A":{"pass":true,"metric":3,"detail":"fc=53 td=3"},
 "B":{"pass":true,"metric":100,"detail":"verified=7 closed_sold=7"},
 "C":{"pass":true,"metric":100,"detail":"matched_clean=56"},
 "D":{"pass":true,"metric":100,"detail":"matched_any=56"},
 "E":{"pass":false,"metric":76.8,"detail":"parcel_linked=43"},
 "F":{"pass":true,"metric":100,"detail":"tier1_sold=7 closed_sold=7"},
 "G":{"pass":true,"metric":97.9,"detail":"density=97.9 far= pk1000="},
 "H":{"pass":true,"metric":0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":71.4,"detail":"card_complete=40 of 56"},
 "J":{"pass":false,"metric":83.9,"detail":"deal_complete=47 ..."},
 "county":"alachua","auctions_total":56}
```
Both queries run live against `mocerqjnksmhcjzxrewo.supabase.co` via the Management API
(`python3 mgmt_sql.py`) this session, 2026-07-24.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| E parcel linkage (highest-leverage per brief's dependency chain) | Fix new unlinked rows | Confirmed 7 of 8 genuinely blocked (no clerk cross-ref doc); found and purged a separate 6-row ghost-placeholder bug instead | Pivoted to the real, fixable bug found during diagnosis rather than forcing an unfixable one |
| J generator | Run for gap rows | Did not run — confirmed by column inspection it would be a no-op for all 9 rows (no real ARV input) | Avoided wasted/no-op execution, documented as residual |
| F/C/D | Not in original per-letter plan priority (brief listed E as top lever) | F, C, D all fixed | Found tractable, high-confidence real fixes for these while E was confirmed blocked |

## Next-session priorities

1. **I**: blocked on the same 13-row E gap; also check `v_zoning_gold_standard_card` coverage
   independently once/if any of those rows get real parcel linkage.
2. **J**: same 6-row E-dependency; the 3 non-E rows (`003156`, `004261`, `005935`) need a real
   assessed_value/market_value source (BCPAO or similar) before the Shapira generator can run
   for them.
3. **E**: the 7 confirmed-blocked rows need either (a) waiting for the clerk to cross-reference
   a recorded judgment doc (re-check docid periodically, cheap), or (b) a different linkage
   method entirely (owner-name/address match against the Alachua ArcGIS PublicParcel
   FeatureServer once/if RealForeclose ever publishes a real property_address for them — 6 of
   the 7 currently have neither).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
