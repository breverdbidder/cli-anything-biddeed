# Gold Standard shard-2 — calhoun / gilchrist / walton / osceola, 2026-08-18

dispatch: `d3ebfbe4-c166-436f-8e4d-f8284d789936` (loop run 12450)

## Summary

**walton: C and D fixed, verified, and adversarially confirmed — walton is now 10/10 (all
letters A-J PASS).** Root cause: 10 tax_deed rows were bulk-flipped to
`PHANTOM_NOT_ON_CLERK` at a single timestamp (2026-08-18 07:18:52 UTC) by a process with no
corresponding script anywhere in this repo — an untracked/erroneous direct write. Live
re-verification against Walton Clerk's own Tax Deed Division search system
(`taxsmart.clerkofcourts.co.walton.fl.us`) confirmed all 10 are real, valid cases that
were simply `REDEEMED` (owner paid off taxes pre-sale — a normal outcome, not "not on
clerk"). Reverted to `matched_clean` with a new parity_source tag citing the live
re-verification. An independent adversarial refuter agent (not the agent that made the
fix) re-ran the DB check and independently re-fetched 4/10 cases from the live Clerk site
itself — survived=true.

**calhoun, gilchrist, osceola: no writes made — genuinely blocked or structural, not for
lack of trying.** BLANK > WRONG followed throughout; no fabricated matches or ghost-success
writes.

**New finding surfaced for follow-up (not acted on this session):** osceola's C letter
(and potentially ~1059 other osceola rows sharing the same `parity_scope`) may be resting
on a self-referential "verification" — see osceola section below. Flagging per Honesty
Protocol rather than silently fixing or silently ignoring.

## Live verification — before and after

```json
BEFORE (session start, loop run 12450 — matches original brief exactly):
calhoun:   C FAIL 87.5  | all else PASS (9/10)
gilchrist: E FAIL 78.6, I FAIL 78.6 | all else PASS (8/10)
walton:    C FAIL 92.9, D FAIL 92.9 | all else PASS (8/10)
osceola:   C FAIL 89.3, D FAIL 89.3, I FAIL 90.7, J FAIL 90.7 | all else PASS (6/10)

AFTER (live re-query via SELECT public.pencil_dod_evaluate_county(<county>), this session):
calhoun:   C FAIL 87.5 (unchanged — genuinely inconclusive, see below)         → still 9/10
gilchrist: E FAIL 78.6, I FAIL 78.6 (unchanged — genuinely blocked, see below) → still 8/10
walton:    C PASS 100.0, D PASS 100.0 (matched_clean=141, matched_any=141)    → NOW 10/10
osceola:   C FAIL 89.3, D FAIL 89.3, I FAIL 90.7, J FAIL 90.7 (unchanged — structural, see below) → still 6/10
```

### SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('walton');
-- C: {"pass": true, "detail": "matched_clean=141", "metric": 100}
-- D: {"pass": true, "detail": "matched_any=141", "metric": 100}
-- auctions_total: 141, A/B/E/F/G/H/I/J all unchanged PASS -> walton = 10/10
-- Timestamp: 2026-08-18T~17:34Z UTC (live Management API re-query, this session)

SELECT public.pencil_dod_evaluate_county('calhoun');   -- C unchanged: matched_clean=7, metric=87.5, pass=false
SELECT public.pencil_dod_evaluate_county('gilchrist'); -- E unchanged: parcel_linked=11, metric=78.6; I unchanged: card_complete=11 of 14
SELECT public.pencil_dod_evaluate_county('osceola');   -- C/D unchanged: matched_clean=134, metric=89.3; I/J unchanged: 136 of 150, metric=90.7
-- All 3 re-run live at ~17:34Z UTC, identical to session-start baseline: zero regression, zero fabricated movement.
```

Audit trail: `gold_standard_ultraloop_audit` ids 16613 (walton/C) and 16614 (walton/D),
`survived=true`, independent refuter evidence attached in `refuter_evidence` jsonb.
Close-out: `gold_standard_campaign` id 4619, `exit_reason='partial_progress_verified'`.

## walton C/D — the fix

10 case numbers (`2026-0078TD`, `2026-0070TD`, `2026-0062TD`, `2026-0058TD`, `2026-0061TD`,
`2026-0064TD`, `2026-0105TD`, `2026-0104TD`, `2026-0120TD`, `2026-0124TD`) were tagged
`PHANTOM_NOT_ON_CLERK` despite having sale dates still in the future (today through
2026-09-29) — a logical impossibility for a "not confirmed on clerk after the sale"
classification. `grep -r PHANTOM_NOT_ON_CLERK` combined with `walton` across the whole repo
(scripts, migrations, workflows) returns nothing — this tag was written by something
outside the tracked pipeline. All 10 also have pre-existing `sale_type='foreclosure'`
sibling rows (same case_number/parcel_id) that were left untouched at `matched_clean` by
the exact same 07:18:52 UTC timestamp, strongly suggesting a `sale_type`-scoped bug in
whatever wrote the PHANTOM flip, not a genuine new reconciliation finding.

Live re-check against `taxsmart.clerkofcourts.co.walton.fl.us` (Walton Clerk's own Tax Deed
Division search, found via its `/Home/GridSearchData?SearchType=Case%20%23` JSON endpoint)
confirmed all 10 as real cases, status `REDEEMED`, parcel_id and sale_date matching our DB
exactly.

```sql
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:manual_reverify_20260818_walton_live_recheck'
WHERE county = 'walton' AND sale_type = 'tax_deed'
  AND parity_status = 'PHANTOM_NOT_ON_CLERK'
  AND case_number IN ('2026-0078TD','2026-0070TD','2026-0062TD','2026-0058TD',
                       '2026-0061TD','2026-0064TD','2026-0105TD','2026-0104TD',
                       '2026-0120TD','2026-0124TD');
-- 10 rows affected, confirmed via RETURNING and independently re-queried by the refuter agent.
```

Applied via migration `supabase/migrations/20260818_gold_standard_shard2_walton_phantom_revert.sql`
(committed alongside this report).

## calhoun C — genuinely inconclusive (no write)

Single gap row: case `546 OF 2024` (tax_deed), tagged `CLERK_SSOT_CANCELLED` after a
reconfirm pass against `calhounclerk.com`'s tax-deed feed came back empty. Live-fetched the
same feed for all 5 *other* calhoun tax_deed cases that currently PASS — every single one
also returns an empty `[]` from `calhounclerk.com/wp-json/wp/v2/taxdeeds`. The entire
`taxdeeds` REST collection on the Clerk's site is broken/empty site-wide right now (the
sibling `foreclosures` collection on the same site works fine, confirming the API itself is
reachable). No Wayback/archive.org snapshot exists for either URL. Calhoun Property
Appraiser (`calhounpa.net`) returned HTTP 403. Result: cannot positively confirm case 546 is
either still valid or genuinely cancelled — the very signal that triggered the cancellation
(empty feed) is now shown to be unreliable across the board. Left as-is. Zero rows written.

## gilchrist E/I — still blocked (no write)

3 foreclosure cases (`212025CA000033CAAXMX`, `212025CA000043CAAXMX`, `212025CA000070CAAXMX`)
remain unlinked. This is the 4th session to attempt this exact gap (see dispatches
`28bd9542`, `61f11933`, `7617ebac`, and the 2026-08-01 session report). New angle attempted
this session: cross-referencing the DB's stored (truncated) defendant surnames (SLOCUM,
MERCADO, HUTCHINSON) against the full FL GIO statewide cadastral owner-name index for
Gilchrist (all 14,453 parcels fetched and searched) — the method was validated against 2
already-linked gilchrist rows (exact owner-name match confirmed) but found no owner-name
match for any of the 3 target cases (all 3 appear to be estate/probate-flavored
foreclosures where the auction-system defendant name and the appraiser's owner-of-record
name diverge). RealForeclose, Gilchrist Clerk site, and Property Appraiser GIS all returned
403/login-walled. Firecrawl credits confirmed exhausted (`remainingCredits: -16`, matches
`supabase/migrations/20260818_shard5_madison_run12346_firecrawl_exhaustion_reconfirmed_blocked.sql`).
Gilchrist OCRS case search was navigated successfully through the disclaimer/ViewState flow
but the search submission returned an ambiguous empty response that could not be trusted as
either a positive or negative result. Zero rows written.

## osceola C/D/I/J — structural gap + one new audit flag (no write to C/D/I/J-blocking rows)

14 rows block I and J identically (13 fresh tier1-promoted tax_deed rows + 1 foreclosure
row with a synthetic placeholder parcel_id). Backfilled real lat/lon/address/assessed_value
for all 13 tax_deed rows via the FL DOR statewide parcel-centroid ArcGIS layer (CO_NO=59,
confirmed against the official FL DOR county-number map after an initial wrong guess) —
this is a real, verified data improvement, applied via
`supabase/migrations/20260818_gold_standard_shard2_osceola_geo_enrich.sql` — **but it did
not move I or J**, because the actual I-blocker is a separate join requirement
(`v_zoning_gold_standard_card` / `parcel_zones`) that these mostly-rural parcels aren't in —
a completely different pipeline (ZoneWise zoning-ordinance ingestion) than geo/address data.
Documented so the next session doesn't re-attempt the same (already-exhausted) geo angle.
C/D for these rows is confirmed structural: osceola has no independently-parseable public
clerk calendar reachable by `scripts/clerk_ssot/run_parity.py` (explicitly excluded by
name), so there is no second source to reconcile parity against.

**New finding, flagged not fixed:** investigated why 3 already-`matched_clean` osceola rows
lack a `parity_source` tag. Traced `parity_status='matched_clean'` on those 3 (and
potentially ~1059 other osceola rows sharing `parity_scope='supplementary_litmus_run1524_official_platforms'`
with `parity_source` still NULL) to `scripts/shard5_run1524_osceola_cd_fix.py`, whose
`classify_row()` sets `matched_clean` purely from non-null parcel_id/address checks on our
*own* row — zero external cross-check — with a hardcoded `parity_confidence=0.92` literal.
The script's own docstring self-labels these as "INFERRED (supplementary litmus,
pre-authorized)". Declined to backfill `parity_source` for the 3 rows (would be
ghost-success dressing a self-referential classification in the same naming convention used
for genuinely independently-verified rows). This warrants a dedicated audit of the
`run1524` script's methodology across every county it touched (also ran variants for
suwannee, glades/union, walton, santa_rosa, seminole per grep) — **recommended next-session
priority**, separate from this shard's assigned counties.

## Next-session priorities

1. **osceola**: audit `run1524`-sourced `matched_clean` rows fleet-wide (not just osceola)
   for genuine independent-source backing before they're relied on for any C/D pass.
2. **osceola I/J**: needs ZoneWise zoning-ordinance/parcel_zones ingestion for the 14 rural
   Holopaw/St. Cloud-area parcels, not more geo backfill (exhausted this session).
3. **calhoun C**: re-check `calhounclerk.com/wp-json/wp/v2/taxdeeds` in a future session —
   if the feed comes back online, re-attempt case `546 OF 2024` confirmation.
4. **gilchrist E/I**: same 3 cases blocked for the 4th consecutive session; likely needs a
   RealForeclose authenticated bidder account or a working Gilchrist OCRS case-number search
   to break — both currently inaccessible to this pipeline.

## Ultraloop audit

`gold_standard_ultraloop_audit`: ids 16613 (walton/C), 16614 (walton/D), both `survived=true`,
independently refuted by a separate agent (live DB re-query + live re-fetch of 4/10 Walton
Clerk records). No claims made for calhoun/gilchrist/osceola since no letter flipped for
those counties this session — nothing to adversarially verify.
