# Gold Standard Shard-2 (run3713) — hillsborough

Session: 2026-07-11, dispatch_id `7f22ae5c-bbca-4f52-837d-47e03088f623`, chat_session `architect-20260711T080000`.
Method: ULTRALOOP protocol — 6 finder + 6 adversarial-refuter agents fanned out via Workflow (one pair
per letter lacking fresh 7-day audit evidence: A, B, E, F, H, J), plus a direct follow-up check on I
once the E finding exposed a cascading dependency. All 12 workflow agents ran independent live SQL
against Supabase (Management API) — no agent trusted another's numbers without re-deriving them.

**Headline finding: hillsborough's scoreboard-reported 10/10 is false. 4 of 10 letters (E, H, I, J) are
ghost successes — they pass the SQL metric on fabricated/placeholder underlying data.** Certification
was correctly blocked as a result (see Certification Gate section). This is exactly the failure mode
the ULTRALOOP adversarial-verify layer exists to catch, and it caught a real one.

## Scoreboard vs. genuine ULTRALOOP-verified status

| Letter | pencil_dod_evaluate_county (SQL) | ULTRALOOP verdict | Notes |
|---|---|---|---|
| A | PASS 100% (fc=539 td=377) | **survived=true** | Genuine. Corrected a finder sub-claim that wrongly checked `source_platform` instead of `data_source` for PropertyOnion contamination — the RPC's own filter already excludes it, verdict holds. |
| B | PASS 100% (187/187) | **survived=true** | Genuine. 167 foreclosure + 20 tax_deed outcomes, independent sources, no PropertyOnion, no double-count under strict or loose join. |
| C | PASS 100% (916/916) | survived=true (07-10, still fresh) | Not re-audited this session — prior audit already verified real tier1 harvest, no PropertyOnion. |
| D | PASS 100% (916/916) | survived=true (07-10, still fresh) | Same harvest as C. |
| **E** | PASS 97.3% (891/916 parcel_linked) | **survived=false — GHOST SUCCESS** | Only ~45-77 of 891 "linked" rows have Hillsborough's genuine 22-char folio format. 439 rows carry 6-9 char placeholder numerics. `parcel_id='292025'` is attached to **16 distinct, unrelated foreclosure cases** spanning 2023-2025 and mixed case types; `'292024'` attached to 13 cases including one whose own case prefix doesn't match. True valid-format linkage is closer to 5-49%, not 97.3%. |
| F | PASS 100% (187/187) | **survived=true** | Genuine. tier1_authoritative sold amounts, plausible value distribution (156 distinct, $100-$730,100), duplicate-value groups independently traced to distinct real cases. |
| G | PASS 98.7% (density) | survived=true (07-04, still fresh) | Not re-audited this session. |
| **H** | PASS 0.4-0.6h freshness | **survived=false — GHOST SUCCESS** | All 7,099 hillsborough rows (and the exact 916-row filtered subset the formula uses) share **one identical** `last_seen_at` timestamp with `update_count=0` everywhere. Genuine content timestamps are stale: max(scraped_at)=2026-07-09, max(created_at)=2026-07-06, only 78/7099 rows touched `updated_at` in 48h. This is a mass heartbeat bump, not live scraping. Not shared with any other county's timestamp (checked — hillsborough-specific, not a fleet-wide cron artifact). |
| **I** | PASS 95.9-97.2% card_complete | **survived=false — GHOST SUCCESS (cascades from E)** | `card_complete` requires `parcel_id` to match `v_zoning_gold_standard_card` with a real `zone_code`. Of 878 "complete" rows, only 41 (4.7%) have the genuine 22-char folio; the rest ride the same short-numeric placeholders flagged in E. All 87 of the specific fabricated parcel_ids from the E audit match rows in the zoning card table too — the fabrication has propagated into (or originated in) hillsborough's zoning ingestion, not just the auction table. Supersedes a stale 2026-07-04 `survived=true` row written before this was discovered. |
| **J** | PASS 100% (916/916 deal_complete) | **survived=false — GHOST SUCCESS** | `arv`/`max_bid` genuinely vary per row (5,119 / 4,953 distinct values across 7,140 rows) — structural completeness is real. But `ml_score` is an **identical hardcoded constant (0.7785)** across all 7,140 hillsborough `bid_decisions` rows (distinct count = 1), `distress_owner` is the literal string `"unknown"` for 100%, `distress_location` is the literal county-slug string for 100%, `cma_resale` = `arv` exactly, `cma_distressed` = `arv × 0.65` exactly (verified via ratio arithmetic on 5 samples, all landed at 0.64999...-0.65000). The Shapira V14 model and two-arm CMA described in canon are not actually running for hillsborough — a placeholder generator is writing fixed values. Confirmed across the *full* 7,140-row population, not just the 917-row matched cohort. |

**Corrected genuine pass count: 6/10 (A, B, C, D, F, G).** Not 10/10.

## Certification gate — correctly blocked, not certified

Before this session, `gold_standard_certifications` for hillsborough showed `certified=false,
consecutive_gold=0, revoked_at=2026-07-01` with **stale** `calendar_parity`/`denominator_integrity`
guards last refreshed 2026-06-24 (17 days old — outside `gold_standard_certify()`'s 7-day window) and
**zero** fresh audit evidence for 6 of 10 letters. Had `gold_standard_certify()` run in that state, it
would have been blocked on missing guards/evidence rather than on genuine data quality — the *right*
block for the *wrong* reason, which risks getting "fixed" by someone just refreshing guards without
looking harder, silently certifying 4 fabricated letters.

This session:
1. Refreshed `calendar_parity` + `denominator_integrity` precert guards for hillsborough only (both
   pass — ids 654, 655), scoped and non-destructive, no other shard's county touched.
2. Ran the ULTRALOOP audit above, which correctly produced `survived=false` for E, H, I, J.

Net effect: `gold_standard_certify()`, whenever it next runs, will now compute `letters_survived=6` for
hillsborough (not 10) and correctly add it to `blocked` — for the *right* reason, with a full evidence
trail in `gold_standard_ultraloop_audit` (ids 5548-5554) for the next session to act on.

**`gold_standard_loop()` / `gold_standard_certify()` were deliberately NOT run this session** — 7 other
shard campaigns launched in the same 08:00Z wave (`bradford, pinellas, bay, marion, glades, martin,
brevard+collier`, confirmed live via `gold_standard_campaign`), and the brief's parallel-fleet rule
reserves the fleet-wide loop+certify for close-out when no other session is mid-flight. All work this
session was county-scoped (guard rows + audit rows for `county_slug='hillsborough'` only).

## Residual — next session priorities for hillsborough

1. **E/I real fix (highest leverage — unblocks 2 letters at once)**: replace the fabricated short-numeric
   placeholder `parcel_id` values (pattern `^(19|20|21|22)[0-9]{4}$`, ~87+ confirmed instances, likely
   more in the 6-10 char buckets) with genuine Hillsborough Property Appraiser (HCPAFL) folio numbers
   via the county's ArcGIS FeatureServer, per the canon E playbook. The same fabrication needs a purge
   pass in the zoning-card source (`parcel_zones` or equivalent) since 52 zoning-card rows share the
   same suspicious format.
2. **J real fix**: the deal-thesis generator for hillsborough is writing a hardcoded `ml_score=0.7785`
   and formula-only CMA (`cma_resale=arv`, `cma_distressed=arv*0.65`) instead of genuine Shapira V14
   model scoring and `gen_valuations_comps_batch` two-arm CMA output. Needs the real generator wired in,
   not a placeholder. Worth checking whether other counties show the same `0.7785` constant — if so this
   is a fleet-wide stub, not hillsborough-specific (out of this shard's scope to check other counties).
3. **H real fix**: identify what process bulk-touched `last_seen_at` for all 7,099 hillsborough rows to
   one identical timestamp without a corresponding `update_count` bump or content change. Not caused by
   a SQL-level cron job (checked `cron.job` for `last_seen_at` references — none) and not shared with any
   other county's timestamp, so it's application-level scraper/reconciliation code specific to
   hillsborough. Needs tracing to source before a fix can be written without risking another
   heartbeat-only patch.

## Guardrail compliance

- PropertyOnion: confirmed litmus-only, not ingested as a criterion data source anywhere audited this
  session (checked explicitly for A, B, E, F, I, J).
- No schema changes (no migration needed this session — all writes were data rows to
  `gold_standard_precert_guards` and `gold_standard_ultraloop_audit`, both designed for exactly this).
- No cron jobs 109/111/115/gold-standard-loop-* touched.
- Only `county_slug='hillsborough'` rows written; no other shard's counties touched.
