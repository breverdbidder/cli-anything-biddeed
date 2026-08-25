# GOLD STANDARD shard — union, holmes — dispatch `767d79ca-dfac-49df-88f9-de74d53d832f` (2026-08-25T08:00Z)

## Result: 0 letters moved — both structural blocks reconfirmed live via ULTRALOOP diagnose+adversarial-verify, zero fabrication, zero regression

```sql
select public.pencil_dod_evaluate_county('union');
-- A pass(1) B pass(100.0) C fail(66.7, "matched_clean=2") D pass(100.0) E pass(100.0)
-- F pass(100.0) G pass(100.0) H pass(2.5) I pass(100.0) J pass(100.0)  -- 9/10, unchanged

select public.pencil_dod_evaluate_county('holmes');
-- A pass(6) B fail(null,"verified=0 closed_sold=0") C fail(68.8,"matched_clean=11")
-- D fail(68.8,"matched_any=11") E pass(100.0) F fail(null,"tier1_sold=0 closed_sold=0")
-- G pass(100.0) H pass(2.5) I pass(100.0) J pass(100.0)  -- 6/10, unchanged
```

## Method: ULTRALOOP workflow (native), 3 diagnose agents + 3 adversarial verifiers, all fresh live sources

Ran `Workflow` (dispatch-scoped, resumable at `wf_37d96315-820`) with independent, isolated-context
subagents — no shared context with each other or with this orchestrating session:

1. **union-C** — reconfirm the structural block on the `CLERK_SSOT_CANCELLED` row.
2. **holmes-B/F** — fresh 16-day-later sweep (last checked 2026-08-09, 17th+ session) including a
   deep-dive on the one `auction_status='completed'` row and a new defendant-surname search lever.
3. **holmes-C/D** — fresh re-check of the 5-row parity gap, including a new parcel-ID (not just
   case-number) search lever against holmesclerk.com.

Every claim then got an independent adversarial refuter subagent whose only goal was to break it by
re-fetching sources itself rather than trusting the claimant. **All 3 claims survived** (see
`gold_standard_ultraloop_audit` ids 18004–18006, plus 18002–18003 from the holmes-B/F sub-session,
all `survived=true`, dispatch-tagged, `ultraloop_mode='native'`).

## union — letter C (66.7%, matched_clean=2 of 3)

Structurally blocked, **not a bug**. `pencil_dod_evaluate_county`'s C rule is
`(parity_status='matched_clean' AND parity_source LIKE 'tier1%') OR parity_status IN ('PARITY_OK','CLERK_VERIFIED')`.
Row `bddc9acb-805b-49e4-8fe1-5048351604a5` (case `63-2025-CA-0053`) carries
`parity_status='CLERK_SSOT_CANCELLED'` — the sale was legally vacated (Order Granting Motion to
Cancel Foreclosure Sale and Vacate Final Judgment, filed 2026-08-03, cross-referenced against the
original Final Judgment filed 2026-01-12, exact parcel/address match). `CLERK_SSOT_CANCELLED` is
**deliberately** excluded from C by the evaluator's design (migration
`20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`) — it counts for D
(`matched_any`) but not C, because it represents a divergence the clerk corrected, not a
no-divergence-ever clean match. Relabeling it clean would be fabrication (guardrail #3). Identical
structural pattern to the calhoun precedent (`calhoun_c_546of2024_phantom_ssot_cancel_reconcile.sql`).

With `auctions_total=3`, 95% requires 3/3 — mathematically unreachable while this row exists and is
correctly classified. No 4th union auction has appeared to dilute the denominator. Live re-check of
`recording.unionclerk.com` (both cited instrument URLs) returned HTTP 403 Cloudflare "Just a
moment..." challenge on independent fetch attempts by both the diagnose and verify agents — the
clerk's official-records portal is bot-walled, consistent with (not copied from) prior findings.
**No fix exists that doesn't fabricate a match.** Zero writes made to `multi_county_auctions`.

## holmes — letters B, C, D, F (18th+ consecutive session confirming the identical ceiling)

**B/F** (verified=0/closed_sold=0, tier1_sold=0/closed_sold=0): holmes now has 16 rows (was 13 at
the 17th session, dispatch `3b7ed6ea`) — the 3 new rows are all future-dated foreclosures
(Aug 27–Oct 15 2026) that structurally cannot have outcomes yet. The one `auction_status='completed'`
row (id `123a1bd5`, sale date 2026-06-11, now 75 days past) was deep-dived this session: its
`case_number` is a synthetic `HOLMES-LEGACY-<uuid>` placeholder — no real court case number was ever
captured at ingestion, making it unmatchable by case-number lookup against any clerk source by
construction. A pre-existing `foreclosure_outcomes` row (`outcome='sold'`, `winning_bid=null`,
enriched 2026-06-25) confirms a disposition label exists but the dollar amount was never captured
and is unrecoverable via case-number search. New lever tried this session — defendant-surname
("Gillis") and street-name ("Beckwood") site search on holmesclerk.com — both returned zero results.
`holmescountytaxcollector.com` still carries zero tax-deed hyperlinks. The `myfloridacounty.com`
ORI / `civitekflorida.com` OCRS Cloudflare Turnstile wall remains the only theoretical remaining
lever and remains explicitly out of bounds (no CAPTCHA bypass). Full independent write-up:
`GOLD_STANDARD_HOLMES_BF_18TH_SESSION_RECHECK_DISPATCH_4CB27213.md` (sub-dispatch
`4cb27213-6fb5-44ee-8eeb-d97c1ccc0808`, own audit rows 18002–18003).

**C/D** (matched_clean=matched_any=11 of 16 = 68.8%): the same 5 gap cases as every prior session
(`TD#2020-589`, `TD#2023-185`, `TD#2023-225`, `TD#2023-496`, `TD#2023-584`) remain `parity_status=null`.
Fresh live fetch of all 3 holmesclerk.com pages (foreclosures/tax-deeds/lands-available-for-taxes,
`lastmod=2026-08-20`, confirmed current) shows zero of the 5 cases anywhere. New lever this
session — site search **by underlying parcel_id** in addition to case_number — also returned zero
results for all 5, ruling out a renumbering/re-key scenario. No PropertyOnion litmus exists for
holmes (`cd_litmus_parity_v2` has 0 rows), so the only litmus in force is the self-referential
"currently live on holmesclerk.com" check, which all 5 genuinely fail. Zero writes made.

## Regression check (P0 per PARALLEL-FLEET RULES)

Re-ran `pencil_dod_evaluate_county` for both counties after all agent work completed: **identical**
to the pre-session brief for every one of the 20 letter-checks (9/10 union, 6/10 holmes, same
metrics to one decimal place). No regression.

## Writes this session

- `gold_standard_ultraloop_audit`: 5 rows this session (18002–18003 under sub-dispatch `4cb27213`,
  18004–18006 under this dispatch `767d79ca`), all `survived=true`, refreshing the certify-gate
  7-day freshness window for union-C and holmes-B/C/D/F.
- `summit_chat_dispatch`: 1 sub-dispatch row (`4cb27213...`, state `closed`) as the FK target for
  the holmes-B/F sub-session, following the same pattern as prior non-SUMMIT-launched audit writes.
- `gold_standard_campaign`: 1 closeout row (id 5024), `dispatch_id=767d79ca...`,
  `exit_reason='blocked_confirmed_dead_end'`, full A–J `criteria_passed` for both counties.
- **Zero** writes to `multi_county_auctions`, `tax_deed_outcomes`, or `foreclosure_outcomes` — no
  fabrication, per guardrail #3 (fail-loud, never manufacture a match to force a pass).
- Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run (other
  shards may be mid-flight this 08:00Z wave); per-county `pencil_dod_evaluate_county` was used for
  all verification instead.

## Recommendation for future sessions

Both counties are exhausted on every currently-reachable, non-CAPTCHA-gated public source:
- **union C**: mathematically blocked until either (a) 2+ new union auctions are ingested to dilute
  the 1-bad-row-of-3 ratio below 5%, or (b) never — a legally vacated sale cannot become "clean."
  Do not re-attempt `recording.unionclerk.com` scraping without Cloudflare-bypass tooling that
  doesn't yet exist in this pipeline (and per policy would need explicit authorization, not silent
  adoption).
- **holmes B/C/D/F**: do not re-run the holmesclerk.com / tax-collector / site-search checks as if
  new — 18+ sessions across 6 weeks have now exhausted every indexed search vector (case number,
  parcel ID, defendant surname, street name) with zero results. The only remaining lever is the
  Turnstile-gated ORI/OCRS portals, which requires either a funded browser-rendering service or a
  human/courthouse step, neither available autonomously today.

Timestamp UTC: 2026-08-25T08:12Z.

---
dispatch_id: 767d79ca-dfac-49df-88f9-de74d53d832f
workflow_run_id: wf_37d96315-820
