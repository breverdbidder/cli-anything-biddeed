# Gold Standard shard-4 (citrus, osceola) — dispatch d574fe69-df23-47c4-8c12-db32796f2235

Session: architect-20260725T000000, ~2h elapsed (ultracode-authorized: 8-agent research+verify workflow, 135 sub-agents, 1117 tool calls, then direct live-DB fix + verify + commit by the orchestrating session).

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| citrus I (177/191, 92.7%) | Fix enough of 14 gap rows to reach 95% | Fixed 2/14 (179/191, 93.7%) — still FAIL | 12 rows blocked by CAPTCHA/403/portal maintenance on every accessible Citrus foreclosure-case source; honestly left UNKNOWN |
| osceola G (density=78.7, far=0, pk1000=0) | Backfill FAR/parking/density for ~6 zone codes from ordinance text | 0 fixed — still FAIL | Municode + American Legal Publishing both 403 (Cloudflare) to automated fetch; firecrawl CLI not installed; Firecrawl API key out of credits (402); osceola.org/osceolaclerk.com static pages 403 (Akamai). No numbers found from an authoritative source — none written (guessed standards are BANNED) |
| osceola I (107/134, 79.9%) | Fix enough of 27 gap rows to reach 95% | Fixed 4/27 (111/134, 82.8%) — still FAIL | Remaining 18 need a per-case tax-deed-detail lookup (same method that worked for citrus); our MCA parcel_id for them is a non-unique section-level prefix shared by dozens of real parcels, so a GIS prefix-match would be a guess, not a fix — correctly left unresolved |
| (unplanned) citrus G | — | Caught and fixed a self-inflicted regression (95.6%→94.8%) before commit, ended at 96.4% (PASS, above original baseline) | Adding 2 new parcel_zones rows to a zero-standards district (RUR MH) would have dropped G below threshold; live re-verification caught it before push |

## Before/After (pencil_dod_evaluate_county, live)

**citrus — before:**
```json
{"A":{"pass":true,"metric":40},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":96.9},
"D":{"pass":true,"metric":98.4},"E":{"pass":true,"metric":96.9,"detail":"parcel_linked=185"},
"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":95.6,"detail":"density=95.6 far= pk1000="},
"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":92.7,"detail":"card_complete=177 of 191"},
"J":{"pass":true,"metric":99.5},"auctions_total":191}
```

**citrus — after:**
```json
{"A":{"pass":true,"metric":40},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":96.9},
"D":{"pass":true,"metric":98.4},"E":{"pass":true,"metric":97.4,"detail":"parcel_linked=186"},
"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":96.4,"detail":"density=96.4 far= pk1000="},
"H":{"pass":true,"metric":0},"I":{"pass":false,"metric":93.7,"detail":"card_complete=179 of 191"},
"J":{"pass":true,"metric":99.5},"auctions_total":191}
```
Still 9/10 (I failing). E improved as a side effect (185→186, the 2026-0134TD parcel_id was NULL before). G held at PASS (regression caught+fixed, ends above baseline).

**osceola — before:**
```json
{"A":{"pass":true,"metric":5},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},
"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},
"G":{"pass":false,"metric":0,"detail":"density=78.7 far=0.0 pk1000=0.0"},"H":{"pass":true,"metric":8.5},
"I":{"pass":false,"metric":79.9,"detail":"card_complete=107 of 134"},"J":{"pass":true,"metric":96.3},
"auctions_total":134}
```

**osceola — after:**
```json
{"A":{"pass":true,"metric":5},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},
"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},
"G":{"pass":false,"metric":0,"detail":"density=78.7 far=0.0 pk1000=0.0"},"H":{"pass":true,"metric":0.1},
"I":{"pass":false,"metric":82.8,"detail":"card_complete=111 of 134"},"J":{"pass":true,"metric":96.3},
"auctions_total":134}
```
Still 8/10 (G, I failing). I improved genuinely (+4 rows); G untouched (no fabricated values written).

## What shipped (live, main, migration `supabase/migrations/20260725_gold_standard_shard4_citrus_osceola_d574fe69_i_g_fixes.sql`)

**citrus I** (2 of 14 fixed, via Citrus Clerk TaxSmartWeb case-detail pages + Citrus County GIS ArcGIS spatial queries — maps.citrusbocc.com):
- `2026-0134TD`: real parcel identified (Cert 23-5450, PRCLKEY 79073). Confirmed genuinely landlocked (Citrus GIS address-points layer has zero features for this PRCLKEY while every neighbor has one) — cleaned the address field (was `"0 NO ACCESS, $6,223.00"`, a scraper artifact concatenating an unrelated dollar figure; real opening bid is $2,493.24 per the clerk record). Set `parcel_id`, inserted `parcel_zones` row (zone `RUR MH`, spatially confirmed).
- `2026-0147TD`: parcel_id/address were already correct; only the `parcel_zones` linkage was missing. Inserted it (zone `RUR MH`, confirmed via address-point-to-zoning-polygon spatial intersection, with a documented false-positive ruled out by geometry match).
- 12 remaining rows genuinely blocked: Citrus Clerk SCORSS case search is CAPTCHA-gated to anonymous/automated access; citrus.realforeclose.com (deprecated) and bid4assets.com/CitrusFLForeclosures both return HTTP 403 to automated fetch; citruspa.org was down for maintenance at time of research. No defendant/address/legal-description key could be obtained for these cases from any accessible source — left as UNKNOWN, not fabricated.

**citrus G regression catch** (same migration): the 2 new `parcel_zones` rows above link to district id 11957 (`RUR MH`), which had zero `zone_standards` on file. That pushed density from 95.6%→94.8% (FAIL) — caught by live re-verification before push. Fixed with a real, cited value: Citrus County's own official LDC PDF (Chapter Two §2402, "Rural Residential District (RUR)") — max density 1.0 unit/10 acres = 0.1 du/acre; FAR (0.2) is explicitly non-residential-uses-only per the same section, so `far_regulated` set false. Result: G at 96.4%, PASS, above the original baseline.

**osceola I** (4 of 27 fixed, via Osceola County GIS ArcGIS FeatureServer — gis.osceola.org/hosting/rest/services/Parcels/FeatureServer/3, discovered and field-mapped live this session):
- Parcel `262630061300` (cases `48482022` and `52562018`, two certificates against the same parcel): real address/lat/lng/value.
- Parcel `133234278000` (case `77492018`): vacant lot, address confirmed genuinely in Okeechobee ZIP (Osceola borders Okeechobee County — not an error).
- Parcel `19252900` (case `35192022`): vacant commercial lot, full address/geo/value.
- Prior "address" for all of these was a useless placeholder (`"Osceola County, FL 34741"`) — a scraper bug, not real data.

Two more cases (`2025 CA 002509 MF`, `2025 CA 001061 MF`) had their internal placeholder parcel IDs (`OSC-<hash>`) replaced with real parcel numbers + real address/geo/value via Osceola Clerk case search + County GIS cross-reference, but did **not** flip to card-complete because the real parcel isn't yet in `parcel_zones` — left honestly unresolved rather than defaulted.

## CRITICAL AUDIT FLAG (not fixed this session — flagging per ULTRALOOP mandate)

**405 of osceola's 504 `parcel_zones` rows (80.4%) carry `source='shard4_run5153_osceola_i_default:INCORP_or_nomatch'`, `zone_code='PD'`** — a blanket default assigned by a prior session (run5153) to every parcel it couldn't match, not a researched zoning determination. Verified this does **not** currently inflate the G pass rate: the `PD` district has `far_regulated=false`, `density_regulated=false` explicitly, and its category (`planned_development`) is excluded from the parking-applicability default — so all 405 ghost rows are excluded from all three G sub-metric denominators. It **does** mean ~80% of osceola's "zone-linked" status (feeding the I card-completeness check) rests on a placeholder rather than a real zone. Recommend: before trusting osceola I/G going forward, either (a) re-run a genuine zoning ingestion for Kissimmee/St Cloud/unincorporated Osceola to replace these defaults, or (b) explicitly exclude `source LIKE '%_default:%'` rows from the I zone-link join so I doesn't silently credit them. Not touched by this migration — informational only, logged to `gold_standard_ultraloop_audit`.

## Verification evidence

- `SELECT public.pencil_dod_evaluate_county('citrus')` / `('osceola')` run before and after every write (pasted above).
- 3 rows in `gold_standard_ultraloop_audit` (dispatch_id `d574fe69-df23-47c4-8c12-db32796f2235`, `ultraloop_mode='native'`): citrus/I, citrus/G, osceola/I — each `survived=true` with `refuter_evidence` jsonb citing the adversarially-verified source URLs from the research workflow, plus (for citrus G) this session's own live re-verification.
- Did not run `gold_standard_loop()` / `gold_standard_certify()` per PARALLEL-FLEET RULES (other shards mid-flight); per-county `pencil_dod_evaluate_county` used throughout.
- Rebased onto `origin/main` before every push (parallel shard commits from shard5/shard6/shard14/shard2 landed mid-session with zero conflicts).

## Honesty Protocol accounting

- 91 of 127 raw research findings were refuted or left UNKNOWN by the adversarial verify pass or by this session's own direct re-checks — **not applied**. This includes an entire zoning-standards research thread (Kissimmee RA-3/T3/T5-M/SRPUD, St Cloud R-3, Osceola E-1/CR/CT) that returned only zone *names*, never usable FAR/density/parking numbers, because every ordinance source tried (Municode, American Legal Publishing, Zoneomics-derived inference, osceola.org, osceolaclerk.com) was either bot-blocked or too derivative/inferential to trust as VERIFIED.
- 36 findings survived adversarial verification (2 were additionally re-confirmed directly by this session via independent ArcGIS re-query after the auto-refuter's verdict looked inconsistent with a sibling finding using the identical source).
- Zero fabricated zoning standards, zero fabricated addresses/coordinates. Every applied value traces to a source_url captured during research and spot-checked live before the migration was written.

## Next-session priorities

1. **osceola G** — needs an interactive/authenticated fetch path (firecrawl-browser with a real session, or manual courthouse/library lookup) since Municode/amlegal/osceola.org are all bot-blocked and the Firecrawl API key is out of credits (top-up needed, or use a different account). Target codes: Kissimmee RA-3/T3/T5-M/SRPUD, St Cloud R-3, Osceola County E-1, and CR/CT parking (only field missing for those two — everything else on those two districts already has real standards).
2. **osceola I remaining 18 parcels** — use the citrus-taxdeed method (case-specific tax-deed-detail page lookup, not GIS prefix-matching) via osceolaclerk.com/tax-deeds or officialrecords.osceolaclerk.org (form-based search, needs firecrawl-browser or similar for interactive submission — plain WebFetch got 403 on both).
3. **citrus I remaining 12 rows** — genuinely blocked pending Citrus Clerk SCORSS CAPTCHA solve or citruspa.org coming back from maintenance; retry citruspa.org first (transient).
4. **osceola ghost-PD audit** (flagged above) — decide whether to exclude `_default:` source rows from the I zone-link join, independent of new zoning research.
