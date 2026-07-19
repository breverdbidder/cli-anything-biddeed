# Gold Standard Shard-6: hillsborough / flagler / bay — dispatch 1f302343, 2nd firing

Session: architect-20260719T160000, loop run 5153. Same dispatch/issue fired twice; live DB
state at session start was verified to exactly match the first firing's "AFTER" checkpoint
(no regression, nothing lost between firings), so this session picked up the first firing's
own "NEXT-SESSION PRIORITIES" rather than re-running the diagnostic pass. Ultracode/Workflow
used for the adversarial-verify phase (33-agent fan-out) per ULTRALOOP protocol.

## Scope this firing

flagler/bay B+F: Firecrawl credits re-checked live (`team/credit-usage` API) — still
`remaining_credits: 0`. Still a billing decision flagged to Ariel, not re-attempted.
bay I: still needs browser automation this sandbox doesn't have + an Ariel definitional
call on excluding timeshare rows from the denominator. Not attempted.
**hillsborough I** (the one genuinely actionable, unblocked priority) was the target.

## hillsborough I — real fix, adversarially verified, then a caused-and-repaired G regression

### Method
268 has-parcel-id, all-other-fields-ok gap rows (240 unique STRAPs) had no `parcel_zones`
match. 204 of these share a placeholder centroid in `multi_county_auctions.lat/lon`, so a
coordinate-keyed fix was structurally wrong (same conclusion the first firing reached for
its own point-coordinate proposal). Real fix: fetch each parcel's own real polygon from the
county Property Appraiser (`gis.hcpafl.org` WebParcels, STRAP-keyed, ground truth,
independent of our stored lat/lon), then point-in-polygon test against three confirmed-live
zoning layers — Hillsborough unincorporated (`maps.hillsboroughcounty.org` DSD_Viewer, field
`NZONE`), City of Tampa (`arcgis.tampagov.net` OpenData/Planning, field `ZONECLASS`), and
City of Plant City (`services5.arcgis.com/.../Plant_City_Zoning_WFL1`, field `PCZONING`).

### Adversarial verify caught a real bug, and disproved a 9-session-old "no source" claim
A 33-agent fan-out (Workflow tool) independently re-derived a 30-row sample from scratch.
5/30 refuted. Manual re-derivation of all 5 disputed rows found: **2 were genuine bugs** —
the first-pass method used `esriSpatialRelIntersects` against each parcel's *full polygon*,
which false-positives when a parcel's boundary merely touches an adjacent zone polygon's
edge. Fixed by switching to a `shapely.representative_point()` (strictly-interior point,
not a bounding centroid) for the zoning lookup. **3 were refuter errors**, not real bugs —
re-querying the disputed STRAPs live, repeatedly, returned the exact same reproducible
geometry and zone code the original pass had claimed; the refuter's own reported geometry
for those 3 did not reproduce against the live API on independent re-query, so those 3
refutations are logged as false positives in the ledger, not counted as defects.
Separately, **three independent refuter agents each found a live Plant City zoning GIS
service** (`Plant_City_Zoning_WFL1/FeatureServer/15`, field `PCZONING`) that this session's
first pass — and this campaign's own 2026-06-10 fleet-wide finding, and 9+ prior sessions —
had concluded didn't exist. Verified live and reproducible by this author; added as a third
resolution jurisdiction (id 961).

### Result
238 of 240 unique gap STRAPs resolved (180 county, 49 Tampa, 9 Plant City). 2 remain
genuinely unresolved (both `SiteCity=TAMPA`, no point-in-polygon match in any of the 3
layers — a real residual coverage gap, left untouched). Shipped as
`supabase/migrations/20260719m_gtm22j_shard6_hillsborough_i_hcpafl_spatial_zoning_backfill.sql`.

```
BEFORE: I fail 68.0% (623/916)
AFTER:  I PASS 96.1% (880/916)
```

### Caused regression: G, diagnosed and mostly repaired live
The 238 new `parcel_zones` rows used 17 zone codes hillsborough had never had a
`zoning_districts` row for. `v_zoning_gold_standard_kpi_v3` treats a missing district as
"applicable, no value" by default (worst case) — this crashed G from PASS (density 98.7) to
FAIL (density 79.3, far 0.0, pk1000 4.9). Same failure class already seen once this campaign
(commit `838e9a53`, santa_rosa+putnam). Root cause confirmed live: far/pk1000-applicable
parcel count went from 0 (NULL denominator, ignored by Postgres `LEAST()`) to 41 (real
denominator, no longer ignorable).

Repaired via two more migrations (`20260719n`, `20260719o`), classification-only, no
fabricated numeric values except where independently confirmed:
- Created the 17 missing `zoning_districts` rows with correct category classification.
- Backfilled `max_density_du_acre` for RSC-N/RMC-N/RDC-N (Hillsborough LDC names these
  districts for their exact max density in du/acre — **RSC-6=6 du/acre independently
  confirmed live via web search against the LDC**; the other RSC/RMC/RDC codes apply the
  identical, systematic naming convention at lower `confidence_score`) and AS-1/AS-0.4
  (**AS-1=1-acre minimum lot, confirmed live**; density = 1/acres).
- Marked `density_regulated=false` for PD/PD-A category rows (Planned Development sets
  density per individual development order, not a single ordinance number — same reasoning
  already applied to far/pk1000 for these same rows). This one fix closed 119 of the gap.
- Marked `far_regulated=pk1000_regulated=false` for CG/CN (unincorporated Hillsborough
  County only) — Hillsborough's own comprehensive plan text (verified live) shows FAR is
  governed by Future Land Use category, not base zoning district, and Part 6.11 sets
  parking per use type, not per district — a structural mismatch with a
  flat-per-district value, not a sourcing gap.

```
BEFORE (this firing):    G PASS 98.7%
AFTER I-fix (unrepaired): G FAIL density=79.3 far=0.0 pk1000=4.9
AFTER repair migrations:  G FAIL density=95.6(pass) far=0.0(fail) pk1000=100.0(pass)
```

**G is NOT fully repaired — reported as FAIL, not claimed as PASS.** The residual is now
isolated to exactly 2 pre-existing parcels this session did not create: City of Tampa `CN`
(zoning_districts.id=1861) and Plant City `C-1` (id=1772), both missing `max_far`. Genuine
attempts this session to source real values: Tampa Code Ch.27 §27-156 Table 4-2 and Plant
City Code §102-6xx — hit Municode's WAF (403 on direct fetch), a stale/redirected county PDF
link, and an Angular SPA shell with no server-rendered content on curl-with-browser-UA.
Search results repeatedly surfaced Plant City's *C-2* §102-620 FAR section but never a C-1
equivalent — suggestive that C-1 may genuinely lack a FAR section, but that's absence of
evidence, not a confirmed absence, so **not applied**. Also flagged, not touched (outside
this session's scope): Plant City C-1's existing `parking_per_1000sf=4.00` value carries
`confidence_score=0.00` in the live DB — looks like a placeholder from an earlier session,
worth a dedicated audit pass.

### Net letter composition this firing
```
hillsborough: A✓ B✓ C✓ D✓ E✓ F✓ G✗(was ✓, now density=95.6 far=0.0 pk1000=100.0 -- 2-parcel residual) H✓ I✓(was ✗, now 96.1%) J✓  -- 9/10 (flat count, but I fixed + G precisely diagnosed to a 2-parcel gap instead of the prior full-mystery 293-row I gap)
flagler:      unchanged from 1st firing -- 8/10 (B,F fail, structurally blocked, re-confirmed still blocked: Firecrawl credits still 0)
bay:          unchanged from 1st firing -- 7/10 (B,F,I fail, same residuals as 1st firing, re-confirmed no regression)
```

## ULTRALOOP audit rows
`gold_standard_ultraloop_audit` ids 7533 (hillsborough/I, survived=true) and 7534
(hillsborough/G, survived=false — repair attempted and improved but letter still fails,
logged honestly as not-survived rather than omitted).

## VERIFICATION PROTOCOL
Live `pencil_dod_evaluate_county` re-run after every migration (5 total this firing across
I-fix, G-diagnosis, and two G-repair passes) — exact before/after JSON pasted above and in
the tool-call log. Did not run `gold_standard_loop()`/`gold_standard_certify()` (other shards
may be mid-flight per PARALLEL-FLEET RULES).

## NEXT-SESSION PRIORITIES
1. **hillsborough G**: source real `max_far` for Tampa `CN` (zoning_districts.id=1861) and
   Plant City `C-1` (id=1772) from a primary source reachable from a future sandbox (or a
   different Municode-bypass method), or find a citable confirmation that C-1/CN genuinely
   have no FAR standard. Either closes G to PASS — this is now a 2-parcel problem, not a
   41-parcel one.
2. **hillsborough I residual**: 2 STRAPs (`2027175LB000026000220A`, `20271823F000000000280A`,
   both `SiteCity=TAMPA`) have no point-in-polygon match in county, Tampa, or Plant City
   zoning layers — a real, small coverage gap; low priority given I already passes.
3. **flagler/bay B+F**: still blocked on the Firecrawl credit top-up decision (Ariel). Bay I:
   still needs browser automation + an Ariel call on the timeshare-row denominator question.
4. **Data-quality flag for a dedicated pass (not blocking)**: Plant City C-1's
   `parking_per_1000sf=4.00` has `confidence_score=0.00` — looks like a placeholder from a
   prior session; audit before trusting it further.

---
dispatch_id: 1f302343-9361-451a-8baa-7c22dd8844d8
chat_session: architect-20260719T160000
