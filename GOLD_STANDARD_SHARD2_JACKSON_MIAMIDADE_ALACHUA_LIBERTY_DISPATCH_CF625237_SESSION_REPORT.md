# Gold Standard shard-2 — jackson / miami_dade / alachua / liberty

dispatch_id: cf625237-e30e-49ae-96ca-eee259884436
chat_session: architect-20260830T160001
issue: #19621
date: 2026-08-30

Session type: ULTRALOOP native `Workflow` fan-out per the ULTRALOOP PROTOCOL (user opted into ultracode this
turn). 6 pipeline targets (diagnose -> fix -> adversarial-verify, 3 agents each = 15 total agents), one per
county+letter cluster. Every fix claim was independently re-verified by a separate agent with no shared context
with the fix agent, per the mandatory two-round survival-vote protocol. **All 6 claims survived verification**
(`gold_standard_ultraloop_audit` ids 19787, 19790, 19791, 19792, 19793, plus the liberty-A/B/F verify round).
Workflow stats: 15 agents, 451 tool calls, ~1.31M subagent tokens, ~29.6 min wall-clock for the fan-out itself.

## Scoreboard (BEFORE — live, matches the dispatch brief exactly, 2026-08-30 16:00Z)

| County | Score | Failing letters |
|---|---|---|
| jackson | 9/10 | I FAIL 86.9 (card_complete=126 of 145) |
| miami_dade | 9/10 | G FAIL 66.7 (density=98.1 far=95.0 pk1000=66.7) |
| alachua | 8/10 | E FAIL 91.2 (parcel_linked=83), I FAIL 91.2 (card_complete=83 of 91) |
| liberty | 7/10 | A FAIL 0, B FAIL null, F FAIL null (single-auction county, 6 prior sessions same result) |

## Scoreboard (AFTER — independently re-queried live via `pencil_dod_evaluate_county`, 2026-08-30 ~16:44Z, by the
orchestrating session directly, not copied from any fix/verify agent)

| County | Score | Change |
|---|---|---|
| **jackson** | **10/10** | **I 86.9%->97.9% PASS. Full Gold Standard achieved this session.** |
| miami_dade | 9/10 | **G improved 66.7%->80.0%, still FAIL** — real progress, one documented residual (see below). |
| alachua | 8/10 | No change. E/I re-confirmed structurally blocked (same 8 rows, 4th+ consecutive session). |
| liberty | 6/10 | A/B/F unchanged (still FAIL, 7th consecutive session same result). **H newly FAIL** (49.8h, natural time-drift since the 2026-07-29 session — not caused by any action this session; see below). |

### SQL VERIFICATION (run live by the orchestrating session, 2026-08-30 ~16:44 UTC, after all commits landed)
```
POST /rest/v1/rpc/pencil_dod_evaluate_county {"p_county":"jackson"}
-> A PASS 20 | B PASS 100.0 | C PASS 98.6 | D PASS 98.6 | E PASS 98.6 | F PASS 100.0
   G PASS 100.0 | H PASS 0.1 | I PASS 97.9 (card_complete=142 of 145) | J PASS 99.3 | auctions_total=145

POST /rest/v1/rpc/pencil_dod_evaluate_county {"p_county":"miami_dade"}
-> A PASS 188 | B PASS 100.0 | C PASS 95.3 | D PASS 95.3 | E PASS 97.8 | F PASS 100.0
   G FAIL 80.0 (density=98.1 far=100.0 pk1000=80.0) | H PASS 0.1
   I PASS 95.7 | J PASS 100.0 | auctions_total=623

POST /rest/v1/rpc/pencil_dod_evaluate_county {"p_county":"alachua"}
-> A PASS 19 | B PASS 100.0 | C PASS 100.0 | D PASS 100.0 | E FAIL 91.2 (parcel_linked=83)
   F PASS 100.0 | G PASS 96.7 | H PASS 0.1 | I FAIL 91.2 (card_complete=83 of 91) | J PASS 100.0
   auctions_total=91

POST /rest/v1/rpc/pencil_dod_evaluate_county {"p_county":"liberty"}
-> A FAIL 0 (fc=1 td=0) | B FAIL null (verified=0 closed_sold=0) | C PASS 100.0 | D PASS 100.0
   E PASS 100.0 | F FAIL null (tier1_sold=0 closed_sold=0) | G PASS 100.0
   H FAIL 49.8 (SLA 48h) | I PASS 100.0 | J PASS 100.0 | auctions_total=1

SELECT criteria_passed FROM gold_standard_campaign WHERE dispatch_id='cf625237-e30e-49ae-96ca-eee259884436';
-> jackson{A-J: all true} | miami_dade{A-F,H-J:true, G:false} | alachua{A-D,F-H,J:true, E,I:false}
   liberty{C,D,E,G,I,J:true, A,B,F,H:false}
   criteria_total=10, exit_reason='timeout', session_end_at='2026-08-30T16:44:52.091014+00:00'
```

## What shipped (2 commits on main: `95f6cd88`)

1. **jackson I, 86.9%->97.9% PASS (full gold standard).** Root cause (re-derived fresh — dataset had grown
   73->145 auctions since the last jackson session): 15 of 19 gap rows were fully field-complete
   (address/geo/value/parcel_id) but had zero `parcel_zones` coverage — a real zoning-substrate gap, not a
   join/key-format bug. 14 are in the "Compass Lake Hills" subdivision (unincorporated Jackson County) — point-
   in-polygon queried live against the Jackson FLUM ArcGIS FeatureServer, all 14 landed in the same existing
   `FLU-RES` district already in the DB (no new district = zero G-regression risk). The 15th
   (`322025CA000221CAAXMX`) sits inside Town of Cottondale's incorporated limits, needing a new town-level FLU
   district (`FLU-COTTONDALE-RES-SUBURBAN`) sourced from Cottondale's own FLUM layer — that layer carries no
   numeric density/FAR/parking fields, so all three regulated-flags were correctly left `false`, not guessed.
   One opportunistic 16th fix: backfilled real lat/lon for case `2803 OF 2019` from the same FeatureServer, which
   made it field-complete and linked it to the existing `FLU-CONSERVATION` district. 3 rows remain a genuine,
   documented residual (1 has zero features at its APN in the parcel FeatureServer; 2 have no parcel_id/address/
   geo at all in the DB — a source-scrape-level gap, out of scope for a zoning-substrate fix).
   Migration: `supabase/migrations/20260830_gold_standard_jackson_i_zoning_substrate_15row_backfill.sql`.
2. **miami_dade G, 66.7%->80.0% (still FAIL).** Root cause: a Hialeah parcel (`zone_code='RDD'`, Residential
   Development District, added by a prior session's live ArcGIS ingestion) had no matching `zoning_districts` row,
   so the KPI view's unmatched-zone-code fallback (`COALESCE(...,true)`) incorrectly counted a purely residential
   parcel against the FAR and parking-per-1000sf (commercial/industrial-GFA) denominators. Registered the real RDD
   district (Hialeah LDC Sec. 98-1605) with `pk1000_regulated=false`, the same override-column precedent already
   live fleet-wide for other genuinely non-GFA-parking residential districts. This moved pk1000 66.7%->80.0%
   (4/6->4/5) and, as a side effect, far 95.0%->100.0% (the same misclassified parcel had also defaulted into the
   FAR denominator). density stayed 98.1% unchanged (correct — residential legitimately stays density-applicable).
   Residual: Miami Beach `MXE` (Mixed Use Entertainment District) has `far_regulated=true`/`max_far=2.0` but no
   sourced parking ratio — Municode Sec. 130-31/142-545 both returned HTTP 403, and the elaws.us mirror that
   serves other Miami Beach sections timed out on 4 attempts for these two specific sections. Left `NULL` rather
   than guessed; this is the sole remaining reason G is still FAIL.
   Migration: `supabase/migrations/20260830_gold_standard_shard2_cf625237_miamidade_g_rdd_misclassification_fix.sql`.

## Not fixed this session (honest residuals, all re-confirmed via NEW avenues, not blind re-checks)

- **alachua E/I** (same 8 rows, unchanged 91.2%/91.2%): all 8 are bare stub rows (`case_number` only, no address/
  legal description/owner/plaintiff — nothing to search a parcel-appraiser or clerk system with). New avenues
  tried and confirmed blocked this session: RealForeclose's actual JSON AJAX enrichment endpoint (not just the
  plain page GET) still fails even for currently-live dates (redirects to an internal error page — needs session
  state a plain replay can't reproduce); the 8 rows' captured auction dates have also rolled entirely off
  RealForeclose's ~3-date near-term calendar window. qpublic (403), alachuaclerk.org (login wall),
  myfloridacounty.com->alachuacounty.us disclaimer chain (login-gated, and structurally irrelevant — deed/
  instrument search needs an owner name none of these 8 rows have), Trellis (403), Firecrawl (HTTP 402, credits
  exhausted again in a fresh Aug-28 billing period — likely consumed by concurrent shard sessions). One genuinely
  new lead (WebSearch surfaced `alachuaforeclosures.com` indexing case `01 2025 CA 003287` as **two** differently-
  sized multi-parcel sub-cases with zero disambiguating data) hit the fabrication-ban wall directly — no single
  parcel_id could be written without guessing which of two real parcels it is. Correct honest non-fix.
- **liberty A/B/F** (7th consecutive session, same structural result): tried 3 genuinely new avenues beyond prior
  sessions' plain-HTTP landing-page checks — (1) `myfloridacounty.com/orisearch/39` official-records route,
  confirmed Cloudflare-Turnstile-gated via a real POST; (2) Civitek OCRS driven with an actual Playwright/Chromium
  click-path through Public-access -> disclaimer -> Case Search tab for the first time — the tab genuinely exists
  and is fillable, but a live screenshot confirms a real, unchecked, required Turnstile checkbox blocks
  submission (Cloudflare's bot-detection actually suppressed the widget's iframe entirely across 3 headless
  attempts — a harder block than a solvable captcha); (3) Liberty County Tax Collector parcel search (a genuinely
  new, non-Cloudflare-gated lead) returned zero records for the parcel, and would only have been a tax-bill
  source anyway, not a deed/sale-outcome source. libertyclerk.com re-fetched fresh: still byte-identical empty
  listings, zero Certificate-of-Title reference anywhere on-site 40 days post-sale-date. No CAPTCHA bypass was
  attempted (out of scope, against ToS, and would be exactly the banned ghost-success pattern).
- **liberty H** (newly FAIL, 49.8h): root cause diagnosed — the daily `shard-liberty-clerk-scraper.yml` cron IS
  running correctly every day (15/15 successful runs including this morning), but it only parses the clerk's
  "upcoming sales" listing pages. Case `24-CA-22`'s auction_date (2026-07-21) has passed, so it no longer appears
  on any "upcoming" page the scraper reads — the scraper has nothing to write, `last_seen_at` stays frozen, and
  the workflow's own verify step queries the DB directly (not scrape output) so it reports green/success despite
  zero real writes for weeks. This is a durable structural gap (no post-sale-date outcome-check step exists) tied
  to the same A/B/F outcome-discovery blocker above — not independently fixable without either (a) a real
  disposition discovery (which A/B/F confirmed is Turnstile-blocked this session) or (b) fabricating a
  freshness touch with no underlying verification, which the guardrails correctly prohibit. No write made.

## Verification protocol followed

ULTRALOOP native `Workflow` fan-out: 6 diagnose agents -> 6 fix agents -> 6 independent adversarial-verify agents
(pipeline-parallel, no shared context between fix and verify). Every verify agent re-ran
`pencil_dod_evaluate_county` fresh from scratch, independently re-queried any written rows (not trusting the fix
agent's counts), and checked for ghost-success patterns (PropertyOnion-derived `data_source`, duplicate-value
fabrication clusters, the B 95-105% anomaly band, denominator mismatches). All 6 survived. 6
`gold_standard_ultraloop_audit` rows inserted (ids 19787/19790/19791/19792/19793 + one more for the liberty-A/B/F
round), `ultraloop_mode='native'`, `dispatch_id='cf625237-e30e-49ae-96ca-eee259884436'`. The orchestrating session
then independently re-ran all 4 counties' `pencil_dod_evaluate_county` calls itself (pasted above) before writing
this report and the `gold_standard_campaign` close-out — a third, non-agent layer of confirmation.

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run this session (other
shards were confirmed concurrently mid-flight via the fleet's ongoing 3x-daily wave cadence — this session's
rebase picked up 5 other shards' commits mid-session) — the per-county `pencil_dod_evaluate_county` evaluations
above are the authoritative before/after proof. `git pull --rebase origin main` was run before every push; both
commits landed directly on main, no side branches, no PRs.

## Close-out

`gold_standard_campaign` row (dispatch `cf625237-e30e-49ae-96ca-eee259884436`) updated: `criteria_passed` set to
the real per-county A-J booleans pasted above, `criteria_total=10`, `exit_reason='timeout'`, `session_end_at`
stamped 2026-08-30T16:44:52Z.

## Next-session priorities

1. **jackson**: now 10/10 — needs a second consecutive 10/10 daily run to auto-certify. Worth a lightweight
   freshness/regression recheck in ~24-48h given this county's dataset grows organically (73->145 rows in ~5
   weeks) and could reintroduce a zoning-substrate gap as new auctions post, the same pattern that created this
   session's 15-row gap in the first place.
2. **miami_dade G**: one parcel (Miami Beach MXE) blocks the remaining 20 points to PASS. Try a different Municode
   mirror or a direct Miami Beach city clerk records request for Code Sec. 130-31 (Parking District boundaries)
   and Sec. 142-545 (MXE development regs) text — both returned HTTP 403 on Municode and timed out on elaws.us
   this session specifically for these two sections (other Miami Beach sections rendered fine on elaws.us).
3. **alachua E/I**: do not re-attempt the same 8 case numbers without a new lead — 4+ independent sessions now
   converge on the identical structural block (bare stub rows with zero address/owner/legal-description, and
   every clerk/appraiser avenue either Cloudflare-gated, login-walled, or Firecrawl-credit-exhausted). Worth
   revisiting only if Firecrawl credits genuinely refresh with headroom (they were re-exhausted mid-cycle this
   session, likely by concurrent shard sessions), or if RealForeclose ever exposes a wider calendar window.
4. **liberty A/B/F/H**: 7th consecutive session confirming the identical dead end, now via 3 new avenues
   including an actual browser-driven Turnstile encounter (not just landing-page inference). The Civitek OCRS
   Turnstile widget's iframe failing to render at all for headless Chromium (vs. presenting a solvable challenge)
   is new, harder information — worth flagging fleet-wide since Civitek OCRS gates many other shards' B/F work
   too. H cannot be durably fixed without solving A/B/F first (or the fleet accepting a documented no-recent-
   activity exemption for single-auction dead-counties past their sale date) — recommend the AI Architect decide
   whether liberty should be deprioritized from daily shard rotation until a fleet-level CAPTCHA-solving decision
   is made, rather than burning further session budget on an 8th identical recheck.
