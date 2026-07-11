# Gold Standard shard-13 — lee — duplicate dispatch re-fire addendum

dispatch_id: `61454491-3b8a-4b0c-8c92-1f17041cc821`
chat_session: `architect-20260711T160000`
county: **lee** (6/10: A,B,F,G,H,J PASS; C,D,E,I FAIL)

## This dispatch was a duplicate re-fire

The exact same dispatch_id + chat_session already shipped in full as commit
`d1154f80` (`GOLD_STANDARD_SHARD13_RUN3786_LEE_SESSION_REPORT.md`). At this
session's start, live `pencil_dod_evaluate_county('lee')` matched that report's
"Final live state" JSON exactly (H differed only by elapsed hours, as expected).
Zero drift confirmed before doing any new work — this is the same pattern the
campaign has documented before (e.g. the lafayette `b34a2384` re-fire addendum).

Rather than stop at "nothing to do," this session picked up the prior report's
own documented residual next-session priorities and made real, adversarially
verified progress on one of them.

## Before / after (`SELECT public.pencil_dod_evaluate_county('lee')`)

| Letter | Session start (= prior session's final state) | This session's final (live, re-confirmed stable) |
|---|---|---|
| A | PASS 38 | unchanged |
| B | PASS 100.0 | unchanged |
| C | FAIL 91.9 (matched_clean=251/273) | **FAIL 91.9 (unchanged, reconfirmed)** |
| D | FAIL 91.9 (matched_any=251/273) | **FAIL 91.9 (unchanged, reconfirmed)** |
| E | FAIL 93.4 (parcel_linked=255/273) | **FAIL 93.4 (unchanged, reconfirmed)** |
| F | PASS 100.0 | unchanged |
| G | PASS 97.5 (density=97.5) | **PASS 96.1 (density=96.1, far=100.0 — new, safe)** |
| H | PASS | unchanged (freshness metric only) |
| I | FAIL 79.5 (card_complete=217/273) | **FAIL 87.9 (card_complete=240/273) — +8.4pt** |
| J | PASS 100.0 | unchanged |

Final live state (2026-07-11, this session):
```json
{"A":{"pass":true,"metric":38},"B":{"pass":true,"metric":100},
 "C":{"pass":false,"metric":91.9,"detail":"matched_clean=251"},
 "D":{"pass":false,"metric":91.9,"detail":"matched_any=251"},
 "E":{"pass":false,"metric":93.4,"detail":"parcel_linked=255"},
 "F":{"pass":true,"metric":100},
 "G":{"pass":true,"metric":96.1,"detail":"density=96.1 far=100.0 pk1000="},
 "H":{"pass":true,"metric":2.1},
 "I":{"pass":false,"metric":87.9,"detail":"card_complete=240 of 273"},
 "J":{"pass":true,"metric":100},"auctions_total":273}
```

County remains **6/10**. I improved substantially but did not flip to PASS.

## I: real, adversarially-safe recovery (79.5% → 87.9%)

Full method and row-level detail is in the migration file
`supabase/migrations/20260711x_shard13_lee_dupe_refire_gapfix_i_backfill.sql`.
Summary:

1. Re-derived the current I gap live: 38 canon lee auctions have a real
   `parcel_id` but no matching `parcel_zones` row. Queried the live Lee County
   ArcGIS Parcels FeatureServer for all 38 STRAPs — 38/38 matched with real
   zoning + site-city data.
2. Classified each against the **live** `v_zoning_district_applicability` view
   (empirically verified this session to be a category-based heuristic,
   independent of the raw `zoning_districts.far_regulated`/`density_regulated`
   columns the prior session's diagnosis had focused on — that distinction
   matters and is documented in the migration for the next session):
   - **30 safe** (zero G risk — either FAR/density not applicable per the live
     view for that code, or applicable with a real `zone_standards` value
     already present).
   - **5 risky** (Fort Myers CG/NC — FAR applicable, value NULL; RS-6/RS-7 —
     density applicable, value NULL). Inserting these without real ordinance
     values would reproduce the exact G regression the prior session hit.
   - **3 unresolvable** (ArcGIS `ZONING` field genuinely null/empty for the
     STRAP — not a query bug, confirmed by direct feature inspection).
3. Inserted the 30 safe rows via PostgREST with a **fresh, never-reused**
   `source` tag (`lee_shard13_dupe_refire_20260711_gapfix_safe30`) — deliberately
   not reusing any prior tag, directly applying the lesson from the prior
   session's documented source-tag-collision incident that deleted 45
   legitimate rows.
4. Verified live immediately after insert: **G stayed PASS** (97.5→96.1,
   still >95%; `far` moved 97.5%→100.0% because a Cape Coral "C"-zone parcel
   with a real `max_far=1.00` entered the applicable set for the first time —
   an improvement, not a regression). **I moved 79.5%→87.9%** (217→240 of 273),
   exactly the 23-row subset of the 30 inserts that also had address+geo+value
   already present (8 of the 30 lack lat/lng and so didn't flip card-complete —
   flagged as a residual geocode gap, not a zoning problem).

## G/I: the last 5 rows — honest negative, not shipped

An ultracode Workflow (`wf_7a70d81e-023`, 5 agents, ~294K tokens: 2 research +
2 adversarial refuters + 1 orchestration) attempted to source the 4 real Fort
Myers LDC values needed to safely insert the remaining 5 rows (CG max FAR, NC
max FAR, RS-6 max density, RS-7 max density). Result: **0 of 4 confirmed.**

- `library.municode.com/fl/fort_myers` returned HTTP 403 Forbidden on every
  fetch attempt from every agent (bot-gated). The city's own GIS PDF endpoints
  were unreachable (`ECONNREFUSED`) or blocked (Firecrawl account is out of
  credits — confirmed via a direct API call this session, `"Insufficient
  credits"`).
- The only reachable content was a third-party mirror
  (`zoneomics.com/code/fort-myers-FL/chapter_2`). RS-7 density=7 du/acre was
  found there and internally corroborated three ways (sequential lettering
  vs. adjacent districts, a cross-referencing city PDF, an independent Redfin
  listing snippet) — but the adversarial refuter correctly rejected it anyway:
  single third-party source only, primary ordinance text unreachable, doesn't
  meet the bar for a production write. CG/NC/RS-6 stayed `UNKNOWN` — no
  candidate value could even be extracted with enough confidence to send to
  the refuter.
- Notably, the same mirror's dimensional-standards table has **no FAR column
  at all** for CG/NC (only lot area/width/setbacks/height/coverage), which is
  suggestive that FAR may genuinely not be a regulated standard for these base
  districts — but that's not primary-source-confirmed either, so it was left
  `UNKNOWN` rather than guessed in either direction.

Per the campaign's "do not guess" hard requirement, none of these 4 values
were written and the 5 rows remain uninserted. This is exactly what the
ULTRALOOP adversarial-verify layer exists to produce when the evidence isn't
strong enough — reporting it as a disciplined negative, not rounding up.

## C/D and E hard remainder: reconfirmed unchanged, no new lever found

- **C/D**: the 22 in-scope `parity_status='mca_only'` rows
  (`data_source='calendar_sweep_mca_v3'`, dates 2026-06-25/07-09/07-30) are the
  same set the immediately-prior (already-shipped) session live-reharvested via
  `scripts/gold_standard_shard10_lee_cd_e_i_ajax_harvest_run3679.py` and found
  genuinely absent from RealForeclose's calendars for those dates. This
  session's own quick recheck of `lee.realforeclose.com` got HTTP 403 —
  consistent with needing the browser-context harvester already used and
  already exhausted this same day. Not re-running the identical probe for a
  third time without a new angle.
- **E hard remainder** (12 rows, `parcel_id`/`property_address` both NULL):
  `leeclerk.org` → HTTP 403, `matrix.leeclerk.org` → unreachable (Akamai WAF),
  matching the prior session's finding exactly. Firecrawl was tried as a new
  angle this session specifically to attempt to clear the WAF — blocked on
  exhausted API credits, not a tooling choice. Needs RealAuction bidder
  credentials or a funded Firecrawl/Playwright pass.

## Residual / next-session priorities for lee

1. **G/I lever (real, scoped, safe path forward):** retry the 4 Fort Myers LDC
   values (CG max FAR, NC max FAR, RS-6/RS-7 max density) with a tool that can
   actually reach `library.municode.com` (funded Firecrawl, a different egress
   IP, or a real headless browser) rather than plain WebFetch, which is
   uniformly 403-blocked there. If confirmed, insert the 5 remaining
   `parcel_zones` rows (STRAPs captured in this session's tool transcript) —
   worth ~1.8pt of I.
2. **I geocode gap:** 8 of the 30 newly-zoned rows (plus others) have
   address+value but no lat/lng — a geocoding pass (not a zoning problem)
   would recover these independent of the ordinance-research residual.
3. C/D: needs either a genuine date-correction source for the 22 `mca_only`
   cases or an alternate tier1 source — the RealForeclose calendar re-sweep
   path is exhausted for now.
4. E hard remainder: needs RealAuction bidder credentials or a funded
   Firecrawl/Playwright pass against Lee Clerk's Akamai WAF.

## Process note

Confirming a dispatch is a duplicate before doing any work, then verifying live
DB state matches the last shipped report exactly, avoided wasted/duplicate
effort and let this session go straight to the documented residual instead of
re-deriving from scratch. The ultracode research+verify workflow correctly
declined to certify a plausible-looking single-source ordinance value rather
than let it through — the intended failure mode of the adversarial layer,
working as designed.

---
dispatch_id: 61454491-3b8a-4b0c-8c92-1f17041cc821
chat_session: architect-20260711T160000 (duplicate re-fire, this addendum)
