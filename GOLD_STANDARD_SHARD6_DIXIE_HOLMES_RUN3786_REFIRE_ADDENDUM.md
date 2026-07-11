# GOLD STANDARD shard-6 (dixie, holmes) — duplicate-dispatch re-fire addendum

**Dispatch:** `f790053e-7def-44f4-914c-0af228ef16b1` (chat_session `architect-20260711T160000`)
**Finding:** this exact dispatch had already been fully worked and shipped ~1h earlier —
commit `0ba7ed91` (2026-07-11 21:33Z) references the identical dispatch ID in its message and
contains the ghost-row purge (dixie) + taxdeed platform metadata fix (holmes) plus the C/D and
B/C/D/F structural-ceiling findings. This session is a **re-fire**, not new work.

## Reconfirmation (live, this session)

`SELECT public.pencil_dod_evaluate_county(...)` at session start, byte-compared to the prior
session's closing state:

| county | A | B | C | D | E | F | G | H | I | J | pass_count |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dixie | PASS (1) | PASS (100.0) | FAIL (75.0) | FAIL (75.0) | PASS (100.0) | PASS (100.0) | PASS (100.0) | PASS | PASS (100.0) | PASS (100.0) | **8/10** |
| holmes | PASS (3) | FAIL (null) | FAIL (61.5) | FAIL (61.5) | PASS (100.0) | FAIL (null) | PASS (100.0) | PASS | PASS (100.0) | PASS (100.0) | **6/10** |

Zero drift. `gold_standard_county_status` independently confirms the same `pass_count`/values,
`evaluated_at=2026-07-11T21:13:54Z` (the prior session's timestamp — not re-evaluated stale data
from before that fix either).

## ULTRALOOP probe: new avenues only

Per protocol, ran one workflow with 4 probe agents targeting sources **not** already exhausted
across the 7+ prior passes logged in `gold_standard_ultraloop_audit` for these counties today,
followed by adversarial verification of the one probe that surfaced a positive claim.

**dixie C/D** (structural ceiling 93.75% max, from the prior session — 2 future auctions baked
into the denominator, 6 Aug-2025 sales show blank results on both known sources):
- Civitek OCRS (Dixie's official-records doorway) + F.S. 197.582 surplus-funds list — both
  checked, both clean negatives, no crawlable/public data for any of the 6 gap parcels.
- Alternate live auction platform — **new, definitive finding**: ruled out RealTaxDeed,
  RealForeclose, GovEase, LienHub, and Bid4Assets. `dixieclerk.com` states outright *"We do not
  conduct the auctions online"* (in-person, Courthouse Board Room, Tuesdays 11am). `dixie.
  realtaxdeed.com` is a dead/unconfigured subdomain redirecting to RealAuction's generic
  marketing homepage — same pattern already found for Holmes. This survived independent
  adversarial refutation (refuter re-fetched every cited source, found the underlying
  conclusion reproducible; flagged only a minor methodology note that the redirect required a
  browser User-Agent to observe, not a bare `curl`). **No dollar amounts claimed or found** —
  this closes off an entire class of "maybe another source has it" hypotheses for future
  sessions, it does not move C/D.

**holmes B/C/D/F** (all 13 auctions have `sold_amount IS NULL`; 6 gap cases with no published
disposition):
- Alternate official-records vendor + Property Appraiser sales history — Civitek OCRS
  identified as the same underlying gate as `myfloridacounty.com` (not an independent source,
  both Civitek-backed). `qPublic.schneidercorp.com` (Schneider Corp confirms it hosts Holmes)
  returned HTTP 403 on every direct-fetch URL pattern — **genuinely UNTESTED, not
  confirmed-empty**. Attempted a Firecrawl browser-bypass to get past the 403 and hit an
  orthogonal blocker: **the Firecrawl API key is out of credits** (`"Insufficient credits to
  perform this request"`, verified live against `api.firecrawl.dev/v1/scrape`). Logging this
  explicitly as a residual rather than silently conflating "billing exhausted" with "source has
  no data."
- F.S. 197.582 surplus-funds list + legal-notice archives — confirmed Holmes's surplus list is
  **email-request-only** (no public PDF, unlike Columbia/Marion/Highlands/Sumter which all
  publish one) — a concrete, actionable finding for a human follow-up, not a scraper gap.
  `fltreasurehunt.gov` (FL DFS unclaimed-property portal) is WAF/bot-gated on direct fetch,
  closing off the state-level fallback too.

**Result: 4/4 new probes are genuine negatives.** No sold/consideration amount recovered for
any gap case on either county. No B/C/D/F/anomaly-class risk (no positive dollar claims made).

## What shipped

`supabase/migrations/20260711u_gold_standard_shard6_dixie_holmes_refire_addendum.sql` — applied
live via the Supabase Management API (direct `SUPABASE_ACCESS_TOKEN`, confirmed the DB-password
connection path documented as stale since 2026-07-03 in `migrations/run_migration.js` is
correctly avoided). Inserts 6 fresh `gold_standard_ultraloop_audit` rows (dixie C/D, holmes
B/C/D/F, all `survived=true`) so the certify-gate's 7-day freshness window doesn't lapse while
these letters remain honestly blocked. **No row in `multi_county_auctions` or `pipeline.counties`
was touched this pass** — there was nothing to fix; the prior firing already covered the only
real defects found (dixie ghost row, holmes taxdeed platform metadata).

## Residuals for a future session (not fixed here, out of scope for this shard)

1. **Firecrawl API credits exhausted** — blocks browser-bypass of `qPublic.schneidercorp.com`'s
   403 for Holmes Property Appraiser sales-history data (the one still-untested lead for
   B/C/D/F). Needs a funded Firecrawl account or a manual browser check.
2. **Holmes surplus-funds list is email-request-only** — a human could email the Clerk directly;
   this is not something a scraper session can close.
3. Dixie C/D structural ceiling (93.75% max) and Holmes B/C/D/F block are now **more thoroughly
   ruled out** than before (an entire alternate-platform hypothesis space closed for Dixie), but
   remain genuinely unresolved online. Manual courthouse/phone contact is the only remaining
   lever for either county, per the prior session's conclusion — unchanged.

## Verification protocol

```sql
SELECT public.pencil_dod_evaluate_county('dixie');   -- 8/10, unchanged
SELECT public.pencil_dod_evaluate_county('holmes');  -- 6/10, unchanged
SELECT * FROM public.gold_standard_ultraloop_audit
  WHERE dispatch_id = 'f790053e-7def-44f4-914c-0af228ef16b1';  -- 6 new rows, all survived=true
```

`gold_standard_loop()` / `gold_standard_certify()` **not** invoked this session — PARALLEL-FLEET
RULES; concurrent shard activity confirmed in git log within the hour (miami_dade, lafayette).
