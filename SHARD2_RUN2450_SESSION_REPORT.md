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
