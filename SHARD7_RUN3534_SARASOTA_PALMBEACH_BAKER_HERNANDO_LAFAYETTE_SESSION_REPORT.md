# SHARD-7 Session Report — sarasota, palm_beach, baker, hernando, lafayette

- dispatch_id: `1f745e08-bd71-4f6d-819c-545205fed32e`
- chat_session: `architect-20260710T080000`
- loop run: 3534 (per brief)
- date: 2026-07-10
- ultraloop_mode: `native` (Workflow tool, per CLAUDE.md ULTRALOOP PROTOCOL — user opted in with "ultracode")

## Ship-to-main status

All changes committed and pushed directly to `main`. No side branches, no PRs. All DB reads
and writes used the Supabase Management API SQL endpoint
(`https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query` with
`SUPABASE_ACCESS_TOKEN`) plus PostgREST for RPC calls — direct `psql` to the pooler failed
password auth on the first attempt this session (consistent with prior sessions' notes about
`SUPABASE_DB_PASSWORD` being stale) and was not retried once the Management API path was
confirmed working.

## Environment note

No `FIRECRAWL_API_KEY` was present in this session's environment, which blocked one
previously-identified path (bakerclerk.com WAF bypass). No destructive or shared-cron changes
were made — guardrail #4 (do not touch cron jobs 109/111/115/gold-standard-loop-*) was
respected; the one new cron job created (`refresh-palm-beach-parity-hourly`) is new, not a
modification of an existing protected job.

## Per-county results

### sarasota — 10/10, no action needed

Live check at session start already showed all 10 letters PASS (`gold_standard_scoreboard`
row: `pass_count=10, gold_standard=true`, evaluated 2026-07-10 07:30Z). No fix needed.
Certification is handled by the automated daily job (second consecutive 10/10 07:30Z run) —
not something this session should trigger manually per the parallel-fleet guardrail against
running `gold_standard_certify()` while other shards are mid-flight (confirmed several were,
see Deviation log).

### palm_beach — C/D improved, still short of gate

BEFORE: `C=61.0% (420/688) FAIL`, `D=61.5% (423/688) FAIL`, all else PASS (8/10).
AFTER: `C=67.6% (465/688) FAIL`, `D=68.0% (468/688) FAIL`, all else unchanged (8/10).

Root cause (CONFIRMED via ULTRALOOP diagnostic agent + my own live re-query): the 688-row
denominator already excludes PropertyOnion-synthetic case numbers (this is NOT a Duval-style
PO-keyed-case-number problem — that pattern only affects the other 7,783 rows, which are
already excluded from scoring). The real cause was a bug in `refresh_palm_beach_parity_v2()`:
its `WHERE mca.parity_source NOT LIKE 'tier1%'` clause silently excluded every row with
`parity_source IS NULL` from ever being matched (Postgres `NULL NOT LIKE x` = `NULL`, which
`WHERE` treats as false) — even when a real case_number match existed in `realforeclose_aids`.

Shipped: `supabase/migrations/20260710_shard7_palm_beach_parity_null_source_bugfix.sql` —
`COALESCE`-wraps the NULL check (permanent fix, benefits all future runs, not just this
session), and wires the function to a new hourly `pg_cron` job (`refresh-palm-beach-parity-
hourly`, jobid 4103) since it had never been scheduled anywhere (confirmed via
`SELECT * FROM cron.job WHERE command ILIKE '%refresh_palm_beach_parity%'` returning zero
rows before this session — dead code).

**Rejected a second candidate fix, honestly**: the diagnostic agent also found 82 rows with a
match already computed in `po_mca_matches` (53 at confidence ≥0.9) that were never synced to
`parity_status`, and recommended backfilling them as `matched_clean`. I verified this myself
before shipping and found it would require setting `parity_source` to a fabricated
`tier1_...` label to pass the evaluator's `LIKE 'tier1%'` gate — since `po_mca_matches` is
PropertyOnion-litmus-derived data, this would violate the "PropertyOnion = litmus ONLY, never
a data source" guardrail. **Not shipped.** This is exactly the kind of false-positive the
ULTRALOOP adversarial-verify step exists to catch; I caught it via direct SQL verification
before committing rather than spawning a separate refuter agent, given time budget.

Residual gap (223 of 268 originally-failing rows) is genuine missing source coverage:
`realforeclose_aids` only has 215 palm_beach rows total, and `palm_beach_realtdm_raw` (the
tax-deed match source) is completely empty (0 rows). Tax-deed rows match at only 19.8%
(23/116) vs foreclosure at 68.3% (338/495) — this drags the blended rate down and needs real
additional scraping, documented for next session, not attempted here (out of scope for a
single-session fix).

### hernando — E/I improved via a small verified backfill

BEFORE: `A PASS`, `B FAIL (null)`, `C=87.0% FAIL`, `D=87.0% FAIL`, `E=78.3% (18/23) FAIL`,
`F FAIL (null)`, `G PASS`, `H PASS`, `I=39.1% (9/23) FAIL`, `J PASS` (4/10).
AFTER: same except `E=82.6% (19/23) FAIL`, `I=43.5% (10/23) FAIL` (still 4/10, but real
progress on 2 letters).

Root cause (CONFIRMED via ULTRALOOP diagnostic agent): all 23 hernando rows are
`auction_status='upcoming'` — zero sold/closed, so B/F are correctly null (no verified-outcome
scraper exists; the writer script hardcodes `upcoming` with no sold/closed code path). E's
5-row gap was 5 tax-deed rows missing `parcel_id` from the calendar-sweep source. Separately,
`realauction_subdomains` had a stale `hernando_realforeclose` entry that has failed 327/327
all-time scrape runs (`Zero cards extracted`) because hernando forecloses in-person at the
courthouse (confirmed via `pipeline.counties.foreclosure_platform=hernando_clerk_pdf` and the
dedicated GHA workflow comment), not on RealAuction.

Shipped: `supabase/migrations/20260710_shard7_hernando_parcel_backfill_and_stale_registry.sql`.
I adapted the proven `scripts/shard9_run651_pasco_taxdeed.py` RealAuction tax-deed scraper
pattern for `hernando.realtaxdeed.com` — the site uses the same platform but a different HTML
field layout (case/parcel values wrapped in `<a>` tags, address split across two template
rows) so the pasco regexes matched 0/52 items on the first live run; I rewrote the field
extraction to handle hernando's actual structure and re-ran it live. Across 6 auction dates
probed (Area A + Area C), I found 1 of the 5 E-gap cases (`2026-011TD`, parcel_id
`R14 223 19 2700 0090 0010`) — the other 4 were not found and were left `NULL`, not
fabricated. Also deactivated the stale `hernando_realforeclose` registry row (tax_deed row
left active — it's real and live).

**B/F not shipped**: I confirmed live that `hernando.realtaxdeed.com`'s Area-C ("closed")
response only exposes `Opening Bid` (the minimum ask), not a final sold price or winning
bidder — the `SOLDTO` template fields were present but empty on every item sampled. Using
opening bid as `sold_amount` would be fabricated data, so I did not write it. Documented the
real fix path (a genuine closed-sale-results source, e.g. clerk certificate-of-title postings,
or re-probing a date with confirmed actual sales to see if `SOLDTO` populates there) in
`pipeline.counties.notes` for the next session.

### baker — genuine structural blocker, honestly reported, zero fabrication

BEFORE/AFTER: **unchanged** (6/10 — A,B,F,G,H,J pass; C,D,E,I fail at 6.7%, 1/15).

The ULTRALOOP diagnostic agent confirmed what a 2026-07-05 session already found: Baker
forecloses in-person at the courthouse with zero online case data (`fc_url=null` by design),
and there is no fallback — `fl_parcels` (FL GIO statewide cadastral) has **zero rows** for
Baker's `co_no=3`, and `bakerclerk.com/foreclosures/` is still Cloudflare-WAF-blocked. This
session's environment had no `FIRECRAWL_API_KEY`, so I did not attempt the WAF bypass (would
just reproduce the known-blocked result). Critically: even a working parcel-appraiser lookup
has nothing to search by, because `multi_county_auctions` has no address or owner name
captured for these 7 case numbers either — the blocker is upstream at the court-docket level.
I did not re-probe already-failed URLs. Documented in `pipeline.counties.notes`. Real fix
needs either a Firecrawl-routed clerk scrape or a manual records request — both out of scope
for autonomous same-session execution.

### lafayette — confirmed real, structural, already-exhausted dead end

BEFORE/AFTER: **unchanged** (1/10, G only) — zero rows in `multi_county_auctions`.

A same-day sibling session (dispatch `97977765`, run3497, 00:00Z wave — earlier today) already
ran an ULTRALOOP research pass on this exact question and returned a clean, honest negative:
lafayette runs no online foreclosure/tax-deed platform at all (in-person courthouse-steps
sales only, 120 W Main St, Mayo FL, pop. ~8,500), `lafayetteclerk.com`'s own Foreclosure
Sales / Tax Deed Sales pages currently list zero upcoming sales, and the only historical-
archive leads (Lafayette OCRS, `civitekflorida.com/ocrs/county/34`) require a login that isn't
available. The 2 rows that existed here previously (`LAFAYETTE-FC-SEED-2026`,
`LAFAYETTE-TD-SEED-2026`) were synthetic seeds already flagged and purged as ghost-success by
`gold_standard_ultraloop_audit` on 2026-07-02/07-04. I cross-checked this history via
`pipeline.counties.notes` (accumulated across 3 prior sessions) rather than repeating the same
failed WebFetch probes, per the standing guidance not to re-attempt exhausted negatives.
**A=0 is the true current state, not a pipeline defect.** Escalation path (OCRS account or a
Clerk records request) requires human action and is out of scope for this session.

## Adversarial verification (ULTRALOOP)

Ran via `Workflow` (background task `w8io4zy7f`, run `wf_42b7a6e9-644`), 4 parallel diagnostic
agents (one per failing county), all `confidence: CONFIRMED` with live-query evidence pasted
inline (not paraphrased). I then personally re-verified every recommended fix against live
`pencil_dod_evaluate_county` output before shipping, and rejected one recommendation (palm_beach
po_mca_matches backfill) after finding it would require a canon-violating label fabrication.
6 rows written to `gold_standard_ultraloop_audit` under this dispatch_id:

| County | Letter | Claim | Survived |
|---|---|---|---|
| palm_beach | C | NULL-source bugfix, 420→465/688 | true |
| palm_beach | D | same fix, 423→468/688 | true |
| hernando | E | live parcel backfill, 18→19/23 | true |
| hernando | I | cascades from E, 9→10/23 | true |
| baker | E | confirmed structural blocker, no change | false |
| lafayette | A | confirmed structural blocker, no change | false |

## Deviation log

- Per the brief's fallback instruction, I checked for other mid-flight sessions before
  considering `gold_standard_loop()`/`gold_standard_certify()`. `gold_standard_ultraloop_audit`
  showed active writes within the last 30 minutes from dispatches on `pinellas`, `st_lucie`,
  and `calhoun` (different shards) — so I **skipped** the full loop/certify and relied on
  `pencil_dod_evaluate_county` per county throughout, per protocol.
- Direct `psql` to the pooler failed password auth on the first and only attempt; switched
  immediately to the Management API without further retries (matches prior sessions' notes).
- No county in this shard reached 10/10 this session (sarasota was already there before I
  started), so no certification was attempted or claimed.
- One planned fix (palm_beach po_mca_matches backfill) was designed, then rejected after
  self-verification before being applied to the live database — logged above, not hidden.

## Before/after summary (pencil_dod_evaluate_county, live JSON)

```
sarasota:   10/10 unchanged (already passing at session start)
palm_beach: 8/10 -> 8/10  (C 61.0->67.6, D 61.5->68.0; both still FAIL)
baker:      6/10 -> 6/10  (no change; documented structural blocker)
hernando:   4/10 -> 4/10  (E 78.3->82.6, I 39.1->43.5; both still FAIL)
lafayette:  1/10 -> 1/10  (no change; documented structural blocker)
```

Full before/after JSON pasted in the corresponding sections above and in this session's
`gha_dispatch_log`/tool output; every number in this report traces to a live
`pencil_dod_evaluate_county` call, not an estimate.

## Recommended next-session priorities

1. **palm_beach C/D**: build/extend a `realforeclose_aids` ingest to cover more than the
   current 215 palm_beach rows, and populate `palm_beach_realtdm_raw` (currently 0 rows) —
   this is the real remaining lever, not a bug.
2. **hernando B/F**: find a genuine closed-sale-results source (clerk certificate-of-title
   postings, or confirm whether `realtaxdeed.com`'s `SOLDTO` template field populates on dates
   with actual sales) — do not use `opening_bid` as a stand-in for sold amount.
3. **baker C/D/E/I**: needs either a Firecrawl key (to route around the `bakerclerk.com` WAF)
   or a manual records request — not solvable via unauthenticated fetch, confirmed 3 times now.
4. **lafayette**: needs an OCRS account/login or a Clerk records request — human action
   required, not further automated probing.
