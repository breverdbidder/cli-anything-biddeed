# Gold Standard Shard-2 — brevard / bradford / lee / madison / columbia

dispatch_id: `5a29383b-5711-42b1-b0b8-c42b73a6d85b` | chat_session: `architect-20260807T080000` | loop run 9488

Ran via ULTRALOOP protocol: one Workflow fan-out, 6 levers (research+fix), each independently adversarially verified against the live evaluator. `ultraloop_mode=native`. All 11 audit rows (`gold_standard_ultraloop_audit`) landed with `survived=true` — every claim below was independently reproduced by a refuter agent, not just self-reported.

## Before → After (live `pencil_dod_evaluate_county`, re-run at session start and session end)

No letter changed state for any of the 5 counties this session. Score unchanged: brevard 9/10, bradford 8/10, lee 8/10, madison 7/10, columbia 6/10.

| County | Before | After |
|---|---|---|
| brevard | `{A:T,B:T,C:T,D:T,E:T,F:T,G:T,H:T,I:F(84.4),J:T}` | `{A:T,B:T,C:T,D:T,E:T,F:T,G:T,H:T,I:F(84.0),J:T}` |
| bradford | `{A:T,B:F,C:T,D:T,E:T,F:F,G:T,H:T,I:T,J:T}` | identical |
| lee | `{A:T,B:T,C:T,D:T,E:F(94.7),F:T,G:T,H:T,I:F(92.9),J:T}` | identical |
| madison | `{A:F,B:F,C:T,D:T,E:T,F:F,G:T,H:T,I:T,J:T}` | identical |
| columbia | `{A:T,B:F,C:T,D:T,E:T,F:F,G:T,H:T,I:F(44.1),J:F(44.1)}` | identical |

(I metric drift 84.4→84.0 on brevard is auction-volume growth diluting the denominator during the session, not a regression from anything this session touched — auctions_total moved 7099→7244.)

## Lever-by-lever

### brevard I — BCPAO address backfill: BLOCKED
Pulled 200 eligible rows missing `property_address` (of ~1112). BCPAO (`www.bcpao.us`) now returns HTTP 403 with `cf-mitigated: challenge` (Cloudflare bot-challenge) on both the JSON API and the HTML search UI — this is new since the reference scraper in `enrichment.py` was written; verified live via curl and WebFetch. Escalation to firecrawl-scrape failed with HTTP 402 "Insufficient credits" — confirmed via `api.firecrawl.dev/v1/team/credit-usage`: **`remaining_credits=-6` of `plan_credits=1000`, billing period 2026-07-28→2026-08-28.** The account is over quota, not the key being invalid. Zero writes.

### lee E/I — LeePA parcel linkage: BLOCKED
Reproduced the exact 17-row cohort. LeePA is a stateful ASP.NET POST form (not WebFetch-able). Tried the official Lee County ArcGIS parcel FeatureServer directly as an alternate real source: 0 matches for "16300 PINE RIDGE RD" (address doesn't exist in the county parcel index — nearby real addresses are 16245/16255/16265), and 137 ambiguous condo-unit STRAPs for "2825 PALM BEACH BLVD" with no unit number to disambiguate — picking one would be a fabricated linkage, so none was written. `lee.realforeclose.com` and `leeclerk.org` both 403. Firecrawl: same 402 credits-exhausted as above. Zero writes.

### columbia I — Columbia PA (search.ccpafl.com) enrichment: PARTIAL, real writes, metric unmoved
**Only lever with real writes this session.** search.ccpafl.com is reachable (not Cloudflare-gated). Enriched all 17 of 19 gap rows with real `assessed_value`; 10 of those 17 also got real situs addresses geocoded to rooftop lat/long via OSM Nominatim (spot-checked live post-write, see table in prior tool output). The remaining 7 parcels are genuinely no-situs vacant parcels per CCPA's own records (Use Code 0000/0700) — correctly left null, not fabricated.
**Why I didn't move:** `pencil_dod_evaluate_county`'s card-complete definition also requires the parcel to resolve against `v_zoning_gold_standard_card` with a non-null `zone_code` — Columbia's zoning-ingestion coverage for these 17 parcels doesn't exist yet. That's a separate G/I zoning-substrate lever (fleet-wide, not county-scraping), explicitly out of scope for this session. The address/geo/value now on these rows is still real, durable progress that a future zoning-linkage session (or the standing valuations cron) can build on.

### bradford B/F (case `25000457CAAXMX`) — BLOCKED
7th consecutive session on this exact case (prior 6 exhausted non-CAPTCHA channels). `bradfordclerk.com` 403's WebFetch; Firecrawl 402 credits-exhausted; Bradford OCRS public tier has no case-number search form (login-gated). No independent WebSearch hit. Zero writes — the "new capability" premise (FIRECRAWL_API_KEY present) did not actually translate into working access this session because the account is over quota, not because the key is missing.

### madison A/B/F — fresh recheck only: unchanged
Per prior sessions' explicit finding that Civitek OCRS is Turnstile-CAPTCHA-gated (a confirmed dead end, not to be re-attempted), this was a cheap recheck of `madisonclerk.com` only, not a rebuild. Tax-deed page still lists zero properties (A remains structurally FAIL-by-design). Cases `21-36-CA` and `24-62-CA` remain vanished from the calendar with no disposition. No CAPTCHA bypass attempted. Zero writes.

### columbia B/F (7 past-due cases) — BLOCKED
`columbiaclerk.com` 403's WebFetch on every page tried (upcoming-foreclosure-sales, Foreclosure-Log PDF, surplus page). Firecrawl escalation: same 402 credits-exhausted, confirmed with a control request against `example.com` (rules out target-site-specific blocking). Only Wayback snapshot available predates all 7 target auction dates. Zero writes.

## Infra finding worth escalating (not a county-data issue)

**The Firecrawl account (`FIRECRAWL_API_KEY`) is over its monthly quota: `remaining_credits=-6` of `plan_credits=1000` for billing period 2026-07-28→2026-08-28.** This blocked 5 of 6 levers' Cloudflare-bypass escalation path this session, even though the key itself is present and authenticates. Every "BLOCKED" verdict above that cites Firecrawl 402 would very plausibly have succeeded with a working credit balance (BCPAO, LeePA, bradfordclerk.com, columbiaclerk.com are all reachable via browser rendering, just not via plain WebFetch/curl). Recommend refilling/upgrading the Firecrawl plan before the next shard session that touches Cloudflare-gated county sites.

## Verification protocol executed

- Live `pencil_dod_evaluate_county` re-run for all 5 counties at session start (matched brief exactly) and session end (pasted above, identical except brevard I denominator drift).
- 6 independent adversarial refuter agents, each re-querying the live evaluator, spot-checking written/claimed rows via PostgREST, and independently re-fetching cited source URLs rather than trusting the fix agent's transcription. All 6 claims `survived=true` — no false positives, no anomalies (columbia I's writes were verified as real and correctly attributed to not moving the gated metric, not misreported as a pass).
- 11 `gold_standard_ultraloop_audit` rows written (dispatch_id `5a29383b-5711-42b1-b0b8-c42b73a6d85b`), all `survived=true`, timestamps 08:21–08:26 UTC.
- `gold_standard_campaign` checkpoint row inserted (id 3847) with `criteria_passed` per county, `exit_reason='timeout'` (work queue for this shard is currently blocker-bound, not exhausted by choice).

## Plan vs. actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| brevard I | BCPAO address backfill, target 30-50+ rows | 0 rows (BCPAO Cloudflare + Firecrawl quota exhausted) | Structural blocker, not a scope-execution gap |
| lee E/I | LeePA parcel linkage, 17 rows | 0 rows (stateful form + ambiguous/no-match ArcGIS results) | Structural + genuine data ambiguity |
| columbia I | Columbia PA enrichment, 19 rows | 17/19 real writes; metric unmoved (zoning-link gap out of scope) | Partial — real data landed, letter didn't flip |
| bradford B/F | Fresh outcome discovery w/ Firecrawl | 0 rows (Firecrawl quota exhausted) | Structural blocker |
| madison A/B/F | Cheap recheck only | Cheap recheck only, no change | As planned |
| columbia B/F | Fresh outcome discovery w/ Firecrawl | 0 rows (Firecrawl quota exhausted) | Structural blocker |

## Next-session priorities

1. **Refill Firecrawl credit balance** — this single fix unblocks 5 of 6 levers above (brevard I, lee E, bradford B/F, columbia B/F all cite the same 402 quota error, not a per-site problem).
2. **Columbia G/I zoning substrate** — load Columbia County zoning districts/parcel_zones so the 17 newly-enriched tax-deed parcels (and the rest of the county) can resolve `v_zoning_gold_standard_card`; this is the actual I blocker now, not missing address/value data.
3. **Lee E** — the "2825 PALM BEACH BLVD" case needs a unit number from the original case filing (Lee Clerk case detail, currently 403'd) before the 137-way STRAP ambiguity can be resolved without guessing.
4. Bradford/madison/columbia B/F remain genuinely data-unavailable via any automated channel this session had access to (once Firecrawl is refilled, worth one more real attempt before declaring them permanent phone-call-only blockers).
