# GOLD STANDARD shard-11 (union, gulf) — 3rd firing session report

dispatch_id: `1a211136-77c7-4125-b70c-06b26ad13ebe` · chat_session: `architect-20260719T160000` (3rd firing) · 2026-07-20
mode: ULTRALOOP native (Workflow tool: 3 research agents + 2 adversarial refuters; plus 1 follow-up
Agent-tool refuter for a hand-derived spatial finding) — 6 subagents total

## Duplicate dispatch, re-confirmed live before any work

This is the 3rd firing of the same `dispatch_id`. The 1st firing shipped fixes (commit `7ffd8c88`). The
2nd firing found zero drift and closed two of three open leads. Before doing anything, this session
re-queried `pencil_dod_evaluate_county` live for both counties and confirmed the 2nd firing's closing
numbers exactly: union 8/10 (A,C,D,E,G,H,I,J), gulf 4/10 (A,G,H,J). Union's B/F block is genuinely
time-gated (`select case_number, auction_status from multi_county_auctions where county='union'` shows
1 `redeemed` cert + 2 `upcoming` — no closed sale exists to verify; earliest real close 2026-08-13) and
was not touched.

## What shipped this session (gulf only)

A 3-lead research workflow re-attempted the 2nd firing's documented next-session priorities with fresh
tooling. Two leads produced adversarially-verified, actionable findings; one remained genuinely
unresolved; one was refuted on its central premise.

### Gulf unincorporated zoning substrate — FOUND, adversarially verified (survived=true)
Gulf County's Land Development Regulations (LDR) PDF is directly hosted on the county's own CDN
(`cdnsm5-hosted.civiclive.com/.../LDR%20Complete%2009-2019.pdf`, HTTP 200, 53,579,518 bytes) — a
different domain from the perpetually-403 Municode mirror every prior session hit. OCR (the PDF has no
text layer) of Article III Sec. 3.01.03 confirms unincorporated Gulf County regulates by 8 Future Land
Use districts (RESIDENTIAL, COMMERCIAL, MIXED COMMERCIAL/RESIDENTIAL, AGRICULTURAL, PUBLIC, RECREATION,
CONSERVATION, INDUSTRIAL), not conventional lettered zone codes. An independent refuter byte-matched the
PDF and reproduced the OCR'd district list verbatim. `refuted=false`.

### Gulf parcel 06248-410R zone assignment — RESOLVED and WRITTEN (survived=true)
This parcel was confirmed unincorporated Gulf County in the 2nd firing (audit row 7535) but that alone
couldn't flip letter I — no jurisdiction/zoning_districts row existed for unincorporated Gulf, and no
per-parcel Future Land Use had been determined. This session closed both gaps directly: fetched the
parcel's real polygon geometry from Gulf GIS (layer 12/Parcels, keyed by PIN) and ran a live
`esriSpatialRelIntersects` query against Gulf GIS layer 40/Land Use, which returned
`Type=Mixed_Comm/Res` (1420.02-acre polygon). Methodology was validated against 3 known in-city control
parcels (`06051-008R`, `05004050R`, `05762000R`) — all three correctly return `Type=Municipal` (the
layer's placeholder for areas where city zoning applies instead of county FLU), confirming the layer's
semantics are real rather than a spurious constant. An independent Agent-tool refuter reproduced every
step from scratch (same geometry, same `Type`, same control result, same city-limits-exclusion result).
`refuted=false`.

**Shipped**: new jurisdiction "Gulf County Unincorporated" (id 1507), all 8 LDR-sourced zoning_districts
rows, and a `parcel_zones` row for `06248-410R` (`zone_code='Mixed_Comm/Res'`).

**Also confirmed by this same check (not written, not actionable)**: `05004050R` and `05762000R` are
BOTH inside Port St Joe city limits (`Type=Municipal`), so they remain gated on the separate, still-
unresolved City of Port St Joe zoning-map ambiguity (identical fill colors across residential
sub-districts, no georeferencing in the vector zoning PDF) documented in the 2nd firing. Not touched.

### P0 regression caught and fixed same-session: gulf G dropped 100.0 -> 88.9
The `parcel_zones` write above joins to `v_zoning_district_applicability`, which defaults
`density_applicable=true` for any non-commercial/industrial district category — including the new
`Mixed_Comm/Res` (mixed_use) district, which had no `zone_standards` row. That flipped one previously-
100%-passing parcel-density check to "applicable but missing," dropping G below the 95% threshold. Per
the campaign's "any regression = P0" rule, fixed immediately in the same session: added a
`zone_standards` row for the Mixed_Comm/Res district with `max_density_du_acre=4`, the real LDR-cited
base-district maximum (Art. III Sec. 3.01.03 density table, PDF p.67 — "1-4 DU/Acre" before any
overlay-specific reduction; `confidence_score=0.75` because the applicable overlay for this specific
parcel was not determined). Re-verified live: G back to 100.0/PASS, zero other letters affected.

### Gulf OCRS Cloudflare wall (B/C/D/E/F blocker) — lead REFUTED, not written
Research initially found `gulfclerk.com/record-search/` also links to
`myfloridacounty.com/orisearch/23`, a non-Cloudflare recorded-documents search distinct from the blocked
`civitekflorida.com/ocrs/county/23` case docket. However, the adversarial refuter could not reproduce
the claim's central premise: 4 independent fetches of `civitekflorida.com/ocrs/county/23/` (2x WebFetch,
2x curl with different UAs) all returned a clean HTTP 200 landing page with zero Cloudflare signatures
(no `cf-ray`/`server:cloudflare` header, no Turnstile markup). `refuted=true` — not written, not acted
on. This is flagged as a genuine open question for a future session (see below), not closed either way:
either the wall is deeper in the flow (past the initial "select access option" page) or it is no longer
present at all and 4+ sessions' worth of "blocked" status is stale. Untested claim in either direction —
BLANK, not guessed.

### Gulf parcel 05762000R zoning ambiguity — still UNRESOLVED
No new resolution. This session did find that the City zoning-map PDF has a real vector text layer
(`R-1, R-1A, R-2A, R-2B, R-3, C-1, C-1A, C-2, PU, PUD` labels at specific coordinates) rather than being
purely a scanned image as previously assumed — but the PDF has no embedded georeferencing and no
street-name labels near Block 1004/Ave C, so the label-to-parcel binding still cannot be resolved without
guessing. Confirmed via the same GIS check that this parcel is inside Port St Joe city limits, consistent
with prior findings. Recommended next step unchanged: human call to City of Port St Joe Planning,
(850) 229-8261, re: Block 1004 Lot 20.

## SQL VERIFICATION

```sql
-- run 2026-07-20, live via mgmt_sql.py (Management API)
select public.pencil_dod_evaluate_county('union');
-- union: A pass(1) B fail(null) C pass(100.0) D pass(100.0) E pass(100.0) F fail(null)
--        G pass(100.0) H pass(13.0) I pass(100.0) J pass(100.0)  -- 8/10, unchanged (zero drift)

select public.pencil_dod_evaluate_county('gulf');  -- BEFORE this session's writes
-- gulf: A pass(5) B fail(null) C fail(78.6) D fail(78.6) E fail(78.6) F fail(null)
--       G pass(100.0) H pass(3.5) I fail(42.9, "card_complete=6 of 14") J pass(100.0)  -- 4/10

-- ... migrations applied (jurisdiction + 8 zoning_districts + 1 parcel_zones write) ...
-- immediately after: G regressed to 88.9 (P0), fixed same-session with a zone_standards write ...

select public.pencil_dod_evaluate_county('gulf');  -- AFTER this session's writes
-- gulf: A pass(5) B fail(null) C fail(78.6) D fail(78.6) E fail(78.6) F fail(null)
--       G pass(100.0) H pass(3.8) I fail(50.0, "card_complete=7 of 14") J pass(100.0)  -- 4/10
--       (I moved 42.9 -> 50.0, still fails 95% threshold; G restored to 100.0 after P0 fix; no other
--        letter moved)

select id, county_slug, letter, survived from gold_standard_ultraloop_audit
  where dispatch_id = '1a211136-77c7-4125-b70c-06b26ad13ebe' order by id;
-- 8 rows total (6 from firings 1-2 + 2 new: substrate finding + parcel 06248-410R finding, both
-- survived=true)
```

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`certify()` were not run (other shards may be mid-flight
concurrently) — per-county `pencil_dod_evaluate_county` was used for all verification instead.

## Migrations shipped (direct to main, live-applied)
- `migrations/20260720_gold_standard_shard11_union_gulf_3rd_firing_i_unincorp_zoning.sql` — jurisdiction
  + 8 zoning_districts + 1 parcel_zones write
- `migrations/20260720_gold_standard_shard11_gulf_g_regression_fix.sql` — P0 fix for the G regression
  caused by the above

## Next-session priorities (carried forward + refined)

1. **gulf `civitekflorida.com/ocrs/county/23` status is genuinely unclear** (new, highest-leverage item):
   this session's refuter got a clean, non-Cloudflare 200 on the landing page 4/4 times, contradicting
   4+ prior sessions' "Turnstile-walled" status. Before spending more research budget assuming it's
   blocked, a session should manually click through the "Public/Attorney/Registered/Party Access"
   selection to see whether the wall is deeper in the flow, or whether it's simply gone. If genuinely
   open, this is the single biggest unlock available for gulf B/C/D/E/F.
2. **gulf `05762000R`** — still needs the human phone call to City of Port St Joe Planning
   (850-229-8261); the newly-found vector-text zoning map doesn't help without georeferencing.
3. **gulf remaining unincorporated parcels** — `05004050R` and `05762000R` are confirmed in-city (not
   unincorporated), so the new zoning substrate doesn't apply to them; no other currently-tracked gulf
   parcel is known-unincorporated-and-unzoned at this time.
4. **union B/F** — nothing to do until a real auction closes (earliest 2026-08-13).

---
dispatch_id: 1a211136-77c7-4125-b70c-06b26ad13ebe (3rd firing)
