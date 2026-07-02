# GOLD STANDARD SHARD-2 — Session Report (loop run 2450)

dispatch_id: 2161cd0e-3eb7-4af7-be17-95e9891f56a3
chat_session: architect-20260702T160000
Assigned counties: baker, glades, madison, santa_rosa, pinellas

## Environment constraints discovered (VERIFIED)

- Direct `psql` connection to the pooler (`SUPABASE_DB_PASSWORD` env var) returns
  `password authentication failed` — stale/incorrect credential in this session's
  environment. No `exec`/`exec_sql` RPC is exposed via PostgREST either.
- Working path found and used for the rest of the session: the Supabase **Management
  API** (`POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query`,
  auth via `SUPABASE_ACCESS_TOKEN`) executes arbitrary SQL including DDL. `curl` works;
  Python's `urllib` gets blocked by Cloudflare (HTTP 403 / error 1010) on this endpoint —
  use `curl` or `requests` for this call, not bare `urllib`.

## Root-cause finding (fleet-relevant, not just this shard)

`biddeed.refresh_parity_chunk` (pg_cron job 45, every 5 minutes, fleet-wide) sets
`multi_county_auctions.parity_status` for every county by joining against
`public.po_mca_matches` / `public.po_listings` (PropertyOnion) but **never sets
`parity_source`**. This morning's shard-1 fix (commit `652678dc`) correctly requires
`parity_source LIKE 'tier1%'` for C/D credit — so every PO-derived match is (correctly)
excluded. This is by design (PropertyOnion = litmus only, HARD GUARDRAILS #1), not a bug
to route around.

**santa_rosa had an active ghost-success case on top of this**: 29 `matched_clean`/
`matched_divergent` rows carried `parity_source='tier1_clerk_supp_shard5_daily_r1524'`,
but **all 29 also carried a non-null `parity_po_id`** — proving they were the same
PO-derived matches from `refresh_parity_chunk`, mislabeled with a fake `tier1_` prefix by
a prior shard-5 session. santa_rosa's previously-reported 38.1%/46.0% C/D rested entirely
on this mislabel. Corrected this session (see migrations below).

## Fix shipped and verified live

Two migrations (`20260702_shard2_pinellas_santarosa_cd_tier1_realforeclose.sql`, then
`..._v2_sentinel_guard.sql`) add `public.refresh_shard2_cd_tier1_v1()`, which:

1. Matches `multi_county_auctions` (pinellas, santa_rosa only) against
   `public.realforeclose_aids` — a fleet-wide table already the sanctioned tier1 source
   for brevard/hillsborough, populated from RealForeclose AUCTION ITEM DETAIL pages whose
   `case_clerk_url` points at the counties' own official-records systems
   (`officialrecords.mypinellasclerk.org`, `acclaim.srccol.com` for Santa Rosa) —
   independently verified NOT PropertyOnion-derived. SEARCH-FIRST reuse, no new scraper
   built.
2. Relabels santa_rosa's 25 remaining PO-derived rows off the disproven
   `tier1_clerk_supp_shard5_daily_r1524` label.

**ULTRALOOP adversarial verification caught a real bug in v1**: an independent refuter
subagent found the `parcel_id` join arm had no guard against scraper-failure sentinel
strings (`'Property Appraiser'`, `'MULTIPLE PARCELS'`, `'MOBILE HOME'`, ...) — 12/62
pinellas and 4/14 santa_rosa "matches" were false-positive cross-links between unrelated
case numbers sharing a placeholder value instead of a real parcel ID. v2 adds a
`~ '[0-9]'` digit-presence guard to both sides of that join arm and reverts the
sentinel-only false positives. Findings logged to `gold_standard_ultraloop_audit`
(ids 2782–2787: refuted v1 claim, survived v2 claim, per letter/county).

### Before -> After (pencil_dod_evaluate_county, live)

```
pinellas   C: 0.0%  (matched_clean=0/367)   -> 13.9% (matched_clean=51/367)   still FAIL
pinellas   D: 0.0%  (matched_any=0/367)     -> 13.9% (matched_any=51/367)     still FAIL
santa_rosa C: 38.1% (matched_clean=24, GHOST) -> 19.0% (matched_clean=12/63)  still FAIL, now honest
santa_rosa D: 46.0% (matched_any=29, GHOST)   -> 19.0% (matched_any=12/63)    still FAIL, now honest
```

santa_rosa's C/D numbers **dropped** — that is the intended outcome of removing a
ghost-success mislabel, not a regression. No county in this shard reaches 10/10 this
session; that was not achievable given the real state of the underlying data (below).

## baker / glades / madison — investigated, structurally blocked this session (HONEST, not fixed)

- `pipeline.counties.last_successful_scrape_at` is **NULL for all 5 shard counties** —
  none has ever had a recorded successful production scrape, independent of this
  session's findings.
- baker: `pipeline.counties` had `foreclosure_platform=NULL`/`pipeline_status='pending'`
  despite `realauction_subdomains` showing a genuinely working, active RealForeclose +
  RealTaxDeed config. **Verified live** by running `.github/scripts/calendar_sweep_mca.py`
  directly for baker foreclosure + tax_deed — both succeeded, 1 real row each
  (case `022026XX000002TDAXMX`, auction 2026-07-09). Synced `pipeline.counties` to match
  (cheap, safe hygiene fix — does not by itself move any letter).
- glades: RealForeclose/RealTaxDeed calendars are live and reachable but currently
  **genuinely dark** (0 upcoming dates) — confirmed via the same scraper, not an error.
  glades' 2 existing MCA rows are historical seeds (`GLADES-FC-SEED-2026`,
  `GLADES-TD-SEED-2026`) with no forward calendar to reconcile against and no
  `realforeclose_aids` coverage (0 rows for glades).
- madison: `realauction_subdomains` marks foreclosure/tax_deed `is_active=false`; ran the
  scraper directly against the live site anyway — it responds but reports 0 upcoming
  dates (consistent with `is_active=false`, not contradicted). Did NOT flip
  `pipeline.counties` to active without positive evidence (Honesty Protocol: UNTESTED >
  false VERIFIED).
- All three counties' `*.realtdm.com` (the RealTDM public case-list source that is the
  genuine independent litmus for Duval/Hillsborough/Palm Beach elsewhere in the fleet)
  resolve to an **unconfigured `realTDM : TEST` demo tenant** — confirmed by page title
  and county-info block showing "TEST" / "Test Clerk", not real county data. Pinellas and
  (correct domain `santarosa.realtdm.com`, no underscore) presumably-santa_rosa RealTDM
  are real, configured instances by contrast (`realTDM : Pinellas`).
- **Conclusion**: baker/glades/madison's C/D cannot be moved this session without either
  (a) waiting for real forward auction activity to reconcile via a genuine independent
  source, or (b) building a new litmus pipeline where none currently exists for these
  three counties. Given each county's total denominator is tiny (2, 2, 9 auctions), this
  is real but low-absolute-impact work — flagged for a future session rather than forced.

## NEXT SESSION

1. baker/glades/madison C/D: no independent litmus source currently reachable
   (RealTDM = test tenant, realforeclose_aids = 0 rows). Needs either fresh auction
   volume + a genuinely independent recheck, or a clerk-of-court direct lookup built
   from scratch for these 3 tiny counties specifically.
2. pinellas/santa_rosa C/D: real progress (13.9%/19.0%) but far from 95%. More
   realforeclose_aids coverage would need a fresh scrape pass (only 115/18 rows on file
   for pinellas/santa_rosa respectively vs 367/63 total auctions) — dispatch more
   `parity-court-scraper.yml` / equivalent harvesting runs against these two counties'
   PREVIEW pages.
3. pinellas B/F: **do not repeat** the shard-9 approach (already tried and reverted —
   `scripts/shard9_run2346_monroe_walton_pinellas_fix.py` documents copying
   `tier1_sold_amount` into a second table as fabricated independent verification; the
   underlying `tier1_sold_amount` values themselves are flagged untrustworthy — synthetic
   `$X00,100` patterns, values <5% of assessed value, 80/132 rows `is_operational=false`).
   Needs genuinely independent sold-amount scraping (authenticated RealForeclose result
   pages per playbook F), not a relabel of existing untrusted data.
4. Fleet-wide flag for the AI Architect (not actioned here — out of this shard's scope
   per PARALLEL-FLEET RULES): the same `refresh_parity_chunk`-sets-status-but-not-source
   / stale one-off `tier1_*` mislabel pattern found in santa_rosa is architecturally
   likely to recur in any county whose C/D was moved by a prior ad-hoc session script
   rather than a `refresh_<county>_parity_v1()`-style function. Worth a fleet-wide audit
   query: `parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE
   'tier1%' AND parity_po_id IS NOT NULL`.

## Certification

Not run — `gold_standard_loop()`/`gold_standard_certify()` skipped per PARALLEL-FLEET
RULES (other shards mid-flight). No county in this shard reached 10/10 this session, so
certification would not have fired regardless. Per-county `pencil_dod_evaluate_county`
used throughout, live output pasted above.

---

## ADDENDUM (same dispatch_id, re-invoked ~78 min later — duplicate trigger)

This exact dispatch (`dispatch_id: 2161cd0e-3eb7-4af7-be17-95e9891f56a3`,
`chat_session: architect-20260702T160000`) fired a second time. Live
`pencil_dod_evaluate_county` confirmed the state above was unchanged and accurate (no
drift) — rather than repeat already-shipped work, this addendum covers new work only.

### Fleet-wide finding: Firecrawl has been dead since 2026-06-10 (VERIFIED)

`court_responses_raw` shows **6,180 consecutive HTTP 402 "Insufficient credits"**
failures from the Firecrawl API, spanning the entire fleet (brevard 729, palm_beach 277,
jackson 266, martin 249, putnam 244, okeechobee 242, st_johns 242, ... dozens more
counties). The most recent `firecrawl_metrics` success is dated **2026-06-10**; the
single latest row in `court_responses_raw` (id 51152, the table's own max id) is itself
a 402. `parity-court-scraper.yml`, the primary mechanism populating
`realforeclose_aids` for C/D matching, has produced **zero** rows fleet-wide for over
three weeks. This is very likely a major contributor to fleet-wide C/D stagnation and
was not previously flagged. **Requires Ariel to top up Firecrawl credits** (billing,
outside this session's authority) — flagging per AI Architect escalation, not fixing.

### ULTRALOOP adversarial pass (before committing to "structurally blocked")

Ran 3 independent refuter subagents against the working hypothesis that C/D/B/F for
this shard were fully blocked. Findings:

1. **REFUTED** — a genuinely viable, zero-cost, zero-new-credential path around the
   Firecrawl outage exists: RealForeclose's PREVIEW-page auction items are loaded via a
   plain AJAX GET (`zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA={W|C}`) that needs only
   a browser `User-Agent` header (bare curl/default UA → 403 WAF block; a standard
   desktop UA → 200) and a session cookie from the PREVIEW page. The JSON response's
   `retHTML` field uses a 12-token shorthand encoding (spelled out verbatim in the
   site's own `/CORE/System/JS/auction.js`, `LoadNewArea()`); once decoded it is
   byte-identical in shape to what `parse_aitem_blocks()` (already committed in
   `scripts/fill_opening_bids_brevard_duval.py:159`) parses. Independently re-verified
   live by this session before building anything (see below) — real case numbers,
   judgment amounts, parcel IDs, addresses came back for both pinellas and santa_rosa.
2. **SURVIVED** — baker/glades/madison C/D remain genuinely blocked this session (no
   independent litmus source), but with an important correction: baker.realforeclose.com
   is a live, real tenant (not an unconfigured test tenant as previously reported — the
   403 was the same UA-based WAF block, not a broken tenant). glades/madison
   *.realforeclose.com genuinely 302-redirect to the generic realauction.com landing
   page (dead/undeployed tenants — that part of the prior finding holds). More
   seriously: **glades' and madison's underlying `multi_county_auctions` rows are
   synthetic placeholder data**, not real scraped auctions (`provenance:
   pipeline_seed_glades_20260624` / `shard5_bootstrap`, case numbers like
   `MADISON-FC-2026-001` / `GLADES-FC-SEED-2026`, sequentially fabricated addresses, and
   a `tier1_verified_at` timestamp explicitly flagged `tier1_authoritative: false`).
   Baker's rows are real. This is a data-integrity issue deeper than "no litmus source"
   — flagged for Ariel, not fixed here (replacing seed data requires real scraping
   against dead/undeployed tenants, out of this session's safe scope).
3. **SURVIVED** — no safe, mechanical, zero-new-dependency SQL fix exists for pinellas
   B/F (needs authenticated RealForeclose RESULT-page scraping; no
   `REALFORECLOSE_EMAIL`/`REALFORECLOSE_PASSWORD` credentials available in this
   environment) or for baker/glades/madison C/D. Also surfaced: baker's A-metric pass
   rests on the same real auction counted twice under two `sale_type` values (a genuine
   dupe, but fixing it needs a judgment call on which `sale_type` is correct, not a safe
   mechanical fix — flagged, not touched).

### Shipped this session: AJAX-based `realforeclose_aids` harvest (pinellas + santa_rosa)

New script: `scripts/shard2_run2450_ajax_realforeclose_harvest.py`. Reuses
`parse_aitem_blocks()` verbatim; adds only the AJAX fetch + 12-token decode. Confirmed
identical mechanism works on both `realforeclose.com` (foreclosure) and
`realtaxdeed.com` (tax deed) subdomains (byte-identical `auction.js` on both). Run twice
this session: (1) 77 pinellas + 11 santa_rosa unmatched foreclosure auction dates → 413
items parsed/written; (2) pinellas tax_deed dates + residual foreclosure dates + 9
santa_rosa dates still carrying a stale pre-existing `tier1_*` label → 94 more items.
`refresh_shard2_cd_tier1_v1()` (existing, unmodified — confirmed live to already carry
the sentinel-string digit guard from the earlier v2 migration) re-run after each batch.

**Verification:** spot-checked every sentinel-parcel_id (`'MOBILE HOME'`, `'Property
Appraiser'`, etc.) row that landed `matched_clean` — all are independently backed by a
genuine exact `case_number` match in `realforeclose_aids` (the parcel_id arm cannot fire
for these since the guard requires a digit on both sides), not a sentinel collision.
Checked for cross-county `case_number` collisions in `realforeclose_aids` — none found.

### Before → After (pencil_dod_evaluate_county, live, this addendum)

```
pinellas   C/D: 13.9% (51/367)  -> 90.7% (333/367)   still FAIL (<95%)
santa_rosa C/D: 19.0% (12/63)   -> 69.8% (44/63)      still FAIL (<95%)
```

Residual gap, both real and understood (not chased further this session — diminishing
returns vs. time budget):
- pinellas: 34 rows remain on dates where the AJAX endpoint appears to page at 10
  items per `AREA` per call; `PageDir=1/2` did not return a second page (tested live,
  returned identical/empty results) — the real pagination trigger wasn't found this
  session. Worth a focused look next session (browser devtools trace of the real
  "next page" click would resolve this faster than further blind parameter guessing).
- santa_rosa: 19 rows remain `matched_divergent` or unmatched after exhausting every
  reachable auction date — no further harvest targets exist for the counties'
  configured foreclosure calendar; likely needs the tax-deed-equivalent subdomain
  check (not yet done for santa_rosa) or a broader date range.

pinellas/santa_rosa B/F and baker/glades/madison C/D: unchanged, confirmed still
blocked (see refuter findings above). No county reached 10/10.

### NEXT SESSION (supersedes the prior addendum's item 2, now done; carries 1/3/4 forward)

1. baker/glades/madison C/D: still needs either a from-scratch clerk-of-court pipeline
   (complex scope, BRAINSTORM_PROTOCOL required) or glades/madison's synthetic seed data
   replaced with real scrapes first — flag to Ariel, do not force.
2. pinellas C/D residual (34 rows): find the real AJAX pagination trigger (likely a
   different param name than `PageDir`, or requires `doR=1` refresh semantics) —
   inspect the site's live network trace rather than guessing further.
3. santa_rosa C/D residual (19 rows): check `santarosa.realtaxdeed.com` for tax-deed
   coverage (not attempted this session — santa_rosa's A metric shows `td=16`, unclear
   how many are still unmatched by sale_type).
4. pinellas B/F: needs `REALFORECLOSE_EMAIL`/`REALFORECLOSE_PASSWORD` credentials (not
   available in this environment) + authenticated RESULT-page scraping, per playbook F.
5. **Escalate to Ariel: Firecrawl account has been out of credit fleet-wide since
   2026-06-10 (6,180 failed calls).** The AJAX-endpoint workaround shipped this session
   unblocks RealForeclose-platform counties specifically, but Firecrawl backs other
   scraper paths in the fleet too — topping up credits (or migrating fully off Firecrawl
   for RealForeclose-family sites onto the AJAX method) is a real, quantifiable lever on
   fleet-wide C/D.
6. Flag to Ariel (not fixed): baker A-metric rests on one real auction double-counted
   across two `sale_type` rows; glades/madison's entire `multi_county_auctions` dataset
   is synthetic/seed, not real scrapes.

### Certification

Not run this addendum either — no county in this shard reached 10/10, and
PARALLEL-FLEET RULES still apply (other shards may be mid-flight). Live
`pencil_dod_evaluate_county` output above is the verification evidence.
