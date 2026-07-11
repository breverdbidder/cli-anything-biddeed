# Gold Standard shard-7 — run3786 — flagler, osceola

dispatch_id: `2f9f6a3e-a24c-4638-bcd3-5fe8f031d830`

| county | before | after | headline |
|---|---|---|---|
| flagler | 8/10 (B, F fail) | **8/10** (B, F fail) | No change — B/F reconfirmed a genuine, exhausted ceiling (see below). |
| osceola | 5/10 (B, C, D, F, I fail) | **8/10** (G, I fail) | **B, C, D, F flipped PASS.** G correctly regressed 100→0 and I 17.2%→13.4% — both are honesty corrections (a fabricated zoning dataset was purged), not real losses. |

## flagler — B/F reconfirmed, no new work (mandatory per ULTRALOOP: no new evidence, not retried)

Before dispatching any agent, re-ran the existing probe (`scripts/shard6_run3645_flagler_sold_amount_source_probe.py`)
fresh against all four previously-identified sources. All four dead ends reconfirmed live, unchanged:

1. `flagler.realtdm.com` case detail (SOLD case 25-002) — no winning-bid/sold-amount field exists on the page.
2. `flagler.realtaxdeed.com` FNC=UPDATE AJAX — empty for closed historical auction dates (live-bidding-only mechanism).
3. `qpublic.schneidercorp.com` — HTTP 403 WAF block. No `FIRECRAWL_API_KEY` in this environment to bypass it.
4. `records.flaglerclerk.gov` Landmark Web — reCAPTCHA v3 gate on the actual search POST, no CAPTCHA-solving in scope.

No agent budget was spent re-attempting this per the ULTRALOOP protocol ("no new evidence this session, not
retried"). All other flagler letters (A, C, D, E, G, H, I, J) confirmed unchanged and still passing.

## osceola — 5/10 → 8/10, three fix-and-verify items dispatched via Workflow (all survived adversarial verify)

### Pre-dispatch finding that reordered priorities: fabricated zoning dataset

Before writing any code, a live audit of osceola's `parcel_zones` (the table backing G's PASS and part of I) found
127 rows under `source='shard5-loop472-seed'` (jurisdiction 1186, unincorporated Osceola County) with **zero
exceptions** carrying `zone_code='R-1'`, all inserted in a single 5-minute window (2026-06-25 08:18:10–08:23:08 UTC).
A prior shard-12 session (`SHARD12_RUN3645_BROWARD_MARTIN_OSCEOLA_TAYLOR_SESSION_REPORT.md`) had already flagged
this exact dataset as needing "an adversarial ULTRALOOP pass on the underlying zone_code accuracy in a future
session" but had not purged it, since the parcel_id linkages themselves were real (unlike the confirmed-fabricated
martin/taylor/broward incidents). This session ran that pass.

### 1. G/I zoning veracity — FABRICATION CONFIRMED, PURGED, REBUILT

A 20-parcel exact-match sample (auction parcel → `fl_parcels` address match → real 18-digit DOR parcel_id → live
query against `gis.osceola.org`'s `Zoning_Parcels` ArcGIS FeatureServer) found **0 of 18 resolvable matches
confirmed R-1**. Real zones were PD(7), INCORP(5), AC(2), CT(1), CR(1). Purged the full fabricated chain
(`parcel_zones` + orphaned `zoning_districts`/`zone_standards` rows) and rebuilt 26 real `parcel_zones` rows with
zone codes sourced live from the same GIS FeatureServer (7 distinct real codes: AC, CR, CT, PD, PMUD, RMH, STRPD).

- **G: 100.0 → 0.0 (honest FAIL).** The 26 real zone assignments exist but contribute 0% to density/FAR scoring
  because `zone_standards` numeric fields (density, FAR, setbacks) were left NULL rather than fabricated —
  `library.municode.com/fl/osceola_county` (Osceola's Land Development Code) returns HTTP 403 WAF to both curl and
  WebFetch, and Firecrawl is confirmed absent from this environment. **This is a correction, not a regression** —
  the prior 100.0 was never real.
- **I: 17.2% → 13.4% (18/134, down from 23/134).** The new number rests entirely on the real 26-row join; the old
  number partly rested on the fabricated 116-row join. Genuine remaining gaps: 89 of 124 scoring-eligible parcels
  have no usable street address at all; 8 zoned-but-address-complete rows are blocked on missing `centroid_lat/lng`
  in `fl_parcels` itself (verified at the source, not just our table); 9 resolved parcels fall inside an
  incorporated municipality (Kissimmee/St Cloud, zone_code='INCORP') with no city-level zoning layer scraped.
- Holmes County carries 13 rows under the identical `shard5-loop472-seed` tag and `zone_code='R-1'` — **left
  untouched**, out of scope for this osceola-only pass, flagged for a future Holmes-scoped session.

### 2. B/F sold-amount sourcing — PASS via a genuinely new source

Found `osceola.realtaxdeed.com`'s authenticated "Auction Results Report" (`report_id=18`, RealAuction jqGrid), an
independent Clerk/RealAuction post-sale ledger distinct from our own pre-sale calendar-sweep scraper — the same
mechanism already proven for santa_rosa, not yet tried for osceola. Pulled all 574 report rows (verified no
pagination truncation), matched 40 of osceola's 117 completed/redeemed case_numbers to a real `status="Sold"` row
with a winning_bid, backfilled `sold_amount`/`tier1_sold_amount` on those 40 MCA rows, and inserted 40 independent
`tax_deed_outcomes` rows (`data_source='tier1:realtaxdeed_results_report:report18'`).

- **B: null → 100.0 PASS** (verified=40, closed_sold=40 — closed_sold is itself defined as `sold_amount IS NOT
  NULL`, so this is tautologically 100% once exactly the matched 40 rows got a value; true underlying coverage of
  the full 117-row completed/redeemed set is 34.2%, disclosed honestly, not hidden).
- **F: null → 100.0 PASS** (tier1_sold=40, same 40 rows, same source).
- Residual: 74 of 117 case_numbers have no matching row in report_id=18 yet (mostly very recent auction dates —
  2026-05-15 and 2026-06-30 — plausibly still pending Clerk data-entry, not permanently absent). 3 case_numbers had
  a winning_bid but status='Cancelled' and were correctly skipped (stray last-bid artifact, not a real sale).
- Also confirmed a prior shard-12 script's fabricated `VERIFIED_BUYER_*` mock outcome rows never actually landed
  (target tables lack the columns it tried to write — would 400 — confirmed live, zero pre-existing rows).

### 3. C/D parity — PASS, exact 14-row gap closed via two independent sources

- **Group 1 (9 rows):** already `matched_clean` but `parity_source` was NULL. 8 verified live via a
  from-scratch reverse-engineered RSA-encrypted API call to `officialrecords.osceolaclerk.org`'s tax-deed
  "browserview" system (real record returned for every case, `strap_num` exact-prefix-matches our stored
  parcel_id); 1 verified via exact parcel_id match in the existing `realforeclose_aids` harvest table. Backfilled
  honest tier1-prefixed `parity_source` values.
- **Group 2 (5 rows):** foreclosure cases with `OSC-<hex>` placeholder parcel_ids. `osceola.realforeclose.com`
  confirmed site-wide offline (not just WAF — literal "This feature is currently offline" notice, checked both via
  curl and a real headless browser). Substituted the Ninth Judicial Circuit's official docket system
  (`courts.osceolaclerk.com/BenchmarkWeb`) — reverse-engineered its ASP.NET MVC form flow, independently confirmed
  all 5 case numbers as real distinct court cases with real judges/parties/docket history (one shows a "FORECLOSURE
  HELD" event matching our stored auction_date exactly). Promoted `parity_status` to `matched_clean`. **The OSC-
  placeholder parcel_ids were deliberately left unchanged** — no live source exposed a real parcel identifier for
  any of the 5, and the hard rule against guessing was followed.
- **C: 89.6% → 100.0% PASS** (matched_clean 120→134). **D: 89.6% → 100.0% PASS** (matched_any 120→134).

## ULTRALOOP audit

23 rows logged to `gold_standard_ultraloop_audit` under dispatch `2f9f6a3e-a24c-4638-bcd3-5fe8f031d830` (letters
B/C/D/F/G/I × fix + independent verify claims). **Every claim survived=true** — no refutations. Verifiers
independently re-ran `pencil_dod_evaluate_county`, cross-checked live sources themselves (GIS FeatureServer samples,
the encrypted Clerk API, the court docket system, report_id=18 row counts), and explicitly checked for cross-item
side effects (e.g. confirmed the G/I regression was not caused by the C/D or B/F writes, and vice versa).

## Before / after — `pencil_dod_evaluate_county` (pasted verbatim, fresh calls post-session)

### flagler
```
{"A":{"pass":true,"metric":40,"detail":"fc=40 td=97"},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":97.8,"detail":"matched_clean=134"},"D":{"pass":true,"metric":97.8,"detail":"matched_any=134"},"E":{"pass":true,"metric":99.3,"detail":"parcel_linked=136"},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},"H":{"pass":true,"metric":5.2},"I":{"pass":true,"metric":95.6,"detail":"card_complete=131 of 137"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=137"},"auctions_total":137}
```
(unchanged from session start — confirmed no cross-contamination from osceola work)

### osceola
```
BEFORE: {"A":{"pass":true,"metric":5,"detail":"fc=5 td=129"},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":false,"metric":89.6,"detail":"matched_clean=120"},"D":{"pass":false,"metric":89.6,"detail":"matched_any=120"},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=134"},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},"H":{"pass":true,"metric":5.8},"I":{"pass":false,"metric":17.2,"detail":"card_complete=23 of 134"},"J":{"pass":true,"metric":96.3,"detail":"deal_complete=129"},"auctions_total":134}
AFTER:  {"A":{"pass":true,"metric":5,"detail":"fc=5 td=129"},"B":{"pass":true,"metric":100.0,"detail":"verified=40 closed_sold=40"},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=134"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=134"},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=134"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=40 closed_sold=40"},"G":{"pass":false,"metric":0.0,"detail":"density=0.0 far=0.0 pk1000="},"H":{"pass":true,"metric":0.3},"I":{"pass":false,"metric":13.4,"detail":"card_complete=18 of 134"},"J":{"pass":true,"metric":96.3,"detail":"deal_complete=129"},"auctions_total":134}
```

## Commits shipped to main

- `56bd2ac4` — osceola B/F sold-amount backfill
- `70e90622` — osceola G/I zoning ghost-purge + real GIS rebuild

C/D was a pure REST-API data backfill (parity_status/parity_source only, no schema change) — no migration file per
the campaign's "simple backfills don't need a migration" rule; the exact endpoints/SQL used are logged in the
`gold_standard_ultraloop_audit` rows above.

## Next-session priorities

1. **osceola G — zone_standards numeric backfill.** 7 real zone codes (AC, CR, CT, PD, PMUD, RMH, STRPD) now exist
   with correct provenance but NULL density/FAR/setback values — `library.municode.com/fl/osceola_county` 403s
   without Firecrawl. Highest-leverage single fix once Firecrawl access exists.
2. **osceola B/F — re-run the report_id=18 pull later.** 74 of 117 completed/redeemed case_numbers aren't in the
   Clerk's results report yet (mostly very recent auction dates); likely recoverable with zero new source-discovery
   work once the Clerk posts them.
3. **osceola I — incorporated-municipality zoning.** 9 resolved parcels sit inside Kissimmee/St Cloud
   (zone_code='INCORP' in the county layer) with no city-level zoning source scraped yet.
4. **holmes county** — the same `shard5-loop472-seed`/`zone_code='R-1'` fabrication pattern (13 rows, jurisdiction
   1185) exists there too, found but correctly left untouched as out-of-scope this session. Needs its own
   ULTRALOOP pass.
5. **flagler B/F** — remains a fully exhausted ceiling (4/4 sources dead, no Firecrawl, no CAPTCHA-solving in
   scope). Do not re-attempt without new evidence (a Firecrawl key, or a newly discovered source).

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were NOT run this session — the main
branch's concurrent commit history (shard1/2/4/5/6/8/13/14 all landed today) confirms other shards were mid-flight.
