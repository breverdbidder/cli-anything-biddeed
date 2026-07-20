# Gold Standard shard-11: gadsden — dispatch 52bf028c, item `gadsden_I_municipal_zoning` re-fire

## Result: I unchanged, FAIL 56.5% (13/23) — genuinely new angles tried, all confirmed still blocked, no fabrication, no regression

| Letter | Before | After | Notes |
|---|---|---|---|
| I | FAIL 56.5 (13/23) | FAIL 56.5 (13/23) | Unchanged — new research this session, no metric change |
| (all others) | unchanged | unchanged | This item scoped to I only; not touched |

**This is a re-fire of an item a sibling worktree session (commit `5b029a0d`, same dispatch
`52bf028c`) already worked ~2 hours earlier in wall-clock terms.** That session independently
found the same Quincy-WA-not-Quincy-FL naming collision, checked Wayback (found only an
image-only-scan 2012 zoning map PDF), and reconfirmed Firecrawl at 0 credits — logging `I` as
`survived=true` with zero writes. This session ran the same class of new-angle research
independently (own live queries, not read from that report until after most of the research was
done) and additionally found one thing not documented in either the `5b029a0d` or the
`GOLD_STANDARD_SHARD13...2ND_REFIRE` report: **a genuinely new ordinance source
(`chattahoochee.elaws.us`) that turns out to already be loaded into `zoning_districts`/
`zone_standards` by an even earlier (2026-07-18) session** — but with the per-parcel spatial
assignment link (`parcel_zones`) still completely empty for both Quincy and Chattahoochee. This
report documents that state precisely and does not re-claim credit for work already logged by the
`5b029a0d` session.

## What was tried this session (new angles per item instructions)

### Angle 1: City of Quincy's own ArcGIS org (item instruction #1)
Live search surfaced `cityofquincy.maps.arcgis.com`, owner `quincyadmin` — a real, separate-from-
county ArcGIS organization with a live "Zoning" FeatureServer
(`services3.arcgis.com/jl3zLujxj5OMMkmC/.../Planning_View/FeatureServer/2`, fields `ZoneCode`/
`ZoneDescription`, `isView:true`, recently edited per `editingInfo.lastEditDate`). Point-in-polygon
queried this layer (and its companion "City Limits" layer, `FeatureServer/0`) against the lat/lon
of all 4 Quincy-addressed unzoned auction parcels (208 S. Love St, 226 Carver St, 2320 Pavillion
Dr, 614 Williams St) — **all four returned zero features**, including against the "City Limits"
layer at a guessed-downtown coordinate. Pulled the raw geometry of the 3 "City Limits" features
directly (`outSR=4326`) to check: their bounding boxes resolve to **lon ≈ -119.83 to -119.90, lat ≈
47.21 to 47.26** — Grant County, **Washington state**, not Gadsden County, Florida. Sample Zoning
features returned `ZoneCode: G-I "City Industrial"` / `L-I "City Light Industrial"` at the same WA
coordinates. **CONFIRMED via live geometry: this is Quincy, WA, a name collision, not usable.**
(A sibling session, `5b029a0d`, independently found this same collision via a different check —
this session's contribution is confirming it directly from the layer's own returned geometry
rather than inference.)

### Angle 2: Wayback Machine CDX for Quincy/Chattahoochee zoning pages (item instruction #2)
- `myquincy.net` CDX (301 captures) surfaced a `building-planning/pages/maps` nav link inside a
  2023 capture of the Building & Planning page — but that specific sub-URL has **zero of its own
  Wayback captures** (`matchType=prefix` query returned `[]`), a genuine dead end, not a fetch
  failure.
- `chattgov.org` / `chattahoocheefl.gov` CDX (201 captures) surfaced no zoning map, zoning
  ordinance PDF, or GIS page ever crawled — only a 2017 "comprehensive plan" public-notice post and
  a 2019 Planning & Zoning Commission vacancy notice, neither containing usable district/parcel
  data.
- Live `chattgov.org` homepage nav (HTTP 200, works with a browser UA) has no
  zoning/planning/GIS link at all in its menu; its `document_center.php` (HTTP 200) contains only
  financial/administrative PDFs (audits, budgets, employment forms) — no zoning map or LDC PDF.
- **Genuinely new find, not previously logged by any session:** a live search surfaced
  `chattahoochee.elaws.us/code/chii` — Chattahoochee's Land Development Regulations Chapter II
  (Land Use Districts), hosted on **eLaws**, a codification vendor entirely distinct from
  Municode (whose `api.municode.com` search already conclusively returns `NumberOfHits:0` for
  both Gadsden County and, this session, for "Chattahoochee Florida zoning" too). Fetched live
  (HTTP 200, "Last Updated: August 25, 2014"): real ordinance text for districts R-1, R-1MH, R-2,
  R-3, B-1, I-C, I with real density (4/6/10 du/acre), lot-coverage (40/60/80%), and FAR (1.0 CBD /
  0.75 elsewhere / 0.75 industrial) figures.
- Cross-checking this against the live DB found this exact source (`source_url =
  http://chattahoochee.elaws.us/code/chii`) **already loaded** into `zoning_districts` /
  `zone_standards` for `jurisdiction_id=1003` (Chattahoochee) by a **2026-07-18** session (commit
  history shows `75e2b7af feat(gadsden): G+I fix scripts...` and earlier), predating both the
  `52bf028c` dispatch's own `5b029a0d` report and the `47974994` shard-13 reports — none of which
  mention this eLaws source by name. Quincy (`jurisdiction_id=925`) similarly already has R-1/R-2/
  R-3/C-1/C-2/M-1 districts loaded from `zoneomics.com/code/quincy-FL/chapter_3` (confidence
  0.60-0.65, itself citing a 403'd Municode mirror as the underlying primary source).
- **The missing link, confirmed still open:** `SELECT count(*) FROM parcel_zones WHERE
  jurisdiction_id IN (925,1003,1005)` returns **0**. Ordinance district text exists for both
  cities, but there is still no per-parcel spatial assignment (no ArcGIS zoning FeatureServer for
  either city — confirmed dead, see Angle 1 and prior sessions — and no address-to-zone lookup
  tool). Each of our 8 unzoned parcels has `fl_parcels.dor_uc = '001'` (single-family-residential
  *land use* code) — but DOR_UC is a use code, not a zoning district code, and Chattahoochee alone
  has 4 different residential-adjacent districts (R-1, R-1MH, R-2, R-3) any of which could
  legitimately apply to a `dor_uc=001` parcel. Assigning one without a real spatial or
  authoritative address match would be an unverifiable guess — explicitly the fabrication pattern
  this item's instructions prohibit. **No parcel_zones write was made.**

### Angle 3: Firecrawl MCP re-check (item instruction #3)
`GET https://api.firecrawl.dev/v1/team/credit-usage` → `remaining_credits: 0` (same as every prior
session this dispatch and shard). No change, no MCP firecrawl tool was surfaced via ToolSearch
either — confirmed still unusable this session.

### Additional angles tried, not in the item's numbered list, ruled out
- `gadsdenpa.com` (an alternate Gadsden County Property Appraiser domain distinct from
  `qpublic.net`, surfaced via live search) — HTTP 403, Cloudflare cookie-challenge page, same WAF
  infrastructure class as the confirmed-dead qpublic domains. Not usable.
- `gadsdencountypropertyappraiser.org` — resolves (HTTP 200) but is an unofficial WordPress/
  GeneratePress SEO content-marketing site (`datePublished: 2025-10-06`), not the county's real
  appraiser site; its "GIS Maps" page contains no data endpoints, only marketing copy and schema.org
  JSON-LD. Not usable.
- Municode's own unscoped search API, run this session for `"Chattahoochee Florida zoning"` →
  `NumberOfHits: 0`, confirming (independently of the county-level check already closed by a prior
  session) that Chattahoochee itself is also not meaningfully indexed on Municode.

## Why I cannot PASS regardless (unchanged structural ceiling, re-confirmed)
`card_complete`'s denominator is all 23 gadsden auctions; only 21 have a `parcel_id` at all (E's
unchanged gap, out of this item's scope — 2 rows: `25000901CA` PLSS-only legal description,
`25000942CA` possible chattel/manufactured-home case). Even a full win on all 8 municipal parcels
this session would cap I at 21/23 = 91.3%, still below the 95% PASS threshold. This was true before
this session and remains true after.

## Honesty notes
- This item was already worked by a sibling worktree session (`5b029a0d`) for this exact
  dispatch a short time before this session started; this report documents this session's own
  independent research (some overlapping conclusions, reached independently; one genuinely new
  finding — the eLaws source and its cross-reference to already-loaded-but-unlinked DB data — not
  present in that report).
- Zero writes were made to `zoning_districts`, `zone_standards`, or `parcel_zones` this session.
  Three rows were written to `gold_standard_ultraloop_audit` (ids 8063-8065) documenting the
  angles tried and their outcomes, all `survived=true` (i.e., the "still blocked" claim is honest
  and was not refuted by re-checking my own evidence).
- No zone_code was guessed or fabricated for any of the 8 municipal parcels despite having a
  plausible-looking `dor_uc='001'` shortcut available — explicitly declined per the item's
  fabrication-prohibition rule, since DOR_UC (land use) does not equal zoning district and
  Chattahoochee alone has 4 residential-adjacent district codes it could resolve to.

## Recommendation for the next gadsden session
- Do not re-search ArcGIS Online, qpublic-family domains, or Municode for Quincy/Chattahoochee
  zoning — now confirmed dead across 6+ sessions via multiple independent methods.
- The only remaining untried path for I: a manual public-records request to Quincy's or
  Chattahoochee's building/planning department for a current georeferenced zoning shapefile or an
  address-to-zone lookup — genuinely out of reach for an automated session (no such self-service
  tool exists on either city's live site).
- If E ever closes (see the `5b029a0d` report's E recommendations: ASP.NET WebForms postback
  simulation for `25000901CA`, CourtScribe docket lookup for `25000942CA`), I's ceiling rises to
  95.7% (22/23) or higher — worth re-running the I item at that point since the ordinance data for
  Chattahoochee (at least) is now real and already loaded, only the spatial link is missing.

## Live evaluation JSON — BEFORE (this session, 2026-07-20)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.0},"I":{"pass":false,"detail":"card_complete=13 of 23","metric":56.5},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

## Live evaluation JSON — AFTER (this session, post-research)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.2},"I":{"pass":false,"detail":"card_complete=13 of 23","metric":56.5},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```
(H's 0.0→0.2 metric drift is wall-clock elapsed time only — no write made to any `multi_county_auctions` row this session; H is out of this item's scope.)

## SQL VERIFICATION
```sql
-- Run live via curl + browser User-Agent against the Supabase Management API, 2026-07-20 23:1x UTC:

SELECT public.pencil_dod_evaluate_county('gadsden');
-- returns the "AFTER" JSON above -- I unchanged FAIL 56.5, no regressions anywhere.

SELECT jurisdiction_id, count(*) FROM parcel_zones WHERE jurisdiction_id IN (925,1003,1005) GROUP BY jurisdiction_id;
-- (empty result set) -- confirms zero per-parcel municipal zoning assignments exist, the still-open gap.

SELECT jd.jurisdiction_id, jd.code, zs.source_url, zs.confidence_score
FROM zoning_districts jd JOIN zone_standards zs ON zs.zoning_district_id=jd.id
WHERE jd.jurisdiction_id IN (925,1003) AND jd.code IN ('R-1','R-1MH','R-2','R-3','C-1','C-2','M-1','I');
-- 11 rows -- real, sourced ordinance-level district data already exists (loaded 2026-07-18,
-- confidence 0.60-0.95), but with no parcel-level link.

SELECT id, dispatch_id, county_slug, letter, survived FROM gold_standard_ultraloop_audit
WHERE dispatch_id='52bf028c-78fe-49ad-ae77-284c02a1f201' AND county_slug='gadsden' AND id >= 8063
ORDER BY id;
-- 8063 | I | true  (Quincy WA collision, confirmed via live geometry)
-- 8064 | I | true  (eLaws Chattahoochee source found + cross-referenced to already-loaded-but-unlinked DB rows)
-- 8065 | I | true  (gadsdenpa.com / gadsdencountypropertyappraiser.org / Firecrawl all confirmed not usable)
```

dispatch_id: 52bf028c-78fe-49ad-ae77-284c02a1f201
item_key: gadsden_I_municipal_zoning
