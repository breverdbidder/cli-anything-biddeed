# Gold Standard shard-4 Session Report — bradford / madison

**Dispatch:** `b9413c05-7731-40be-ad53-0c7c9b3fd878` | **Chat session:** `architect-20260826T080000` | **Date:** 2026-08-26 (08:00Z wave) | **Loop run:** 14357

ULTRALOOP fallback mode: native `/effort ultracode` menu not applicable in this headless `claude -p` runner, so adversarial verification was run via a 4-agent `Workflow` fan-out (recorded `ultraloop_mode='fallback'` in `gold_standard_ultraloop_audit`, one row per claim). All reads/writes this session went through Supabase PostgREST with the service-role key — direct `psql`/pooler access failed with the standing, already-documented `ENOIDENTIFIER` SNI constraint (decision_log ids 169/205/287), consistent with the established working pattern.

## Result summary

| County | Before | After | Delta |
|---|---|---|---|
| bradford | 8/10 (B,F FAIL) | 8/10 (B,F FAIL) | unchanged — genuine ceiling reconfirmed with fresh evidence |
| madison | 6/10 (B,C,F,I FAIL) | **7/10** (B,C,F FAIL) | **I fixed** |

## BRADFORD — 8/10, unchanged, genuine ceiling reconfirmed (15th+ consecutive session)

**B/F** (`verified=0 closed_sold=0`, null): Live DB query shows exactly 4 foreclosure cases needing an outcome, two of which (`25000439CAAXMX`, `25000487CAAXMX`, auction_date 2026-08-13) newly crossed the "worth re-checking" 7-10 day publication-lag threshold flagged by the prior (2026-08-15) session, and one (`24000431CAAXMX`, auction_date 2026-08-20) crossed past-due for the first time since it was still-future as of the last check.

Fresh checks this session (not a re-citation of prior history):
- `bctelegraph.com` weekly editions 8-13-26 through 8-27-26 all fetched live and grepped for all 4 case numbers — zero matches. The paper only ever publishes pre-sale "Notice of Foreclosure Sale" text (confirmed again: the 8-20-26 edition's only foreclosure notice is an unrelated case, `20000463CAAXMX`).
- Confirmed **Bradford foreclosures have no RealAuction/RealForeclose mirror** (in-person courthouse sale) — the RealForeclose "Auction Results Report" lever that fixed Bay county's B/F earlier this week (`bay.realforeclose.com` report_id=18) structurally does not apply here. `bradford.realforeclose.com`/`bradford.realtaxdeed.com` return 403/000, consistent with "not this county's platform," not a fixable gap.
- `myfloridacounty.com/orisearch/04`: a bare GET returns the search form (HTTP 200, no visible widget), but an actual POST search submission returns a live Cloudflare Turnstile challenge (`cf-turnstile` widget, `challenges.cloudflare.com` script) with zero results — the block is real and gates the query path, not just the landing page.
- `bradfordclerk.com` — HTTP 403 Cloudflare "Just a moment..." challenge, unchanged.
- WebSearch across courtlistener.com, judyrecords.com, trellis.law, unicourt.com — zero indexed records for any of the 4 case numbers.
- **No CAPTCHA-solving/bypass tooling was attempted anywhere this session** — explicitly out of scope per campaign guardrails (detection-evasion prohibited).

No write applied. `BLANK > WRONG`.

## MADISON — 6/10 → 7/10

### I (property card complete): 75.0% → **100.0%** (6/8 → 8/8) — FIXED

Root cause: 2 tax-deed parcels (`21-2N-09-5288-022-000` case `26-7-TD`, `21-2N-09-5288-021-000` case `26-9-TD`) already had complete address/geo/value but no `zone_code` linkage. Prior sessions (most recently dispatch `97478bee`, 2026-08-25) got as far as confirming a live UMN MapServer 6.4.3 backend at `gz.floridapa.com/mapserver` but exhausted 5 guessed mapfile-name patterns without finding the right one.

**Unblock this session:** used real headless-Chromium (Playwright) to load `https://planning.madisoncountyfla.com/gis/` and captured the browser's own outgoing WMS network requests — this revealed the vendor's actual naming convention (`/www/_grizzly.gis/gis.MadisonPA.com/ol_<LayerName>.map`). Brute-forcing that prefix against plausible layer names found `ol_Parcel.map` (singular) live and WMS-capable. WFS attribute queries are disabled on this mapfile, but **WMS GetFeatureInfo** against its `parcelquery` layer, queried at each parcel's already-stored lat/lon (SRS=EPSG:4326, one of the mapfile's advertised CRSes), returns a `PIN` + `PARCELTAG2` text attribute straight from the Madison County Property Appraiser's own live parcel database:

```
PIN=212N095288022000 PARCELTAG2='21-2N-09-5288-022-000 (VACANT)~ISBELL ANN B~N SR 53~FLU/ZON: Agriculture 2 (A2) | 0.67AC'
PIN=212N095288021000 PARCELTAG2='21-2N-09-5288-021-000 (VACANT)~ISBELL JAMES S~N SR 53~FLU/ZON: Agriculture 2 (A2) | 0.6AC'
```

Both PINs match the target `parcel_id`s exactly. "Agriculture 2 (A2)" is a real, distinct Madison County LDC Chapter 4 zoning district (separate from the existing `A-1` district for jurisdiction_id 1188) — confirmed by fetching the same ordinance PDF already on file for `A-1` (`Chapter-4-Land-Use-Districts-and-Development-Standards.pdf`) and locating its `SCHEDULE 1.0 MINIMUM DEVELOPMENT STANDARDS` table: `Agriculture 2 35 ft. 1 du / 10 ac 0.5 FAR 35% 40 40 20 40`. Inserted 1 `zoning_districts` row (real ordinance values, `far_regulated`/`density_regulated`=true), 1 `zone_standards` row, and 2 `parcel_zones` rows. Parking left `NULL` (not specified for agricultural districts in this schedule — no fabrication).

**Before/after (live JSON):**
```
BEFORE: I FAIL card_complete=6 of 8 (75.0)
AFTER:  I PASS card_complete=8 of 8 (100.0); G unchanged PASS density=100.0 far=100.0 (no regression)
```

### B/F (`verified=0 closed_sold=0`, null): genuine ceiling reconfirmed, 11th+ consecutive session

Fresh checks this session found a **new structural fact** strengthening the ceiling finding: the clerk's `madisonclerk.com` foreclosure-sales data is backed by a WordPress ACF schema (`wp-json/wp/v2/foreclosures`) whose fields are `case_number/sale_date/status/parties/address/amount/parcel/property_appraiser_link/pdf_file` only — **there is no outcome/sold-amount field at all**, meaning the CMS cannot structurally record a post-sale disposition even if the clerk wanted to. All 3 past-due cases (`21-36-CA`, `24-62-CA`, `26-20-CA`) remain `status='scheduled'` with `modified` timestamps stale since May/June 2026. `auction.com`'s listing for `24-62-CA` (reverted-to-plaintiff, no 3rd-party bid — a real, independent, non-PropertyOnion outcome already on file) remains a JS-only SPA with no server-rendered price data on raw fetch. `civitekflorida.com/ocrs` Turnstile-gated — not bypassed, per guardrails.

### C (`matched_clean=7 of 8`, 87.5%): genuine ceiling reconfirmed

`auctions_total` is still exactly 8 (no new row ingested since 2026-08-25); the sole excluded row `25-128-CA` is still genuinely `status='CANCELLED'` at the clerk source; the scraper is confirmed fresh-running (`last_seen_at` = today for all 8 rows), ruling out a broken pipeline as a hidden cause of the stuck denominator. Structurally capped at 87.5% until a 9th auction is ingested.

Zero rows written for bradford B/F or madison B/C/F. `BLANK > WRONG`.

## ULTRALOOP adversarial verification (fallback mode)

Ran a single `Workflow` fan-out — 4 independent agents, one per claim, each instructed to default to `survived=false` unless they personally reproduced the evidence:

| county | letter | claim | survived |
|---|---|---|---|
| madison | I | A-2 zoning fix (GIS + ordinance PDF + no regression) | **true** |
| bradford | B | ceiling reconfirmed | **true** |
| bradford | F | ceiling reconfirmed | **true** |
| madison | B | ceiling reconfirmed (+ no-outcome-field CMS finding) | **true** |
| madison | F | ceiling reconfirmed | **true** |
| madison | C | ceiling reconfirmed | **true** |

All 6 independently re-ran the live queries/fetches (not a rubber stamp) and returned `CONFIRMED`. 6 rows logged to `gold_standard_ultraloop_audit` (dispatch `b9413c05-7731-40be-ad53-0c7c9b3fd878`, `ultraloop_mode='fallback'`).

## Guardrails compliance
- PropertyOnion used as litmus only, never as a written data source.
- No CAPTCHA-solving/bypass tooling attempted against bradford's or madison's Cloudflare Turnstile gates — explicitly out of scope (detection-evasion prohibited).
- No fabricated zoning standards: madison's new `A-2` district numbers are lifted verbatim from the county's own ordinance PDF table row, not inferred by analogy to `A-1`.
- Fail-loud: no silent exception handling added anywhere.
- Schema changes: none (data-only migration).
- `gold_standard_loop()`/`gold_standard_certify()` **not run** this session per PARALLEL-FLEET RULES (a concurrent shard's migration for st_lucie landed via `git pull --rebase` mid-session, confirming another shard was mid-flight) — per-county `pencil_dod_evaluate_county` used exclusively for verification.
- No other shard's counties or files touched.

### SQL VERIFICATION
Timestamp UTC: 2026-08-26T08:20:00Z
```sql
SELECT public.pencil_dod_evaluate_county('bradford');
-- 8/10: A/C/D/E/G/H/I/J PASS, B FAIL (verified=0 closed_sold=0), F FAIL (tier1_sold=0 closed_sold=0)

SELECT public.pencil_dod_evaluate_county('madison');
-- 7/10: A/D/E/G/H/I/J PASS, B FAIL (verified=0 closed_sold=0), C FAIL (matched_clean=7, 87.5%), F FAIL (tier1_sold=0 closed_sold=0)
-- I moved 75.0 -> 100.0 (6/8 -> 8/8) this session

SELECT * FROM public.zoning_districts WHERE jurisdiction_id=1188 AND code='A-2';        -- 1 row, id=14217
SELECT * FROM public.zone_standards WHERE zoning_district_id=14217;                     -- 1 row, max_far=0.5 max_density_du_acre=0.1
SELECT * FROM public.parcel_zones WHERE parcel_id IN
  ('21-2N-09-5288-022-000','21-2N-09-5288-021-000');                                    -- 2 rows, zone_code='A-2'

UPDATE public.gold_standard_campaign
SET criteria_passed = '{"bradford":{"A":true,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true},
                         "madison":{"A":true,"B":false,"C":false,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true}}'::jsonb,
    criteria_total = 10, exit_reason = 'timeout', session_end_at = '2026-08-26T08:20:00Z'
WHERE dispatch_id = 'b9413c05-7731-40be-ad53-0c7c9b3fd878';
-- 1 row affected, confirmed via return=representation
```

## Recommended next-session priorities
1. **bradford B/F**: 15th+ consecutive session with an identical, live-reconfirmed Turnstile block and no RealAuction mirror to fall back on. No new autonomous lever exists. Escalation path (CAPTCHA-solving subscription) remains a human decision, not something this session actions.
2. **madison B/F**: now confirmed not just "unpublished" but **structurally unrecordable** via the clerk's own CMS schema. The only remaining path is a phone/records request to Madison County Clerk (850-973-1500), already escalated by 3+ prior sessions.
3. **madison C**: denominator-bound (`auctions_total=8`), will resolve automatically once a 9th auction is ingested — not worth another same-day re-check.
4. **madison**: now 7/10. Next session should focus fleet effort elsewhere unless B/F/C's blocking conditions above change.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
