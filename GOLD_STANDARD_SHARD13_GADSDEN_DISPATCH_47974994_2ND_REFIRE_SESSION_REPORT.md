# Gold Standard shard-13: gadsden — dispatch 47974994, 2nd re-fire (session architect-20260719T160000)

## Result: 7/10 → 8/10 — G flipped PASS via real GIS+ordinance data, no fabrication

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS (fc=16 td=7) | PASS (fc=16 td=7) | Unchanged |
| B | PASS 100.0 | PASS 100.0 | Unchanged |
| C | PASS 95.7 | PASS 95.7 | Unchanged |
| D | PASS 95.7 | PASS 95.7 | Unchanged |
| E | FAIL 91.3 (21/23) | FAIL 91.3 (21/23) | Genuinely blocked, unchanged — see below |
| F | PASS 100.0 | PASS 100.0 | Unchanged |
| **G** | **FAIL (null)** | **PASS 100.0** | **Flipped — see below** |
| H | PASS 28.5 | PASS 28.9 | Wall-clock drift only, no writes |
| I | FAIL 0.0 (0/23) | FAIL 56.5 (13/23) | Real progress, still FAIL — structurally capped by E |
| J | PASS 100.0 | PASS 100.0 | Unchanged |

**This dispatch (47974994) has now been re-fired twice today.** The first re-fire (session
architect-20260719T??? earlier today, see `GOLD_STANDARD_SHARD13_GADSDEN_DISPATCH_47974994_SESSION_REPORT.md`)
concluded 7/10 with E/G/I genuinely blocked after exhaustive research and made zero DB writes.
A separate concurrent session (commit `75e2b7af`, `architect-20260719T210000`) wrote scripts and
a migration for the same G/I gap but explicitly left it **unrun** (zone_standards intentionally
NULL, district codes marked INFERRED-not-verified) and never executed it. This session found a
genuinely new, verifiable data source neither prior session located, used it to make one real
metric move (G), and is honest that E stays blocked and I stays FAIL.

## What happened

Per the ULTRALOOP protocol (ultracode opted in), ran one Workflow (`gadsden-shard13-gi-refire`,
`wf_e10550cd-a42`) with a research agent + conditional adversarial verify, targeting the *two*
specific unexplored threads flagged as open by the first re-fire's report: (1) IIS-style static
export paths on `gadsdencountyfl.gov` / Wayback Machine, and (2) Municode's own API for
`clientId=5945`.

### Thread 2 (Municode API): closed negative, confirmed
`api.municode.com/Search?clientId=5945&query=zoning` returns `NumberOfHits:0` — Municode's own
search index has zero content for Gadsden County. `Products?clientId=5945` returns `204 No
Content`. Combined with the earlier chapter-tree walk (no Zoning/LDC chapter exists in Municode's
published index), this is now conclusively closed: Gadsden County is not meaningfully on Municode.

### Thread 1 (Wayback static exports): found real ordinance text
`gadsdencountyfl.gov` returns HTTP 403 (Akamai) on **every** path tested, including the domain
root and nonsense paths — a domain-wide block, not a targeted WAF rule. But the Wayback Machine
CDX API surfaced a real, fetchable document: **Gadsden County LDC Chapter 4 "Land Use Categories"
(rev. 11-15-16)**, an 18-page PDF containing real per-category density/FAR/lot-size/setback
figures for 13 land-use categories (USA, RR, AG-1/2/3, NC, COMM, LI, IND, CONS, REC, SILV, PUB,
HIS, MINING). This is genuinely new — no prior gadsden session (4+ before this one) found this
specific document. An independent adversarial-verify agent re-fetched the exact URL, re-extracted
the PDF text, and verbatim-confirmed every cited figure (SURVIVED).

### The missing link: spatial parcel-to-category assignment
Ordinance text alone doesn't move G/I — the pipeline needs to know *which category each specific
auction parcel is in*. Prior sessions found Gadsden's `Gadsden_FLUM` ArcGIS FeatureServer
(`services8.arcgis.com/.../Gadsden_FLUM/FeatureServer`) but dismissed it as "not zoning, no
density/FAR/parking numbers" — true on its own, but its 15 category-polygon layers (Ag1, Ag2,
Gads_RuralRes, Gads_Municipal, etc.) use the **exact same category names** as the newly-found LDC
Chapter 4 text (confirmed non-coincidental: Ch4 §4001 explicitly ties the chapter to the "Future
Land Use Map Series," and the ArcGIS service is literally named FLUM).

Ran a live point-in-polygon spatial query (all 15 category layers) against the centroid lat/lon of
all 21 parcel-linked gadsden auction rows. Result, independently re-verified for 3 sample points
across all 15 layers with zero cross-layer overlap:
- **8 parcels → "Municipal"** (inside Quincy/Chattahoochee/Havana city limits) — **left untouched**.
  No per-parcel municipal zoning source exists; assigning a municipal zone_code here without one
  would be fabrication. Confirmed dead end across 4+ prior sessions (qpublic 403 x2 methods, no
  Quincy_Zoning/Chattahoochee_Zoning FeatureServer).
- **10 parcels → Rural Residential (RR)**, **2 → Agriculture-2 (AG-2)**, **1 → Agriculture-1
  (AG-1)** — real, unincorporated-county categories matching the LDC Chapter 4 text exactly.

### What was written (migration `20260719_gold_standard_shard13_gadsden_uninc_rr_ag_verified.sql`)
- `jurisdictions`: "Unincorporated Gadsden County" (was missing).
- `zoning_districts`: RR / AG-1 / AG-2 under that jurisdiction, `far_regulated=false`,
  `pk1000_regulated=false`, `density_regulated=true` — **explicitly**, because the ordinance
  genuinely provides no FAR or parking-count regulation for these 3 rural/ag categories (only
  Neighborhood Commercial has FAR/parking, and no auction parcel falls in NC). This is the same
  applicability-flag pattern already established for brevard/duval residential districts, not a
  new exploit.
- `zone_standards`: `max_density_du_acre` = 1.0 (RR) / 0.2 (AG-1) / 0.1 (AG-2), verbatim from the
  ordinance. **`confidence_score = 0.85`, not 1.0** — logged honestly because the adversarial
  verifier found the ArcGIS layers are ~7 years stale (lastEditDate 2019-01-14) and evidence of a
  possibly-superseding 2023 LDC revision that is unreachable behind `gadsdencountyfl.gov`'s WAF.
  Could not confirm the density figures are unchanged in a newer revision — flagged as residual
  risk, not treated as disqualifying (the cited 2016 figures are still real and sourced).
- `parcel_zones`: 13 rows, one per unincorporated auction parcel, `zone_code` from the live spatial
  match, `source` field records both the ArcGIS layer edit date and the ordinance snapshot date.
- Two rows logged to `gold_standard_ultraloop_audit` (letters G and I) with the adversarial
  verifier's agent ID and evidence, `survived=true`.

This migration is a **distinct, better-sourced replacement** for the unrun `75e2b7af` migration's
zoning-districts content (that one used INFERRED "Chapter 5" district codes never matched to any
live ordinance text). Jurisdiction name is identical so no collision (`jurisdictions.name` is
UNIQUE); district codes are disjoint strings (RR/AG-1/AG-2 vs A-1/A-2/R-1/R-2/...) so no
`zoning_districts` collision if that migration is ever also run.

### E: unchanged, reconfirmed genuinely blocked
Not re-attempted this session — the first re-fire's report already confirmed via 2+ independent
methods (plain HTTP, real headless Chromium) that the clerk's own published record for
`25000901CA` lacks a parcel ID entirely (not a scraping gap), and `25000942CA` has fallen off the
active sale sheet with no accessible sold-case archive. Firecrawl re-checked this session: still 0
credits (`remaining_credits: 0`). No new avenue existed to retry.

### I: real progress, honestly still FAIL
`card_complete` moved from 0/23 to 13/23 (56.5%) — every one of the newly-zoned 13 unincorporated
parcels already had address/geo/value present in `multi_county_auctions`, so all 13 became
card-complete immediately. **This does not cross the 95% threshold and does not PASS.** It is
structurally capped at a maximum of 21/23 = 91.3% this session, because `card_complete`'s
denominator is all 23 auctions and only 21 have a `parcel_id` at all (E's unchanged gap). Even if
the 8 municipal parcels were somehow zoned too, I could not exceed 91.3% < 95% until E closes.
Reporting the real 56.5% rather than rounding up or implying a pass.

## Recommendation for the next gadsden session
- **G/I (municipal)**: the 8 Quincy/Chattahoochee/Havana parcels still need a per-parcel municipal
  zoning source. Confirmed dead ends: qpublic (Cloudflare 403 x2 methods), no
  Quincy_Zoning/Chattahoochee_Zoning ArcGIS FeatureServer. Untried: check whether Quincy or
  Chattahoochee city hall itself (not the county) publishes a GIS zoning layer under its own
  ArcGIS org, separate from the county's ARPC-hosted `Gadsden_FLUM` org.
- **E/I ceiling**: I cannot PASS until E does. Do not spend further session time trying to zone the
  8 municipal parcels for I's sake alone — it would still cap below 95%.
- **G confidence caveat**: if a future session gets past `gadsdencountyfl.gov`'s WAF (currently a
  domain-wide 403, not path-specific), check whether the 2023-06-23-timestamped LDC revision
  changes the RR/AG-1/AG-2 density figures; if unchanged, bump `confidence_score` to 1.0.

## Live evaluation JSON — BEFORE (session start, 2026-07-19)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100},"G":{"pass":false,"detail":"density= far= pk1000=","metric":null},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":28.5},"I":{"pass":false,"detail":"card_complete=0 of 23","metric":0},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

## Live evaluation JSON — AFTER (post-migration, same session)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":28.9},"I":{"pass":false,"detail":"card_complete=13 of 23","metric":56.5},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

## SQL VERIFICATION
```sql
-- Applied live via Supabase Management API SQL executor, 2026-07-19:
-- migrations/20260719_gold_standard_shard13_gadsden_uninc_rr_ag_verified.sql

SELECT id,name,county,co_no FROM jurisdictions WHERE name='Unincorporated Gadsden County';
-- {"id":1474,"name":"Unincorporated Gadsden County","county":"Gadsden","co_no":20}

SELECT d.code,d.name,s.max_density_du_acre,s.max_far,s.parking_per_1000sf,s.confidence_score
FROM zoning_districts d JOIN zone_standards s ON s.zoning_district_id=d.id
WHERE d.jurisdiction_id=1474;
-- RR    | Rural Residential | 1.00 | null | null | 0.85
-- AG-1  | Agriculture-1     | 0.20 | null | null | 0.85
-- AG-2  | Agriculture-2     | 0.10 | null | null | 0.85

SELECT count(*) FROM parcel_zones WHERE jurisdiction_id=1474;
-- 13

SELECT public.pencil_dod_evaluate_county('gadsden');
-- returns the "AFTER" JSON above, run live 2026-07-19.

SELECT county_slug, letter, survived FROM gold_standard_ultraloop_audit
WHERE dispatch_id='47974994-0d84-4a27-a865-6429cab3303d' AND county_slug='gadsden' ORDER BY id DESC LIMIT 2;
-- gadsden | I | true
-- gadsden | G | true
```

dispatch_id: 47974994-0d84-4a27-a865-6429cab3303d
