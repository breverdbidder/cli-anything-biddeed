# Gold Standard shard-1 — brevard / manatee / walton / highlands / liberty

dispatch_id: `87096f0f-276d-4331-9205-2cab62559d15` · loop run 14047 · chat_session `architect-20260824T160000`

## Status board (live `pencil_dod_evaluate_county`, before → after)

| County | Before | After | Notes |
|---|---|---|---|
| brevard | 9/10 (I fail) | 9/10 (I fail) | I improved 85.3%→85.8% (6225→6265 of 7298), real fixes, still short of 95% |
| manatee | 9/10 (C fail) | 9/10 (C fail) | C unchanged 93.4% (155/166) — 11-row gap confirmed genuinely blocked, no fabrication |
| walton | 9/10 (I fail) | 9/10 (I fail) | I improved 87.6%→94.1% (134→144 of 153), 2 rows short of PASS |
| highlands | 8/10 (C, D fail) | **10/10 — all letters PASS** | C 94.8%→96.5%, D 94.8%→97.0%, both FLIPPED to PASS |
| liberty | 7/10 (A, B, F fail) | 7/10 (A, B, F fail) | Confirmed genuinely accrual-gated, fresh re-check post sale-date-passage |

Live numbers pulled directly from `pencil_dod_evaluate_county` via PostgREST RPC at session start and re-confirmed after all fixes (both times independently, not trusted from agent self-report). Note the brief's snapshot numbers were already slightly stale vs live at session start (e.g. brevard denominator grew 7099→7298 auctions) — all work below is against the live-verified baseline, not the brief's numbers.

## Method: ULTRALOOP (ultracode fan-out)

One Workflow (`wf_1d4b4f65-f13`) ran 5 diagnose+fix agents in parallel (one per county-letter target, each briefed with the exact prior-session scripts for that letter so it wouldn't repeat known dead ends), followed by 5 independent adversarial refuter agents whose only job was to try to break each claim. **All 5 claims survived refutation** — zero regressions, zero anomalies (no metric >100%, no denominator/numerator mismatches), all row-level fixes independently re-verified against the live external source (not just the DB).

## What actually moved

### highlands C+D: 94.8% → 96.5% / 97.0% — FLIPPED TO PASS (highlands now 10/10)
Root cause: `highlands.realtdm.com`'s clerk parser only queried the "Active" status filter, so 9 tax-deed cases that had progressed to *Active-Redemption*, *Active-Resale 30day*, or *Canceled-Reschedule* on the clerk's own system were mislabeled `PHANTOM_NOT_ON_CLERK` by the phantom-detection heuristic — even though they're genuinely live/resolved cases. Fix: query realtdm.com with no status filter, cross-verify parcel_id + auction_date against our DB for all 9, apply the evaluator-recognized label (`matched_clean`/tier1 for the 7 still-active, `CLERK_SSOT_CANCELLED` for the 2 truly cancelled). Script: `scripts/highlands_cd_realtdm_active_redemption_fix.py`, commit `c02d8c75`.

Refuter independently reproduced the exact live realtdm.com XHR query (POST + `X-Requested-With` header, unfiltered status) across 9 paginated pages and matched all 9 case statuses/parcel_ids/auction_dates field-for-field. **SURVIVED.**

**Note:** highlands is now live 10/10 across all A–J. This does **not** mean CERTIFIED — per the evaluator V6 rule, certification requires `survived=true` ultraloop_audit rows for **all 10 letters** within a rolling 7-day window, and this session only refreshed C/D. I did not run `gold_standard_certify()` (per PARALLEL-FLEET RULES — other shards were confirmed mid-flight, see below). Flagging this for the certifying session: highlands' other 8 letters need a fresh audit-freshness check within 7 days to actually clear the cert gate.

### brevard I: 85.3% → 85.8% (6225→6265 of 7298), still FAIL
Two new, previously-untried levers this session (6 prior brevard-I scripts had already exhausted BCPAO NAL/GIS/geom-centroid approaches):
- `scripts/brevard_i_cocoa_countyzoning_backfill_e91f7a52.py` — City of Cocoa ArcGIS Online `Cocoa_Zoning_with_Split_Lots` FeatureService + Brevard `Zoning_WKID2881` MapServer point-in-polygon, for 7 zone-unlinked condo/split-lot parcels (1 hit a genuine unique-constraint conflict on a real second zone for a split-lot parcel — documented, not a bug).
- `scripts/brevard_i_clerk_platform_legal_backfill_e91f7a52.py` — AcclaimWeb legal-description (LT+PB+PG) → gis.brevardfl.gov parcel lookup, for 35 rows missing parcel_id/address/geo/assessed_value.

42 rows fixed total. **Structural finding:** the remaining ~879-927 row gap is `STREET_NAME=UNKNOWN` vacant land in Brevard's own authoritative GIS parcel layer — confirmed by this session and 4 prior sessions since 2026-08-10 to be a real data absence, not a scrape gap. Separately: `gold_standard_exclusions` (4,016 brevard rows tagged redeemed/cancelled) is **not actually consulted** by the live `pencil_dod_evaluate_county()` RPC — applying it would make I *worse* (74.7%), since excluded rows are disproportionately more complete than the active population. Reported against the RPC's real live formula, not the brief's stated exclusion rule.

Refuter re-queried the Cocoa FeatureService and Brevard MapServer live and matched both zone codes exactly, including reproducing the split-lot 409 conflict. **SURVIVED.**

### walton I: 87.6% → 94.1% (134→144 of 153), still FAIL by 2 rows
`scripts/gold_standard_walton_i_letter_run_85f2942e.py` — Walton EnerGov ArcGIS (Layers 4/9/19/1) + FL DOR Statewide Cadastral backfill, 11 rows fixed. Remaining 9 rows genuinely blocked: 1 parcel has zero situs address across 3 independent sources (vacant land), 8 cases have no reachable parcel_id anywhere (scrape-artifact placeholders, HTTP 403, non-scrapeable JSF forms, or a scanned-image PDF with no text layer).

Refuter live-queried the actual EnerGov endpoint for 2 spot-checked parcels — both matched DB `assessed_value` exactly ($15,200 and $400,000), and confirmed the zoning-link inserts carry the dispatch ID + today's date (not fabricated). **SURVIVED.**

### manatee C: unchanged 93.4% (155/166), FAIL confirmed genuine
All 11 gap rows carry `parity_status='CLERK_SSOT_CANCELLED'` — the evaluator (migration `20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`) intentionally counts these toward `matched_any` (D passes 100%) but not `matched_clean` (C), same class as `matched_divergent`. Live re-check against Manatee Clerk's own foreclosure-sales page confirms all 11 are genuinely cancelled (`CANCELLED ONLINE`) right now. This is the identical fact pattern already adjudicated for st_lucie's C letter. No PATCH issued — forcing a flip would require fabricating a status that isn't true. `V2_LITMUS` is null for manatee (no PropertyOnion litmus row exists for this county), so this isn't even a PropertyOnion-coverage question.

Refuter independently re-ran the manatee clerk parser against the live `records.manateeclerk.com` endpoint for all 11 case numbers — all returned `CANCELLED ONLINE` with matching sale dates. **SURVIVED.**

### liberty A/B/F: unchanged, FAIL confirmed genuine (fresh re-check)
Prior finding (SHARD14_RUN3534, dispatch `121fa7c3`) found liberty "genuinely accrual-gated" with the single tracked case (24-CA-22) unsold and a future sale date of 2026-07-21. That date has now passed (today is 2026-08-24), so this session re-verified fresh rather than assuming the prior finding still holds:
- The case fell off `libertyclerk.com`'s forward-looking calendar as expected post-sale-date — but the clerk's site has **no outcomes/archive page at all**, so no sale result was ever posted anywhere. `sold_amount` remains NULL, `foreclosure_outcomes` has 0 rows for this case.
- Tax deed listings remain at zero — verbatim identical page text to every prior check.
- `myfloridacounty.com` Official Records search (the one new lead from the 2026-08-01 session) is confirmed Turnstile-gated on the actual search action, and structurally unsuited even if unblocked (party-name/document-type/date-range search, no case-number field, no distinct "Certificate of Title" doc type).
- Liberty is FL's least-populous county (~8,000 residents) and does not reliably generate a second row/closed case/sold outcome on any predictable timeline.

No fabricated row, outcome, or listing was written. Refuter independently re-curled all 5 cited source URLs and the two DB tables — zero discrepancies. **SURVIVED.**

## Verification evidence

- ULTRALOOP Workflow `wf_1d4b4f65-f13`: 10 agents (5 diagnose+fix, 5 refute), 411 tool calls, ~1.04M subagent tokens.
- 8 rows written to `gold_standard_ultraloop_audit` (dispatch_id `87096f0f-276d-4331-9205-2cab62559d15`, `ultraloop_mode='native'`), all `survived=true`.
- Live `pencil_dod_evaluate_county` re-run for all 5 counties immediately before writing this report — confirmed **zero drift** from the workflow's own post-fix numbers, and no regression on any previously-passing letter across all 5 counties.
- `gold_standard_campaign` row `id=4958` updated with `criteria_passed` (full A–J map per county), `criteria_total=10`, `exit_reason='timeout'`, `session_end_at`.
- No `gold_standard_loop()` / `gold_standard_certify()` run this session — other shards were confirmed mid-flight (commits `252e6159` bradford/lake and `128ea20a` landed on `origin/main` between this session's start and its close-out), per PARALLEL-FLEET RULES.
- All script writes committed to git and pushed to `origin/main`: `c02d8c75` (highlands), `0793f18f` (manatee investigation), `b5442e3d` (brevard + walton, this session's own commit after a `git pull --rebase` to absorb the two commits that landed mid-session).

## Guardrail compliance

- No PropertyOnion data ingested or treated as anything but litmus (manatee's `V2_LITMUS` is null — not used at all).
- No fabricated parcel_id, address, zone code, sale outcome, or tax-deed listing. Every write traces to a live-queried, independently-reproducible external source (Cocoa/Brevard/Walton ArcGIS FeatureServers, AcclaimWeb, FL DOR Cadastral, realtdm.com).
- Liberty's structural conclusion was re-earned fresh this session (not copy-pasted from the prior finding) specifically because the prior finding's stated future sale date had passed.
- Fail-loud honored throughout: every genuinely-blocked row is documented with source-level evidence, not silently dropped.

## Residual work for next session

- **highlands**: needs a 7-day audit-freshness refresh across all 10 letters (not just C/D) before `gold_standard_certify()` can actually clear it — flagging this explicitly so the next certifying session doesn't skip the gate.
- **brevard I**: 879-927 row ceiling is `STREET_NAME=UNKNOWN` vacant land in Brevard's own GIS — needs either a new address source (E911/county road-naming records) or a policy call to exclude unaddressed vacant land from the I denominator.
- **walton I**: 2 rows short of PASS; remaining 9-row gap is genuinely blocked (no address/parcel_id reachable) — would need manual courthouse record lookup, out of scope for automated scraping.
- **manatee C**: structurally blocked by the CLERK_SSOT_CANCELLED classification; only path to PASS is a policy decision on what counts as "clean" for correctly-classified cancelled rows.
- **liberty A/B/F**: genuinely accrual-gated; will only move if a second foreclosure/tax-deed case appears or a real (non-bot-detection-bypassing) source publishes an outcome for 24-CA-22.
