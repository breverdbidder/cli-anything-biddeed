# SHARD-11 run2820 — washington, leon, gilchrist, hernando

dispatch_id: `daae41d2-50b3-4b6f-91d9-963ae6e74083`
session: architect-20260704T000000

## Environment note
`SUPABASE_DB_PASSWORD` / psql auth failed against the pooler host (consistent with prior
sessions this campaign). All live DB reads/writes went through the Supabase Management API
(`https://api.supabase.com/v1/projects/{ref}/database/query`, `SUPABASE_ACCESS_TOKEN`). That
endpoint intermittently 403'd (Cloudflare error 1010) under rapid sequential requests —
resolved each time with a short backoff-and-retry loop, no data impact.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| washington C/D | fix if broken | fixed 61.3%→100.0% via live AJAX re-harvest | none — found genuinely fixable |
| leon | assess | already 10/10; fixed 7 stale ultraloop_audit rows (certify-gate hygiene) | scope narrowed to audit hygiene, no data change needed |
| gilchrist C/D | fix if broken | fixed 80.0%→100.0% via live AJAX re-harvest (1 stray row) | none |
| hernando (5 failing letters) | fix what's tractable | C/D 0.0%→87.0% (real progress, still FAIL); B/F/I honestly left as structural blockers | did not reach 95% on C/D; no fabrication attempted to force it |

## Before/After (live `pencil_dod_evaluate_county`, pasted verbatim)

**washington BEFORE:**
```json
{"A":{"pass":true,"metric":12},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":61.3},"D":{"pass":false,"metric":61.3},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},"I":{"pass":true,"metric":96.8},"J":{"pass":true,"metric":96.8}}
```
**washington AFTER:**
```json
{"A":{"pass":true,"metric":12},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":true,"metric":96.8},"J":{"pass":true,"metric":96.8}}
```
10/10.

**gilchrist BEFORE:**
```json
{"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":80.0},"D":{"pass":false,"metric":80.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":23.0},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0}}
```
**gilchrist AFTER:**
```json
{"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":23.3},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0}}
```
10/10.

**hernando BEFORE:**
```json
{"A":{"pass":true,"metric":10},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":13.7},"I":{"pass":false,"metric":43.5},"J":{"pass":true,"metric":100.0}}
```
**hernando AFTER:**
```json
{"A":{"pass":true,"metric":10},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":87.0},"D":{"pass":false,"metric":87.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":13.9},"I":{"pass":false,"metric":43.5},"J":{"pass":true,"metric":100.0}}
```
5/10 (unchanged letter count — C/D moved substantially but still below the 95% bar).

**leon:** unchanged 10/10 throughout (`A:46,B:100.0,C:100.0,D:100.0,E:98.7,F:100.0,G:100.0,H:13.8,I:96.1,J:98.7`).

## Method

Reused (not reinvented) an existing, previously campaign-audited tool:
`scripts/shard9_run3059_citrus_manatee_cd_parity.py` (wraps
`scripts/shard2_run2450_ajax_realforeclose_harvest.py`'s `harvest_date()`), which re-fetches a
county's *own* live RealForeclose/RealTaxDeed AJAX calendar for a given date and exact-matches
case numbers — an independent, real-time cross-source confirmation, not a PropertyOnion
comparison and not a blanket parcel-presence promotion. For hernando's foreclosure lane
(platform = `hernando_clerk_pdf`, not RealAuction — checked `pipeline.counties` first per the
COUNTY EXCEPTIONS guidance), used the analogous existing scraper
`scripts/shard3_hernando_fc_scraper.py` to re-fetch and parse (PyMuPDF) the actual clerk PDF
sale lists.

Ran a **Workflow (ultracode)** with 3 independent adversarial refuter subagents (one per
county-claim) after applying the fixes, each with fresh read-only DB + live web access and told
to try to break the claim from scratch. Results:

- **washington**: refuter reproduced all 12 live calendar matches independently (factually
  true), but flagged `parity_checked_at`/`updated_at` as stale because the reused harvester
  script's PATCH body never sets those columns — a real hygiene gap, not a fabrication. Fixed
  with an explicit stamp UPDATE.
- **gilchrist**: same pattern — refuter independently reproduced the live match, then got
  confused by the same stale-timestamp issue plus an older same-day audit note describing the
  row as still unmatched *before* this session touched it (true at that earlier time; this
  session's fix came after). Reconciled directly: I had queried the row live immediately before
  the fix (confirmed `mca_only` at that moment) and watched the evaluator metric jump in the
  same session. Stamp UPDATE applied here too.
- **hernando**: Part A (tax_deed) confirmed true, and the refuter also reconciled a real
  discrepancy — a 2026-07-02 finding said `hernando.realtaxdeed.com` 403s; a bare curl still
  does, but a normal browser-shaped request (what the harvester sends) gets HTTP 200. Part B
  (foreclosure PDF) caught a **genuine bug in this session's own work**: case `25000885CA` was
  wrongly left `mca_only` on the belief it was absent from the 2026-07-14 PDF — the refuter
  read the raw extracted text and found it present but OCR-garbled (`2 5000885CA`, breaking the
  case-number regex). Corrected using the refuter's own evidence (matching dollar amount +
  defendant name). The refuter also surfaced a 6th real PDF case (`22000726CA`) never scraped
  into the DB at all — logged as a coverage gap for a future session, not inserted here.

All findings (including the false-alarm provenance framing) are logged verbatim to
`gold_standard_ultraloop_audit` (9 rows, dispatch_id above) so a future session has full
context rather than re-litigating settled work.

## Deviation log

- Initial live check showed washington/gilchrist at 8/10, not the 10/10 and lower-than-expected
  numbers implied by the dispatch brief's stale snapshot — expected drift given the fleet's
  parallel-session cadence; reconciled against fresh live queries, not the brief's numbers.
- The AJAX re-harvest tool's PATCH body doesn't stamp `parity_checked_at`/`updated_at` — flagged
  as a latent defect worth fixing in the shared script itself in a future session (not fixed
  here to keep this session's diff scoped to the 4 assigned counties, per K3 surgical-changes
  guidance) — currently patched per-row as a follow-up UPDATE, not at the script level.
- hernando did not reach 95% C/D and remains 5/10. This is honest: B/F/I require either a real
  sale to occur (B/F) or a fleet-wide zoning-ingestion pass (I), neither fabricable within
  guardrails.

## Verification evidence

All before/after JSON above is from direct `pencil_dod_evaluate_county` RPC calls executed
this session (not cached/inferred). The 12 washington + 1 gilchrist + 19 hernando row
promotions were each independently reproduced by a fresh adversarial subagent re-running the
same live external fetch, not merely trusted from the fixing process.

## Not run this session (per PARALLEL-FLEET RULES)

`gold_standard_loop()` / `gold_standard_certify()` were **not** run — other shards may be
mid-flight. Per-county `pencil_dod_evaluate_county` was used for all verification instead.

## Residual / next-session hit list

- hernando: 3 rows (2026-07-28) need OCR (scanned-image PDF, no text layer) to close C/D
  further; case `22000726CA` needs to be scraped into `multi_county_auctions` at all (missing
  row, not a parity problem); I needs real zoning/parcel_zones ingestion for hernando (fleet-wide
  gap, brevard is still the only county with it); B/F wait on real sales.
- `scripts/shard2_run2450_ajax_realforeclose_harvest.py` / the `shard9_run3059_ajax_harvest`
  label convention should be updated to stamp `parity_checked_at`/`updated_at` on every PATCH,
  to avoid the same refuter false-alarm recurring for the next county that reuses it.
