# Gold Standard Shard-12 — Collier County — Session Report

**Dispatch ID:** `9d04299e-3c67-4ccf-8550-3e0e3272c0f1`
**County:** collier (1-county shard)
**Date:** 2026-07-19
**Closer role:** honest closeout only — no re-work, no second-guessing SURVIVED verdicts absent new evidence.

## Mission Recap

This was a 1-county Gold Standard shard targeting three letters for collier: **A, G, I**.

- **Letter A (out of scope):** Verified structural dead end — no online auction source exists for Collier County. Independently re-confirmed twice prior to this session (2026-07-03 and 2026-07-18). Not attempted this session, no rows fabricated. Remains failing (fc=0 td=212) by design, not by omission.
- **Letter G:** Zoning FAR/density/parking coverage. Lane applied real-ordinance research (LDC citations for PUD, VR, RMF-12, RT) to flip applicability flags and add one sourced density value (RT=16 du/acre). Independently refuted — SURVIVED.
- **Letter I:** Property card completeness. Lane applied live GIS zoning lookups (Naples + Marco Island ArcGIS FeatureServers) to backfill 13 parcel_zones rows + 1 new zoning_districts row. Independently refuted — SURVIVED.

## BEFORE State (captured live at session start)

```json
{
  "county": "collier",
  "auctions_total": 212,
  "A": { "pass": false, "metric": 0, "detail": "fc=0 td=212" },
  "B": { "pass": true, "metric": 100, "detail": "verified=62 closed_sold=62" },
  "C": { "pass": true, "metric": 100, "detail": "matched_clean=212" },
  "D": { "pass": true, "metric": 100, "detail": "matched_any=212" },
  "E": { "pass": true, "metric": 100, "detail": "parcel_linked=212" },
  "F": { "pass": true, "metric": 100, "detail": "tier1_sold=62 closed_sold=62" },
  "G": { "pass": false, "metric": 0, "detail": "density=67.9 far=0.0 pk1000=0.0" },
  "H": { "pass": true, "metric": 5.7, "detail": "hours since last_seen (SLA 48h)" },
  "I": { "pass": false, "metric": 89.6, "detail": "card_complete=190 of 212" },
  "J": { "pass": true, "metric": 100, "detail": "deal_complete=212 (triangle + two-arm CMA + ml_score + max_bid)" }
}
```

Score BEFORE: **7/10** (A, G, I failing)

## AFTER State (fresh query, this session)

Command run: `python3 mgmt_sql.py "SET statement_timeout=0; SELECT public.pencil_dod_evaluate_county('collier');"`

Raw output (verbatim):

```json
{
  "A": { "pass": false, "detail": "fc=0 td=212", "metric": 0 },
  "B": { "pass": true, "detail": "verified=62 closed_sold=62", "metric": 100 },
  "C": { "pass": true, "detail": "matched_clean=212", "metric": 100 },
  "D": { "pass": true, "detail": "matched_any=212", "metric": 100 },
  "E": { "pass": true, "detail": "parcel_linked=212", "metric": 100 },
  "F": { "pass": true, "detail": "tier1_sold=62 closed_sold=62", "metric": 100 },
  "G": { "pass": false, "detail": "density=84.4 far=0.0 pk1000=0.0", "metric": 0 },
  "H": { "pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 6.1 },
  "I": { "pass": true, "detail": "card_complete=203 of 212", "metric": 95.8 },
  "J": { "pass": true, "detail": "deal_complete=212 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100 },
  "county": "collier",
  "V2_LITMUS": null,
  "auctions_total": 212
}
```

Score AFTER: **8/10** (A, G still failing; I flipped to passing)

**VERIFIED** — this is the actual query output read in this session, not carried over from either lane's self-report.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Letter A | Out of scope, do not attempt | Not attempted | None — as directed |
| Letter G | Research + apply real LDC zoning density/FAR/parking data, drive metric to pass | Applied `density_regulated=false` for PUD/VR/RMF-12 (floating-zone/GMP-governed, no fixed LDC value) + 1 sourced density value for RT (16 du/acre, confidence 0.55). FAR/parking for C-1/C-4/C-5/I left NULL (elaws.us 503, Firecrawl 402, municode JS-shell, collier.gov 403 — all reconfirmed live) | **Still fails.** Density sub-metric rose 67.9→84.4 (drifted slightly further from the applier's own post-apply snapshot of 85.7, attributable to a concurrent shard task touching collier parcels mid-session per the refuter's own note) but `far=0.0`/`pk1000=0.0` remain the binding constraint via `LEAST()` in the evaluator. No fabrication was used to force a pass — this is an honest partial improvement, not a fix. |
| Letter I | Research + backfill missing property-card fields via live GIS, drive metric to ≥95% | Backfilled 13 `parcel_zones` rows (4 Naples via naplesgov ArcGIS, 9 Marco Island via cityofmarcoisland ArcGIS) + 1 new `zoning_districts` row (RSF-3, Marco Island). Left Everglades City case 26111 and 8 Group-2 no-DOR-match folios unenriched (no discoverable zoning source / DOR match) | **Now passes.** card_complete 190→203 of 212, metric 89.6→95.8, pass=true. Matches lane's applied claim exactly, confirmed both by lane's own refuter and by this session's fresh top-level evaluator query. |

## Ultraloop Audit Verdicts

Confirmed via `SELECT letter, survived, created_at FROM gold_standard_ultraloop_audit WHERE dispatch_id='9d04299e-3c67-4ccf-8550-3e0e3272c0f1' ORDER BY created_at;` (fresh query, this session):

```json
[
  { "letter": "G", "survived": true, "created_at": "2026-07-19 21:28:14.777538+00" },
  { "letter": "I", "survived": true, "created_at": "2026-07-19 21:28:30.642111+00" }
]
```

**VERIFIED** — both refuter rows landed, both `survived=true`. No second-guessing performed on either verdict per instructions; no new evidence surfaced that contradicts either.

### G — SURVIVED (evidence, per refuter)
- Re-ran G metric fresh: density moved 85.7→84.4 between two close-together re-runs, attributed to a concurrent shard commit (`680b81b7`, the I-lane fix) altering collier parcel data mid-session, not to fabrication in the G claim. Pass/fail conclusion (still fails) unchanged either way.
- Live-queried `zoning_districts` confirmed `density_regulated=false` for PUD (11691), RMF-12 (11692), VR (11698) exactly as claimed.
- Live-queried `zone_standards` confirmed RT (11697) row: `max_density_du_acre=16.00`, `confidence_score=0.55`, sourced to `colliercounty.elaws.us/code/ldc_ch2_2.05.00_sec2.05.01`.
- Confirmed MH/RSF-3/4/5 and C-1/C-4/C-5/I FAR+parking all still NULL — nothing fabricated for skipped districts.
- Independent WebSearch corroborated the RT 16 du/acre value from the same LDC section, independent of the applier's own quote.
- Category-error check passed: RT is residential, so `far_applicable=false`/`pk1000_applicable=false` correctly excludes it from FAR/parking scoring.
- No `shard`/`bootstrap`-pattern fabricated source_urls found in collier zone_standards.
- Commit `d201eb07` confirmed on `main` via `git merge-base --is-ancestor`.

### I — SURVIVED (evidence, per refuter)
- Re-ran I metric fresh: `card_complete=203 of 212, metric=95.8, pass=true` — exact match.
- All 13 `parcel_zones` rows + 1 `zoning_districts` row confirmed present with exact field values matching the migration SQL.
- All 13 case_numbers cross-referenced against `multi_county_auctions`, lat/lng matched to the coordinates cited in each row's source string.
- 11 of 13 rows (85%) spot-checked live against the actual ArcGIS FeatureServers (Naples 4/4, Marco Island 7/9) — zero discrepancies.
- Residual-gap honesty checks: Everglades City GIS domain doesn't resolve (DNS failure) — consistent with claimed dead end; all 8 Group-2 folios independently confirmed still fully NULL.
- Commit `680b81b7` — confirmed shipped.

## Residual Gaps (honest, left for a future session — UNKNOWN, not fabricated)

**Letter G:**
- MH, RSF-3, RSF-4, RSF-5 density: only UNKNOWN/INFERRED confidence available this session (LDC §2.03.02 references the density rating system generically, no fixed number, no staff clarification memo found analogous to RMF-6's). Left NULL.
- C-1, C-4, C-5, I: `max_far` and `parking_per_1000sf` — 8 values total, all NULL. Blockers reconfirmed live: `elaws.us` 503 on every LDC section tried, `library.municode.com` JS-only Angular shell (403 on WebFetch), `collier.gov` PDFs 403, Firecrawl API 402 (insufficient credits), `archive.org` blocked entirely for WebFetch.
- This is why G still fails even after the density sub-metric improvement — `far=0.0`/`pk1000=0.0` are the binding constraint via `LEAST()` in the evaluator.

**Letter I:**
- Case 26111 (Everglades City, parcel_id 83741800007): no ArcGIS FeatureServer/MapServer or point-in-polygon-queryable zoning source exists; only a static 1992 PDF land use map found. GIS domain confirmed non-resolving (DNS failure) by the refuter.
- 8 Group-2 folios with no DOR match (23164, 24099, 24108, 24109, 24110, 24111, 24147, 25184): `collierappraiser.com` is a JS-gated legacy ASP.NET app unscriptable via curl/WebFetch; FL DOR statewide cadastral (CO_NO=21 confirmed correct) has zero matches for these folio formats; Collier GIS Hub / GMCD GIS Hub have no parcel-value dataset; `county-taxes.net` blocked by WAF (403); Firecrawl out of credits; browser-use CLI not installed.
- These 9 rows account for the remaining gap to 100% on I (203+9=212); 95.8% already clears the ≥95% threshold so I is passing, but the 9 rows remain genuinely unenriched.

**Letter A:** Out of scope by design — verified structural dead end (no online auction source for Collier), re-confirmed twice prior to this session (2026-07-03, 2026-07-18). Not re-attempted.

## Migrations Shipped

- `supabase/migrations/20260719_gold_standard_shard12_collier_g_zoning_backfill.sql` (commit `d201eb07`)
- `supabase/migrations/20260719_gold_standard_shard12_collier_i_card_completeness.sql` (commit `680b81b7`)

Both confirmed present in-repo at session close and confirmed merged to `origin/main`.

## Final Scoreboard

**Collier: 8/10** (BEFORE 7/10 → AFTER 8/10)

- Moved: **I** (fail→pass, 89.6→95.8)
- Unchanged-fail: **A** (out of scope, untouched), **G** (0→0, partial honest improvement on density sub-metric only, still gated by FAR/parking NULLs)
- Unchanged-pass: B, C, D, E, F, H, J

## What's Left for Tomorrow's Session

1. **G — FAR + parking for C-1/C-4/C-5/I:** Need a working path to LDC §4.02.01 (Table 2, Building Dimension Standards) and §4.05.04 (Table 17, Parking). Candidates: retry `elaws.us` (may recover from 503s), refresh Firecrawl credits, or find a third-party/PUD staff-report source quoting these tables verbatim. Do not fabricate values.
2. **G — MH/RSF-3/4/5 density:** Look for a staff clarification memo analogous to RMF-6's SC-06-04, or confirm definitively that no fixed value exists (as was done for RMF-12/PUD/VR) so these can be flipped to `density_regulated=false` with a real citation.
3. **I — Everglades City case 26111:** No GIS path found this session (DNS failure on the city GIS domain). May require manual/static-map lookup or a different data source entirely.
4. **I — 8 Group-2 folios with no DOR match:** All standard tool paths exhausted this session (JS-gated appraiser site, WAF-blocked county-taxes.net, Firecrawl credits exhausted, no browser-use CLI). Would need either Firecrawl credit refresh + browser automation, or a manual lookup.
5. **A remains a verified dead end** — no action recommended unless a new online auction source for Collier surfaces independently.
