# GOLD STANDARD SHARD-4 — palm_beach / hernando / santa_rosa / martin

dispatch_id: `84d095d7-0a1a-46ee-b7aa-7ac21b7f06f7`
chat_session: `architect-20260718T160000`
loop_run: 4870

## Result summary (live `pencil_dod_evaluate_county`, verified 2026-07-18)

| County | Before | After | Delta |
|---|---|---|---|
| palm_beach | 10/10 | 10/10 | already gold — no changes needed, re-confirmed clean |
| hernando | 8/10 | 8/10 | no change — B/F re-confirmed structurally blocked |
| santa_rosa | 7/10 | **9/10** | C, D flipped PASS |
| martin | 5/10 | **7/10** | C, D flipped PASS |

## What moved

### santa_rosa: C 89.5%→100%, D 89.5%→100%
9 rows had never been through the parity matcher (`parity_status IS NULL`, `data_source='calendar_sweep_mca_v3'`) — fresh calendar-sweep ingests across 3 (sale_type, auction_date) buckets not yet harvested by the AJAX matcher. Ran `scripts/shard11_run3534_santa_rosa_cd_harvest.py` against the live `santarosa.realforeclose.com` / `santarosa.realtaxdeed.com` AJAX calendar for 2026-07-21 (foreclosure), 2026-07-28 (foreclosure), 2026-08-24 (tax_deed). All 9 exact-case-number matched; `parity_status='matched_clean'`. Zero fabrication — every matched row traces to a live calendar item.

### martin: C 83.8%→97.3%, D 83.8%→97.3%
6 rows unmatched (5 `parity_status IS NULL`, 1 `mca_only`). Ran the same AJAX harvester against `martin.realforeclose.com` for 2026-07-14 and 2026-09-01 (foreclosure). 5/6 matched; the 6th (tax_deed case `2024-001-TD-MARTIN`, auction_date 2026-08-15) returned 0 items from the live calendar for that date and remains unmatched — left as-is, not fabricated.

**Bug caught by adversarial review and fixed live:** the first pass of this fix reused `shard11_run3534_santa_rosa_cd_harvest.py`'s hardcoded parity_source label text unmodified, so the 5 newly-matched martin rows initially carried `tier1:shard11_run3534_santa_rosa_ajax_harvest:...` — a foreign county's name in the provenance string, even though the underlying match logic was correctly scoped to `county='martin'`. A refuter subagent caught this from a cross-county `parity_source` audit. Relabeled all 5 rows live to `tier1:shard4_84d095d7_martin_ajax_harvest:<sale_type>:<auction_date>`; a second independent refuter pass confirmed the corrected labels are internally consistent (embedded sale_type/date match the real columns) and the case numbers are genuinely martin-native (zero overlap with santa_rosa's case_number set).

Also geocoded 5 of those newly-matched martin rows (real street addresses existed, only lat/lng was missing) via the free US Census geocoder — `scripts/shard4_martin_geocode_backfill.py`. This does not move any letter on its own (martin I is capped far below this by a structural zoning-ingestion gap, below) but is real, verified, government-sourced data now on the row.

## What's genuinely blocked (confirmed, not fabricated)

- **hernando B/F**: all 49 hernando rows are `auction_status='upcoming'`, `sold_amount IS NULL` — `closed_sold=0` fleet-wide, so B/F are structurally undefined (null denominator), not FAIL-with-a-fixable-gap. Independently re-probed the live `hernando.realtaxdeed.com` AJAX preview for a now-past tax-deed date (2026-07-15, 3 days stale) and found no `SOLDTO`/results text — the source genuinely does not expose post-auction results via this endpoint. Matches and reconfirms the prior 2026-07-10 session's identical finding, now re-verified independently after more elapsed time.
- **santa_rosa I** (81.4%, 70/86, need ≥82/86): 13 of the 16 gap rows have a real `parcel_id` that is simply not present in `v_zoning_gold_standard_card` — confirmed via ILIKE search that no format/matching bug is hiding the row (94 real zoning-card rows exist for santa_rosa, these 13 parcels are genuinely absent). Needs a dedicated zoning-ingestion (parcel_zones) session for those specific parcels.
- **martin E** (91.9%, 34/37, need ≥36/37): the 3 remaining NULL-`parcel_id` rows (`23001555CCAXMX`, `25001634CCAXMX`, `25001632CCAXMX`) carry zero usable metadata — no `owner_name`, `plaintiff`, or `legal_description`, only a generic city-level placeholder address (`"Stuart, Martin County, FL 34997"`). A quick attempt against `martinclerk.com`'s case-search endpoint did not yield a scriptable API in the time available. Needs a dedicated Martin Clerk case-detail scrape.
- **martin I** (40.5%, 15/37, hard ceiling): `v_zoning_gold_standard_card` has only **15 total rows** for the entire county — every one of them already backs a complete card. This is the same Phase-4 zoning-ingestion coverage gap pattern documented for hernando on 2026-07-10, now confirmed for martin too. No amount of row-level linkage/geocoding work can move this further without real zoning-district/parcel_zones ingestion.
- **martin J** (89.2%, 33/37): the 4 newly-linked rows have no `bid_decisions` yet. Deliberately declined to reuse the prior `shard12_run1113` martin fix's pattern (a `HYPOTHESIS`-tagged `assessed_value*1.2` synthetic ARV formula) — that pattern is the likely reason martin's zoning/card data was later partially purged from a prior session. `public.gen_valuations_comps_batch()` (the legitimate per-2-min rearmer) can't pick these up yet: only 1 of the 5 affected parcels exists in `public.parcels` at all. Needs the real Shapira/CMA generator once canonicalization catches up.

## Verification (ULTRALOOP PROTOCOL)

Ran a `Workflow` fan-out of 7 independent adversarial refuter subagents (one per claim), then a follow-up single refuter after fixing the martin provenance bug the first pass caught. All 7 original claims + the 1 follow-up claim ended `survived=true`; **1 of the 7 original claims (martin C) was `refuted=true`** on its first pass — for a real provenance-labeling bug, not a fabricated metric — and was fixed live before being re-submitted and surviving.

16 rows written to `public.gold_standard_ultraloop_audit` (dispatch `84d095d7-...`, `ultraloop_mode='native'`): santa_rosa C/D, martin C/D (both `survived=true`, martin's evidence field documents the 2-pass refute/fix/re-verify), hernando B/F, and palm_beach A–J (10 rows, confirming the pre-existing 10/10 with no anomalous ratios).

## Honesty markers

- All C/D/I/J/E numbers above are **VERIFIED** — read live from `pencil_dod_evaluate_county` and cross-checked with direct row queries, both by this session and by independent refuter subagents.
- No zone_standards, ARV formulas, case data, or parcel IDs were fabricated this session.
- No `pipeline.counties` notes update was completed (intermittent Cloudflare WAF block on the Supabase Management API, `error code 1010`, non-critical) — the audit trail lives in this file, the linked session-log YAML, and `gold_standard_ultraloop_audit`.
- Did not run `gold_standard_loop()` / `gold_standard_certify()` per the PARALLEL-FLEET RULES (other shards may be mid-flight this session) — reported per-county `pencil_dod_evaluate_county` evaluations only.

## Next-session priorities (for whichever shard picks these counties up next)

1. **martin/santa_rosa I**: real zoning-ingestion session — jurisdictions/zoning_districts/parcel_zones for the specific unmatched parcels (13 in santa_rosa, all of martin beyond the existing 15). Ordinance-text values only, honesty markers, no guessing (per the G DIAGNOSIS precedent).
2. **martin E**: Martin Clerk case-detail scrape for 3 case numbers with zero metadata, to recover a real address before parcel-matching.
3. **martin J**: once #1 lands (parcel canonicalization), re-run `gen_valuations_comps_batch()` and the real Shapira/CMA generator for the 4 newly-linked rows — do not fabricate.
4. **hernando B/F**: revisit only if/when hernando's upcoming auctions actually close (no current action possible — genuinely future-dated data).
