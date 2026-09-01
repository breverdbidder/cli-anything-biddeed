# Gold Standard Shard-5 — suwannee, wakulla (dispatch 5935a5e6, loop run 16062)

**Session:** 2026-09-01T16:00Z wave · **Mode:** ULTRALOOP native (Workflow tool, 3 concurrent refuter agents) · **Outcome:** zero metric movement — both target letters reconfirmed as genuine structural ceilings under fresh adversarial verification. No fabricated progress.

## Before (live, confirmed at session start)

```json
suwannee: A✓4 B✓100.0 C✗80.0(matched_clean=28/35) D✓100.0 E✓100.0 F✓100.0 G✓100.0 H✓0.1 I✓100.0 J✓100.0
wakulla:  A✓12 B✓100.0 C✗78.8(matched_clean=41/52) D✓100.0 E✗92.3(parcel_linked=48/52) F✓100.0 G✓100.0 H✓5.9 I✗92.3(48/52) J✗92.3(48/52)
```

## After (live, confirmed at session end — byte-identical to before)

```json
suwannee: 9/10, C still FAIL 80.0
wakulla:  6/10, C/E/I/J still FAIL (78.8 / 92.3 / 92.3 / 92.3)
```

## What was done

Rather than re-attempting probes already exhausted by ~10 prior sessions on these exact counties (dispatches 5cd42fe0, 0bf31675, 697ee013, 7c6a5d83, e3fa8568, 8e5bff5d, 3eefe79f, d3cdb7ce, e06b4684, and the 2026-08-25 44-row reconfirm), this session ran three independent adversarial refuter agents (per ULTRALOOP PROTOCOL step 3) whose only goal was to break the ceiling claims with genuinely new evidence or find an actionable lever. All three returned `refuted=false`.

### suwannee C (matched_clean=28/35, 80.0%)
7 gap rows (case_numbers 4741, 4681, 4744, 4693, 4694, 4672, 4676) all carry `parity_status=CLERK_SSOT_CANCELLED`, `parity_source=suwannee_clerk_verified_20260830`, `auction_status=redeemed`, sale date 2026-09-03. Confirmed live against the evaluator's real WHERE clause (`supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`) — CLERK_SSOT_CANCELLED deliberately counts toward D (matched_any=35/35, 100%) but is excluded from C by design, the same canon rule already governing lake/brevard/gadsden/highlands/okeechobee/st_johns/union/wakulla. Refuter additionally checked suwannee.realtaxdeed.com (new source, confirms "no cases currently being auctioned" for 2026-09-03) and the current live clerk PDF schedule (unchanged since 8/30 — no new signal). One genuinely untried lever surfaced: myflcourtaccess.com (FL statewide court records, linked from suwgov.org) — a Nuxt.js SPA requiring Playwright/browser automation, not executable with curl-only tooling this session. Flagged for a future session with browser tooling, not executed on speculation.

### wakulla E/I/J (parcel_id NULL for 4 rows: 2026-TXD-124/125/126/127)
All 4 are tax-deed applications redeemed before the Clerk ever generated a populated case PDF — no address/parcel data has ever existed anywhere. Refuter tried 2 genuinely new angles: LandmarkWeb CaseNumberSearch (new endpoint vs. prior session's NameSearch-only recipe — returned HTTP 500, and confirmed via the full 280+ document-type taxonomy that Wakulla's LandmarkWeb tenant has **no** "Tax Deed Redemption" document type at all, i.e. redemptions are structurally never recorded as official-records documents in this county); RealTDM public case portal (still a non-production "TEST" tenant, unchanged in 2 months); Wakulla County Tax Collector site (JS-shell, needs browser automation); wayback machine (no snapshots cover the case-number window); appraiser site (now identified specifically as Cloudflare-JS-challenge-protected, not just unreachable). Zero writes — no genuine new data found.

### wakulla C (matched_clean=41/52, 78.8%) — light-touch reconfirm
11 gap rows, parity_source=`wakulla_clerk_tax_deed`. Refuter distinguished, for the first time, that 4 of the 11 (TXD-124/125/126/127 — the same rows blocking E/I/J) are **still listed** on the live docket with status "Redeemed" (vs. 7 that have fully rolled off). Traced the code path: `scripts/clerk_ssot/parsers/wakulla.py:92` intentionally maps "Redeemed" → cancelled; `refresh_parity_tier1_outcomes()`'s allow-list (`supabase/migrations/20260704_...`) only re-evaluates rows with `parity_source IN (NULL, 'tier1_tax_deed_outcome', 'tier1_foreclosure_outcome')` — `wakulla_clerk_tax_deed` is permanently outside that gate, so the function structurally cannot re-score these rows regardless of outcome data. Cross-confirmed the identical mechanism independently blocking sumter (`sumter_c_4row_clerk_ssot_redeemed_structural_block_20260829.sql`) and gadsden (2026-08-23) — a 3rd independent county now hitting the same shared-function ceiling shape. **The one real lever**: widen `refresh_parity_tier1_outcomes()`'s parity_source allow-list fleet-wide. This is a shared-function change affecting every clerk_ssot county simultaneously — explicitly out of scope for a single-county session (already flagged out-of-scope once before, by the sumter 2026-08-29 session, for the identical reason). Recommended as a dedicated cross-county review item, not executed here.

## Verification

- Live `pencil_dod_evaluate_county` re-run for both counties after all 3 refuters completed: metrics byte-identical to session start. No regression, no fabricated gain.
- `gold_standard_campaign` row (dispatch_id=5935a5e6-d3af-447b-b579-5623d7435ddf, id=5529) closed out with real `criteria_passed` per county, `exit_reason='adversarial_verify_confirms_structural_ceilings_zero_writes'`, `session_end_at` set live.

## Recommendation for future sessions on these counties

1. **Do not re-run the same wakullaclerk.org / LandmarkWeb / appraiser probes on wakulla E/I/J or suwannee C** — exhaustively tried across ~10+ sessions now with consistent negative results. Only two levers remain, both requiring capability this session lacked:
   - Playwright/browser automation against myflcourtaccess.com (suwannee C) and the Wakulla Tax Collector JS portal (wakulla E/I/J) — genuinely untried, not just re-probed.
   - A DR-512 public-records request or phone call to the respective Clerk (non-web channel) for the redeemed-TDA case files — out of scope for automated sessions.
2. **wakulla C's real fix is a fleet-wide function change**, not per-county scraping: widen `refresh_parity_tier1_outcomes()`'s parity_source allow-list to include native clerk_ssot labels (`wakulla_clerk_tax_deed`, `sumter_clerk_tax_deed`, and equivalents). This would very likely also move sumter and gadsden C simultaneously. Recommend a dedicated cross-county session scoped to this one function, with its own regression testing (touches every clerk_ssot county — high blast radius, needs care).

No database writes were made this session beyond the close-out checkpoint. No code changes. No schema changes.
