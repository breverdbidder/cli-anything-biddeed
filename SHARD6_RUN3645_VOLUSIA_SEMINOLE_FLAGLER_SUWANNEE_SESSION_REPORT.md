# SHARD-6 run3645 — volusia / seminole / flagler / suwannee

dispatch_id: `c32c619b-e979-4e9e-916f-7a5a0eca5b9d`

## Status board (BEFORE brief baseline → AFTER, live `pencil_dod_evaluate_county`)

| County | Letters PASS (before) | Letters PASS (after) | Notes |
|---|---|---|---|
| volusia | 10/10 | 10/10 | Unchanged, no regression. Already gold on live metrics. |
| seminole | 8/10 (E, I fail) | 8/10 (E, I fail) | No movement — E and I were already ULTRALOOP-confirmed genuine ceilings by a prior session earlier today (12:41Z); no new evidence exists to justify a retry per protocol ("refuted claim never retries without new evidence"). |
| flagler | 6/10 (B, C, D, F fail) | **8/10** (B, F fail) | **C and D flipped PASS** (90.5%→97.8%). |
| suwannee | 4/10 (A, B, C, D, F, I fail) | **6/10** (A, B, F, I fail) | **C and D flipped PASS** (22.2%→100%). |

## What actually moved this session (ULTRALOOP-verified, both SURVIVED)

### flagler C/D: 90.5% → 97.8% (124/137 → 134/137)
Script: `scripts/shard6_run3645_flagler_realtdm_case_search.py`.

Extended the live-source discovery SHARD-9 run3534 made earlier today (`flagler.realtdm.com`, a public no-login RealTDM case-search portal) to the 10 remaining unmatched rows (all `auction_date=2026-08-11`, upcoming). POSTed `filterCaseNumber` to the real HTML `<form id="caseFiltersForm" action="public/cases/list">`, parsed the server-rendered case card, and promoted to `matched_clean` only when the card's own **Parcel Number** field exactly matched our stored `parcel_id` (independent field corroboration, not a bare case-number string match). All 10 came back `ACTIVE` with matching parcels and were promoted.

The 3 still-unmatched rows (`25-026`, `25-031`, `25-032 TDC`) were re-confirmed live as `COMPLETED - REDEEMED` (owner redeemed before deed issuance, no bidder sale) and correctly left `parity_status=NULL` — same conservative behavior as this morning's session, i.e. **not** force-matched, and the auctions_total denominator was **not** altered.

**Correction to my own commit message, caught by the adversarial refuter:** I wrote that redeemed-case exclusion was "a rule SHARD-9 run3534 already established" — that overstates it. Rereading `SHARD9_RUN3534_BAY_STJOHNS_FLAGLER_MADISON_SESSION_REPORT.md` line 49, it is explicitly an **open scope question for Ariel** ("should redeemed cases be excluded from the C/D denominator"), not a resolved rule. My action itself was fine and policy-neutral (I didn't touch the denominator either way, same as this morning), but the provenance framing in the commit was imprecise. Flagging it here per HONESTY PROTOCOL rather than letting the mischaracterization stand. **Open question for Ariel still unresolved.**

Refuter (independent, `Workflow` background run `wf_10342231-5f6`): live-refetched 3 of the 10 promoted cases fresh, confirmed ACTIVE status + exact parcel match; re-ran `pencil_dod_evaluate_county` and confirmed C/D pass at 97.8% with no regression on A/E/G/H/I/J (B/F unchanged fail, as expected). **SURVIVED.** Logged to `gold_standard_ultraloop_audit` ids 4503 (C), 4504 (D).

### suwannee C/D: 22.2% → 100% (2/9 → 9/9)
Script: `scripts/shard6_run3645_suwannee_cd_realtaxdeed_fix.py`.

Suwannee's 9 total auctions are all `tax_deed`, all upcoming, all sharing `auction_date=2026-08-06`. Reused the proven fleet-wide RealForeclose/RealTaxDeed AJAX harvester (`scripts/shard2_run2450_ajax_realforeclose_harvest.py::harvest_date()`, same mechanism already verified for pinellas/santa_rosa/miami_dade/seminole) against `suwannee.realtaxdeed.com` for that date. Live harvest returned 8 items covering all 7 previously-unmatched case numbers (plus one auction, `4713`, not yet in our DB — a genuine coverage gap noted below, not touched this session). Promoted to `matched_clean` only where the harvested item's own `parcel_id` exactly matched our stored value — all 7 confirmed and promoted.

Refuter: independently re-ran the harvester fresh (new cookie session) plus a second raw-request cross-check, got the same 8 items with matching parcel_ids, confirmed live via REST that all 9 rows are `matched_clean` with 7 tagged `parity_source=tier1:shard6_run3645_suwannee_realtaxdeed_ajax`, re-ran the RPC and confirmed C=100.0/D=100.0 with zero regression on A/B/E/F/G/H/I/J. Flagged the extra live item `4713` as independent proof the feed isn't circular. **SURVIVED.** Logged to `gold_standard_ultraloop_audit` ids 4501 (C), 4502 (D).

## Residual gaps confirmed genuine this session (no fabrication attempted)

- **suwannee A** (fc=0): re-confirmed with **new, more thorough evidence** than any prior session — live-queried `suwannee.realforeclose.com` across every Tue–Fri date for the next 120 days (48 dates), zero real foreclosure items on any of them. Corroborates this morning's ghost-success revert finding (suwannee's only 2 prior FC rows were fabricated bootstrap data). Suwannee genuinely has no foreclosure-lane activity right now — a real dual-product ceiling, not a scraper gap.
- **suwannee I** (22.2%, 2/9): the auction rows already carry address/value/lat-lon (not a card-field gap) — the gate is `v_zoning_gold_standard_card` zoning coverage, and only 2 of 9 suwannee parcels have any `zone_code` row. Suwannee County has no ArcGIS/zoning REST endpoint reachable from this environment: `gis.suwanneecounty.com` fails TLS SNI handshake (dead/misconfigured host), `suwanneecountyfl.gov` returns 403, and a web search turned up no public ArcGIS MapServer for Suwannee zoning (only a Schneider/qPublic parcel portal, already known 403-blocked, and paid aggregators). This is a genuine zoning-ingestion substrate gap (same class as brevard/duval G/I work), not fixable from this session's network path.
- **suwannee/flagler B, F**: re-confirmed unchanged — extensively documented across many prior sessions (2026-07-03 through today) as a genuine ceiling: no independent (non-PropertyOnion, non-self-promoted) outcome source is reachable for either county. `FIRECRAWL_API_KEY` is absent from this session's environment (checked), so the previously-identified Cloudflare/JS-rendering blockers on the results channels remain unaddressed. No new evidence this session; per ULTRALOOP protocol, not retried.
- **seminole E/I**: not touched. Already ULTRALOOP-confirmed today (12:41Z, by a different session) as genuine ceilings: E's 7 missing rows carry source-side placeholder parcel values (`Property Appraiser`/`MULTIPLE PARCELS`/`ALCOHOLIC LICENSE`), and I's gap is a zoning-view coverage shortfall (14 of 92 real-parcel rows unmapped). No new evidence surfaced this session to justify revisiting.
- **Data-quality note (not a letter blocker, flagging honestly):** all 9 suwannee rows share the identical `latitude=30.2949, longitude=-83.0035` — a placeholder/centroid value, not per-parcel geocoding. It does not currently gate I (I is blocked by zoning, not geo), so left untouched, but noted for whoever eventually does real suwannee geocoding.

## Verification evidence

- `pencil_dod_evaluate_county` re-run live for all 4 counties post-fix (JSON captured in this session, matches status board above); a second re-run afterward confirmed zero regression across all 40 letter checks.
- ULTRALOOP background `Workflow` run `wf_10342231-5f6` (2 refuter agents + 2 logger agents, resumed once after the first attempt crashed on a refuter schema-formatting failure — fixed and re-run, first agent's completed result reused via `resumeFromRunId`). Both claims **SURVIVED**. 4 rows written to `gold_standard_ultraloop_audit` (ids 4501–4504), dispatch_id `c32c619b-e979-4e9e-916f-7a5a0eca5b9d`, `ultraloop_mode=native`.
- No `gold_standard_loop()`/`gold_standard_certify()` run this session — concurrent shard commits visible in git log during this session (other shards mid-flight), per PARALLEL-FLEET RULES.
- Direct psql/pooler DB access confirmed stale this session (password auth fails on both the pooler and direct host) — consistent with every prior shard finding referenced in this repo. All reads/writes went through PostgREST.

## Guardrail compliance

- No PropertyOnion data ingested as anything but litmus (not used at all this session).
- No fabricated parcel_id, case match, or outcome. Every promoted row was corroborated by an independent field (parcel number) from a live, freshly-fetched external source, not a bare case-number string match.
- Schema unchanged — no migration needed (pure data writes via PostgREST `PATCH`).
- Scripts committed to git (`b50558dd`), DB writes via PostgREST only.
- Cost: 2 live-HTTP-scraping Python scripts (no paid APIs), one background Workflow (~320K subagent tokens across two runs, well under the $10/session guidance for this class of work).
