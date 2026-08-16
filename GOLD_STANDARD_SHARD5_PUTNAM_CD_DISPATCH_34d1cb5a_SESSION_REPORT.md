# Gold Standard Shard-5 — Putnam C/D Session Report

- **dispatch_id:** `34d1cb5a-793f-4312-9c5f-bda77527a3fd`
- **chat_session:** `architect-20260816T160000`
- **county:** putnam
- **repo:** cli-anything-biddeed (branch `main`)
- **result: DID NOT SURVIVE ADVERSARIAL VERIFY.** The RPC scoreboard shows C/D at 100%, but independent re-verification against the live Putnam Clerk tax-deed certification system found that 4 of the 32 rows promoted to `matched_clean` are actually **redeemed certificates**, incorrectly matched due to a bug in the fix script. This is reported plainly per the SHIP GATE and HONESTY PROTOCOL — no success is claimed for the underlying data-quality goal, even though the raw metric moved.

## Diagnosis

Putnam had 35 `calendar_sweep_mca_v3` stub rows with `parity_status IS NULL`. This is a genuine coverage gap, not a matcher bug: PropertyOnion has not yet scraped these particular auction dates/case numbers, so the standard PropertyOnion-litmus parity check had nothing to compare against for these 35 rows. 32 of the 35 were tax-deed certificate numbers (format `YYYY-NNNNNNN`); the remaining 3 were foreclosure-format case numbers (`5420YYCANNNNNNCAAXMX`).

## Fix Applied

Per the standing C/D litmus-fallback authorization in this repo's CLAUDE.md ("if your parity audit proves PropertyOnion source coverage — not our matcher — is the root cause, you are pre-authorized to adopt clerk/official-records as supplementary litmus source"):

- **STEP 1:** Re-ran `scripts/putnam_clerk_certification_cd_fix.py` against the Putnam Clerk's own tax-deed certification system (`apps.putnam-fl.com/coc/taxdeeds/public/public_certification.php`) for the 32 tax-deed-format rows. Output: `VERDICT COUNTS: {'confirm': 32, 'redeemed': 0, 'mismatch': 0, 'not_found': 3, 'fetch_error': 0}` — promoted 32 rows to `parity_status='matched_clean'`, `parity_source='tier1:clerk_certification_php:putnam:<date>'`.
- **STEP 2:** For the 3 remaining foreclosure-format rows, harvested the live `putnam.realforeclose.com` AJAX calendar for the relevant auction dates and matched all 3 case numbers by exact case_number + auction_date. PATCHed all 3 to `matched_clean` with `parity_source='tier1:realforeclose_ajax_calendar:putnam:<date>'`.
- Net: 35/35 previously-NULL rows promoted; `putnam` scoreboard denominator held constant at 670 rows before and after (verified via independent `content-range` header count both times).

## Before / After `pencil_dod_evaluate_county('putnam')` — pasted verbatim

**BEFORE (session brief baseline):**
```json
{"A": {"pass": true, "detail": "fc=48 td=622", "metric": 48}, "B": {"pass": true, "detail": "verified=3 closed_sold=3", "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=635", "metric": 94.8}, "D": {"pass": false, "detail": "matched_any=635", "metric": 94.8}, "E": {"pass": true, "detail": "parcel_linked=658", "metric": 98.2}, "F": {"pass": true, "detail": "tier1_sold=3 closed_sold=3", "metric": 100.0}, "G": {"pass": true, "detail": "density=98.1 far=100.0 pk1000=100.0", "metric": 98.1}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": true, "detail": "card_complete=639 of 670", "metric": 95.4}, "J": {"pass": true, "detail": "deal_complete=666 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 99.4}, "county": "putnam", "V2_LITMUS": null, "auctions_total": 670}
```

**AFTER (re-run live in this close-out session, 2026-08-16T16:12Z):**
```json
{"A": {"pass": true, "detail": "fc=48 td=622", "metric": 48}, "B": {"pass": true, "detail": "verified=3 closed_sold=3", "metric": 100.0}, "C": {"pass": true, "detail": "matched_clean=670", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=670", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=658", "metric": 98.2}, "F": {"pass": true, "detail": "tier1_sold=3 closed_sold=3", "metric": 100.0}, "G": {"pass": true, "detail": "density=98.1 far=100.0 pk1000=100.0", "metric": 98.1}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": true, "detail": "card_complete=639 of 670", "metric": 95.4}, "J": {"pass": true, "detail": "deal_complete=666 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 99.4}, "county": "putnam", "V2_LITMUS": null, "auctions_total": 670}
```

Raw metric read: C and D both moved 94.8% (635/670) → 100.0% (670/670), denominator unchanged.

## Adversarial Verify Outcome (verbatim)

**overall survived = false**

**clerk-match refuter:**
> "refuted":true,"reasons":"The DB-side facts in the report are accurate (all 35 promoted rows exist with the claimed parity_status/parity_source, and the 670/670 totals check out via live REST queries). However, independently re-fetching the live Putnam Clerk tax-deed certification pages (https://apps.putnam-fl.com/coc/taxdeeds/public/public_certification.php?certnum=<cert>) for all 32 STEP-1 case numbers just now revealed that 4 of them display an explicit, unambiguous banner at the very top of the page reading 'Certificate Number <X> has been redeemed.': case 2021-0011399, case 2024-0010776, case 2024-0017158, and case 2024-0016884. This directly contradicts the prior agent's verdict of 'confirm' (live, unredeemed) for these rows and the resulting promotion to parity_status='matched_clean'. Full page text for 2021-0011399 and 2024-0010776 was inspected and confirmed the banner is genuine (not a parsing artifact of an unrelated section) -- it appears as the very first sentence of the page body, distinct from the 'CERTIFICATES REDEEMED BY APPLICANT' table further down that lists other, older consolidated certificates. The referenced script scripts/putnam_clerk_certification_cd_fix.py has a redemption-detection bug: its evaluate() function only searches for the case number inside the 'CERTIFICATES REDEEMED BY APPLICANT' table section or an explicit 'THIS SALE WAS/IS CANCELLED' string -- it never checks the page's own top-of-page status banner ('has been redeemed') for the certificate actually being queried. Because the boilerplate 'Date of Sale September 30, 2026' text is still present lower on these redeemed-certificate pages (it's part of the static certification form template regardless of redemption status), the script's Date-of-Sale match check passed and produced a false 'confirm' verdict. The STEP-2 realforeclose_ajax_calendar promotions (3 rows) were not independently disproven -- I re-verified their DB records match exactly what was reported, but did not re-harvest the AJAX calendar live (not needed once STEP-1 already failed). Since 4 of 32 (12.5%) sampled promoted case_numbers fail independent re-verification against the live authoritative source -- showing redeemed status rather than a live/unredeemed matching sale -- the claim that all 35 promotions represent genuine live matches is refuted. Putnam's parity_clean rate is NOT genuinely 670/670; at minimum 4 rows were incorrectly promoted from redeemed certificates."

**anomaly refuter:**
> "refuted":false,"reasons":"Independently re-ran pencil_dod_evaluate_county(putnam) live and cross-checked directly against multi_county_auctions. (1) C and D genuinely crossed 95%: BEFORE C=94.8 (matched_clean=635), D=94.8 (matched_any=635); AFTER C=100.0 (matched_clean=670), D=100.0 (matched_any=670), both pass=true — a real +35 row increase, not an artifact. (2) Denominator not gamed: auctions_total=670 in both BEFORE and AFTER RPC output, and an independent raw content-range count query on multi_county_auctions also returns 670/670 for county=putnam — identical denominator, so the % increase is real, not a shrunk-denominator illusion. (3) Fetched all 670 matched_clean rows for putnam directly via REST; zero have a parity_source that doesn't start with 'tier1'. Specifically checked all 35 case_numbers the fix report claims to have promoted — all 35 are present, all are matched_clean, and each has exactly the parity_source claimed in the report (32x tier1:clerk_certification_php:putnam:2026-09-30, 3x tier1:realforeclose_ajax_calendar:putnam:<date>). The 3 STEP-2 ids (95dd0a65-..., 5772c1e3-..., b7cc15e2-...) were queried by exact id and match the claimed case_number/auction_date/sale_type/parity_source in full. (4) No duplicate-counting: 670 rows have 670 distinct case_numbers (0 dupes). Additionally confirmed zero remaining NULL parity_status rows for putnam county (content-range */0). No evidence of the brevard-style denominator-mismatch or ghost-success pattern — the fix is backed by real tier1 sources, a stable denominator, and no double-counting."

**Net verdict:** the DB write is real and not fabricated (facts, denominator, and provenance all check out), but the underlying data-quality claim is FALSE for at least 4 of 35 rows — those 4 certificates are redeemed, not live matched sales. `overall survived = false`.

## Outcome — plainly stated

The DoD gap did **not** genuinely close. The scoreboard metric reads C=100%, D=100%, but this is **not certifiable** because 4 of the 32 clerk-certification promotions (`2021-0011399`, `2024-0010776`, `2024-0017158`, `2024-0016884`) are REDEEMED tax-deed certificates that were incorrectly matched as live `matched_clean` sales due to a redemption-banner detection gap in `scripts/putnam_clerk_certification_cd_fix.py` (it checks the "CERTIFICATES REDEEMED BY APPLICANT" table and a "SALE WAS/IS CANCELLED" string, but never the page's own top-of-page "has been redeemed" banner for the certificate being queried).

This session did **not** fix that bug — it is logged here as an open follow-up for the next Putnam session:
1. Patch `scripts/putnam_clerk_certification_cd_fix.py` to also check for a top-of-page "has been redeemed" banner and treat it as a `redeemed` verdict (not `confirm`).
2. Re-run against the 4 flagged case numbers and demote them from `matched_clean` back to an appropriate non-clean status, or find a genuine alternative match.
3. Re-run `pencil_dod_evaluate_county('putnam')` and re-submit to adversarial verify before any certification claim.

## Session-close actions taken (this session)

- Re-ran `pencil_dod_evaluate_county('putnam')` live (see AFTER JSON above).
- Inserted 2 rows into `gold_standard_ultraloop_audit` (id 16085 letter=C, id 16086 letter=D), both `survived=false`, `ultraloop_mode='fallback'`, with both refuter verdicts stored verbatim in `refuter_evidence`.
- Updated `gold_standard_campaign` (id 4489, `dispatch_id=34d1cb5a-793f-4312-9c5f-bda77527a3fd`) with `criteria_passed` reflecting the fresh after-state RPC (all A-J read `pass=true` from the raw scoreboard), `criteria_total=10`, `exit_reason='timeout'` (NOT `'certified'` — the C/D claim did not survive adversarial verify, so certification cannot be claimed despite the raw metric showing 10/10), `session_end_at=now()`.
- **Did not** fire the `telegram-notify.yml` completion notification — `survived=false`, so per instructions this step is skipped.
- No new script was created for this close-out session; the fix-phase agent reused the pre-existing `scripts/putnam_clerk_certification_cd_fix.py` (already committed prior to this session). `git status` confirmed a clean working tree at session start — nothing to stage from the fix phase.

### SQL VERIFICATION

```
RPC call:
curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"p_county":"putnam"}'

Output:
{"A": {"pass": true, "detail": "fc=48 td=622", "metric": 48}, "B": {"pass": true, "detail": "verified=3 closed_sold=3", "metric": 100.0}, "C": {"pass": true, "detail": "matched_clean=670", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=670", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=658", "metric": 98.2}, "F": {"pass": true, "detail": "tier1_sold=3 closed_sold=3", "metric": 100.0}, "G": {"pass": true, "detail": "density=98.1 far=100.0 pk1000=100.0", "metric": 98.1}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": true, "detail": "card_complete=639 of 670", "metric": 95.4}, "J": {"pass": true, "detail": "deal_complete=666 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 99.4}, "county": "putnam", "V2_LITMUS": null, "auctions_total": 670}

Timestamp (UTC): 2026-08-16T16:12:15Z
```

**Caveat on the SQL VERIFICATION output above:** this is the raw scoreboard read, pasted verbatim as required by the SHIP GATE rule. It shows 10/10 PASS by the RPC's own arithmetic. It is explicitly **not** a certification claim — see Adversarial Verify Outcome above for why `exit_reason='timeout'` (not `'certified'`) was written to `gold_standard_campaign`, and why the Telegram completion notification was withheld.
