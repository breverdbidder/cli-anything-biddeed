# GOLD STANDARD SHARD-3 — CONTINUATION ADDENDUM
Dispatch: `26f01b9b-e405-422e-9908-229f26e0ae5a` · chat_session `architect-20260718T160000` · 2026-07-18

This is a same-day continuation of the original session report (`..._SESSION_REPORT.md`,
commit `4be63570`). That session already shipped seminole's pk1000 fix and the C/D AJAX
harvest, and left a "next-session priorities" list. This continuation worked that list.
Per this dispatch's own ULTRALOOP protocol, all claims below were independently
re-derived from live tables/RPC calls in this same turn before being written — not
carried forward from memory of the earlier session.

## Live before/after (`pencil_dod_evaluate_county`, pasted verbatim, this continuation)

### seminole — **8/10 → 9/10, real improvement (G fixed)**
```
before: A=P(11) B=P(100.0) C=P(100.0) D=P(100.0) E=P(98.1) F=P(100.0) G=F(80.6) H=P I=F(91.4) J=P(100.0)
after:  A=P(11) B=P(100.0) C=P(100.0) D=P(100.0) E=P(98.1) F=P(100.0) G=P(96.9) H=P(2.5) I=F(91.4) J=P(100.0)
```
Only I remains. Full root-cause and fix detail in migration
`supabase/migrations/20260718k_gold_standard_shard3_seminole_g_density_oviedo_sanford_fix_run26f01b9b.sql`
(checked in, commit `b058cc75`).

### marion, franklin, liberty — unchanged, re-confirmed genuinely blocked
```
marion:   9/10 (G FAIL, density=100.0 far=100.0 pk1000=0.0)
franklin: 8/10 (B/F FAIL, closed_sold=0)
liberty:  7/10 (A/B/F FAIL, fc=1 td=0, closed_sold=0)
```
No writes made to these three this session — every avenue tried and blocked (see below),
consistent with, and now a third independent confirmation of, prior sessions' findings.

## What was fixed (seminole G, density sub-metric)

Root cause: 5 zoning districts across Seminole's 8 jurisdictions had `density_regulated`
either `true` or `NULL` (defaulting to "applicable" via `v_zoning_district_applicability`'s
category fallback) with no sourced `max_density_du_acre`:

- Oviedo (jid 862) R-1, R-1C: real values sourced and computed from Oviedo LDC Table
  4.2.1's stated minimum lot size (43,560 / min_lot_sqft — the actual density-control
  mechanism this code uses for conventional single-family districts). PDF downloaded
  directly via WebFetch, then read with `pypdf` since the WebFetch AI summarizer could
  not parse the compressed PDF stream — R-1=5.1 du/ac, R-1C=17.4 du/ac.
- Oviedo (jid 862) PUD: LDC Sec. 4.11(F) states density is set per development agreement
  per the parcel's FLU designation, not a fixed zoning-district value — same statewide FL
  PUD convention already applied elsewhere in this exact dataset. `density_regulated` set
  `false`, not fabricated.
- Sanford (jid 904) PD: existing `zoning_districts.description` already documented this
  as a negotiated-development code type identical to Seminole Co. unincorporated's own PD
  districts (already correctly `density_regulated=false` in this dataset) — applied the
  same established treatment, not a new guess. `density_regulated` set `false`.
- Casselberry (jid 850) PRD: **not fixed**, disclosed residual. WebSearch found real
  ordinance text showing PRD density is genuinely FLU-dependent (5 du/ac Low/Medium, 20-25
  du/ac High) — a real fixed cap exists, unlike PUD, but assigning one number without
  knowing this specific parcel's FLU would be a guess. Left `NULL`. Does not block G
  (31 of 32 applicable = 96.9% ≥ 95% without it).

All writes applied live via PostgREST PATCH (direct psql pooler auth confirmed stale
again this session — `password authentication failed`, same constraint documented in
every migration this dispatch). SQL VERIFICATION block below.

## Marion G (B-2 parking ratio) — re-confirmed BLOCKED, third session in a row

Attempted, this session, independently of the prior two sessions' attempts:
- `library.municode.com` (Marion LDC Article 6) → **HTTP 403**
- `marioncounty-fl.elaws.us` (Sec. 6.11.8 mirror) → **connection reset** (ECONNRESET)
- `marionfl.org` (official LDC page) → **HTTP 403**
- `tranzon.com` PDF (a third-party zoning excerpt found via search) → downloaded and read
  with `pypdf`; contains Article 4 use tables, not the Article 6 parking schedule — wrong
  document, dead end
- Firecrawl scrape of the municode URL → **HTTP 402** (this session's Firecrawl account
  credit is exhausted — flagged, not silently retried or estimated)
- WebSearch (3 queries) → confirms Table 6.11-4/6.11-5 exists and governs this exact
  requirement, but no search result quotes the actual numeric ratio

No number fabricated. Genuinely blocked pending either restored Firecrawl credit, a
different network egress, or a direct call/PDF request to Marion County Growth Services
(352-438-2600, per the search results' own recommendation).

## Franklin + Liberty B/F — re-confirmed accrual-blocked (no new writes)

This exact recheck was already run and committed earlier today
(`scripts/franklin_liberty_bf_recheck_2026-07-18.py`, commit `27923972`) via the live
franklinclerk.com `wp-json/kma/v1` REST API and libertyclerk.com's foreclosure-sales page
— third consecutive check (07-10, 07-11, 07-18) finding franklin's 4 past-due tax-deed
certs still `auction_status='scheduled'` with clerk `modified` timestamps frozen from
before the sale date (upstream clerk data-entry lag, not a scraper defect), and liberty's
sole case still 3 days out from its sale date at the time of that check. Not re-run a
second time this continuation to avoid duplicate work / wasted budget — see that
commit's script docstring for full detail.

## Seminole I — re-confirmed BLOCKED via three additional, independently-tried GIS paths

The residual documented in `20260718e` (6 real-parcel rows need `parcel_zones` coverage)
was re-attempted this session via paths not tried in the earlier session today:
1. `gis.scpafl.org/arcgis/rest/services` → **connection reset** (same as every prior
   session's finding for this exact host)
2. `seminolearcgis.seminolecountyfl.gov:6443` (a *different* subdomain/port on the same
   county network, discovered via the live ArcGIS Online web-app config for Seminole
   County's own published "Zoning" viewer) → **connection timeout** — same infrastructure
   block extends beyond the one previously-tried hostname
3. Public ArcGIS Online search surfaced a `Pinellas_Seminole_Zoning` FeatureServer that
   looked promising by name; queried live for all 6 gap parcels' coordinates → zero
   matches. Checked the layer's extent: it resolves to Pinellas County, not Seminole
   County — "Seminole" in the name refers to the City of Seminole, a municipality
   *within Pinellas County*, an unrelated same-name false lead. Confirmed and ruled out,
   not silently discarded.

Three independent, real attempts, all confirmed blocked or wrong-target. This is now a
well-evidenced infrastructure constraint, not an under-tried one.

## SQL VERIFICATION

```sql
-- seminole, live via rpc/pencil_dod_evaluate_county, 2026-07-18T[this session]:
SELECT public.pencil_dod_evaluate_county('seminole');
-- G: {"pass": true, "detail": "density=96.9 far=100.0 pk1000=100.0", "metric": 96.9}
-- Full row: A=P(11) B=P(100.0) C=P(100.0) D=P(100.0) E=P(98.1) F=P(100.0)
--           G=P(96.9) H=P(2.5) I=F(91.4) J=P(100.0)  =>  9 of 10 PASS

SELECT public.pencil_dod_evaluate_county('marion');
-- G: {"pass": false, "detail": "density=100.0 far=100.0 pk1000=0.0", "metric": 0.0}
-- Full row unchanged from dispatch brief: 9 of 10 PASS (G only failure)

SELECT public.pencil_dod_evaluate_county('franklin');
-- 8 of 10 PASS (B, F FAIL, closed_sold=0) — unchanged

SELECT public.pencil_dod_evaluate_county('liberty');
-- 7 of 10 PASS (A, B, F FAIL) — unchanged
```

## Certification status

No county in this shard reached 10/10 this continuation (seminole moved 8→9). No
`gold_standard_loop()` / `gold_standard_certify()` run — other shards' commits (e.g.
`1df8824e` from shard-4/sarasota-nassau-bay-gulf) landed on `origin/main` during this
session, confirming concurrent shard activity, consistent with PARALLEL-FLEET RULES.

## Next-session priorities (this shard)

1. Seminole I: needs `parcel_zones` for ≥3 of the 6 real-parcel gap rows (96→99 of
   105 = 94.3%, still FAIL) or all 6 (96→102 of 105 = 97.1%, PASS). Blocked on GIS
   network access from this sandbox — three independent paths now confirmed dead. Try
   restored Firecrawl credit or a different egress next session.
2. Marion G: same B-2 parking-ratio blocker, third session confirming the same
   conclusion. A direct phone/PDF request to Marion County Growth Services may be the
   only remaining path from a sandboxed session.
3. Casselberry PRD (seminole, `zoning_district_id=6357`): real FLU-dependent density cap
   exists (5 or 20-25 du/ac) but needs this parcel's specific FLU designation to assign
   correctly. Does not block G's current PASS; low priority.
4. Franklin/Liberty B/F: genuinely accrual-blocked, third consecutive confirmation
   (07-10, 07-11, 07-18). Do not re-check again until a materially new signal exists
   (e.g. a new auction_date passing, or a clerk `modified` timestamp updating) — repeated
   identical checks are not productive use of session budget.
5. Liberty A: no online tax-deed tenant exists for Liberty County — structurally
   blocked absent a courthouse-only ingestion mechanism. Lowest-leverage item in this
   shard (`auctions_total=1`).
