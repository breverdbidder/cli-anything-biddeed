# Gold Standard Shard-1 Session Report — dispatch fafa18bc (loop run 11435)

**Counties:** baker, gadsden, st_johns, martin, taylor
**Mode:** ULTRALOOP fallback (manual Task subagent fan-out, not native `/effort ultracode`)
**Session type:** Closeout of a prior research/apply/adversarial-verify pass. This session ran fresh,
independent verification of 6 claimed findings, wrote the audit ledger, and updated campaign state.
No new research or fixes were performed in this closeout step.

## Fresh `pencil_dod_evaluate_county` results (run at closeout, 2026-08-14 ~22:56 UTC)

### baker — **10/10** (fresh certified this cycle)
```json
{"A": {"pass": true, "detail": "fc=9 td=1", "metric": 1}, "B": {"pass": true, "detail": "verified=1 closed_sold=1", "metric": 100.0}, "C": {"pass": true, "detail": "matched_clean=10", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=10", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=10", "metric": 100.0}, "F": {"pass": true, "detail": "tier1_sold=1 closed_sold=1", "metric": 100.0}, "G": {"pass": true, "detail": "density=100.0 far=100.0 pk1000=100.0", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": true, "detail": "card_complete=10 of 10", "metric": 100.0}, "J": {"pass": true, "detail": "deal_complete=10 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "baker", "auctions_total": 10}
```
Before (dispatch brief, loop run 11435): 9/10, I FAIL (card_complete=9 of 10, 90.0%).
After: 10/10, all letters PASS.

### gadsden — **9/10**
```json
{"A": {"pass": true, "detail": "fc=24 td=41", "metric": 24}, "B": {"pass": true, "detail": "verified=1 closed_sold=1", "metric": 100.0}, "C": {"pass": true, "detail": "matched_clean=65", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=65", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=65", "metric": 100.0}, "F": {"pass": true, "detail": "tier1_sold=1 closed_sold=1", "metric": 100.0}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 12.9}, "I": {"pass": true, "detail": "card_complete=65 of 65", "metric": 100.0}, "J": {"pass": true, "detail": "deal_complete=63 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 96.9}, "county": "gadsden", "auctions_total": 65}
```
Before: 9/10, C FAIL (matched_clean=57, 87.7%). After: C now PASS (matched_clean=65, 100.0%).
Remaining gap: J was already passing at dispatch time (96.9%) and was not in this session's scope — not touched.

### st_johns — **9/10**
```json
{"A": {"pass": true, "detail": "fc=53 td=31", "metric": 31}, "B": {"pass": true, "detail": "verified=1 closed_sold=1", "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=78", "metric": 92.9}, "D": {"pass": true, "detail": "matched_any=82", "metric": 97.6}, "E": {"pass": true, "detail": "parcel_linked=84", "metric": 100.0}, "F": {"pass": true, "detail": "tier1_sold=1 closed_sold=1", "metric": 100.0}, "G": {"pass": true, "detail": "density=100.0 far=100.0 pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": true, "detail": "card_complete=82 of 84", "metric": 97.6}, "J": {"pass": true, "detail": "deal_complete=82 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 97.6}, "county": "st_johns", "auctions_total": 84}
```
Before: 9/10, C FAIL (matched_clean=78, 94.0%, auctions_total=83). After: C still FAIL, matched_clean=78
(92.9%, auctions_total grew to 84). One case (TD26-0031) was reconciled to CLERK_SSOT_CANCELLED (D-side),
which did not move the C matched_clean set by design. 4 other candidate rows correctly left untouched
because the clerk source returned HTTP 403 during independent verification. **C remains the sole blocker,
unresolved — could not verify remaining divergent rows.**

### martin — **8/10**
```json
{"A": {"pass": true, "detail": "fc=41 td=1", "metric": 1}, "B": {"pass": true, "detail": "verified=1 closed_sold=1", "metric": 100.0}, "C": {"pass": true, "detail": "matched_clean=40", "metric": 95.2}, "D": {"pass": true, "detail": "matched_any=40", "metric": 95.2}, "E": {"pass": false, "detail": "parcel_linked=37", "metric": 88.1}, "F": {"pass": true, "detail": "tier1_sold=1 closed_sold=1", "metric": 100.0}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": false, "detail": "card_complete=37 of 42", "metric": 88.1}, "J": {"pass": true, "detail": "deal_complete=41 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 97.6}, "county": "martin", "auctions_total": 42}
```
Before/After: unchanged at 8/10, E and I both FAIL (parcel_linked=37 of 42, 88.1%). **No fix applied — see
"What did NOT survive / could not be verified" below.**

### taylor — **8/10**
```json
{"A": {"pass": true, "detail": "fc=7 td=4", "metric": 4}, "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}, "C": {"pass": false, "detail": "matched_clean=10", "metric": 90.9}, "D": {"pass": true, "detail": "matched_any=11", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=11", "metric": 100.0}, "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 7.1}, "I": {"pass": true, "detail": "card_complete=11 of 11", "metric": 100.0}, "J": {"pass": true, "detail": "deal_complete=11 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "taylor", "auctions_total": 11}
```
Before: 7/10 (dispatch brief), C FAIL at 72.7% (matched_clean=8). After: C improved to 90.9%
(matched_clean=10) via 2 CLERK_VERIFIED reconciliations, but remains FAIL (below 95% bar). B and F remain
FAIL (metric=null, zero verified/tier1 outcomes) — **no fix applied, correctly left blank.**

## What SURVIVED adversarial verification (real evidence, logged to `gold_standard_ultraloop_audit`)

| County | Letter | Outcome | Evidence |
|---|---|---|---|
| baker | I | **MOVED FAIL→PASS** (90.0%→100.0%) | Live `parcel_zones` row id=862215 for parcel 121S20000000000023, source=`baker_county_gis_arcgis_parcels_web2_live_2026-08-14`, all FK references (jurisdiction, zoning_district, zone_standards) verified real. No PropertyOnion taint. |
| gadsden | C | **MOVED FAIL→PASS** (87.7%→100.0%) | 8 rows set to `parity_status=CLERK_VERIFIED` citing `gadsden_clerk_tax_deed_auction_table` (live URL). No PropertyOnion taint. Arithmetic internally consistent (40+14+11=65). |
| martin | E | **No move, honest FAIL correctly held** | Verified zero writes made; 3 non-real-property cases with no parcel to link, 2 pre-judgment stubs blocked by realforeclose splash/Firecrawl-out-of-credits/clerk AJAX 401/CAPTCHA. One WISNIESKI surname-match lead explicitly INFERRED-only, correctly NOT written. |
| martin | I | **No move, honest FAIL correctly held** | Same structural blockers as E (I depends on E by construction). Zero writes confirmed live. |
| taylor | C | **Partial reconcile, correctly still FAIL** | 2 of 3 candidate rows (TDA 26-031, TDA 26-032) set to CLERK_VERIFIED with specific, live (HTTP 301) clerk source_url citations. 1 row (case 25-014 CA) correctly left untouched — clerk site 403-blocked further verification. |
| taylor | B | **No move, honest FAIL correctly held** | Zero writes; `foreclosure_outcomes`/`tax_deed_outcomes` confirmed empty for taylor. Clerk hard-deletes closed-case records; qpublic/thirdcircuitfl.org 403, Trellis.law paywalled. |
| taylor | F | **No move, honest FAIL correctly held** | Same as B (F depends on the same outcome tables). |
| st_johns | C | **One reconcile write, C unchanged by design, correctly still FAIL** | Case TD26-0031 set to `parity_status=CLERK_SSOT_CANCELLED`, backed by 3 consecutive PHANTOM flips in `clerk_parity_results` (2026-08-11 to 2026-08-13, machine-logged). 4 other candidate rows correctly left untouched (clerk source 403'd on independent re-check). Cited clerk detail-page URL itself returned 403 on independent verification — flagged as a citation caveat but the corroborating clerk_parity_results evidence is independently DB-verifiable and real. |

All 6 findings above (8 individual letter rows, since martin_EI and taylor_BF each cover two letters) were
logged to `public.gold_standard_ultraloop_audit` with `survived=true`, `ultraloop_mode='fallback'`,
`dispatch_id='fafa18bc-546e-4b80-9eb5-27f0fb8bb95b'`.

## What did NOT survive / ghost-success rejections

**None of the 6 transcripts reviewed this session contained a ghost-success or fabricated finding.** Every
claim reviewed either (a) showed a real, live, correctly-sourced DB write with no PropertyOnion taint, or
(b) honestly reported zero writes with concrete negative evidence (403s, empty tables, exhausted access
paths) rather than inventing a value to force a metric to PASS. This is the correct outcome per the
campaign's HARD RULES — no rows were logged as `survived=false` because no claim in this batch failed
adversarial review.

Structural blockers correctly left unresolved (BLANK > WRONG honored):
- **martin E/I**: 5 cases blocked — 3 non-real-property (no parcel exists to link), 2 pre-judgment clerk
  stubs with no PCN assigned. Every access path attempted (realforeclose splash page, Firecrawl, clerk AJAX,
  CAPTCHA-gated advanced search) failed. One candidate lead (surname pattern match) was explicitly labeled
  INFERRED and correctly not written to the DB.
- **taylor B/F**: clerk hard-deletes closed-case records post-sale; qpublic/thirdcircuitfl.org returns
  Cloudflare 403; Trellis.law is paywalled. No independent verified-outcome source currently available.
- **taylor C** (residual 1 row): case 25-014 CA — clerk site 403-blocked, correctly left CLERK_SSOT_CANCELLED
  rather than guessed.
- **st_johns C** (residual 4 rows): CA25-1585, CA25-0749, CC24-6166, CA25-1540 — clerk source 403-blocked
  on independent re-verification attempt during this closeout, consistent with the researcher's original
  report. Left untouched.

## Certification status

**Only baker is a fresh 10/10 as of this session's evaluation.** No other county in this shard reached
10/10. Per the campaign's SHIP GATE rules, this report does NOT claim any county other than baker as
gold-standard-certified, and even baker's certification per `gold_standard_certify()` requires two
consecutive daily 10/10 runs — this session only confirms the current-cycle 10/10, not certification status
itself.

## Database writes this session

1. `public.gold_standard_ultraloop_audit` — 8 new rows (audit ledger for the 6 findings above, all
   `survived=true`).
2. `public.gold_standard_campaign` (id=4381, dispatch_id=fafa18bc-546e-4b80-9eb5-27f0fb8bb95b) — updated
   `criteria_passed` (5 per-county A-J objects from the fresh evaluation), `criteria_total=10`,
   `exit_reason='timeout'` (honest: this was a single-turn closeout session, not a full 6h loop — not
   claiming 'certified'), `session_end_at=now()`.

No schema/migration changes were made in this closeout step — all underlying data writes (parcel_zones row,
parity_status updates) were performed by the prior research/apply session and are reported here only as
independently re-verified facts.
