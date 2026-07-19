# Gold Standard Shard-2: jackson / dixie / hendry / columbia — session report

dispatch_id: 190ac19f-8ae0-465c-be8b-ec314028eb77
chat_session: architect-20260719T160000
mode: ultracode (Workflow-orchestrated fan-out fix → adversarial verify, 5 parallel pipelines), plus direct orchestrator diagnosis/commit

## Status Board (before -> after, live `pencil_dod_evaluate_county`)

| County | Before | After | Delta |
|---|---|---|---|
| jackson | 10/10 | **10/10** | none needed; certification history flagged (see below) |
| dixie | 8/10 (C/D fail, 75.8%) | 8/10 (C/D fail, 75.8%) | unchanged — exhaustively investigated, genuinely blocked |
| hendry | 7/10 (B/F/G fail) | **10/10** | B, F, G all fixed |
| columbia | 5/10 (A/B/E/F/I fail) | **7/10** | E fixed; I improved 53.3%→80% (still fail); A/B/F reconfirmed blocked |

All numbers are from live `public.pencil_dod_evaluate_county(<county>)` calls I ran myself before and after the fix workflow — not just subagent self-reports.

### SQL VERIFICATION (fresh, this session, 2026-07-19)

```
SELECT * FROM public.pencil_dod_evaluate_county('jackson');
 -> A15 B100 C98.4 D98.4 E95.3 F100 G100 H4.3 I95.3 J100  (10/10, auctions_total=64)

SELECT * FROM public.pencil_dod_evaluate_county('dixie');
 -> A2 B100 C75.8(FAIL) D75.8(FAIL) E100 F100 G100 H0.3 I97 J100  (8/10, auctions_total=33)

SELECT * FROM public.pencil_dod_evaluate_county('hendry');
 -> A3 B100 C100 D100 E100 F100 G100 H0.3 I100 J100  (10/10, auctions_total=20)

SELECT * FROM public.pencil_dod_evaluate_county('columbia');
 -> A0(FAIL) B null(FAIL) C100 D100 E100 F null(FAIL) G100 H0.1 I80(FAIL) J100  (7/10, auctions_total=15)
```

## jackson — no fix needed, but a flag for a future session

Reconfirmed genuinely 10/10 live. However `gold_standard_certifications` shows `certified=false`, `consecutive_non_gold=9`, `revoked_at=2026-07-17 13:30 UTC` despite today's scoreboard row reading `gold_standard=true` — jackson appears to have been flapping pass/fail across the last several daily evaluation cycles even though it evaluates clean right now. I did not run `gold_standard_loop()`/`gold_standard_certify()` (other shards may be mid-flight, per protocol) so I can't rule in/out whether this is a scoring-cadence artifact or a real intermittent regression. **Flagged for next session**: pull `gold_standard_certifications` history for jackson and diff against `pencil_dod_evaluate_county` snapshots on the days it was marked non-gold to see what actually regressed.

## hendry — B, F, G fixed live; now 10/10

- **B/F** (null→100%/100%): 17 tax-deed cases (auction_date 2026-07-16, 3 days before session start) were stuck `auction_status='upcoming'`/`sold_amount=NULL` even though the sale had already happened. Reused the proven `scripts/shard7_run3679_santa_rosa_bf_realforeclose_results.py` pattern (authenticated login via `REALFORECLOSE_EMAIL`/`REALFORECLOSE_USERNAME`+`REALFORECLOSE_PASSWORD`, notice-queue drain, "Auction Results Report" report_id=18, jqGrid pagination) against `hendry.realtaxdeed.com`. 10 of the 17 cases had a real posted `Sold` status + winning bid; the honesty guard (only trust rows whose own status says Sold, not a stray bid on a Cancelled row) correctly excluded the other 7, which remain genuinely unresolved (not yet posted). Wrote `sold_amount`/`tier1_sold_amount` on `multi_county_auctions` and independent rows to `tax_deed_outcomes` (`data_source=tier1:realtaxdeed_results_report:hendry`). New script: `scripts/shard2_hendry_bf_realtaxdeed_results.py`.
- **G** (0%→100%): the 2026-07-11 Clewiston placeholder-district fix (`zoning_districts` id 11787) was confirmed still live and *not* the cause of today's failure. Found a second, previously-undocumented applicable-but-missing `pk1000` district: `C-1` (jurisdiction_id 1399). Fixed with a boolean applicability flag only (`pk1000_regulated=false`), citing real ordinance text (Sec. 1-53-4.1, Table 53-2) — no numeric parking standard invented.

Migrations: `supabase/migrations/20260719_shard2_hendry_bf_realtaxdeed.sql`, `20260719_shard2_hendry_g_pk1000_c1_unregulated_confirm.sql`. Adversarially verified independently (fresh re-login/re-fetch reproduced the same 10 case/amount matches; fresh idempotency check on the G flag flip). Audit rows: `gold_standard_ultraloop_audit` (dispatch 190ac19f) — B, F, G all `survived=true`.

## columbia — E fixed, I improved but still failing, A/B/F reconfirmed genuinely blocked

- **E** (93.3%→100%): case `2025-249-CA` ("294 NE OMAR TERRACE") had `parcel_id=NULL`. Found `gis.columbiacountyfla.com`'s own ArcGIS REST services (Columbia County's own GIS, not the blocked qpublic/columbiapa.org vendor sites) — address-matched to real parcel `28-1S-17-04576-002`.
- **I** (53.3%→80%, still FAIL, needs ≥95%): using the same live GIS, resolved zone codes for 4 of the 7 previously zone-less parcels, and disambiguated the malformed dual-parcel field on case `2025-63-CA` ("00130-000 AND 00130-001" — confirmed via live GIS that `00130-001` doesn't actually exist and `00130-000` is the real parcel). 3 rows remain honestly blocked: 2 have no `assessed_value`/`market_value` anywhere sourceable, and case `2025-2196-CC` (parcel `04023-000`) sits inside Fort White city limits, which has zero zoning-atlas coverage in the county's live GIS layer (confirmed via polygon intersect — 0 features in Zoning_Atlas, 1 feature in Ft_White_Limits).
- **A/B/F reconfirmed genuinely blocked, no forced fix**: ran `scripts/columbia_clerk_html_harvest.py` for real (chromium `--dump-dom` against the Cloudflare-protected `columbiaclerk.com` — Firecrawl is out of credits, HTTP 402 confirmed, not purchased/escalated without approval). The live tax-deed page currently shows **zero** listings (site's own "no properties" copy present — genuinely empty, not a scraper failure) and no sold-amount/result data exists anywhere on the foreclosure or property-sales pages for the 4 already-past-due cases. Hardened the harvester itself: it now fails loud if it parses 0 rows *and* the site doesn't show its own "no listings" copy (distinguishing a real empty lane from silent selector drift going forward).

Migrations: `supabase/migrations/20260719_shard2_columbia_ei_gis_zone_and_parcel_fix.sql`, `20260719_shard2_columbia_a_bf_blocked_no_real_data.sql`. All claims adversarially verified via independent live GIS re-queries and independent DOM re-dumps. Audit rows: E, I, A, B, F all `survived=true` in `gold_standard_ultraloop_audit`.

## dixie — C/D exhaustively investigated, genuinely blocked, no forced fix

C/D denominator is **all** auctions (not just closed ones): 25 of 33 already `matched_clean`, 2 are real future foreclosure cases that structurally cannot resolve yet, and 6 are stale `DIXIE-SYNTH-*` tax-deed rows dated across Feb–Aug 2025 stuck `upcoming`/`parity_status=NULL`. Even resolving all 6 would only reach 31/33 = 93.9%, still short of 95% — a genuine structural ceiling this session, not a bug to fix.

The fixer checked 8 sources (dixieclerk.com tax-deed page + nav, tax collector, property appraiser) looking for a real disposition of the 6 stale parcels. The adversarial verifier caught one narrative inaccuracy worth recording: the fixer's claim that the 6 parcel IDs are *absent* from dixieclerk.com's live page is wrong — a plain `curl` (no headless browser needed) shows all 6 present in the page's embedded Vue data, each with `status:'scheduled'`, `sold_amount:null`. That's still not a real disposition (it's the clerk site's own stale/never-updated metadata for an 11-month-old sale date), so the bottom-line metric claim (unchanged, 75.8%, no fabricated match) survives — but the exhaustive-due-diligence narrative should be corrected before a future session cites it as settled. No migration content changed the DB; `supabase/migrations/20260719_shard2_dixie_cd_synth_row_source_exhaustion.sql` documents the investigation as a no-op.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| jackson | verify/hold | Reconfirmed 10/10 | found a certification-history flap worth flagging (not investigated further, out of scope) |
| dixie C/D | fix parity gap | Investigated exhaustively, genuinely blocked at structural ceiling (max 93.9%) | none on the metric; verifier corrected one narrative overreach in the fixer's evidence |
| hendry B/F | fix verified outcomes | Fixed to 100%/100% (10 of 17 cases; 7 genuinely not yet posted) | none |
| hendry G | fix zoning | Fixed to 100% (found a 2nd, previously-undocumented applicable-but-missing district) | root cause differed from the pre-existing hypothesis (Clewiston fix was already fine) |
| columbia A | fix tax-deed lane | Ran real harvester; site currently has zero listings | genuinely blocked, not a scraper bug — hardened harvester's failure mode as a side benefit |
| columbia B/F | fix verified outcomes | Reconfirmed genuinely blocked (no site-side result data) | none |
| columbia E | fix parcel linkage | Fixed to 100% via county's own GIS | none |
| columbia I | fix card completeness | Improved 53.3%→80%, still FAIL | 3 of 7 rows genuinely unresolvable today (2 missing values, 1 jurisdiction gap) |

## Verification Evidence

10 rows inserted to `gold_standard_ultraloop_audit` (dispatch_id `190ac19f-8ae0-465c-be8b-ec314028eb77`, `ultraloop_mode='native'`): hendry B/F/G, columbia E/I/A/B/F, dixie C/D — all `survived=true`. No `gold_standard_loop()`/`gold_standard_certify()` run (parallel-fleet protocol; other shards may be mid-flight). No PropertyOnion-sourced or `*promote*`-tagged outcome rows written anywhere. No fabricated numeric zoning standards (both zoning fixes this session were boolean applicability-flag corrections with real ordinance citations, not invented FAR/density/parking numbers). Cron jobs 109/111/115 and `gold-standard-loop-*` untouched. Commit `105d091b` (rebased onto `a81c2bb5`, pushed as `fa896ef1`) — 7 files, all migrations + 2 scripts, no secrets (scanned before commit).

## Next-session priorities

1. **columbia I**: revisit case `2025-249-CA`/others' missing `assessed_value` (try a direct owner-name search on Columbia's tax collector or appraiser record rather than address/parcel lookup) and re-check whether Fort White's zoning atlas gap has since been filled county-side.
2. **columbia A/B/F**: columbiaclerk.com's tax-deed lane may simply be between sale cycles — re-run `scripts/columbia_clerk_html_harvest.py` on a later date; if still empty, escalate to Firecrawl once credits are restocked (requires approval, not done this session).
3. **dixie C/D**: the 6 stale SYNTH rows need either (a) a tax-collector deed-application/certificate-status lookup by cert# (not yet tried) or (b) a deliberate, evidence-based purge decision in a dedicated session — do not re-attempt the same 8 sources without new leads.
4. **jackson**: pull `gold_standard_certifications` history to explain the `consecutive_non_gold=9`/`revoked_at=2026-07-17` flap despite today's clean 10/10.
