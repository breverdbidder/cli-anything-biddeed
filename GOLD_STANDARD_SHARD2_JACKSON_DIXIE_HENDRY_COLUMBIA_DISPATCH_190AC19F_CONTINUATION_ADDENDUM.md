# Gold Standard Shard-2 continuation addendum: jackson / dixie / hendry / columbia

dispatch_id: 190ac19f-8ae0-465c-be8b-ec314028eb77
chat_session: architect-20260719T160000 (same dispatch re-fired; prior session's report and next-session-priorities list picked up directly rather than repeating completed work)
mode: ultracode — direct orchestrator diagnosis/fix for jackson, Workflow-orchestrated fan-out fix→adversarial-verify (3 pipelines, 6 agents) for columbia/dixie

## Status Board (before this addendum -> after, live `pencil_dod_evaluate_county`)

| County | Before | After | Delta |
|---|---|---|---|
| jackson | 10/10 (but `certified=false`, flapping) | **10/10, cert-flap root-caused + fixed** | no metric change; audit freshness restored |
| dixie | 8/10 (C/D fail, 75.8%) | 8/10 (C/D fail, 75.8%) | unchanged — new lead investigated, still genuinely blocked |
| hendry | 10/10 | 10/10 | untouched this addendum (already gold from prior firing) |
| columbia | 7/10 (A/B/F/I fail) | **8/10** (A/B/F fail, I improved) | I: 80.0%→93.3% (still FAIL, needs 15/15) |

### SQL VERIFICATION (fresh, this session, 2026-07-19 ~17:50-18:10 UTC)

```
POST /rest/v1/rpc/pencil_dod_evaluate_county {"p_county":"jackson"}
 -> A15 B100 C98.4 D98.4 E95.3 F100 G100 H5.8 I95.3 J100  (10/10, auctions_total=64)

POST .../rpc/pencil_dod_evaluate_county {"p_county":"dixie"}
 -> A2 B100 C75.8(FAIL) D75.8(FAIL) E100 F100 G100 H1.8 I97 J100  (8/10, auctions_total=33)

POST .../rpc/pencil_dod_evaluate_county {"p_county":"hendry"}
 -> A3 B100 C100 D100 E100 F100 G100 H1.8 I100 J100  (10/10, auctions_total=20)

POST .../rpc/pencil_dod_evaluate_county {"p_county":"columbia"}
 -> A0(FAIL) B null(FAIL) C100 D100 E100 F null(FAIL) G100 H1.6 I93.3(FAIL, was 80.0) J100  (8/10, auctions_total=15)
```

Note on DB access this session: direct `psql`/Postgres password auth failed against both the pooler and direct
host (`FATAL: password authentication failed`) — all live queries and writes this session went through PostgREST
(`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`, which bypasses RLS for service_role). This is DML-only; no schema
changes were needed or attempted.

## jackson — certification flap root-caused and fixed (no metric change)

Prior session flagged: `gold_standard_certifications` showed `certified=false`, `consecutive_non_gold=9`,
`revoked_at=2026-07-17 13:30 UTC` despite the scoreboard reading clean. Pulled the full `gold_standard_county_status`
history for jackson since 2026-07-14 (92 loop runs, 10 rows each) — **zero FAIL rows anywhere in that window**; every
run scored 10/10. The metric never regressed.

Root cause: `gold_standard_ultraloop_audit` showed letters A/C/D/E/H/I/J had `survived=true` rows refreshed within
the last 2 days, but **B, F, and G's most recent audit rows were dated 2026-07-10** (ids 4436/4438/4439) — 9 days
stale by 2026-07-19. Per the EVALUATOR V6 CERTIFY GATE rule (certify requires fresh `survived=true` audit rows for
all 10 letters within a rolling 7-day window), those three letters aged out of the window on 2026-07-17, and
`gold_standard_certify()` correctly failed closed on exactly that date (`revoked_at=2026-07-17 13:30:00.408642`
matches loop_run_id 4856's `evaluated_at` to the second). This is the certify gate working as designed, not a bug —
but it does mean a county with genuinely stable metrics can silently decertify if nobody re-touches its passing
letters' audit trail.

Fix: independently re-derived B (2/2 closed sales in `foreclosure_outcomes`, both `data_source=jackson_realforeclose:SHARD3-BF-V1`,
non-PropertyOnion), F (same 2 rows, `winning_bid` populated: $107,984.97 / $88,597.55), and G (`v_zoning_gold_standard_kpi_v3`:
62/62 density-applicable parcels at 100%, FAR/pk1000 correctly N/A for all 62 — not a coverage gap) directly from
source tables, cross-checked against the live RPC, and inserted 3 fresh `survived=true` audit rows (ids 7215/7216/7217).
Migration: `supabase/migrations/20260719_shard2_jackson_bfg_audit_freshness_refresh.sql`. Commit `84cc166f`.

**Not fixed / out of scope**: the certify gate itself will re-decertify jackson again in another 7 days if nobody
refreshes B/F/G (or any other letter) in the interim. A structural fix (e.g. a scheduled job that re-verifies
already-passing letters on a rolling basis, rather than relying on session-by-session touch) is a process
improvement worth raising, not something this DML-only session should build unprompted.

## columbia — I improved via real appraiser data, still FAIL; A/B/F reconfirmed blocked; one live lead surfaced

**I (80.0%→93.3%, still FAIL — needs 15/15):** the two rows missing `assessed_value`/`market_value` were resolved via
Columbia County's own appraiser site (`columbiacountyfla.com/ParcelDetails.aspx`), matched by parcel_id with owner
surname cross-checked against each case's plaintiff field (Rogers ↔ case 2025-63-CA; Stafford ↔ case 2025-249-CA,
address-matched too). The third row (case 2025-2196-CC, Fort White, parcel 04023-000) was **re-verified live, not
assumed** — polygon-intersected against 3 separate Columbia County zoning GIS layers, all returned 0 features; the
query mechanism itself was sanity-checked against a known-good parcel that correctly returned real zoning data. Fort
White has no discoverable zoning GIS service of its own. This is a genuine data-source gap: at `auctions_total=15`,
only 15/15 clears the 95% gate — 14/15=93.3% is the honest ceiling until Fort White's zoning is sourced some other
way (e.g. a scanned zoning-map PDF, out of scope for a DML-only session). Migration:
`supabase/migrations/20260719_shard2cont_columbia_i_valuation_fix_fortwhite_reconfirm.sql`. Commit `05dec1ff`.
Adversarially verified: refuter independently re-fetched both appraiser pages fresh and matched values to the dollar,
independently re-ran the Fort White polygon-intersect, confirmed commit content on main. `survived=true` (audit id 7306).

**A/B/F reconfirmed genuinely blocked:** re-ran the clerk harvester live — tax-deed lane still shows the site's own
"There are no properties on the list of tax deeds at this time" copy (genuinely empty, not scraper drift); the
foreclosure lane's per-case Status field never updates after a sale closes (case 2023-492-CA sat 4 days past its
sale date still reading "scheduled" with no result anywhere in its DOM block). Checked a foreclosure-surplus ledger
(9 real entries) — zero overlap with our 15 tracked cases. Confirmed `columbia.realforeclose.com`/`realtaxdeed.com`
are generic unconfigured RealAuction splash pages, not a live tenant. Migration:
`supabase/migrations/20260719_shard2cont_columbia_abf_recheck_still_blocked.sql`. Commit `44df70c4`.

**New lead surfaced, NOT completed — flagged for next session, high priority:** the fixer found
`civitekflorida.com/ocrs/county/12` (Columbia's public docket search, which could expose real Certificate of
Title/Sale filings) but claimed it required a JS-executing browser "not installed in this sandbox," based only on
checking `which browser-use`. **The adversarial verifier independently confirmed Playwright v1.61.0 IS installed**
and successfully launched/navigated to the same page — the fixer's dead-end claim about tooling was false, even
though the actual metric claims (A/B/F unchanged, no fabrication) held up and were not overturned. The refuter
logged this gap in `refuter_evidence` (audit ids 7303-7305, `survived=true` on the numeric claims, gap flagged for
visibility) rather than reversing the verdict, since the reported metrics and DB state were independently correct.
**Next session should drive `civitekflorida.com/ocrs/county/12`'s Case Search tab with Playwright directly** — this
is a genuinely untried, not-yet-exhausted path to real B/F data for columbia.

## dixie — new tax-collector lead tried, still genuinely blocked at structural ceiling

Per next-session priority #3, tried a genuinely new lead (not one of the prior 8 sources): `dixie.floridatax.us`,
the county tax collector's billing portal, distinct from the Cloudflare-blocked `dixietax.com`. Reverse-engineered
its ASP.NET postback search and retrieved all 6 stale `DIXIE-SYNTH-*` accounts' full payment-history pages.
Confirmed via curl that the portal has **no** certificate-status endpoint (`/CertificateSearch`, `/TaxCertificate`,
`/TaxDeed`, `/DelinquentTax` all 404) — it only shows ad-valorem tax-bill payment history, not tax-deed disposition.
Found circumstantial-only signal: 3 of 6 parcels show an unpaid "5% CERTIFICATE SALE" + "REDEMPTION FEE" line item
(process demonstrably still open), the other 3 are fully current with no such line (ambiguous — can't distinguish
redeemed vs. never-proceeded from this view alone). Per Honesty Protocol, this circumstantial signal was **not**
converted into a fabricated `tax_deed_outcomes` row. `official.myfloridacounty.com` (Clerk Official Records — the
one tool that could plausibly answer this) remains Cloudflare-Turnstile-gated against automation. Migration:
`supabase/migrations/20260719b_gtm22j_shard2_dixie_cd_taxcollector_lead_investigated.sql` (documentation-only, zero
DML). Commit `dfff2883`. Adversarially verified: refuter independently re-ran the RPC, re-confirmed the 6 rows
untouched with their pre-existing `data_source`, independently re-hit the 404 endpoints, confirmed commit content.
`survived=true` (audit ids 7307/7308, letters C and D).

**Remaining path, non-automatable:** a phone/in-person records request to the Dixie Clerk (352-498-1200) or Tax
Collector (352-498-1213) is the only lead left per this session's evidence. Even a full resolution of all 6 rows
only reaches 31/33=93.9%, still below the 95% gate (2 further rows are genuinely-future foreclosure cases) — this
remains a structural ceiling, not a simple fix.

## hendry — untouched this addendum, already 10/10 from the prior firing of this dispatch

No work performed; not re-verified independently in this addendum beyond the fresh scoreboard pull above, which
confirms it is still 10/10 live.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| jackson cert flap | pull certification history, explain flap | Root-caused to stale B/F/G audit rows (9 days, past 7-day certify gate); fixed by refreshing audit evidence | none — matches next-session-priority #4 exactly |
| columbia I | revisit missing assessed_value + re-check Fort White | 2 of 3 rows fixed via real appraiser data (owner-surname cross-checked); Fort White re-confirmed genuinely zoning-uncovered (live re-check, not assumed) | none — matches next-session-priority #1 exactly |
| columbia A/B/F | re-run clerk harvester on a later date | Re-ran, still empty; surfaced a new civitekflorida.com lead but the fixer wrongly self-reported it as blocked by missing tooling (Playwright is in fact installed) | verifier caught this and flagged it rather than silently accepting the dead-end claim |
| dixie C/D | try tax-collector cert# lookup (new lead) | Tried dixie.floridatax.us; portal has no certificate-status field at all, only payment history | none on the metric; ceiling math (93.9% max) unchanged |

## Verification Evidence

7 new rows inserted to `gold_standard_ultraloop_audit` this addendum (dispatch_id `190ac19f-8ae0-465c-be8b-ec314028eb77`,
`ultraloop_mode='native'`): jackson B/F/G (ids 7215-7217, inserted by the orchestrator directly), columbia I (id 7306),
columbia A/B/F (ids 7303-7305), dixie C/D (ids 7307-7308) — all `survived=true`. No PropertyOnion-sourced or
`*promote*`-tagged outcome rows written anywhere. No fabricated numeric zoning standards. Cron jobs 109/111/115 and
`gold-standard-loop-*` untouched. `gold_standard_loop()`/`gold_standard_certify()` NOT run (parallel-fleet protocol;
other shards' commits interleaved in `git log` during this session confirm concurrent activity). Commits `84cc166f`,
`05dec1ff`, `44df70c4`, `dfff2883` — all on `main`, confirmed via `git log`/`git pull` after the fact, all
county-scoped, no secrets (workflow agents instructed never to echo credential values).

## Next-session priorities

1. **columbia A/B/F, HIGH PRIORITY**: drive `civitekflorida.com/ocrs/county/12`'s "Case Search" tab with Playwright
   (confirmed installed and working this session — do not re-trust a `which browser-use` check as proof no browser
   automation exists) to look for real Certificate of Title/Sale filings for the 15 tracked columbia cases.
2. **columbia I**: if civitek's docket search or another source ever surfaces Fort White zoning data, apply it to
   close the last row (14/15→15/15, the only value that clears the 95% gate).
3. **dixie C/D**: only remaining lead is a manual phone/in-person records request to the Dixie Clerk (352-498-1200)
   or Tax Collector (352-498-1213) for the 6 stale SYNTH rows' certificate disposition — do not re-attempt automated
   sources without a genuinely new one.
4. **jackson, process-level**: the certify gate's 7-day rolling freshness requirement means passing letters can
   silently decertify if nobody re-touches their audit trail — worth flagging to the AI Architect as a possible
   process gap (should already-passing letters get a lighter-weight periodic re-audit, not full ULTRALOOP treatment?),
   not something to build unprompted in a county-scoped session.
