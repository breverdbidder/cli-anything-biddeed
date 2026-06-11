# 🔥 FIRE BREVARD B2 — Foreclosure Lane to 95% (Self-Contained Session Kickoff)
**Paste this whole file as the first message of a new Claude Code session with Supabase MCP enabled.**
Project: `mocerqjnksmhcjzxrewo` · Repo: `breverdbidder/cli-anything-biddeed` · Authored 2026-06-11 by Summit session (verified facts only).

---

## MISSION
Close Brevard PENCIL criterion **B** to **≥95%** by landing the **foreclosure lane**: ≥2,400 verified realized foreclosure outcomes written to `public.foreclosure_outcomes` from official primary sources. The tax-deed lane is ALREADY RUNNING autonomously (see "What is already live" — do not rebuild it, do not touch it).

## WHAT IS ALREADY LIVE (verified 2026-06-11, do not duplicate)
- **B = 8.1% and climbing** (was 0.0% this morning). 536 TD + 5 FC verified rows written.
- **TD backfill engine**: cron job **148** (`brevard_td_backfill_tick`, every 2 min) drains `pipeline.brevard_td_backfill_queue` (375 dates) — one serial dispatch of `scrape-brevardclerk.yml` at a time → `pipeline.tier1_card_raw`. **Serial because 18-parallel dispatches crushed Firecrawl concurrency (proven: empty-md failures + page-1 truncation). Never parallelize Firecrawl runs.** Self-unschedules when drained. ETA ~20–25h from 2026-06-11 14:00Z.
- **TD ETL**: cron job **147** (`etl_brevard_td_outcomes_from_tier1`, every 30 min) flushes staging → `tax_deed_outcomes` (`data_source='realtaxdeed_brevard'`). Canon map: SOLD/SOLD_3RD_PARTY/SOLD_CERT_HOLDER→sold, REDEEMED→redeemed, CANCELED→cancelled, LISTED excluded.
- **FC calendar cancellations**: 5 rows written `data_source='brevardclerk_html'` from `http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html` (page is calendar-only, forward-looking, ~108 rows, comment ∈ {blank, CANCELLED}).
- Telemetry repaired: `reconcile_gha_dispatch_log()` + cron 145. Dispatches are observable.

## THE CRITICAL FACT THAT SHAPES THIS BUILD (verified by SQL 2026-06-11)
Of 2,625 Brevard MCA foreclosure rows with `sold_amount IS NOT NULL`:
- **2,584 (98.4%) have PropertyOnion-synthetic case numbers (`PO-XXXXXX`)** — NOT real court case numbers.
- Only 4 have real format (`05-YYYY-CA-######-XXCA-BC`); 37 other/garbage.

**Therefore a per-case BECA lookup keyed on MCA case numbers is IMPOSSIBLE as the primary lane.** The v1 mental model ("for each MCA case, look up the result") is dead. Invert it:

> **Enumerate realized outcomes FROM the primary source BY DATE, and write them all.** B's locked numerator counts verified rows in the outcome tables independent of MCA matching (acceptance SQL below). MCA linkage is a bonus for C/D via the address rekey bridge (`sql/brevard_case_rekey.sql`, 121 FC rows already bridged) — extend it after outcomes land, not before.

## SOURCE MODEL (priority order)

### Lane 1 — PRIMARY: AcclaimWeb official records (Harris/Acclaim), date-range enumeration
- Brevard official records run on AcclaimWeb: `https://officialrecords.brevardclerk.us/AcclaimWeb/` (verify exact base live).
- The Acclaim platform exposes JSON search endpoints behind the grid UI (Duval precedent: the Harris Recording API was decoded for the Duval verified-outcomes pipeline — search everest-vault and prior session notes/issues for the decode; the request shape is a POST to the search controller returning JSON rows with DocType, RecordDate, parties (Grantor/Grantee), case/instrument numbers, Consideration, legal). **Step 1 of this session = locate or re-derive that decode against Brevard's instance.**
- Sweep **doc type `CT` (Certificate of Title)** — the recorded instrument that marks a COMPLETED foreclosure sale — over `2018-08-01 → today`, month by month. Each CT row yields: real case number, winner (Grantee), recording date, often Consideration (= sale amount), legal/parcel.
- Also sweep **`CS` (Certificate of Sale)** and **`CD` (Certificate of Disbursement)** if exposed — CS gives sale date + amount; CD gives disbursement amounts. Union by case.
- `data_source='brevard_acclaim_ct'` (or `_cs`/`_cd` per instrument). `source_url` = the Acclaim document detail URL.
- This is HTTP/JSON — **no Playwright, no WAF fight, cheap, fast**. Throttle politely (1 req/2–3s, single session, exponential backoff on 5xx).

### Lane 2 — GAP-FILL ONLY: BECA docket lookup (Playwright)
- `https://vmatrix1.brevardclerk.us/beca/beca_splash.cfm` — 503 to bare curl; needs real browser session (accept disclaimer → session cookie).
- Use ONLY for: (a) confirming **sale date** where the CT index doesn't expose it (see D1), (b) amounts missing from Consideration, (c) struck-to-plaintiff/no-bid outcomes that never generate a CT.
- **WAF rules (the claude-code-direct.yml crater is denylisted — do not recreate it):** single session, ≤1 request/4s, realistic UA, exponential backoff on 503, and if blocked → STOP the lane and report; never rotate IPs or hammer. If per-case volume is needed at scale and GHA runtime would exceed 6h → Hetzner per canon, with checkpoint/resume.

### Lane 3 — already running: clerk calendar cancellations
Weekly CANCELLED rows. Consider adding a tiny weekly GHA cron that re-scrapes the calendar and upserts cancellations (`data_source='brevardclerk_html'`). ~30 lines. Optional, low value, do last.

## DESIGN DECISION D1 (resolve with live data, do not guess)
`foreclosure_outcomes` unique key = `(case_number, county, auction_date)`. CT gives **recording date**, not sale date (typical lag ~10 days post-sale + redemption). Options, in preference order:
1. CS instrument carries the sale date — if CS sweep works, key on it.
2. BECA docket line per case ("sale held MM/DD") — batched, throttled (Lane 2a).
3. If neither is economical: use recording_date as auction_date **only** with `data_source` suffix marking it (e.g. `brevard_acclaim_ct_recdate`) so it is never mistaken for a verified sale date. Honesty V3: a guessed sale date written as fact = wrong VERIFIED = 3× penalty.

## WRITE CONTRACT (existing table, do not migrate)
`public.foreclosure_outcomes` — required: `case_number, county='brevard', sale_type='foreclosure', auction_date, outcome, data_source, source_url, enriched_at=now()`. Capture where exposed: `winning_bid` (Consideration/CS amount), `winner_name` (Grantee), `winner_type` ('third_party' unless Grantee matches plaintiff → 'plaintiff'), `plaintiff_raw` (Grantor side / case style), `parcel_id`, `property_address`, `final_judgment`.
`outcome` ∈ {sold, redeemed, cancelled, no_bid, struck_to_plaintiff}. A CT existing = 'sold' (or struck_to_plaintiff when Grantee = plaintiff).
**Idempotent upsert on `(case_number, county, auction_date)`. Resumable: persist a month-cursor progress table (e.g. `pipeline.brevard_fc_acclaim_progress(month_start date pk, status, rows_found, completed_at)`).**

## STEP 0 — PRE-FLIGHT (verify, never assume)
```sql
SELECT pct_verified_outcomes, crit_b_pass, gold_standard_pct FROM v_pencil_brevard_dod;  -- expect ≥8% and rising
SELECT status, count(*) FROM pipeline.brevard_td_backfill_queue GROUP BY 1;              -- TD engine draining
SELECT jobname, schedule FROM cron.job WHERE jobname IN ('brevard_td_backfill_tick','brevard_b_td_etl');  -- 148 + 147 alive
SELECT count(*) FROM foreclosure_outcomes WHERE county ILIKE 'brevard';                  -- baseline (expect 5)
```
```bash
gh secret list -R breverdbidder/cli-anything-biddeed   # names only; FIRECRAWL_API_KEY present (verified 2026-06-11)
```

## STEP 1 — DECODE ACCLAIM (the whole game)
1. Search everest-vault + repo + closed issues for the Duval Harris/Acclaim Recording API decode (it exists; it is NOT in `cli-anything-biddeed` under obvious names — verified by code search 2026-06-11).
2. Probe Brevard AcclaimWeb live: load the search page, capture the XHR the grid fires (DocType search, date range), replay it as plain HTTP. Confirm JSON shape, page size, max date window, and whether `Consideration` is populated on CTs.
3. Litmus (Honesty V3 gate before scaling): pull ONE known month (e.g. 2026-05), confirm CT rows correspond to real sales (spot-check 3 against the 05-2026 calendar/news), and that case numbers match Brevard format.

## STEP 2 — BUILD + SHIP THE SWEEP
GHA workflow `scrape-brevard-acclaim-ct.yml` (workflow_dispatch inputs: `month_start`, `month_end`, optional `doc_types` default 'CT,CS'): Python httpx, polite throttle, writes via PostgREST upsert, logs to `pipeline.scrape_runs` pattern, progress table cursor. Then a serial dispatcher mirroring the TD engine (queue of ~96 months, one in flight, self-unscheduling cron) — **copy the `brevard_td_backfill_tick` pattern, it is proven**.

## STEP 3 — VERIFY (locked acceptance, lane-split reporting)
```sql
SELECT round(100.0 * (
  (SELECT count(*) FROM tax_deed_outcomes   WHERE county ILIKE 'brevard' AND COALESCE(data_source,'') !~~* '%promote%')
+ (SELECT count(*) FROM foreclosure_outcomes WHERE county ILIKE 'brevard' AND COALESCE(data_source,'') !~~* '%promote%')
)::numeric / NULLIF((SELECT count(*) FROM multi_county_auctions WHERE county ILIKE 'brevard' AND sold_amount IS NOT NULL),0),1) AS pct_b;
SELECT crit_b_pass, crit_c_pass, crit_d_pass, crit_f_pass, gold_standard_pct FROM v_pencil_brevard_dod;
```
PASS = `pct_b ≥ 95`. Report FC-lane and TD-lane counts SEPARATELY. Denominator = 6,713 → total target ≥ 6,377 rows.

## STEP 4 — AFTER OUTCOMES LAND (bonus, only if budget remains)
Extend `sql/brevard_case_rekey.sql`: link new FC outcome rows to PO-keyed MCA rows by normalized address (+ sale date proximity). This feeds C/D parity. Do not block B on it.

## HARD RULES (non-negotiable)
1. NEVER count PropertyOnion data toward B. `data_source ~~* '%promote%'` or PO-derived = HARD FAIL.
2. NEVER write a row without a real recorded instrument/result. Missing = unwritten, never guessed. Wrong VERIFIED = 3× penalty.
3. NEVER fight the BECA/Acclaim WAF (single session, throttled, backoff, stop-and-report on block). Firecrawl is available as the residential path if Acclaim blocks datacenter IPs — but try plain HTTP first; official-records search endpoints are typically open.
4. Do NOT touch cron jobs 147/148, the TD queue, or the v5 evaluator. Do NOT widen to other counties. One county, one criterion.
5. Idempotent, resumable, ≤$10/session, GHA+Supabase default; Hetzner only if Playwright >6h.
6. Secrets: read vault values over MCP only when genuinely needed, never echo them; GH secrets are names-only from outside the runner.

## INHERITED CONTEXT
- `docs/work-orders/wo_brevard_b.md` (v2 source model — note its §2A per-case framing predates the PO-case-number finding above; this kickoff supersedes the framing, not the canon)
- `docs/work-orders/b_strategy.md`, `docs/work-orders/b_rekey_results_and_launch.md`, `sql/brevard_case_rekey.sql`
- TD engine source of truth: migrations `brevard_b_td_outcomes_etl_from_tier1`, `brevard_b_td_etl_v2_canon_expansion`, `brevard_td_backfill_queue_and_tick` (2026-06-11)

## OPEN ITEM (flag, do not action)
- Rotate GitHub PAT `ghp_…298j` (exposed earlier). After rotation update `vault.everest_gh_pat`.
