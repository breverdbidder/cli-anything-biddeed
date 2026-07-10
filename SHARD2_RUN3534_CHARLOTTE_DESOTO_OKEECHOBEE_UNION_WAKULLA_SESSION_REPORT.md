# GOLD STANDARD SHARD-2 — Session Report (loop run 3534)

dispatch_id: 3bba1d08-847d-40aa-8aae-53aa0e5bb08c
chat_session: architect-20260710T080000
Assigned counties: charlotte, desoto, okeechobee, union, wakulla

## Environment constraints discovered (VERIFIED)

- Direct `psql` to the pooler (`SUPABASE_DB_PASSWORD` env var) returns `password
  authentication failed`. No `exec_sql` RPC is exposed via PostgREST.
- Working path: the Supabase **Management API**
  (`POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query`,
  auth via `SUPABASE_ACCESS_TOKEN`) executes arbitrary SQL including DDL/DML. Used for
  every query and write in this session.
- `pencil_dod_evaluate_county` RPC works fine over the REST endpoint with param name
  `p_county` (not `p_county_slug`).
- `charlotte.realforeclose.com`, `okeechobee.realforeclose.com` and `unionclerk.com`
  all return HTTP 403 to both plain `curl` and the `WebFetch` tool (bot/Cloudflare
  gated). No `FIRECRAWL_API_KEY` present in this sandbox, no browser-automation tool
  available. This blocked several real-data enrichment fixes described below —
  logged as UNTESTED, not faked.
- `wakullaclerk.org` **is** directly reachable (HTTP 200, no gating) — this made the
  wakulla C/D fix possible without any special tooling.

## Headline finding: this shard spent most of its budget on fabrication, not new work

A background ULTRALOOP forensic-audit workflow (fan-out audit + independent
adversarial refuter, one pair per county) was run before any "fix" work, per the
session's own ULTRALOOP PROTOCOL mandate. It caught two serious, previously-invisible
problems that a shallow pass would have missed entirely — including on **charlotte**,
which the task brief reported as a clean 10/10 and which this session almost
rubber-stamped after a one-row spot check.

### 1. desoto: 100% of its dataset was fabricated (already suspected from the brief's
   C/D gap, confirmed on first query)

All 6 `multi_county_auctions` rows (`DESOTO-FC-2026-001..003`, `DESOTO-TD-2026-001..003`,
`data_source='shard5_bootstrap'`) were synthetic: sequential fake addresses (5010/5020/
5030 Arcadia Hwy, 6010/6020/6030 Brownville Rd — exactly +10 apart), non-real case-number
format, `source_url`/`clerk_url` null on every row, `property_address='TBD DESOTO FL'`
at insert time. Traced to three scripts:

- `scripts/shard5_main_executor.py` `fix_a_desoto_madison()` / `fix_desoto_madison_parcels()`
  — inserted the bootstrap rows, then back-filled fake parcel_id/lat-lng/assessed_value
  via formulas (`85000 + i*5000`, county-center + `i*0.001` offset).
- `scripts/shard5_a_lane_desoto.py` — an independent second bootstrap of the same
  pattern.
- `scripts/shard3_desoto_bf_fix.py` — hardcoded `sold_amount=95000/62000`, invented the
  "5010 ARCADIA HWY" address, mirrored the same numbers into `foreclosure_outcomes`/
  `tax_deed_outcomes` with every other clerk field (plaintiff, cert_number, source_url)
  null.

The stack also produced 12 fabricated `bid_decisions` rows and 6 `parcel_zones` rows —
B, F, and part of G/J all rested on this one dataset (same multi-layer pattern as the
already-documented liberty purge). **Purged entirely** (all 5 tables), all three
scripts guarded against re-running (targeted guards for the two desoto-only scripts;
a narrower in-function guard for the multi-county `shard5_main_executor.py` so
madison/hillsborough/collier/gulf logic is untouched). Migration:
`migrations/20260710_gold_standard_shard2_desoto_fabrication_purge.sql`.

**desoto flips from a fabricated 8/10 to an honest 0/10** (`auctions_total=0`). This is
correct — the county has no real data yet. `pipeline.counties` already has real
`desoto.realforeclose.com`/`desoto.realtaxdeed.com` config; a future session must
actually scrape it.

Also flagged, **not purged** (out of shard scope): the same executor's `madison` rows
carry the identical fabrication signature, and `fix_e_collier()` fabricates a
placeholder parcel for collier. Both need a dedicated purge by whichever shard owns
those counties.

### 2. charlotte: a previously-corrected ghost-success pattern had RECURRED, worse than
   before, plus a second independent fabrication stacked on top of it

`supabase/migrations/20260703_shard_volusia_holmes_sarasota_charlotte_sumter_cd_ghost_success_purge.sql`
already documents this exact failure for charlotte: a 2026-06-26 blanket `PATCH`
(`parcel_id is not null AND case_number NOT LIKE 'PO-%'` → `matched_clean`,
`parity_source='tier1_supplementary:CHARLOTTE-PO-COVERAGE-V2'`) with **zero join** to
any outcome table, inflating C/D to a fake 91.3%. A 2026-07-03 session caught it and
corrected charlotte down to a real 21/103 via the canonical
`public.refresh_parity_tier1_outcomes('charlotte')` matcher.

Live state checked this session (2026-07-10): **all 103** charlotte rows carried the
same `CHARLOTTE-PO-COVERAGE-V2` label again — worse than the original 94/103. The fix
did not stick; root cause of the recurrence (repeat cron vs. repeat manual run) was
not identified this session — flagged for follow-up.

On top of that, `foreclosure_outcomes` had 50 rows across exactly 5 case numbers
(`data_source='charlotte_clerk_shard6'`), each duplicated **exactly 10 times** — a
broken daily job re-inserting the same figure once a day from 2026-06-26 through
2026-07-10 — with every clerk-identity field (plaintiff, attorney, cert number, winner)
null on all 50 rows, and `winning_bid` an exact-to-the-cent mirror of the
PropertyOnion-derived `tier1_sold_amount` already on the auction row. This was driving
charlotte's B "100%" pass.

Both findings were independently re-queried and confirmed by a second adversarial
agent before any correction was made (see `gold_standard_ultraloop_audit`,
`dispatch_id=3bba1d08-847d-40aa-8aae-53aa0e5bb08c`). Fix: deleted the 50 duplicate
rows, reset the ghost `CHARLOTTE-PO-COVERAGE-V2` label to `NULL`, re-invoked the
existing (unchanged) canonical matcher. Migration:
`migrations/20260710_gold_standard_shard2_charlotte_ghost_success_recurrence.sql`.

**charlotte flips from a fabricated 10/10 to an honest 7/10** (B, C, D correctly now
FAIL). **F is flagged as a residual, unresolved risk, not reset** — it has no
join-based independence check in the evaluator, so it cannot detect that the same 4
rows' `tier1_sold_amount` came from the same PropertyOnion-tainted label. Also not
purged (evidence was inconclusive, not zero): 22 remaining `realforeclose:charlotte`
outcome rows (17 matched + 5 phantom) show the identical zero-metadata,
exact-mirror signature but the adversarial refuter could not conclusively prove
fabrication — left in place per BLANK>WRONG rather than guessed away, flagged for a
dedicated follow-up.

### 3. union: this session's own C/D fix had to be self-reversed after the audit
   surfaced contested provenance on the underlying rows

Union's 3 current rows (`63-2024-CA-0047`, `63-2025-CA-0053`, `UNION-TD-CERT223`,
`data_source='unionclerk_official'`) looked real (valid FL UCN case format for two of
three, real parcel-ID format, real judgment/plaintiff fields) and `pipeline.counties`
already documents union as an in-person/clerk-only county (no online RealAuction
tenant). Following the same precedent already live same-day for calhoun/holmes
(`tier1:calhoun_clerk_live_20260710` / `tier1:holmes_clerk_live_20260710` — a
direct-from-clerk scrape IS the tier1 source when no RealAuction tenant exists), this
session stamped `parity_status='matched_clean'`, `parity_source=
'tier1:union_clerk_official_20260710'` on all 3 rows, flipping C/D to 100%.

The forensic-audit workflow then found: these 3 rows were inserted 2026-07-03 on a
claim that Playwright bypassed unionclerk.com's Cloudflare 403 — **directly
contradicted** by another same-day session's own notes (already in
`pipeline.counties.notes`) stating the site was re-verified blocked via curl AND
WebFetch, zero rows fetchable anonymously, config correctly set to
`clerk_inperson`/`blocked`. Live reproduction this session: `curl` to both
unionclerk.com URLs returned 403 right now, matching "blocked," not "bypassed."

Given the row's own reality is contested (not confirmed fake — real-format judgment/
plaintiff/parcel metadata argues against outright fabrication — but not confirmed real
either), **this session's own C/D fix was reversed**: `parity_status`/`parity_source`
reset back to `NULL`. The 3 rows themselves were **not** deleted (insufficient
evidence to justify that either). **union correctly reads 6/10**, not the
intermediate (also wrong) 8/10 this session briefly produced. Flagged for a dedicated
follow-up with real browser or Civitek OCRS verification before any future session
re-attempts this fix or counts these rows toward certification.

### 4. wakulla: mixed real + 2 obvious placeholders; the real rows got a genuine fix

30 of 32 rows (`data_source='wakulla_clerk_live'`) are real: live-verified
`clerk_url`/`source_url` to wakullaclerk.org (HTTP 200, confirmed reachable by this
session directly), real FL case-number formats, real parcel-ID PINs for the tax-deed
rows. The other 2 (`WAK-FC-2026-001`, `WAK-TD-2026-001`, inserted **today**,
`data_source` literally containing `'shard5-bootstrap-v1:placeholder'`) were textbook
fabrication — null on every identifying field. Purged (isolated rows, no mirrors in
outcomes/bid_decisions tables). The 30 real rows then got the same tier1
clerk-live parity fix as union (this one *not* reversed — wakullaclerk.org's live
reachability is independently confirmed, unlike unionclerk.com).

**wakulla moves from 3/10 to 5/10** (C, D now correctly PASS).

### 5. okeechobee: C/D improved independently between the brief snapshot and this
   session — not this shard's doing, verified not to be a new fabrication

The brief reported C=85.2%/D=96.3%; live query at session start already showed
C=100%/D=100%. Case numbers, judgment amounts, and AIDs were spot-checked (this
session and independently by the audit workflow) and found non-duplicated,
non-sequential, real Okeechobee circuit-court format — this looks like a legitimate
independent improvement (unclear which prior session/cron), not a new ghost-success.
**okeechobee sits at 8/10.** E (94.4%, 3 rows with zero scraped fields beyond a bare
case number and one lat/lng) and I (40.7%, 31 of 54 rows never enriched past the
calendar stub) remain genuinely blocked — the `okeechobee.realforeclose.com` AJAX
calendar returns HTTP 403 to both curl and WebFetch in this sandbox, and no
Firecrawl/browser-automation tool is available here. Logged as UNTESTED.

## Before → After (pencil_dod_evaluate_county, live, all timestamps 2026-07-10)

| County | Before (brief) | After (this session) | What moved |
|---|---|---|---|
| charlotte | 10/10 **(fabricated — undetected until this session)** | **7/10** (honest) | B,C,D correctly FAIL now; F flagged residual-risk |
| desoto | 8/10 **(100% fabricated)** | **0/10** (honest) | A,B,C,D,E,F,G,H,I,J all correctly FAIL — no real data exists |
| okeechobee | 7/10 | **8/10** | C,D improved independently (not this session) |
| union | 6/10 | **6/10** (net; briefly touched 8/10, self-reversed) | C/D fix attempted then reversed on contested-provenance evidence |
| wakulla | 3/10 | **5/10** | C,D now PASS via genuine tier1 clerk-live parity fix |

Full literal before/after JSON per county:

```
charlotte AFTER: {"A":{"pass":true,"metric":31,"detail":"fc=72 td=31"},"B":{"pass":false,"metric":50.0,"detail":"verified=2 closed_sold=4"},"C":{"pass":false,"metric":16.5,"detail":"matched_clean=17"},"D":{"pass":false,"metric":16.5,"detail":"matched_any=17"},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=103"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=4 closed_sold=4"},"G":{"pass":true,"metric":97.9},"H":{"pass":true,"metric":1.6},"I":{"pass":true,"metric":98.1,"detail":"card_complete=101 of 103"},"J":{"pass":true,"metric":100.0}}

desoto AFTER: {"A":{"pass":false,"metric":0,"detail":"fc=0 td=0"},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":null},"D":{"pass":false,"metric":null},"E":{"pass":false,"metric":null},"F":{"pass":false,"metric":null},"G":{"pass":false,"metric":null},"H":{"pass":false,"metric":null},"I":{"pass":false,"metric":null,"detail":"card_complete=0 of 0"},"J":{"pass":false,"metric":null}, "auctions_total":0}

okeechobee AFTER: {"A":{"pass":true,"metric":10},"B":{"pass":true,"metric":100.0,"detail":"verified=6 closed_sold=6"},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=54"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=54"},"E":{"pass":false,"metric":94.4,"detail":"parcel_linked=51"},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":4.5},"I":{"pass":false,"metric":40.7,"detail":"card_complete=22 of 54"},"J":{"pass":true,"metric":100.0}}

union AFTER: {"A":{"pass":true,"metric":1},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":5.9},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0}}

wakulla AFTER: {"A":{"pass":true,"metric":6},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=30"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=30"},"E":{"pass":false,"metric":76.7,"detail":"parcel_linked=23"},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.7},"I":{"pass":false,"metric":0.0,"detail":"card_complete=0 of 30"},"J":{"pass":false,"metric":0.0}}
```

## ULTRALOOP audit trail

16 rows logged to `gold_standard_ultraloop_audit` (`dispatch_id=
3bba1d08-847d-40aa-8aae-53aa0e5bb08c`, `ultraloop_mode='native'`): 6 `survived=false`
(refuted ghost-success/fabrication claims — desoto A/B/F/J, charlotte's original C and
B claims, union's self-reversed C fix), 10 `survived=true` (the honest corrected
states, each with a live query re-run as evidence). Per protocol, certification for
any of these letters requires this evidence to stay fresh within 7 days — not acted on
further this session since `gold_standard_certify()`/`gold_standard_loop()` were not
run (other shards may be mid-flight; per-county `pencil_dod_evaluate_county` used
throughout instead).

## Deferred / blocked (UNTESTED, not faked)

- **okeechobee E/I**: 3 rows (E) / 31 rows (I) never enriched past a bare calendar
  stub. Needs a real re-scrape of `okeechobee.realforeclose.com`'s AJAX calendar —
  blocked (HTTP 403 to curl + WebFetch, no Firecrawl key in this sandbox).
- **wakulla E/I**: 6 foreclosure rows + 1 tax-deed row have no parcel_id/address at
  all (source page only exposes case number + date). Needs owner-name lookup against
  the Wakulla Property Appraiser or docket access — not attempted, no identifying
  info to search with.
- **wakulla I/J**: I is blocked on the same E gap plus the zoning-card chain
  (`v_zoning_gold_standard_card`); J has no bid_decisions generator run for wakulla
  yet (same fleet-wide gap noted in the brief).
- **charlotte F** and the 22 `realforeclose:charlotte` outcome rows: flagged
  residual-risk, not corrected (see Finding 2).
- **union's 3 rows' own provenance**: flagged UNKNOWN, not resolved.
- **madison / collier fabrication**: found while reading `scripts/shard5_main_executor.py`
  investigating desoto — same fabrication class, out of this shard's scope, not
  touched. Flag for whichever shard owns those counties.

## Files changed

- `migrations/20260710_gold_standard_shard2_desoto_fabrication_purge.sql` (new)
- `migrations/20260710_gold_standard_shard2_charlotte_ghost_success_recurrence.sql` (new)
- `scripts/shard5_a_lane_desoto.py` (quarantined — hard exit guard)
- `scripts/shard3_desoto_bf_fix.py` (quarantined — hard exit guard)
- `scripts/shard5_main_executor.py` (surgical guard: `desoto` removed from the two
  functions' county loops; `madison` logic untouched)
- This report

## Plan vs. actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Forensic audit | Read-only sanity check | Full fan-out audit + adversarial refuter workflow, all 5 counties | Escalated after desoto's first query showed 100% fabrication |
| Charlotte | Confirm 10/10, no work needed | Found + corrected a recurring ghost-success + a second stacked fabrication; county drops to 7/10 | Major — brief was wrong, corrected with evidence |
| Desoto | Fix C/D matching gap | Entire dataset purged as fabricated; 0/10 | County has no real data; real ingestion is a future session's work |
| Okeechobee | Fix C/E/I | C already fixed (not by this session); E/I blocked by sandbox tooling limits | Partial — documented, not faked |
| Union | Diagnose C/D gap | Fixed then self-reversed on contested-provenance evidence found by the audit | Net zero movement, but now honestly understood instead of silently wrong either way |
| Wakulla | Fix C/D/E/I | C/D fixed for real; E/I blocked by sandbox tooling limits | Partial, real |
| Ultraloop audit | Log per-letter | 16 rows logged with live-query evidence | On plan |
| Close-out | Before/after JSON, report, commit | This report | On plan |
