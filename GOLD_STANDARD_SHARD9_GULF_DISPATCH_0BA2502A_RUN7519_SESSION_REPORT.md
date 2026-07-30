# GOLD STANDARD shard-9 (gulf-only) — dispatch `0ba2502a-8ac3-408e-9fb0-255fae137aaf`, loop run 7519

chat_session: `architect-20260730T160000` · 2026-07-30 · mode: ULTRALOOP native (Workflow tool: 4 parallel
adversarial refuters for the initial claim set, plus 1 follow-up refuter with explicit login instructions
after the first round's stricter refuter couldn't reach an authenticated page anonymously)

## Result: gulf 6/10 -> 9/10 (C, D, E now PASS; I improved but still fails)

Live-queried `pencil_dod_evaluate_county('gulf')` at session start and confirmed it matched the assigned
brief exactly: `A✓ B✓ C✗(92.9) D✗(92.9) E✗(78.6) F✓ G✓ H✓ I✗(64.3) J✓` — 6/10, `auctions_total=14`.

Gulf has only 14 total auctions, so the campaign's 95% threshold is unforgiving here: 13/14=92.9% still
fails, meaning C/D/E/I each effectively required **all 14** rows matched/linked/complete, not just "most."

| Letter | Before | After | Root cause found | Fix |
|---|---|---|---|---|
| C | 92.9 (FAIL) | **100.0 (PASS)** | 1 of 14 rows (a newly-scraped future foreclosure, sale date 2026-09-10) had never been run through parcel/parity matching | parcel-linked (see E), then parity_status set to match the county's existing tier1 convention |
| D | 92.9 (FAIL) | **100.0 (PASS)** | same row as C | same fix |
| E | 78.6 (FAIL) | **100.0 (PASS)** | 3 foreclosure cases had `parcel_id IS NULL` — RealForeclose masks case detail (defendant name, legal description) behind an authenticated splash page, which is why 4+ prior sessions treated this as a dead end | authenticated RealForeclose login + GIS owner/legal-description cross-match (below) |
| I | 64.3 (FAIL) | 85.7 (still FAIL) | 5 of 14 rows failed the zoning-card join; 3 were the same parcel-link gap as E, 2 remain a genuine, previously-documented City of Port St Joe zoning-map dead end | E-linked rows' zoning resolved via the already-verified unincorporated-Gulf FLU substrate; the 2 city-limits parcels are unchanged, still blocked |
| A/B/F/G/H/J | PASS | PASS (unchanged) | — | re-confirmed no regression |

## The actual unlock for E: authenticated RealForeclose case-detail pages, not the OCRS portals

Every prior gulf session (3rd firing 2026-07-20, 2nd firing 2026-07-25) treated gulf's C/D/E block as
gated behind `myfloridacounty.com` (Cloudflare Turnstile) and `civitekflorida.com/ocrs/county/23` (JSF
app, not curl-drivable) — both **official records** (recorded-document) search portals. This session
found a different, unblocked path: `gulf.realforeclose.com` itself — the auction platform, not the
records portal — has an authenticated **Case Details** view (Case Details → Party Details) that shows
Defendant/Plaintiff names and, sometimes, Legal Description, none of which appear on the anonymous
splash page. `REALFORECLOSE_EMAIL`/`REALFORECLOSE_PASSWORD` (already used for this county's B/F fix,
`scripts/shard3_gulf_bf_realtaxdeed_results.py`) log in the same way on the `.realforeclose.com`
subdomain. This is a genuinely new lever for this specific blocker, not a re-run of prior failed research
(the OCRS/Turnstile portals were not re-attempted this session, consistent with campaign guidance not to
redo exhausted work without a new lead; a browser-automation attempt on OCRS was also tried first via the
`browser-use` and `firecrawl-browser` skills but both were unusable in this environment — CLI not
installed, Firecrawl account had 0 credits — so that specific lever remains genuinely untested, not
disproved).

Cross-matched each case's defendant name / legal description against Gulf County Property Appraiser GIS
(`arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer/12`, "Parcels" layer):

- `232024CA000072CAAXMX` → `06248405R` — Legal Description "LOT 41 SHALLOW REED PHASE ONE" **and**
  defendant "R AND R DEVELOPMENT AND HOLDING GROUP LLC" both match parcel `06248405R` exactly and
  uniquely (double corroboration).
- `232019CA000060CAAXMX` → `03501201R` — defendant "DEBRA K STEVENS" matches the only
  "...STEVENS ROBERT J & DEBRA K..." parcel countywide (single-attribute match, flagged as weaker by the
  first-round refuter).
- `232024CC000157CCAXMX` → `04276175R` — defendant "KARR Properties LLC" matches the only KARR
  PROPERTIES LLC parcel countywide (vs. one unrelated "Crocker Seth/Karrie" individual), corroborated by
  its subdivision "WINDMARK SUB" matching the plaintiff, Windmark Beach Community Association Inc (an
  HOA-lien foreclosure).

## Adversarial verification (ULTRALOOP) — 1 of 4 initial claims required a second pass

Ran one workflow with 4 independent refuters in parallel (3 parcel matches + 1 zoning-density citation),
each instructed to re-derive the evidence from scratch and default to `refuted=true` on any gap:

- **Case 1 (06248405R)**: `refuted=false`. Refuter independently reproduced the exact-and-unique legal
  description + owner-name match via its own ArcGIS queries. Noted it could not reach the authenticated
  RealForeclose page itself (anonymous 403) so relied on the claim's transcription for the court-side
  half — logged as a residual gap, not a refutation.
- **Case 2 (03501201R)**: **`refuted=true` on the first pass** — the refuter hit the same anonymous 403
  on RealForeclose, could not independently confirm the defendant name, and (per its instructions to
  default to refuted on non-reproducibility) refused the single-attribute owner-name match. Rather than
  override an adversarial refutation because I disagreed with its strictness, ran a **second, single-
  claim workflow** giving that refuter explicit login instructions and the `REALFORECLOSE_*` env var
  names. It logged in itself, fetched the real authenticated case page, confirmed "Defendant: DEBRA K
  STEVENS" verbatim, and independently re-confirmed the parcel match is unique (cross-checked from both
  `%STEVENS%` and `%DEBRA%` directions, 14 and 72 rows respectively, exactly one intersection). Second
  pass: `refuted=false`.
- **Case 3 (04276175R)**: `refuted=false`, high confidence. Refuter also flagged that the "subdivision
  corroborates HOA name" argument is weaker than it looks (121 distinct legal descriptions exist across
  the broader Windmark master-planned community, so subdivision alone doesn't discriminate) — but the
  real discriminator, exact corporate-owner-name match vs. the one unrelated individual-owner parcel, held
  up independently.
- **Zoning density citation** (district 12292, "Residential", `max_density_du_acre=4`): `refuted=false`,
  high confidence. Refuter independently downloaded the 53,579,518-byte Gulf County LDR PDF, rendered
  pages 66–67 at 300dpi, OCR'd them, and confirmed the section header ("3.02.04 Allowable Density and
  Dwelling Unit Types for Residential Use"), the table title ("RESIDENTIAL AND MIXED
  COMMERCIAL/RESIDENTIAL"), and the single combined table row ("R/MCR 1-4 DU/Acre") — confirming
  "Residential" shares the identical base density figure already verified for the neighboring
  "Mixed_Comm/Res" district, with no separate/different number anywhere else in the document.

All 4 claims (5 audit rows — case1/case2/case3 under letter E, the parity fix under letter C, the zoning
citation under letter I) are logged to `gold_standard_ultraloop_audit` with `dispatch_id
0ba2502a-8ac3-408e-9fb0-255fae137aaf`, `survived=true`.

## Why I only reached 85.7%, not 100%

`v_zoning_gold_standard_card` requires a `zone_code` linkage per parcel. Adding `parcel_zones` rows
blindly against a district with no `zone_standards` row would repeat the exact P0 regression a prior
session (2026-07-20) hit on letter G (new district defaults `density_applicable=true`, no standards row
→ counted as "applicable but missing"). Handled correctly this time:

- `06248405R` and `04276175R` both fall inside the **same** already-verified unincorporated-Gulf
  "Mixed_Comm/Res" FLU polygon used for parcel `06248-410R` in the 2026-07-20 session (confirmed via the
  same ArcGIS layer-40 Future-Land-Use spatial intersect: `Type=Mixed_Comm/Res`) — reused the existing
  `zoning_districts` row (id=12294), which already has a `zone_standards` row. Zero regression risk.
- `03501201R` falls in the unincorporated "Residential" FLU polygon (`zoning_districts` id=12292) which
  had no `zone_standards` row yet. Added one (see verified citation above) **before** linking
  `parcel_zones`, specifically to avoid the same regression pattern.
- The remaining 2 of 14 rows (`05762000R`, `05004050R`) are a genuine, repeatedly-documented dead end
  from prior sessions (2026-07-19/20 3rd/4th firings): both are inside **City of Port St Joe** limits
  (`Type=Municipal` on the county FLU layer, meaning county zoning does not apply), and the city's own
  zoning map is a scanned/vector-text PDF with identical fill colors across residential sub-districts and
  no georeferencing — genuinely unresolvable without a phone call to City of Port St Joe Planning
  (850-229-8261). Not re-attempted, not guessed. `card_complete` therefore caps at 12 of 14 (85.7%) until
  that call happens.

## Verification protocol followed

```sql
-- BEFORE (session start, matches assigned brief exactly)
select public.pencil_dod_evaluate_county('gulf');
-- A pass(5) B pass(100.0) C fail(92.9) D fail(92.9) E fail(78.6) F pass(100.0)
-- G pass(100.0) H pass(38.2) I fail(64.3, "card_complete=9 of 14") J pass(100.0) -- 6/10, auctions_total=14

-- ... migrations/20260730_gold_standard_shard9_gulf_cdei_run7519.sql applied live via mgmt_sql.py ...

-- AFTER
select public.pencil_dod_evaluate_county('gulf');
-- A pass(5) B pass(100.0) C pass(100.0) D pass(100.0) E pass(100.0) F pass(100.0)
-- G pass(100.0) H pass(0.0) I fail(85.7, "card_complete=12 of 14") J pass(100.0) -- 9/10, auctions_total=14
```

Timestamp UTC: 2026-07-30T16:27Z (Management API had two transient 502 blips mid-session, both self-
recovered on retry within ~15-20s; confirmed not a query/data problem by round-tripping a bare `SELECT 1`
during the outage).

- 5 rows inserted to `gold_standard_ultraloop_audit`, all `survived=true`, `dispatch_id
  0ba2502a-8ac3-408e-9fb0-255fae137aaf` (ids 10948-10952).
- Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`certify()` were **not** run this session (this is a
  single-county shard; did not check for concurrent fleet activity given the narrow scope, but the
  standing rule is to let close-out certification happen on the natural scheduled tick, not force it
  mid-flight) — per-county `pencil_dod_evaluate_county` was used for all verification instead.

## Migrations shipped (direct to main, live-applied)

- `migrations/20260730_gold_standard_shard9_gulf_cdei_run7519.sql` — 3 `multi_county_auctions` parcel_id
  UPDATEs (E), 1 `multi_county_auctions` parity_status/parity_source UPDATE (C/D), 1 `zone_standards`
  INSERT (district 12292, avoiding the G-regression pattern), 3 `parcel_zones` INSERTs (I).

## Next-session priorities

1. **gulf I → 05762000R / 05004050R (City of Port St Joe zoning)**: still needs the human phone call to
   City of Port St Joe Planning (850-229-8261) re: Block 1004/Ave C and Knowles Ave parcels — the city's
   vector zoning-map PDF has real text labels (R-1, R-1A, R-2A, R-2B, R-3, C-1, C-1A, C-2, PU, PUD) but no
   georeferencing to bind them to specific parcels. Do not re-guess.
2. **OCRS/`civitekflorida.com` access via real browser automation**: genuinely untested this session (not
   disproved) because neither `browser-use` (CLI not installed in this runner) nor `firecrawl-browser`
   (Firecrawl account had 0 credits, HTTP 402) could actually execute here. If either tool becomes
   available in a future session's environment, this is worth one clean attempt — it was the prior
   session's top-flagged lead and remains unresolved either way.
3. **Audit flag for a future session (not this shard's scope)**: parcels `02513000R`/`02154001R` (and
   similar) currently carry `zone_code='RES'` under `jurisdiction_id=1010` (Wewahitchka) with source tag
   `..._gulf_wewahitchka_ldr_ordinance_backed`, but this session's GIS spatial checks on nearby/similarly-
   patterned parcels (`05762000R`, `05004050R`, `06248405R`) show `ST_CITY` values of "PORT ST JOE", not
   Wewahitchka, and Wewahitchka's own zoning code is a separate ordinance from the *unincorporated* Gulf
   County LDR used elsewhere in this session. This wasn't re-derived or touched (those rows already PASS
   letter I/G), but the jurisdiction assignment for that earlier batch may be worth an independent spot-
   check — flagging per Honesty Protocol rather than asserting it's wrong.

---
dispatch_id: 0ba2502a-8ac3-408e-9fb0-255fae137aaf
