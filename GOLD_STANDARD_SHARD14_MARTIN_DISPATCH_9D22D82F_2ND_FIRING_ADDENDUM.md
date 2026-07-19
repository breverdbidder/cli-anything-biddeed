# Gold Standard shard-14 — martin — 2nd firing addendum

dispatch_id `9d22d82f-cbfe-4f01-a459-b5259d8d08df` (same dispatch as the original session,
see `GOLD_STANDARD_SHARD14_MARTIN_DISPATCH_9D22D82F_SESSION_REPORT.md`), re-fired chat_session
`architect-20260719T160000`. Confirmed a duplicate dispatch immediately at session start: live
`pencil_dod_evaluate_county('martin')` matched the prior session's "after" state exactly
(J=100.0, I=78.4 (29/37), E=91.9 (34/37), 37 total auctions, same 3 NULL-parcel-id rows) —
the dispatch brief's stated "before" numbers (I=70.3, J=89.2) were stale, predating the first
firing. Rather than redo identical work, this session pursued the first firing's own
documented "next-session priorities."

## Scoreboard (live-verified before → after)

| Letter | Before (this firing) | After (this firing) | Note |
|---|---|---|---|
| A | PASS 1 | PASS 1 | unchanged |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | PASS 97.3 | PASS 97.3 | unchanged |
| D | PASS 97.3 | PASS 97.3 | unchanged |
| E | FAIL 91.9 (34/37) | FAIL 91.9 (34/37) | unchanged — re-confirmed structurally blocked via new angles |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | PASS 100.0 | PASS 100.0 | unchanged net — self-caught and fixed a real transient regression mid-session (see below) |
| H | PASS ~7 | PASS ~7.6 | unchanged (freshness) |
| I | FAIL 78.4 (29/37) | **FAIL 91.9 (34/37)** | real progress, not yet passing — capped by E's same 3 blocked rows |
| J | PASS 100.0 | PASS 100.0 | unchanged (already fixed in 1st firing) |

**8/10 → 8/10** (no letter crossed its threshold this firing), but I closed nearly its entire
remaining zoning-linkage gap: 29→34 of 37 (+5 rows), leaving only the 3 rows structurally
shared with E's blocker.

## G fragility (flagged by 1st firing, not urgent) — closed

The 1st firing flagged `zoning_districts` id 7519 (R-1A, City of Stuart) as latently fragile:
`density_regulated`/`far_regulated` both `NULL`, passing only because `zone_standards` happened
to carry a real value. Compared it against its sibling district id 7520 (R-1, same
jurisdiction, same category/subtype) which already has explicit `density_regulated=true` — the
view's computed applicability (`v_zoning_district_applicability`) was independently confirmed
identical for both districts before and after, so setting id 7519's flags explicitly
(`density_regulated=true`, `far_regulated=false`, `pk1000_regulated=false`, matching its own
real `zone_standards` values: `max_density_du_acre=7.0`, no stated FAR/parking mechanism) was a
zero-behavior-change hygiene fix, re-verified against the live evaluator (G stayed 100.0).

## I: 78.4% → 91.9% (29/37 → 34/37) via real ordinance text + independent GIS re-verification

**New avenue found: a real headless-browser render succeeds where static WebFetch failed.**
Both the 1st firing and an initial `Workflow` research fan-out this firing hit the documented
municode.com 403 (WebFetch, a static fetcher, can't execute the Angular SPA's JS) and
elaws.us 503. Directly testing with Playwright (already present in this sandbox —
`/usr/bin/chromium` + the `playwright` Python package, contrary to the research subagent's
claim that "browser-use is not installed") against
`https://library.municode.com/fl/martin_county/codes/land_development_regulations_?nodeId=LADERE_ART3ZODI_DIV7CACZODIST`
with a standard browser user-agent returned **HTTP 200 with the full rendered Division 7 body
text** (115KB) — no login wall, no OAuth needed for this public ordinance content. This is a
genuinely new, reproducible access path for future sessions blocked by Municode 403s.

**Real primary-source values recovered for the 3 residual Category "C" codes:**
- **HR-2** (Sec. 3.404.C.3, quoted verbatim): *"A maximum density of 15 apartment units may be
  permitted per gross acre depending on available community services and capital
  improvements."* → `max_density_du_acre=15.0`, `density_regulated=true`. No floor-area-ratio
  concept appears anywhere in Division 7 (height + lot-coverage-% + setbacks are used instead)
  → `far_regulated=false`.
- **B-1** (Sec. 3.417): pure lot-area/height/setback business-district text, no density or FAR
  provision at all → `density_regulated=false`, `far_regulated=false`. Commercial category
  triggered `pk1000_applicable=true` by the view's own category-default logic — caught via a
  full applicability re-check immediately after insert (see regression below) and closed with
  an explicit `pk1000_regulated=false`, backed by the same primary text (no parking-ratio
  clause anywhere in Sec. 3.417).
- **R-2A** (Sec. 3.405.1.B): regulated via minimum lot area (7,500 sq ft) + max 2 units per lot,
  not a stated per-acre density figure. Followed the fleet's own established convention for
  this exact situation — every other lot-area-regulated residential Category C sibling already
  in the DB (R-2, R-1A, RE-1/2A, PUD-R, PUD, PUD-WJ, R-2B — 7 of 7 checked) is explicitly
  `density_regulated=false` rather than a derived guess. Did **not** back-calculate a du/acre
  figure from the lot-area rule (2 units ÷ 7,500 sq ft ≈ 11.6 du/acre) — that would be an
  INFERRED derivation, not a directly-stated ordinance value, and the explicit-false convention
  the fleet already uses for identical siblings is the safer, precedented choice.

**Independent GIS re-verification (not just trusted from the 1st firing's prose — that
session's zone-code findings for these exact 4 parcels were never persisted to
`parcel_zones`/`zoning_assignments`, only documented in the session report text).** Found a
different, fresh ArcGIS endpoint via web search — Martin County's own open-data-portal-indexed
`https://geoweb.martin.fl.us/arcgis/rest/services/Administrative_Areas/Administrative_Areas/MapServer/8`
("Zoning" layer) — geocoded all 4 parcel addresses via Esri's public geocoder to
rooftop-accurate coordinates (100% match score on all 4, including the two "Jupiter, FL"
mailing-address condo units the 1st firing separately confirmed are genuine Martin County
parcels), and ran point-in-polygon queries. **All 4 independently reproduced the 1st firing's
GIS findings exactly**: R-2A (32 SE Taho Ter), B-1 (2700 NW Federal Hwy — layer even carries a
`ZONING_DETAILS` field citing "Resolution 86-10.11 or 86-12.13", an extra provenance signal not
previously captured), HR-2 ×2 (9159 & 9240 SE Riverfront Ter).

**Self-caught regression during this fix (worth flagging explicitly per Honesty Protocol):**
inserting the B-1 `zoning_districts` row initially left `pk1000_regulated` unset. The view's
category-default logic classified B-1 as `subtype=commercial_industrial`, which defaults
`pk1000_applicable=true` — immediately dropping live G from PASS 100.0 to **FAIL 0.0**
(`density=100.0 far= pk1000=0.0`). Caught by re-querying the live evaluator immediately after
every write (not just at session end), root-caused via `v_zoning_district_applicability`, and
fixed within the same session by setting the explicit flag backed by real ordinance evidence —
re-verified G back to PASS 100.0 before moving on. This is exactly the failure class the 1st
firing (and the 2026-07-18 session before it) warned about; the fix here is real primary-source
evidence, not a value chosen to force a pass.

**Note on an earlier flawed self-check:** a broad sweep of all 78 Martin-jurisdiction
`zoning_districts` rows against `zone_standards` (run to double-check for other latent gaps)
initially showed 68 "gap" rows including HR-2, RS-6, and SR — which directly contradicted the
live evaluator's G=PASS 100.0. Root-caused: the sweep's `zone_standards` fetch silently hit
PostgREST's 1000-row default page limit and truncated before reaching the relevant rows — a
tooling artifact, not a real finding. Flagging this rather than silently discarding it: the
live `pencil_dod_evaluate_county` call is the only trustworthy source of truth for this
letter, not ad hoc sweeps against partially-paginated REST results.

**Residual gap (3 of 37, unchanged): the same 3 NULL-`parcel_id` rows blocking E.** Structurally
unreachable for I too, exactly as the 1st firing predicted — resolves automatically if/when E's
blocker clears.

## E: re-confirmed unchanged (91.9%, 34/37) — genuinely blocked, new angles tried and exhausted

Same 3 case numbers as every prior session (`23001555CCAXMX`, `25001632CCAXMX`,
`25001634CCAXMX`). A `Workflow` research agent tried 5 angles beyond the already-documented
CAPTCHA-gated `court.martinclerk.com` case search:
1. **Landmark Web** (`or.martinclerk.com/landmarkweb/`) — a genuinely different official-records
   search system, but gated by a login/session wall ("Session has Expired... log in again").
2. **RealForeclose** (`martin.realforeclose.com`, the county's own auction/sale portal, which
   per the Clerk's site lists case number + legal description for pending sales) — HTTP 403,
   bot-blocked (a different mechanism than CAPTCHA, same practical effect).
3. **KBForeclosures.com**, a public foreclosure aggregator distinct from PropertyOnion (canon
   permits non-PropertyOnion aggregators for cross-reference only, never as `data_source`) —
   1,787 Martin County records, checked all 3 case numbers in dashed/undashed formats, zero
   matches.
4. **Exact-string web search** for all 3 case numbers — zero indexed results anywhere (no
   newspaper legal notice, no aggregator, no court tracker has these surfaced).
5. **UniCourt** — no public case-detail page reachable; a direct guessed-URL fetch returned
   HTTP 405 (requires their authenticated app layer).

No new avenue succeeded. This reinforces, via genuinely new probes rather than re-checking the
same already-documented blocker, that E remains structurally blocked pending the 1st firing's
identified manual channel (`RecordRequest@martinclerk.com`, $1/page) — out of scope for
automated sessions.

## Honesty markers

- All B/C/D/E/G/I/J numbers above are **VERIFIED** — read live from
  `pencil_dod_evaluate_county` before every write, immediately after every write, and again at
  session close.
- I's 3 new zone links (HR-2 ×2, B-1) and the R-2A explicit-false flag are backed by primary
  ordinance text I fetched and quoted directly this session (Municode Division 7, via a newly
  working Playwright-rendered access path), independently corroborated by a fresh live
  point-in-polygon GIS query against a different endpoint than the 1st firing used.
- The G regression this session caused (B-1 pk1000) was self-caught within the same session via
  re-querying the live evaluator after every write, not discovered by a downstream audit — fixed
  before being reported as done.
- R-2A's density was deliberately left `false` (not derived from the lot-area math) — matches
  established fleet convention for 7/7 analogous existing sibling districts, not a guess.
- No `gold_standard_ultraloop_audit` rows written this session (no letter crossed a PASS/FAIL
  threshold — I moved substantially but stayed FAIL; per the certify-gate semantics, audit rows
  matter for certification, not for sub-threshold progress). Did not run
  `gold_standard_loop()`/`gold_standard_certify()` per PARALLEL-FLEET RULES (other shards
  active concurrently) — reported per-county `pencil_dod_evaluate_county` only.

## Next-session priorities

1. **martin E**: unchanged, confirmed structurally blocked across 8 distinct access-method
   attempts (courthouse CAPTCHA, Landmark Web, RealForeclose, KBForeclosures, exact-string web
   search, UniCourt — this firing; the original clerk search + a 3-agent fan-out — the
   2026-07-18 session). Manual Clerk records request is the only remaining path.
2. **martin I**: automatically resolves to PASS (37/37) the moment E's blocker clears — no
   further zoning work needed for this county.
3. **General fleet note**: the Playwright/headless-browser access path for municode.com SPA
   pages (200 + full rendered body text with just a standard user-agent, no auth) may unblock
   other counties' G/I work currently logged as "Municode 403'd" — worth trying before writing
   off a Municode-hosted county as blocked.
