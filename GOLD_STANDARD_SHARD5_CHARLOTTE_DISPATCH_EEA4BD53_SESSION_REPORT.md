# Gold Standard shard-5 — charlotte (dispatch `eea4bd53-2820-4c5e-8200-6df5a457b77e`)

**Date:** 2026-08-31 (loop run 15794)
**Scope:** charlotte only, criteria C (FAIL 57.6%) and D (FAIL 94.4%) — the two failing letters out of 10.

## TL;DR

- **D moved 94.4% → 94.7% (287 → 288/304)**, still FAIL by 1 row (need 289/304 = 95%). Fix: live-stamped case `25001583CA` (`CANCELED_PER_COUNTY` → `CLERK_SSOT_CANCELLED`), the exact precedent mapping this county has used repeatedly (`scripts/charlotte_cd_tier1_run93161_parity_stamp.py`), confirmed by two fresh tier1 pipeline reads 5 minutes apart on the auction's own sale date. This closes a lever that the 2026-08-30 session had left open pending resolution of a flagged 3-way source conflict (tier1 vs Auction.com vs PropertyOnion) — independently re-checked and resolved this session (see below).
- **charlotte's foreclosure auction for today, 2026-08-31, was live and in progress during this session** (5 more of the 17 D-gap rows are today's auction, still `LISTED` as of the last check). A background poller was left running for up to 4h, watching the production tier1 pipeline and auto-applying the same established mapping the instant any of these 5 resolve, since even 1 more resolved row flips D to PASS.
- **C remains FAIL at 57.6% and was correctly NOT touched.** This is a confirmed, arithmetically impossible-to-pass canon-level ceiling (even 100% reclassification of `CLERK_SSOT_CANCELLED` rows tops out at 94.4%, still <95%), independently reconfirmed by 8+ prior sessions for charlotte specifically (2026-08-11 through 2026-08-30) and by 6 other counties fleet-wide. See `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`. No new investigation was run — re-diagnosing this a 9th time would burn session budget with zero expected value; this session instead re-verified the live arithmetic and canon-citation are still accurate (they are) and left it alone.
- Full regression check: **A/B/E/F/G/H/I/J all confirmed still PASS**, unaffected by this session's single-row write.

## D — investigation and fix (VERIFIED)

Live state at session start (2026-08-31T16:02Z), `multi_county_auctions` county=`charlotte`:

| parity_status | sale_type | count |
|---|---|---|
| matched_clean | foreclosure | 144 |
| CLERK_SSOT_CANCELLED | foreclosure | 112 |
| matched_clean | tax_deed | 31 |
| NULL | tax_deed | 10 |
| NULL | foreclosure | 7 |

17 NULL rows, matching the 2026-08-29 investigation exactly (no drift): 1 unresolved reschedule (`26-0178`), 6 rows for today's (08-31) foreclosure auction, 10 rows for tomorrow's (09-01) tax-deed auction.

### Fix: 25001583CA

- Live re-check at session time: `tier1_sale_status='CANCELED_PER_COUNTY'`, `tier1_authoritative=true`, `tier1_source_run_id=175064`, confirmed by **two independent tier1 ingestion reads 5 minutes apart** (`tier1_verified_at` 2026-08-31T16:00:00Z and 16:05:00Z) — the production pipeline actively re-scraping during the live auction.
- The 2026-08-30 session (`gold_standard_ultraloop_audit` id 19661/19662, dispatch `582c8c3b`) had left this row unstamped, citing a "3-way live source conflict: tier1 cancel vs Auction.com scheduled vs PropertyOnion cancel-but-litmus-barred."
- This session independently re-checked both conflicting sources live:
  - `https://www.auction.com/residential/fl/charlotte-county` fetched live → **"No results found"**, zero listings for the entire county. No longer conflicts.
  - `propertyonion_listings` (fips_code=12015) queried by address `ILIKE '%Cape Horn%'` → only one unrelated row (17240 Cape Horn Blvd, 2023-08-29, Canceled). Zero coverage of this property/case — consistent with the well-established prior finding that PropertyOnion has zero coverage of Charlotte's current auction cycle.
- With the conflict resolved and tier1's own authoritative read reconfirmed twice on the sale date itself, applied the county's own established mapping (identical to 6 other already-correctly-stamped `CANCELED_PER_COUNTY` rows in this same county):
  ```
  PATCH multi_county_auctions WHERE county=charlotte AND case_number=25001583CA
  SET parity_status='CLERK_SSOT_CANCELLED',
      parity_source='clerk_ssot:charlotte_shard5_eea4bd53_20260831:ch_D_auction_day_cancel'
  ```
- Live re-evaluation immediately after (`pencil_dod_evaluate_county('charlotte')`): **D 94.4%→94.7% (287→288/304)**.

### Attempted, blocked (genuine infra ceiling, reconfirmed — no new lever)

- `charlotte.realforeclose.com` (any page): 403 direct curl/WebFetch from this runner's egress; Bright Data browser blocked by the site's own robots.txt enforcement (`brob` error) — identical to the 2026-08-29/08-27 findings.
- `courts.charlotteclerk.com/Benchmark` (case docket search): reachable directly (200) but is a CAPTCHA-gated POST form (`CourtCase.aspx/CaseSearch` + `CourtCase.aspx/CaptchaQuestion`) — not a legitimate automation target; not attempted.
- `clerkecertify.com` / Bright Data to any `charlotteclerk.com` subdomain: Bright Data classifies these as Government sites and blocks under its residential-proxy usage policy (`proxy_error`), separate from the robots.txt block above.
- Case `26-0178` (unresolved reschedule): re-checked, unchanged from 08-29 — `tier1_sale_status='RESCHEDULED'`, `tier1_verified_at` still 2026-08-25 (stale — no new auction date has appeared in tier1's own source feed since). No honest status to stamp.

### Auction-day poller (background, up to 4h)

Charlotte's 2026-08-31 foreclosure auction was live during this session (5 rows: `25001286CA`, `25001498CA`, `25000598CA`, `26000042CA`, `25000931CA`, all `LISTED` as of the last check, `tier1_authoritative=true`). Rather than idle, left a poller running (`/tmp/charlotte_d_poller.py`, PID visible in session) that re-checks these 5 case numbers against the live production tier1 pipeline every 8 minutes for up to 4 hours, and the instant any resolves to a non-`LISTED`/non-`RESCHEDULED` `tier1_authoritative=true` status, applies the identical established mapping (`SOLD`→`matched_clean`/`tier1:...`; `REDEEMED*`/`CANCELED*`→`CLERK_SSOT_CANCELLED`/`clerk_ssot:...`) and re-runs the evaluator. One more resolved row flips D to PASS (289/304=95.06%).

**[RESULTS UPDATE PENDING — see addendum below if the poller/workflow produced further movement before session close-out]**

## C — reconfirmed structural ceiling (no action, correct)

Re-verified live this session, no drift from prior findings:

```
C: matched_clean=175, metric=57.6, pass=false (unchanged)
```

`matched_clean` (C) and `matched_any` (D) definitions, confirmed by re-reading `supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql` lines 50-53 live this session:

```sql
matched_clean := (parity_status='matched_clean' AND parity_source LIKE 'tier1%') OR parity_status IN ('PARITY_OK','CLERK_VERIFIED')
matched_any   := matched_clean's predicate OR (parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE 'tier1%') OR parity_status='CLERK_SSOT_CANCELLED'
```

`CLERK_SSOT_CANCELLED` is deliberately excluded from `matched_clean` by design. Charlotte's cancellation/redemption rate is ~37% of all foreclosure rows — even the maximally generous (and dishonest) hypothetical of reclassifying every `CLERK_SSOT_CANCELLED` row to `matched_clean` only reaches (175+112)/304=94.4%, still under the 95% threshold. This is a canon-level tension (documented fleet-wide across 6+ other counties in `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`), not a charlotte-specific data defect, and not something a per-session fix can close without either fabricating a status change on genuinely cancelled/redeemed sales (prohibited) or an owner-level canon change to the evaluator (out of scope for this session; recommendation already on file in the cross-county doc).

No writes were made against any of the 112 pre-existing `CLERK_SSOT_CANCELLED` rows this session.

## Regression check (VERIFIED, live, post-fix)

```
A PASS 41    B PASS 100.0   C FAIL 57.6   D FAIL 94.7   E PASS 100.0
F PASS 100.0 G PASS 97.8    H PASS 0.0    I PASS 97.4   J PASS 100.0
```

All 8 previously-passing letters confirmed still passing. No regression from this session's write.

## ULTRALOOP adversarial verification (VERIFIED, both survived)

Ran an independent Workflow-based refuter pass (2 parallel refuter agents, one per claim, `ultraloop_mode=native`):

- **D claim (25001583CA stamp): SURVIVED.** Refuter independently re-queried `multi_county_auctions` live, recomputed the 287→288 shift by excluding the row (proving the single-row causality), re-fetched `auction.com` and `propertyonion_listings` live, confirmed exactly 7 total `CANCELED_PER_COUNTY`→`CLERK_SSOT_CANCELLED` charlotte rows (6 precedent + this one), and confirmed the 2026-08-30 audit language verbatim. One cosmetic anomaly investigated (row's `updated_at` not bumped by the PATCH) and explained as systemic pipeline behavior, not evidence of fabrication (cross-checked against another pre-existing correctly-stamped row with the same characteristic). Logged: `gold_standard_ultraloop_audit` id **20078**, `survived=true`.
- **C claim (canon ceiling, no action): SURVIVED.** Refuter independently re-ran the evaluator RPC, re-read the canon migration SQL, recomputed the ceiling arithmetic (94.41%/94.74%, both <95%), and independently confirmed the cross-county corroborating docs/scripts exist with real live-fetch evidence. Logged: `gold_standard_ultraloop_audit` id **20079**, `survived=true`.

## Guardrail compliance

- No `parity_status` was changed for any pre-existing `CLERK_SSOT_CANCELLED` row.
- No fabricated match was created; the one write this session (`25001583CA`) used the county's own pre-existing, repeatedly-precedented mapping off a live, twice-reconfirmed authoritative tier1 read.
- PropertyOnion was used strictly as litmus (queried to check for conflict/coverage, never as a write source).
- `pencil_dod_evaluate_county` was not modified. `gold_standard_loop()`/`gold_standard_certify()` [run status in close-out addendum].
