# SHARD-9 Session Report — bay, st_johns, flagler, madison

- dispatch_id: `3dab9937-89d1-4e17-a04c-8006df276419`
- chat_session: `architect-20260710T080000`
- run label: run3534 (matches loop run referenced in the brief)
- date: 2026-07-10
- ultraloop_mode: `native` (Workflow tool, per CLAUDE.md ULTRALOOP PROTOCOL — user opted in with "ultracode")

## Ship-to-main status

All DB mutations applied LIVE via the Supabase Management API SQL endpoint (`api.supabase.com/v1/projects/.../database/query`) and PostgREST — direct psql to the pooler failed auth this session (`SUPABASE_DB_PASSWORD` stale, consistent with notes from prior sessions). This report and all code artifacts are committed and pushed directly to `main`. No side branches, no PRs.

## Honest headline: no letter flipped PASS this session

```
county      before          after           delta
bay         8/10 ABCDEFHJ   8/10 ABCDEFHJ   none (G, I remain FAIL — both genuinely blocked, see below)
st_johns    8/10 ABCDFGHJ   8/10 ABCDFGHJ   none (E, I remain FAIL — genuinely blocked)
flagler     6/10 AEGHIJ     6/10 AEGHIJ     C/D numerator moved 122→124/137 (89.1%→90.5%), still FAIL vs 95% threshold
madison     4/10 EGHJ       4/10 EGHJ       A metric unchanged (0), but pipeline.counties config repaired
```

**Important correction to the assigned brief:** the brief's snapshot showed bay G as PASS
(98.7, "density=98.7 far= pk1000="). A fresh live query at session start already showed G
FAIL (0.0, "density=70.3 far=0.0 pk1000=0.0") — this had already regressed before this
session began, most likely because a parallel/earlier session populated `far_applicable` /
`pk1000_applicable` denominators for bay without also populating the corresponding
`zone_standards` values. This report's numbers are the live, re-verified truth, not the
brief's.

This session ran 4 independent fix tracks in parallel (one per county's highest-leverage
failing letter), each followed by an **independent adversarial refuter agent** (never the
same agent that made the claim) that re-ran every query live and spot-checked the actual
rows before the claim was accepted. All 4 claims **SURVIVED** refutation — meaning the
"nothing moved" and "small nudge" results below are verified-true, not ghost-successes
being under-reported, and the 2 rows that did change are verified-true, not over-reported.

## What shipped

1. **flagler C/D**: found `flagler.realtdm.com/public/cases/list` (linked from
   `flaglerclerk.gov/sales/tax-deeds-sales/`) as a real per-case status source distinct from
   the calendar-sweep AJAX endpoint already exhausted by a prior session. Searched all 15
   previously-unmatched tax-deed case numbers by case number:
   - **2 cases confirmed sold to a third-party bidder** (`25-027 TDC`, `25-028 TDC`) →
     PATCHed `parity_status='matched_clean'`, `parity_source='tier1:shard9_run3534_flagler_deep:realtdm_public_case_search:2026-07-10'`.
     Independently corroborated by a pre-existing `tier1_sale_status='SOLD'` on both rows.
   - **3 cases are `Completed - Redeemed`** (`25-026`, `25-031`, `25-032 TDC`) — owner
     redeemed before deed issuance, no bidder sale occurred. Left untouched (not force-matched).
     **Open scope question for Ariel**: should redeemed cases be excluded from the C/D
     denominator entirely (they're not a "miss", they're a different outcome type) rather
     than counted as unmatched? This is a definitional question, not something resolved
     unilaterally this session.
   - **10 cases are genuinely future-dated** (`26-0xx TDC`, sale date 2026-08-11, ~1 month
     out from today) — nothing to match yet. Re-check after that date.
   - Result: C/D 89.1% → 90.5% (122→124 of 137). Still FAIL (need ≥95%/131). Even fully
     resolving the 3 redeemed cases wouldn't clear the bar without the 10 future cases also
     resolving after 2026-08-11.

2. **madison A — `pipeline.counties` config repair**: madison had zero platform config
   (`foreclosure_platform`, `taxdeed_platform`, urls all NULL, `pipeline_status='pending'`)
   despite 5 real, already-scraped foreclosure rows (`madisonclerk_foreclosure_sales_page`).
   Confirmed live and registered:
   - `foreclosure_platform='clerk_html'`, `foreclosure_url='https://www.madisonclerk.com/departments-services/property-sales/foreclosure-sales/'`
     (matches the `source_url` already on all 5 existing rows — the lane was already working,
     just unregistered).
   - `taxdeed_platform='clerk_html'`, `taxdeed_url='https://www.madisonclerk.com/departments-services/property-sales/tax-deed-sales/'`
     — discovered live; this page and the county's Lands Available page both explicitly state
     **"There are no properties on the list ... at this time."**
   - `pipeline_status='active'`, `pipeline_health='healthy'`.
   - **No tax-deed row was inserted.** There is nothing real to ingest right now — inserting
     a placeholder to flip A green would be fabrication, explicitly forbidden. A remains
     FAIL by design until Madison County actually schedules a tax deed sale.
   - `madison.realtaxdeed.com` returned HTTP 403 (inconclusive — bot-blocked or nonexistent;
     not pursued further since the clerk's own page is already authoritative).

3. **bay G — blocked, zero writes, but a real fleet-wide structural finding**: root-caused
   G to 7 specific `zone_standards` rows (single-family R-1 districts across 5 jurisdictions
   + 2 Callaway mobile-home districts) carrying nearly all of bay's 111 zoned parcels.
   Attempted to fetch real ordinance values from each jurisdiction's municode.com page —
   **every municode.com fetch returned HTTP 403** this session (no `FIRECRAWL_API_KEY` /
   firecrawl CLI available as a fallback). Two non-municode PDFs were retrieved directly and
   parsed, but neither contained applicable bulk-standards tables for the districts in scope.
   Zero fields were written; nothing was guessed.
   **More importantly**: `pg_get_viewdef` on `v_zoning_district_applicability` shows it
   **hardcodes `false AS pk1000_applicable` for every zoning district in the entire
   database** — meaning populating `parking_per_1000sf` on any `zone_standards` row, for any
   county, can never move the G pk1000 sub-metric as the view is currently written. Bay's
   `far=0.0`/`pk1000=0.0` is actually driven by 30 unrelated `parcel_zones` rows whose
   `zone_code` fails to join any `zoning_districts` row (defaulting `applicable=true` via
   `COALESCE(...,true)` on the LEFT JOIN miss) — a different root cause than the 7-row
   hit-list this session targeted. **Flagging for a dedicated future session**: either seed
   the missing `zoning_districts`/`zone_standards` rows for those 30 orphan zone codes, or
   revisit the view's applicability logic (out of scope to change unilaterally — view/schema
   protection). Also flagged, untouched: `zone_standards` rows `id=2535`/`2536` (Callaway
   R-6/R-6M) both carry `max_far=40.00`, implausible for single-family zoning and likely a
   decimal-point error from a prior session — did not touch it since it wasn't this track's
   scope, but a future session should correct it with a real source.

4. **st_johns E/I — blocked, zero writes**: the 5 unlinked cases (`CA25-0128`, `CA25-0351`,
   `CA25-0475`, `CA25-1757`, `CC25-4817`) were investigated by decoding the raw AJAX AITEM
   HTML from `saintjohns.realforeclose.com` directly (not just the parsed output) — confirmed
   the source platform itself has **no Property Address row and an empty parcel `KeyValue=`**
   for all 5 listings. This is a genuine upstream data gap, not a scraper defect.
   `apps.stjohnsclerk.com` (Landmark case search, TaxSmart tax-deed portal) returned HTTP 403
   to WebFetch (WAF/session-protected, no case-number-keyed URL constructible without
   guessing an internal numeric id — declined per the no-fabrication rule). Recommend a
   re-check closer to the actual auction dates (08/13, 08/20/2026), since these platforms
   sometimes attach parcel data only in the days immediately before sale.

5. `pipeline.counties.notes` updated for all 4 counties with this session's exact findings
   so the next session does not re-derive the same investigation.

6. `gold_standard_ultraloop_audit`: 5 rows (`bay/G`, `st_johns/E`, `flagler/C`,
   `flagler/D`, `madison/A`), all `survived=true` — each backed by an independent
   adversarial refuter agent (never the fixer) that re-ran the live queries itself.

## VERIFICATION PROTOCOL — before/after `pencil_dod_evaluate_county` (live, pasted verbatim)

Fetched: 2026-07-10 (session start ≈08:xx UTC, session end ≈10:0x UTC)

### bay

BEFORE:
```json
{"A": {"pass": true, "detail": "fc=50 td=68", "metric": 50}, "B": {"pass": true, "detail": "verified=6 closed_sold=6", "metric": 100.0}, "C": {"pass": true, "detail": "matched_clean=118", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=118", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=117", "metric": 99.2}, "F": {"pass": true, "detail": "tier1_sold=6 closed_sold=6", "metric": 100.0}, "G": {"pass": false, "detail": "density=70.3 far=0.0 pk1000=0.0", "metric": 0.0}, "H": {"pass": true, "metric": 0.7}, "I": {"pass": false, "detail": "card_complete=111 of 118", "metric": 94.1}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 118}
```
AFTER (identical — zero writes made, blocked by municode 403s + view hardcoding, see above):
```json
{"A": {"pass": true, "metric": 50}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": true, "metric": 100.0}, "D": {"pass": true, "metric": 100.0}, "E": {"pass": true, "metric": 99.2}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": false, "detail": "density=70.3 far=0.0 pk1000=0.0", "metric": 0.0}, "H": {"pass": true, "metric": 1.0}, "I": {"pass": false, "detail": "card_complete=111 of 118", "metric": 94.1}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 118}
```
8/10 → 8/10 (unchanged, honestly).

### st_johns

BEFORE:
```json
{"A": {"pass": true, "detail": "fc=34 td=3", "metric": 3}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": true, "metric": 100.0}, "D": {"pass": true, "metric": 100.0}, "E": {"pass": false, "detail": "parcel_linked=32", "metric": 86.5}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 1.6}, "I": {"pass": false, "detail": "card_complete=30 of 37", "metric": 81.1}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 37}
```
AFTER (identical — zero writes made, upstream data gap confirmed, see above):
```json
{"A": {"pass": true, "metric": 3}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": true, "metric": 100.0}, "D": {"pass": true, "metric": 100.0}, "E": {"pass": false, "detail": "parcel_linked=32", "metric": 86.5}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 1.9}, "I": {"pass": false, "detail": "card_complete=30 of 37", "metric": 81.1}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 37}
```
8/10 → 8/10 (unchanged, honestly).

### flagler

BEFORE:
```json
{"A": {"pass": true, "metric": 40}, "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}, "C": {"pass": false, "detail": "matched_clean=122", "metric": 89.1}, "D": {"pass": false, "detail": "matched_any=122", "metric": 89.1}, "E": {"pass": true, "metric": 99.3}, "F": {"pass": false, "metric": null}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 0.5}, "I": {"pass": true, "metric": 95.6}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 137}
```
AFTER:
```json
{"A": {"pass": true, "metric": 40}, "B": {"pass": false, "metric": null}, "C": {"pass": false, "detail": "matched_clean=124", "metric": 90.5}, "D": {"pass": false, "detail": "matched_any=124", "metric": 90.5}, "E": {"pass": true, "metric": 99.3}, "F": {"pass": false, "metric": null}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 0.8}, "I": {"pass": true, "metric": 95.6}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 137}
```
6/10 → 6/10 (C/D numerator +2, still FAIL — honestly reported, not rounded up).

### madison

BEFORE:
```json
{"A": {"pass": false, "detail": "fc=5 td=0", "metric": 0}, "B": {"pass": false, "metric": null}, "C": {"pass": false, "metric": 0.0}, "D": {"pass": false, "metric": 0.0}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": false, "metric": null}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 1.6}, "I": {"pass": false, "detail": "card_complete=0 of 5", "metric": 0.0}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 5}
```
AFTER (metric unchanged by design — no fabricated tax-deed row; `pipeline.counties` config now accurate):
```json
{"A": {"pass": false, "detail": "fc=5 td=0", "metric": 0}, "B": {"pass": false, "metric": null}, "C": {"pass": false, "metric": 0.0}, "D": {"pass": false, "metric": 0.0}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": false, "metric": null}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 1.9}, "I": {"pass": false, "detail": "card_complete=0 of 5", "metric": 0.0}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 5}
```
4/10 → 4/10 (unchanged, honestly; the win this session was infrastructure/data-integrity, not a metric).

## Adversarial verification (ULTRALOOP)

Ran via the `Workflow` tool as 4 independent fix agents → 4 independent refuter agents (never
the same agent), per CLAUDE.md's ULTRALOOP PROTOCOL. All 4 claims **SURVIVED**:

| county | letter | claim | verdict |
|---|---|---|---|
| bay | G | blocked, 0 writes, view-hardcoding finding | SURVIVED |
| st_johns | E | blocked, 0 writes, upstream data gap confirmed | SURVIVED |
| flagler | C/D | 2 rows matched via realtdm.com, 13 correctly left unmatched | SURVIVED |
| madison | A | pipeline.counties repaired, 0 fabricated rows | SURVIVED |

Refuters independently re-ran `pencil_dod_evaluate_county`, spot-checked individual rows by
id/case_number, confirmed no PropertyOnion smuggling, no data loss on pre-existing non-NULL
fields, and no fabricated source citations. Full transcripts retained in the workflow run
(`wf_e7608b3a-f8c`).

## Why the loop/certify step was skipped

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` are skipped this
close-out (no reliable signal that no other shard session is mid-flight) — per-county
`pencil_dod_evaluate_county` evaluations above are the source of truth for this session
instead.

## Deferred / next-session hit list

1. **Bay G**: needs either (a) a Firecrawl-capable session to get past municode.com's 403s
   and populate the 7-row hit-list (though this alone won't move far/pk1000 per the view
   finding above), or (b) — higher leverage — seed `zoning_districts`/`zone_standards` for
   the 30 orphan `parcel_zones` zone codes so they stop defaulting `applicable=true`, or (c)
   a scoped decision to revisit `v_zoning_district_applicability`'s hardcoded
   `pk1000_applicable=false`. Also: correct the suspicious `max_far=40.00` on Callaway
   R-6/R-6M with a real source.
2. **St Johns E/I**: re-check the 5 cases near their 08/13 and 08/20/2026 sale dates.
3. **Flagler C/D**: (a) get Ariel's ruling on whether REDEEMED cases should be excluded from
   the denominator; (b) re-check the 10 future-dated cases after 2026-08-11.
4. **Madison A**: re-check `madisonclerk.com/tax-deed-sales/` periodically; nothing to do
   until the county schedules a sale.
