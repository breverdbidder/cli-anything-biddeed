# GOLD STANDARD SHARD-2 — gadsden / martin / holmes

dispatch_id: `8000b258-5ab4-4abf-8208-ef4a2eea1444`
chat_session: `architect-20260818T080000`
loop run: 12346

## Summary

All three assigned counties were re-evaluated live this session and their failing
letters were given fresh, adversarially-verified investigation. **No metric moved.**
Every finding below is a confirmed structural or tooling ceiling, not a scraping gap
that today's session left unaddressed — each is backed by a live query/fetch this
session, logged to `gold_standard_ultraloop_audit` with `survived=true`.

| County | Before | After | Passing | Failing |
|---|---|---|---|---|
| gadsden | 9/10 | 9/10 (unchanged) | A,B,D,E,F,G,H,I,J | C |
| martin | 8/10 | 8/10 (unchanged) | A,B,C,D,F,G,H,J | E,I |
| holmes | 6/10 | 6/10 (unchanged) | A,E,G,H,I,J | B,C,D,F |

## 1. gadsden C (87.7%, 57/65) — confirmed structural, not a stale-cancel bug

Today's earlier commit `35c162dd` fixed a real bug in `run_parity.py`'s
`clean_matches` handling: once a row was tagged `CLERK_SSOT_CANCELLED` it could
never be reactivated even after the clerk rescheduled it (fixed for lake). Gadsden's
8 non-clean rows (`26000*TDC`, sale date 2026-09-02, `auction_status='redeemed'`)
are exactly that status, so this was a real, evidence-based lever to test — not a
blind re-check.

Built `scripts/gold_standard_shard2_gadsden_martin_holmes_8000b258.py`, a **scoped**
re-run of `run_parity.py`'s `stage_rows`/`diff_and_reconcile` limited to ONLY
gadsden (foreclosure + tax_deed) and holmes (foreclosure), so no other shard's
counties were touched (guardrail compliance — full `main()` would have written to
~25 other counties across other shards). Ran it live:

```
[gadsden/tax_deed] rows=38 -> ssot_count=34 matched=34 cancelled_mismatch=8 status=STALE_CANCEL
```

**Result: 0 rows reactivated.** All 8 are still genuinely cancelled per the live
clerk SSOT — the fix simply synced `auction_status` (`redeemed`→`CANCELLED`) and
`parity_source`, no `parity_status` change, so C is unaffected. Verified no
side-effect regression: the `/lots` feed fix shipped earlier today
(`c91c7d67`) allow-lists only `upcoming,active,scheduled`, so `redeemed` and
`CANCELLED` were already equally excluded — this write changed nothing user-facing.
`closed_sold`/B/F are keyed on `sold_amount IS NOT NULL`, untouched by this write.

By design (migration `20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition`),
`CLERK_SSOT_CANCELLED` counts toward D (matched_any) but deliberately NOT toward C
(matched_clean) — a cancelled/redeemed sale is a corrected divergence, not a
no-divergence-ever clean match. That's intentional, cross-shard-shared scoring logic;
I did not touch it. Gadsden C is capped at 57/65=87.7% until the auction universe
grows enough to dilute the 8 legitimately-redeemed rows below 5% of the total, or
until it's decided the C denominator itself should exclude terminal-redeemed rows
(a fleet-wide evaluator change, out of this session's scope).

## 2. holmes B/C/D/F — 18th confirmation, zero drift since the 17th session (Aug 9)

Per the 17th-session report's own recommendation ("do not re-attempt... they are now
exhausted"), did **not** repeat the full battery. Did a bounded fresh check:

- Scoped clerk_ssot re-run (holmes foreclosure): 4/4 rows matched live, 0 drift.
- Live GET of both `holmesclerk.com` foreclosure/tax-deed pages, byte-grepped for
  the 5 known gap case numbers (2020-589, 2023-185, 2023-225, 2023-496, 2023-584):
  **0 occurrences**, tax-deed page still shows the boilerplate
  "no sales scheduled" text.
- Site freshness confirmed via sitemap (`post-sitemap.xml` lastmod 2026-08-14,
  4 days before this session) — not a stale cache, the site is actively maintained
  and simply has never published a disposition for these cases.
- `closed_sold=0` (all 16 rows have `sold_amount IS NULL`) — B/F are mathematically
  undefined until any single sale outcome surfaces from an independent source.
  myfloridacounty/civitek OCRS remain Cloudflare Turnstile-gated; per hard rule,
  not bypassed.

No writes to `multi_county_auctions`, `tax_deed_outcomes`, or `foreclosure_outcomes`.
Logged 4 fresh `survived=true` audit rows (B/C/D/F) to extend the certify-gate
freshness window, since the prior evidence had aged past the 7-day window (Aug 9 →
Aug 18 = 9 days).

## 3. martin E/I (93.0%, 40/43) — adversarially-verified, no fabricated parcel

The 3 unlinked rows (`23001555CCAXMX`, `25001632CCAXMX`, `25001634CCAXMX`) all carry
`case_classification_code='NON_REAL_PROPERTY'` (plaintiffs: Tropical Acres
Homeowners Association, and Plantation Beach Club Condominium Association ×2 —
HOA/condo-association lien foreclosures). Because 43×0.95=40.85, resolving even ONE
of these 3 flips both E and I to PASS, so this was worth a real research pass rather
than writing it off immediately.

Ran an ULTRALOOP workflow (`wf_1971079d-08b`): 3 independent research agents (one
per case, real WebFetch/WebSearch against RealForeclose, Sunbiz, Martin Clerk,
Martin Property Appraiser, UniCourt) each followed by an independent adversarial
refuter instructed to try to break the finding. All 3 negatives **survived**
refutation:

- **23001555CCAXMX**: no Sunbiz entity named "Tropical Acres Homeowners
  Association" registered in Martin County (only an unrelated Pasco County HOA of
  a near-identical name). Best candidate location, Tropical Acres Mobile Home Park
  (Jensen Beach), is independently confirmed by multiple listing sources to be a
  share-in-cooperative-corporation ownership structure, not individually deeded
  fee-simple lots — structurally consistent with the existing `personal_property`
  tag, but not confirmed as *this* case.
- **25001632CCAXMX / 25001634CCAXMX**: plaintiff resort identified as Plantation
  Beach Club at Indian River Plantation, Stuart — deeded fixed/floating timeshare
  intervals per Fla. Stat. Ch. 721, which are not individually parcelized. Repeated
  independent AI-search attempts at a parcel number produced 3–4 mutually
  inconsistent numbers (including one tied to an unrelated owner) — treated as
  noise and **not written**, per the hard rule against fabricating a parcel_id in
  a live financial pipeline.
- Both RealForeclose detail pages (session-gated) returned HTTP 403 for every
  agent that tried them; Martin Clerk's case search and Property Appraiser parcel
  search are both interactive/form-driven and not reachable via WebFetch/WebSearch.

This matches (and gives fresh, independently-adversarially-verified evidence for)
the prior session's conclusion
(`GOLD_STANDARD_SHARD5_MARTIN_18535_RUN10213_SESSION_REPORT.md`): the only
remaining lever is a paid ($1/page) `RecordRequest@martinclerk.com` public-records
request — non-automatable, multi-day turnaround, not attempted this session (no
spend authorization needed since nothing was spent, but it's a human/email step,
not something a headless session can execute).

One playbook correction for future sessions: `mcpafl.org` (referenced in an earlier
GADSDEN/DUVAL-era note as a generic county-appraiser pattern) is Monroe County's
appraiser, **not** Martin's — flagged so nobody wastes a session on the wrong URL
again. Martin's actual appraiser domain redirects `pa.martin.fl.us` →
`pamartinfl.gov`, also form-driven, no public ArcGIS REST endpoint found this
session.

## Writes this session

- 1 file: `scripts/gold_standard_shard2_gadsden_martin_holmes_8000b258.py` (scoped
  clerk_ssot re-run, reusable), committed + pushed to `main` (`da3885ae`).
- 8 rows to `multi_county_auctions` (gadsden, `auction_status`/`parity_source`/
  `auction_date` sync only — no `parity_status` change).
- 6 rows to `gold_standard_ultraloop_audit` (gadsden C ×1, holmes B/C/D/F ×4,
  martin E/I ×2), all `survived=true`.
- 1 `gold_standard_campaign` close-out row for this dispatch.
- **Zero** fabricated `parcel_id`, `sold_amount`, or `parity_status='matched_clean'`
  writes anywhere.

## Verification (live, pasted from this session)

### SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('gadsden');
-- 9/10 identical before/after: {"C":{"pass":false,"metric":87.7,"detail":"matched_clean=57"}, ...}

SELECT public.pencil_dod_evaluate_county('martin');
-- 8/10 identical before/after: {"E":{"pass":false,"metric":93.0,"detail":"parcel_linked=40"},
--                                "I":{"pass":false,"metric":93.0,"detail":"card_complete=40 of 43"}, ...}

SELECT public.pencil_dod_evaluate_county('holmes');
-- 6/10 identical before/after: {"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
--                                "C":{"pass":false,"metric":68.8,"detail":"matched_clean=11"},
--                                "D":{"pass":false,"metric":68.8,"detail":"matched_any=11"},
--                                "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"}, ...}

SELECT letter, county_slug, survived, created_at FROM gold_standard_ultraloop_audit
  WHERE dispatch_id = '8000b258-5ab4-4abf-8208-ef4a2eea1444' ORDER BY county_slug, letter;
-- 6 rows, all survived=true, created_at 2026-08-18T08:08-08:15Z

SELECT dispatch_id, criteria_passed, exit_reason, session_end_at FROM gold_standard_campaign
  WHERE dispatch_id = '8000b258-5ab4-4abf-8208-ef4a2eea1444';
-- exit_reason='structural_ceiling_confirmed_all_targets', session_end_at=2026-08-18T08:15:28Z
```

Timestamp UTC: 2026-08-18T08:15Z.

## Recommendation for future sessions

- **gadsden C**: no further automated lever exists under current canon (C
  deliberately excludes `CLERK_SSOT_CANCELLED`). Either wait for `auctions_total`
  to grow and dilute the 8 redeemed rows below 5%, or raise a cross-shard proposal
  to exclude terminally-redeemed tax-deed rows from the C/D denominator entirely
  (would need coordination — it changes shared evaluator SQL).
- **holmes B/C/D/F**: do not re-run the site-search/tax-collector checks again as
  if new (exhausted 18 times now). The only remaining theoretical lever is the
  Cloudflare-Turnstile-gated myfloridacounty/civitek OCRS search, which requires
  either a funded Firecrawl browser-rendering account or a human/phone step;
  bypassing Turnstile is out of bounds regardless of tooling.
- **martin E/I**: the only remaining lever is the paid $1/page Martin Clerk
  `RecordRequest` for the 3 personal-property/timeshare cases — a human/email
  action, not something a future autonomous session can execute differently.

---
dispatch_id: 8000b258-5ab4-4abf-8208-ef4a2eea1444
