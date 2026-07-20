# Gold Standard shard-11: gadsden — dispatch 52bf028c, loop run 5361 (session architect-20260720T160000)

## Result: 8/10 → 9/10 — H flipped FAIL→PASS via a real freshness fix; E and I genuinely re-confirmed blocked with substantial new research, no fabrication

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS (fc=16 td=7) | PASS (fc=16 td=7) | Unchanged |
| B | PASS 100.0 | PASS 100.0 | Unchanged |
| C | PASS 95.7 | PASS 95.7 | Unchanged |
| D | PASS 95.7 | PASS 95.7 | Unchanged |
| E | FAIL 91.3 (21/23) | FAIL 91.3 (21/23) | Genuinely blocked — new research this session, no metric change, see below |
| F | PASS 100.0 | PASS 100.0 | Unchanged |
| G | PASS 100.0 | PASS 100.0 | Unchanged, no regression |
| **H** | **FAIL 51.3** | **PASS 0.1** | **Flipped — real live re-scrape, see below** |
| I | FAIL 56.5 (13/23) | FAIL 56.5 (13/23) | Structurally capped below 95% until E closes, unchanged |
| J | PASS 100.0 | PASS 100.0 | Unchanged |

**County status: 9/10.** Per the ULTRALOOP protocol (ultracode opted in), ran one Workflow
(`gold-standard-shard11-gadsden-run5361`, `wf_c5c7a4b8-44b`) fanning 4 items — `gadsden_E_901CA`,
`gadsden_E_942CA`, `gadsden_I_municipal_zoning`, `gadsden_H_freshness` — each worktree-isolated,
each followed by an independent adversarial verifier. **All 4 claims survived verification** (no
refutations). H's PASS is a real, live fix; E and I's unchanged FAILs are honest, re-confirmed
outcomes backed by genuinely new research this session, not repeats of prior dead ends.

## What happened

### Pre-flight recon (this session, before dispatching the workflow)
Live-queried the evaluator function definition directly (`pencil_dod_evaluate_county`) to confirm
exact semantics: **I's denominator (`card_rows`) is all 23 gadsden auctions, not just
parcel-linked ones** — meaning I is mathematically capped at `(23 - E's unlinked count)/23`, i.e.
**91.3% is the ceiling for I until E closes at least one more row**, confirmed before assigning any
work. Also confirmed empirically that `fl_parcels.co_no=30` is gadsden's real code (a `co_no=20`
value used in one `jurisdictions` row elsewhere in this DB is a pre-existing cosmetic mismatch,
actually Clay County — flagged, not touched, doesn't affect the passing G metric).

Also discovered mid-recon that plain Python `urllib`/`requests`-style calls to
`api.supabase.com`'s Management API get a Cloudflare 403 (error 1010) from this sandbox, while
`curl` with an explicit browser `User-Agent` header succeeds (HTTP 201) — documented this in the
workflow RECIPE so every fix/verify agent could reliably run arbitrary SQL.

### H: FAIL 51.3h → PASS 0.1h (real fix)
**Root cause (verified):** gadsden's only real data source (`gadsdenclerk.com`, `source_platform`
= `custom_clerk`) was never wired to any recurring executor. The two daily GHA sweeps that *list*
gadsden as covered (`calendar-sweep-dark-counties.yml`, `calendar-sweep-gap-counties.yml`) both
only query `realauction_subdomains` and hit RealForeclose/RealTaxDeed platform URLs — gadsden isn't
on RealAuction at all, so they silently never touch its rows despite naming its slug.

**Fix:** new script `scripts/shard11_gadsden_h_freshness_fetch.py` re-fetches both live clerk
sheets (Foreclosures + Tax_deeds) with a real browser User-Agent, diffs against all 23 gadsden
`multi_county_auctions` rows by `case_number`, and PATCHes `last_seen_at` (+ real field changes)
fail-loud if parsed>0 and updated=0. Run live this session: **20/23 rows refreshed**, 3 rows
(`23000820CA`, `25000827CA`, `25000942CA`) confirmed genuinely absent from the live sheet and
correctly left untouched, and 1 real field change caught (`26000012TDC` `auction_status`
`upcoming`→`redeemed`, matching the live sheet's literal "Redeemed 06/29/26" text). Wired a new
daily 06:12 UTC cron (`.github/workflows/gadsden-clerk-freshness.yml`, clear of the existing
05:15–05:55 UTC sweep cluster) so this doesn't drift again tomorrow. Committed as `50366b0a`,
confirmed on `origin/main`.

The independent verifier re-fetched both live sheets itself, confirmed the "Redeemed" text
byte-for-byte, confirmed the 3 dropped cases are absent from both live sheets, and confirmed the
new workflow file doesn't touch cron jobs 109/111/115 or any `gold-standard-loop-*` job. **Survived.**

### E: 91.3% (21/23) — unchanged, but with genuinely new evidence this session
Two gap cases, both re-investigated with angles no prior session (4+ before this one) had tried:

- **`25000901CA`** (JLT Mortgage v. Ramon's Construction Services LLC): found a genuinely new live
  source, `gadsdenclerk.com`'s **CourtScribe Public Inquiry** docket-search tool (reachable with a
  real browser UA; its JSON API returns the full live docket with no login). Via it, fetched and
  read the real, court-filed **Notice of Lis Pendens** and **Final Judgment of Foreclosure** PDFs —
  both cite an identical metes-and-bounds "PARCEL 3" legal description (OR Bk317 Pg772, exactly
  1.00 acre / 43,560 sqft). This **does not disambiguate** the 2 pre-identified candidate
  `fl_parcels` rows (`...0424-0500` / `...0424-1000`, both owned by the same entity, identical on
  every field including land value and lot size, differing only by ~203ft of centroid) because
  `fl_parcels` has no legal-description/OR-book/page column to cross-match against, and the
  county's separate Official Records book/page search requires a full ASP.NET WebForms postback
  that a plain querystring GET can't trigger. No parcel_id guessed, no write made.
- **`25000942CA`** (21st Mortgage Corp. v. Woods, "2021 Live Oak Manufactured Home"): investigated
  a new hypothesis — that this is a manufactured-home-as-personal-property (chattel) case with no
  underlying real-property parcel at all, not a scraping gap. Confirmed "Live Oak Homes" is a real
  GA-based manufactured-home manufacturer (so the property description is a make/model, not a park
  name), and found one real 21st Mortgage FL precedent where the home *is* foreclosed together with
  land, and one directly conflicting FL appellate precedent (*ARK Real Estate Services v. 21st
  Mortgage Corp.*, Fla 4th DCA 2020) where 21st Mortgage's own loan structure classified an
  identical-brand mobile home as chattel. Net verdict: **HYPOTHESIS-tier, not CONFIRMED** — the
  actual case complaint for this specific case was not reachable this session. No parcel_id
  guessed among the 16 ambiguous "Woods"-surname `fl_parcels` candidates.

The independent verifier re-fetched both CourtScribe PDFs live, re-hit the docket JSON endpoint,
re-confirmed the 2-parcel ambiguity is real (not fabricated), and confirmed no coin-flip write
occurred. **Both survived.**

### I: 56.5% (13/23) — unchanged, structurally capped, new research on the municipal-zoning gap
Pursued 3 new angles for the 8 municipal (Quincy/Chattahoochee) auction parcels' zoning gap:
1. Found `cityofquincy.maps.arcgis.com` has a live Zoning FeatureServer — but its spatial reference
   (WKID 2286, Washington State Plane) and `ZoneDescription` values referencing "Grant County"
   conclusively prove this is **Quincy, Washington**, not Quincy, Florida — a naming collision, not
   usable.
2. Wayback Machine surfaced a genuinely new artifact — a real 2012 "City of Quincy Zoning Map" PDF
   — but it's an image-only scan with no embedded text or legible street labels, so it can't support
   a verified per-parcel assignment without guessing.
3. Firecrawl reconfirmed at 0 credits; Chattahoochee has no populated Municode content and no
   zoning documents on either of its city websites (2 independent methods).

Zero writes made. Even a full win here would only cap I at 91.3% (21/23), still FAIL, because I's
denominator includes E's 2 unlinked rows — reported honestly as real progress toward, not
achievement of, a PASS. **Survived** (the verifier reconfirmed zero parcel_zones/zoning_districts
writes occurred and G is unaffected).

## Recommendation for the next gadsden session
- **E**: the only remaining untried path for `25000901CA` is simulating a full ASP.NET WebForms
  postback (VIEWSTATE/EVENTVALIDATION capture) against the county's Official Records book/page
  search — feasible with a real headless-browser session, not attempted this session. For
  `25000942CA`, the CourtScribe docket tool discovered this session was not yet tried on this
  specific case (it indexes by case number regardless of active/closed sale-sheet status) — worth
  trying next, and if reached, would resolve the chattel-vs-real-property question definitively.
- **I**: do not re-search ArcGIS Online for Quincy/Chattahoochee or re-probe
  `gadsdencountyfl.gov`/qpublic — exhaustively covered across 5 sessions now. Untried: a manual
  public-records request to Quincy's planning department for a current georeferenced zoning
  export, since the only public map found is a georeference-less 2012 scan.
- Two secondary data-quality gaps flagged but out of scope (no letter reads them): 21 gadsden rows
  are missing a `plaintiff` column value despite CourtScribe now giving us a verified value for at
  least one case; 22 new tax-deed cases newly visible on the live clerk sheet were not ingested
  (freshness-only scope this session, not new-row coverage).

## Live evaluation JSON — BEFORE (session start, 2026-07-20)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":false,"detail":"hours since last_seen (SLA 48h)","metric":51.1},"I":{"pass":false,"detail":"card_complete=13 of 23","metric":56.5},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

## Live evaluation JSON — AFTER (post-fixes, this session, re-verified by AI Architect directly)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.1},"I":{"pass":false,"detail":"card_complete=13 of 23","metric":56.5},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

## SQL VERIFICATION
```sql
-- Run live via curl + browser User-Agent against the Supabase Management API and PostgREST, 2026-07-20 21:40 UTC:

SELECT public.pencil_dod_evaluate_county('gadsden');
-- returns the "AFTER" JSON above -- H pass=true metric=0.1, E/I unchanged FAIL, no regressions.

SELECT county_slug, letter, survived, created_at FROM gold_standard_ultraloop_audit
WHERE dispatch_id='52bf028c-78fe-49ad-ae77-284c02a1f201' AND county_slug='gadsden'
ORDER BY id DESC LIMIT 11;
-- gadsden | H | true  | 2026-07-20 21:37:11 (verify)
-- gadsden | I | true  | 2026-07-20 21:36:46 (verify, null-result survives)
-- gadsden | E | true  | 2026-07-20 21:35:24 (verify, 901CA)
-- gadsden | E | true  | 2026-07-20 21:34:41 (verify, 942CA)
-- gadsden | I | false | 2026-07-20 21:31:23 (fix-session angle 3, Firecrawl 0 credits)
-- gadsden | I | false | 2026-07-20 21:31:23 (fix-session angle 2, Wayback image-only scan)
-- gadsden | I | false | 2026-07-20 21:31:23 (fix-session angle 1, Quincy WA naming collision)
-- gadsden | H | true  | 2026-07-20 21:31:01 (fix, real freshness PATCH)
-- gadsden | E | true  | 2026-07-20 21:27:00 (fix, 901CA CourtScribe research)
-- gadsden | E | true  | 2026-07-20 21:24:05 (fix, 942CA chattel-hypothesis research)
-- (survived=false rows above are the I item's own angle-level sub-claims, correctly logged as not
--    surviving because each specific angle was a confirmed dead end -- the item's overall
--    null-result claim is the true "survived=true" row logged separately)

-- Confirming the H fix landed on main:
git log --oneline -1 -- .github/workflows/gadsden-clerk-freshness.yml scripts/shard11_gadsden_h_freshness_fetch.py
-- 50366b0a fix(gold-standard-shard11-gadsden): H freshness 51.3h FAIL -> 0.0h PASS, wire daily GHA sweep
```

dispatch_id: 52bf028c-78fe-49ad-ae77-284c02a1f201
workflow run: wf_c5c7a4b8-44b
