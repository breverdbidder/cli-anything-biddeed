# Gold Standard shard-5: st_lucie, union (dispatch 3fbcb0c2)

**Date:** 2026-09-02, wave 08:00Z. **Loop run at launch:** 16227. **Mode:** ULTRALOOP fallback
(3-way fresh-angle fan-out on Union's sole blocking row -> adversarial verify, via the Workflow
tool per CLAUDE.md ULTRALOOP PROTOCOL + this session's ultracode opt-in; logged
`ultraloop_mode='fallback'` in `gold_standard_ultraloop_audit`).

## TL;DR scoreboard (before -> after, live `pencil_dod_evaluate_county`)

| county   | before | after | delta |
|----------|--------|-------|-------|
| st_lucie | 9/10   | 9/10  | 0 (confirmed no regression; C reconfirmed structural ceiling, 3rd session to do so) |
| union    | 6/10   | 7/10  | **+1** (E flipped FAIL(75.0)->PASS(100.0)) |

## Baseline (session start, matched issue brief exactly)

```
st_lucie: A PASS B PASS C FAIL(78.9) D PASS E PASS F PASS G PASS H PASS I PASS J PASS -- 9/10
union:    A PASS B PASS C FAIL(75.0) D PASS E FAIL(75.0) F PASS G PASS H PASS I FAIL(75.0) J FAIL(75.0) -- 6/10
```

## st_lucie C — reconfirmed structural ceiling (3rd session), zero writes, correct outcome

The prior day's session (dispatch `9160a21e`, 2026-09-01) explicitly documented this as a 2x-confirmed
canon-level ceiling and recommended **not** re-investigating again without new evidence. Honored that:
ran a cheap DB-only reconfirm instead of a full re-investigation. `CLERK_SSOT_CANCELLED` count grew
47->50 (normal accrual as new auction rows land, not a reversal), 0 of 50 carry a `sold_amount`
(unchanged pattern), C metric unchanged at 78.9%. Independently re-verified by a workflow agent with
no stake in the outcome. This is a fleet-wide canon question (`CLERK_SSOT_CANCELLED` excluded from
`matched_clean` by evaluator design) already flagged in
`GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md` as needing an owner/architect
decision, not more single-shard sessions. No writes made.

## union C — same structural ceiling pattern, reconfirmed, zero writes

Case `63-2025-CA-0053` is union's one `CLERK_SSOT_CANCELLED` row, with a real, previously-cited clerk
order (Book 489 Page 561, cross-referenced against the Final Judgment Book 480 Page 6). Independently
re-verified this session — citation still real, metric unchanged at 75.0%. Not re-litigated for the same
fleet-wide-authority reason as st_lucie C.

## union E/I/J — E fixed via a two-source-independent parcel match; I/J genuinely blocked on value data

Case `63-2026-CA-0022` (row `af29ad63-3b4e-4ec8-8ec5-b6bbfb0a63b2`) was the sole row blocking E/I/J, with
`parcel_id`/`property_address` both NULL. A live re-scrape of `unionclerk.com`'s foreclosure-sales
calendar (fetched directly via Playwright) confirmed the case **newly appeared** on the public calendar
since the 2026-09-01 session (previously absent) — but the clerk's own listing for this case omits
ADDRESS/PARCEL ID (unlike a sibling case on the same page, which has both), so it's a genuine source gap,
not a scraper bug.

Ran a 3-agent parallel fresh-angle workflow (legal-notice publishers, court-record aggregators,
Property-Appraiser CAMA network capture) — the CAMA-search agent claimed a hit, but the adversarial
verifier **refuted it**: the cited URL was a session-state-dependent GIS details pane that doesn't
reproduce via a standalone fetch (a real false positive, correctly caught — the canonical failure mode
this verification layer exists for).

Went further independently: WebSearch on the defendant names surfaced `floridaparcels.com`, a
third-party Florida county-parcel-data aggregator. Its Union County Section 06/Township 06S/Range 20E
roll lists exactly one parcel with both "Crews" and "Hurst" as co-owners: parcel `0606200000006000`
("06-06-20-00-000-0600-0"), owner "CREWS AMANDA RAE & HURST KYLE", site address "16535 SE 86TH TRAIL,
LAKE BUTLER FL 32054" — an exact two-person name match against the case's two named defendants (Kyle
Hurst, Amanda Crews), and Florida foreclosure defendants are by law the record owners. The same
aggregator's parcel-detail page independently added lot size (87,120 sqft), year built (2018), and legal
description. A US Census Bureau geocode (`geocoding.geo.census.gov`, `Public_AR_Current` benchmark) gave
an exact address match with real coordinates.

**A second, independent Agent (not the one that made the fix) adversarially re-verified this entire
chain** before it was logged: confirmed both floridaparcels.com pages and the Census geocode
independently; could not reach unionclerk.com itself (Cloudflare-blocked to its plain-fetch toolset, but
that page was already directly rendered live by this session via Playwright earlier); explicitly labeled
the case-to-parcel *link* as an inference from the name-match (not a single document stating both facts
together) and recommended INFERRED rather than VERIFIED for the linkage specifically, VERIFIED for each
individual source fact. **Verdict: SURVIVED.** Adopted that exact labeling in the DB `parity_source`
citation and this report.

**Write:** `parcel_id`, `property_address`, `owner_name`, `latitude`/`longitude`, `lot_size`,
`year_built`, `legal_description`, `property_type`, `judgment_amount` (`$85,580.70`, read directly off
the clerk's own live page), `plaintiff` ("21st Mortgage Corporation"), `parity_source` (full citation
chain). Also inserted a `parcel_zones` row (parcel linked to jurisdiction 1187 "Union County", zone
`R-1`), following the *exact* pattern already used for union's other 3 parcels in that table (same
jurisdiction, same zone, same honesty-labeled `_ZONECODE_UNVERIFIED` source suffix).

**Result: E 75.0%->100.0%.**

**I stays FAIL (75.0%):** re-read the evaluator SQL directly
(`supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`) — `card_complete`
requires address + lat/long + `COALESCE(assessed_value,market_value)` + a zoned parcel link. Address/geo/
zoning are now satisfied for this row; `assessed_value`/`market_value` are not, and every reachable
source was exhausted this session: FL GIO Statewide Cadastral ArcGIS FeatureServer returns 0 features for
CO_NO=63 (Union) on both an owner-name and an exact-PIN query — a real HTTP 200 empty result, not a
fabrication risk, though the endpoint also became flaky/timeout-prone under repeated calls; Zillow
returned HTTP 403; Realtor.com returned HTTP 429 (Kasada bot-block); the Union County Property
Appraiser's own CAMA widget (`union.floridapa.com/GIS/`) is a legacy GrizzlyLogic/Schneider viewer whose
search results only populate from interactive browser session state, not a fetchable URL — confirmed
`#searchInput`/`SearchBy` radios/`#butSearch` exist, but no working results endpoint was found within
budget. Left null, correctly — no fabricated value written.

**J stays FAIL (75.0%), deliberately not attempted:** `bid_decisions` has exactly the pre-existing 3
union rows. The already-shipped `scripts/gold_standard_shard11_union_j_generator.py` would fall back to
a generic `COUNTY_DEFAULT_ARV=$120,000` for this row (no real assessed/market/opening-bid input
available) — declined to run it. A property-agnostic statewide default with zero property-specific input
sits too close to the fleet-wide "J ghost-fill" pattern flagged for adversarial audit elsewhere in this
campaign (see the `pasco-f-audit-and-j-scope` skill). BLANK > WRONG. Logged as a deliberate non-action,
not a blocker, in `gold_standard_ultraloop_audit`.

## DB writes this session

| table | rows written | county |
|---|---|---|
| multi_county_auctions | 1 (case 63-2026-CA-0022, 12 fields) | union |
| parcel_zones | 1 (parcel 06-06-20-00-000-0600-0) | union |
| gold_standard_ultraloop_audit | 5 (survived=true: union E/I/J, union C reconfirm, st_lucie C reconfirm) | both |
| gold_standard_campaign | 1 (session close-out, dispatch 3fbcb0c2) | shard |

No writes to any st_lucie row (correctly — C is st_lucie's only failing letter and is a reconfirmed
ceiling, not a data gap).

## Guardrail compliance

- Zero fabrication: every written field traces to a named, live, independently-fetched source (2 for the
  parcel/address/owner chain, 1 for geo, 1 for judgment/plaintiff — all cited in `parity_source`).
  PropertyOnion was not used as a source for any classification or amount field.
- A false-positive research claim was correctly caught and killed by the workflow's own adversarial
  verifier before it could reach the database — the canonical case this layer exists for.
- The fix that *was* written was independently re-verified by a second agent with no stake in the outcome
  (verdict SURVIVED) before being logged to the audit table.
- Fail-loud honesty: union I/J were left FAIL with the specific sources/error codes hit, not silently
  skipped, forced, or filled with a generic default.
- No writes to `pencil_dod_evaluate_county`, cron jobs 109/111/115, or the gold-standard-loop-* scoring
  jobs. `gold_standard_loop()`/`gold_standard_certify()` were not run (other shards likely mid-flight —
  hit a `55P03` lock-timeout on the first evaluator call this session).

## Session close-out (written live)

```json
{
  "st_lucie": {"A":true,"B":true,"C":false,"D":true,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true},
  "union":    {"A":true,"B":true,"C":false,"D":true,"E":true,"F":true,"G":true,"H":true,"I":false,"J":false}
}
```
`exit_reason='ceilings_reconfirmed_union_E_fixed'`, `session_end_at='2026-09-02T08:50:00Z'`. Neither
county reached 10/10 this session, so no certification event fired and no telegram notification was sent.

## SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('st_lucie');
-> {"A":{"pass":true,"metric":122},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":78.9},
    "D":{"pass":true,"metric":99.2},"E":{"pass":true,"metric":96.8},"F":{"pass":true,"metric":100.0},
    "G":{"pass":true,"metric":95.5},"H":{"pass":true,"metric":0.1},"I":{"pass":true,"metric":95.6},
    "J":{"pass":true,"metric":100.0},"auctions_total":251}

SELECT public.pencil_dod_evaluate_county('union');
-> {"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":75.0},
    "D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},
    "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},"I":{"pass":false,"metric":75.0},
    "J":{"pass":false,"metric":75.0},"auctions_total":4}
```
Timestamp: 2026-09-02T08:50Z.

## Next-session priorities

1. **union I/J**: only remaining lever is `assessed_value`/`market_value` for parcel
   `06-06-20-00-000-0600-0`. Worth one real interactive-Playwright attempt against
   `union.floridapa.com/GIS/` capturing *every* XHR (not URL-substring-filtered) during an actual
   click-driven search — this session confirmed the form fields exist but never got a live results DOM.
   Once I passes, the existing J-generator script needs zero changes, just a real ARV input.
2. **union C / st_lucie C**: now 3x-confirmed the same fleet-wide `CLERK_SSOT_CANCELLED` canon ceiling.
   Do not re-investigate a 4th time without new evidence — needs an owner/architect decision on
   `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md` Option A/B/C.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
