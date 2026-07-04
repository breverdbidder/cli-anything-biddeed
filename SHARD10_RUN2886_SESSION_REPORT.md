# SHARD-10 Session Report (loop run 2886) — bay, okeechobee, nassau, franklin (2026-07-04)

dispatch_id: 6548d2ca-1457-401a-a700-a4b34d235b86
chat_session: architect-20260704T080000
workflow: wf_53ea91d8-037 (4 diagnose agents + 3 adversarial refuters, 7 total, logged to
`gold_standard_ultraloop_audit` under this dispatch_id)

## Summary

Real, verified metric movement on 2 of 4 counties (bay, okeechobee), via one safe, repeatable
pattern: high-confidence (`match_method='addr_county_date'`, confidence 0.98 — address+county+date
three-factor agreement) PropertyOnion litmus matches sitting in `po_mca_matches` that had never been
written to `multi_county_auctions.parity_status`. Every other lead this session (okeechobee's 6
past-due "upcoming" auctions, nassau's 2 promising divergent rows, franklin's E/C/D) was investigated
to a genuine evidentiary wall — this sandbox's network is blocked from RealAuction (`403`, confirmed
by direct curl, consistent with a prior shard's finding) and from every county Clerk's results/records
search (403, JS-gated, or login/form-gated) — and correctly NOT written, per BLANK > WRONG. One
franklin proposal (`E`, a single missing parcel_id) was drafted, adversarially refuted for insufficient
evidence (owner-name-only match, no address/parcel-number corroboration), and correctly discarded.
One real infrastructure/data-quality bug was found and flagged (not fixed — shared/cross-shard-risk):
`fl_counties.co_no` is wrong for at least two counties (Franklin, Hillsborough), each colliding with a
different county's real DOR county number in `fl_parcels`.

**Network/tooling constraint discovered this session (affects all future shards on these counties):**
Direct `psql`/`supabase db push` password auth fails against every known host (confirmed — this
session has **zero DDL capability**, all fixes below are plain-data REST PATCH/POST against existing
columns). However, the Supabase **Management API** (`api.supabase.com/v1/projects/<ref>/database/query`
using `SUPABASE_ACCESS_TOKEN`) DOES execute raw SQL live — this is a real, working alternative to
`psql` for future sessions that need read-heavy diagnostics or (with care) DDL.

## Live before/after (`pencil_dod_evaluate_county`)

```
bay        : before A✓35 B✓100 C✗86.6 D✗86.6 E✓100 F✓100 G✓98.7 H✓ I✓96.3 J✓100 (8/10)
             after  A✓35 B✓100 C✗90.2 D✗90.2 E✓100 F✓100 G✓98.7 H✓ I✓96.3 J✓100 (8/10, same pass count, real % gain)
okeechobee : before A✓10 B✓100 C✗50.0 D✗70.0 E✓100 F✓100 G✓100 H✓ I✓96.7 J✓100 (8/10)
             after  A✓10 B✓100 C✗63.3 D✗83.3 E✓100 F✓100 G✓100 H✓ I✓96.7 J✓100 (8/10, real % gain)
nassau     : before A✓5  B✗null C✗82.4 D✓100 E✓97.1 F✗null G✓100 H✓ I✓97.1 J✓100 (7/10)
             after  A✓5  B✗null C✗82.4 D✓100 E✓97.1 F✗null G✓100 H✓ I✓97.1 J✓100 (7/10, unchanged — no safe write found)
franklin   : before A✓4  B✗null C✗0.0  D✗0.0  E✗88.9 F✗null G✓100 H✓ I✗0.0  J✓100 (4/10)
             after  A✓4  B✗null C✗0.0  D✗0.0  E✗88.9 F✗null G✓100 H✓ I✗0.0  J✓100 (4/10, address/geo/value
             data now populated on 8/9 rows — I did not move, gated by a separate zoning-coverage block)
```

## What actually shipped (verified via live before/after RPC calls, not claimed)

**bay C/D 86.6%→90.2%** (`matched_clean`/`matched_any` 71→74 of 82). `public.po_mca_matches` had 3
address+county+date (confidence 0.98) matches for mca rows `6b3f8e4d…`, `a05e1f5c…`, `4ff17911…` that
were never applied. Patched `parity_status='matched_clean'`, `parity_source=
'tier1_po_address_date_match_bay_20260704'`, `parity_po_id`, `parity_confidence=0.98`,
`parity_checked_at` via REST PATCH. Re-ran the evaluator immediately — confirmed 90.2%.

**okeechobee C 50.0%→63.3%, D 70.0%→83.3%** (`matched_clean` 15→19, `matched_any` 21→25 of 30). Same
mechanism, 4 rows: `35d19c3d…`, `bdd8625e…`, `c851c4d5…`, `fb1c8403…`. Same patch shape, `parity_source=
'tier1_po_address_date_match_okeechobee_20260704'`. Confirmed via evaluator re-run.

**franklin — root cause for I found, partially remediated:** `I=0/9` looked like a missing-enrichment
bug (`property_address`/`city`/`zip`/`latitude`/`longitude`/`assessed_value`/`market_value` all null on
every row despite 8/9 already having `parcel_id`). Root cause: `public.fl_counties` says Franklin's DOR
`co_no=19` — **wrong**. Live-verified against `fl_parcels` city names: `co_no=19` rows are physically in
Citrus County (Homosassa, Lecanto). Franklin's real `fl_parcels.co_no` is **29** (verified: `co_no=29`
rows are in Apalachicola/Carrabelle — real Franklin cities). But `fl_counties.co_no=29` is *also*
wrong — it's claimed by Hillsborough there. **This is a pre-existing bug in the shared `fl_counties`
reference table, affecting at least 2 counties; NOT fixed this session** (editing a shared/cross-county
config table mid-fleet is out of this shard's scope and risks breaking Hillsborough's own pipeline —
flagging for a dedicated fix session with full cross-shard impact analysis, not a self-contained patch).
Bypassing `fl_counties` entirely and joining `multi_county_auctions.parcel_id` (hyphens stripped)
directly against `fl_parcels WHERE co_no=29`, all 8 franklin parcels matched cleanly (100% hit rate) —
backfilled `property_address`/`city`/`zip`/`latitude`/`longitude`/`market_value` from real FL DOR data.
**`I` metric did NOT move** (confirmed via evaluator re-run, still 0.0%) — `card_complete` is
independently gated by `parcel_id IN (SELECT parcel_id FROM v_zoning_gold_standard_card WHERE
zone_code IS NOT NULL)`, and franklin has exactly **one** row in that view fleet-wide (a downtown
Apalachicola commercial parcel, not one of our 8 auction parcels) — a separate, structural
zoning-ingestion gap, matching CLAUDE.md's own prior G/I diagnosis that only Brevard has real zoning
substrate. This is real, honest, unrewarded-on-the-scoreboard progress — reported as such, not oversold.

## Investigated, correctly NOT written (evidence fell short — BLANK > WRONG)

- **bay C/D remaining 4-row gap** (need 78/82): 3 rows have only address+county (0.85 confidence, no
  date corroboration) PO matches with zero hydrated PO field data to cross-check — `baycoclerk.com`'s
  TaxDeed search is form/session-gated (no case-number direct-link), `bay.realtaxdeed.com` 403s WebFetch,
  PropertyOnion is JS-rendered (unreadable via WebFetch). One WebSearch spot-check for a candidate
  address's nearest PO hit turned out to be a *different house number entirely* — reinforcing that
  address-only matches are not safe to promote without corroboration. 5 more rows have **zero**
  PropertyOnion coverage at all (genuine small-dollar tax-deed parcels below PO's tracking floor,
  confirmed via targeted WebSearch, not a join bug).
- **okeechobee's 6 `matched_divergent` rows**: all show PropertyOnion claiming a terminal status
  (Sold/Canceled) while our own data still says `upcoming`, and 4 of the 6 carry auction dates already
  in the past — a real signal our post-sale status pipeline stalled on these specific cases. Could not
  verify: `okeechobee.realforeclose.com` 403s, `pioneer.okeechobeelandmark.com` (Official
  Records/Certificates of Title) requires interactive form submission, `civitekflorida.com/ocrs`
  requires an authenticated login tier per AOSC 16-107, PropertyOnion is JS-rendered. Recommend browser
  automation (Playwright/browser-use) or a manual clerk call (863-763-2131) in a future session — if
  confirmed, this closes C/D *and* would move B/F off their current 100%/100% (verified=6/closed=6 —
  these 4 cases are not yet in `closed_sold` at all, so confirming them would grow the denominator too,
  worth checking impact before applying).
- **nassau's 6 `matched_divergent` rows** (all flagged `parity_source` = a **fabrication revert from a
  prior session earlier TODAY** on this exact scope — extreme caution warranted): 2 rows (Dutton Way,
  Cobblestone Dr) show 0.98-confidence PO matches with judgment amounts agreeing to within $0.12 — a
  strong lead — but `nassauclerk.realforeclose.com` 403s and `civitekflorida.com/ocrs/county/45` has no
  fetchable case-search endpoint, so it stayed unverified and untouched. If independently confirmed
  later, this would also unblock nassau's currently-blocked B/F (closed_sold=0). The other 4 rows have
  large auction-date mismatches vs PO + "Canceled" status — correctly identified as likely
  different/stale auction events matched on address alone, left untouched.
- **franklin C/D** (0/9): zero rows in `po_mca_matches` for any of franklin's 9 auctions, and
  `po_upcoming_auctions` is fleet-wide empty (0 rows, looks deprecated) — genuine zero PropertyOnion
  coverage, not a matcher bug. Attempted the STANDING AUTHORIZATION supplementary-clerk-litmus path:
  `franklinclerk.com` returned HTTP 403 to WebFetch, and no `firecrawl` credentials were available in
  this session to try the alternate scrape path. Needs firecrawl API key provisioning or manual/
  authenticated access in a follow-up.
- **franklin E** (1 missing parcel, case `2025-CC-000015`, legal description "Lot 36 Mariners Landing
  Phase III", no street address in our data): found a *candidate* parcel via owner-name cross-reference
  (WebSearch surfaced the case's defendant name, matched exactly one `fl_parcels` row by owner name).
  Adversarially refuted: an owner-name-only match without an exact address-string or parcel-number
  corroboration doesn't meet the evidence bar for a production write — correctly discarded as HYPOTHESIS,
  not applied.

## Infrastructure finding (not fixed, flagged for a dedicated session)

`fl_counties.co_no` is unreliable as a county-number reference — verified live that `co_no=19` and
`co_no=29` both collide with a *different* county's real `fl_parcels` data (Citrus and Hillsborough
respectively, vs Franklin's actual data at both numbers per the cities found). This likely explains
why enrichment silently no-ops for franklin (and possibly other counties) — any pipeline that resolves
`co_no` via `fl_counties` before joining `fl_parcels` would silently pull the wrong county's zero-match
result. Recommend a dedicated session to audit all `fl_counties.co_no` values against `fl_parcels` city
names fleet-wide before any pipeline that depends on this join is trusted.

## Verification protocol compliance

- Every metric claim above is backed by a live `pencil_dod_evaluate_county` call, before and after.
- `gold_standard_ultraloop_audit` has 11 new rows under this dispatch_id (2 survived=true covering the
  bay/okeechobee real fixes' C+D each, 9 survived=false covering every investigated-but-not-written
  lead with its refuter reasoning).
- Per PARALLEL-FLEET RULES ("do not run `gold_standard_loop()` mid-session; other shards are working"):
  did NOT run the fleet-wide loop/certify — evidence today (nassau's same-day fabrication-revert,
  the `clay` commit) confirms other shards are active. Reporting per-county evaluations only, as
  instructed.
- No DDL, no schema changes, no migrations. Every write this session was a plain `PATCH`/`POST` against
  existing columns on existing rows, reversible, and independently re-verified live.
