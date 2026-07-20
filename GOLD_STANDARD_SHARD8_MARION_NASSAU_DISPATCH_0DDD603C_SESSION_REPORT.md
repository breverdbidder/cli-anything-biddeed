# GOLD STANDARD shard-8: marion + nassau — session report

dispatch_id: `0ddd603c-68ec-45c0-86b8-3b643c98faf3`
chat_session: `architect-20260720T160000`
date: 2026-07-20

## Result: BOTH COUNTIES 10/10

| County | Before | After |
|---|---|---|
| marion | 9/10 (G FAIL, pk1000=0.0) | **10/10** |
| nassau | 7/10 (B/F FAIL null, I FAIL 20.6%) | **10/10** |

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| marion G | backfill missing parking standard | done — 1 district (B2, 6 parcels) | none |
| nassau B/F | build independent outcome scraper | done — 11 real outcomes via new Playwright render path | scope: also discovered Firecrawl still 402 fleet-wide, worked around it rather than waiting |
| nassau I | extend zoning substrate | done — new jurisdiction + 6 districts + 27 parcel_zones | scope grew beyond "just fill zone_code" once G-regression risk was identified; had to source real density standards too |

## marion — G fix

**Diagnosis (VERIFIED):** `v_zoning_gold_standard_kpi_v3` showed density=100.0, far=100.0, pk1000=0.0. Traced to exactly one zoning_district (id=11738, code `B2` "Community Business", Unincorporated Marion, 6 parcels) being the *only* `pk1000_applicable=true` district in the county — every other district (residential/agricultural/admin) correctly defaults not-applicable. `parking_per_1000sf` was NULL on that one row.

**Source:** Marion County LDC Sec. 6.11.8, Table 6.11-5 "Minimum Off-Street Parking Requirements for Nonresidential Land Use" — fetched live via the Municode `CodesContent` REST API (reverse-engineered the client/product/job/nodeId chain since the site's normal HTML is a JS-only Angular shell that both WebFetch and static curl choke on). Table 6.11-5 is keyed by *use type*, not zoning district, so there's no literal "B2" row — mapped to "Neighborhood or convenience center under 100,000 sq. ft. GLA" = **4 spaces per 1,000 sq. ft. GLA**, matching B2's permitted-use mix (grocery, drug store, bank, restaurant, general retail) and matching the ~4.00/1000sf value already on record for General/Community Commercial districts in ~20 other FL counties in this DB.

Migration: `migrations/20260720e_gold_standard_shard8_marion_g_b2_parking_backfill.sql`

## nassau — B/F fix

**Diagnosis (VERIFIED):** Two prior sessions (`scripts/shard12_run2753_nassau_bf_fabrication_revert.py`, `scripts/shard7_run2753_nassau_bf_c_blocked_diagnosis.py`) had already correctly:
1. Reverted an earlier session's fabricated `sold_amount=150000` placeholder (identical value on all rows, including auctions that hadn't happened yet).
2. Re-diagnosed B/F as genuinely BLOCKED: RealAuction's sold-status widget (`ASTAT_MSGA`/`ASTAT_MSGD`/`ASTAT_MSG_SOLDTO_MSG`) only exists in client-side-JS-rendered HTML, not the bare AJAX endpoint. Firecrawl was their only headless-render tool, and it was 402 Insufficient Credits fleet-wide — re-confirmed still true today (`curl` to Firecrawl API returns "Insufficient credits").

**Fix:** `playwright` + Chromium are locally installed in this environment (not available/tried by prior sessions). Wrote `scripts/shard8_nassau_bf_realauction_pw_harvest.py`: renders `nassauclerk.realforeclose.com`'s PREVIEW page per auction date, parses the "Auctions Closed or Canceled" section, matches case_number, and only counts rows where the live status is literally "Auction Sold" with a parsed dollar amount.

**Execution receipt:** 12 distinct past auction dates rendered, 35 AITEMs parsed, 29/29 of nassau's target cases matched, 11 confirmed "Auction Sold" → `foreclosure_outcomes` (11 rows, `data_source='realauction_live:nassau_pw_harvest_20260720'`) + `multi_county_auctions` patched (`sold_amount`, `tier1_sold_amount`, `tier1_sale_status='sold'`, `tier1_authoritative=true`).

Distribution: 7 distinct real dollar amounts ($77,100–$266,100) + 4 legitimate $100.00 nominal plaintiff-credit-bid amounts (a real, live-verified RealAuction convention when the bank is sole bidder) — structurally different from the prior flat-$150k fabrication.

## nassau — I fix

**Diagnosis (VERIFIED):** All 34 auction rows already had address/geo/value (E=100%). The gap was entirely zoning substrate: only 7 parcels (all City of Fernandina Beach) had *any* `parcel_zones` row. "Unincorporated Nassau County" — the majority of the county, covering Yulee/Bryceville/CR-121 addresses — had **no jurisdiction row at all**.

**Fix:** Built the missing substrate:
- New jurisdiction: "Unincorporated Nassau County"
- 6 new `zoning_districts`: RS-1 / RM / OR / PUD (Unincorporated Nassau), RLD (Callahan), R-1 (Fernandina Beach)
- Density standards sourced live: Nassau Ordinance 97-19 (Municode API, Articles 9/10/22/25), Town of Callahan Code Ch.195 §195-67 (live PDF)
- 27 `parcel_zones` rows, zone codes sourced from the Nassau Property Appraiser ArcGIS "Land Parcels" layer (144), queried by PIN (24/27 exact match, 3 resolved by house-number+street after a PIN miss)

**Regression guard (the important part):** nassau's G was already PASSING (density=100%, far/pk1000 not-applicable) before this fix. Naively adding 27 new zoned parcels with no standards would have flipped `far_applicable`/`pk1000_applicable`/`density_applicable` defaults and tanked G. Handled by:
- Leaving `far_regulated`/`pk1000_regulated` NULL on all new districts (all non-commercial → correctly default not-applicable)
- Populating real `max_density_du_acre` on 5 of 6 new districts (derived from each ordinance's stated minimum lot size: 43,560 sq ft/acre ÷ min lot sqft)
- For PUD, explicitly set `density_regulated=false` — Nassau's own ordinance (Sec 25.01/25.03) sets PUD density per-project via an approved Preliminary Development Plan, not as a zone-level number. This is a documented fact about the district, not a metric dodge.

Verified live before/after: `G.detail` stayed byte-identical (`"density=100.0 far= pk1000="`) while `I` moved 20.6% → 100.0%.

Migration: `migrations/20260720f_gold_standard_shard8_nassau_i_zoning_substrate.sql`

## Adversarial verification (ULTRALOOP PROTOCOL)

Ran a background Workflow with 2 independent refuter agents per claimed letter-move (8 refuters total), each with live DB + web access and explicit instructions to try to break the claim (fabrication signatures, uncited sources, sibling regressions, live re-fetch mismatches).

| County | Letter | Votes | Result |
|---|---|---|---|
| marion | G | 2/2 survived | SHIP |
| nassau | B | 2/2 survived | SHIP |
| nassau | F | 2/2 survived | SHIP |
| nassau | I | 2/2 survived | SHIP |

Refuters independently live-rendered 5+ RealAuction PREVIEW pages and the Municode Table 6.11-5 source, getting exact matches to what was written to the DB. Disclosed (non-invalidating) caveats surfaced by refuters, carried forward for future sessions:
- Nassau RealAuction PREVIEW pages return 403 to a default headless UA — needs UA/context spoofing to render reliably (the harvest script should be checked/hardened for this on any re-run).
- Callahan's ordinance also has a §195-70 density cap (6 du/acre) not cross-cited against the §195-67-derived 5.81 figure used here — both are genuine, close, and non-contradictory, but worth reconciling if Callahan zoning is revisited.
- Fernandina Beach R-1's density (5.00 du/acre) is an explicitly-flagged INFERRED reuse of the sibling R-1A district's value (confidence_score=0.55), not freshly derived from a dimensional table — Ch.2 of FB's LDC doesn't carry one.

Audit rows written to `gold_standard_ultraloop_audit` (dispatch_id above), 4 rows, all `survived=true`.

## Verification evidence (final live query, 2026-07-20)

```
marion: {"A":{"pass":true,"metric":246},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},
"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":98.4},"F":{"pass":true,"metric":100},
"G":{"pass":true,"metric":100,"detail":"density=100.0 far=100.0 pk1000=100.0"},
"H":{"pass":true,"metric":6.2},"I":{"pass":true,"metric":98.4},"J":{"pass":true,"metric":100},
"auctions_total":552}

nassau: {"A":{"pass":true,"metric":5},"B":{"pass":true,"metric":100,"detail":"verified=11 closed_sold=11"},
"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":100},
"F":{"pass":true,"metric":100,"detail":"tier1_sold=11 closed_sold=11"},
"G":{"pass":true,"metric":100,"detail":"density=100.0 far= pk1000="},"H":{"pass":true,"metric":0.5},
"I":{"pass":true,"metric":100,"detail":"card_complete=34 of 34"},"J":{"pass":true,"metric":100},
"auctions_total":34}
```

## Close-out protocol note

Did **not** run `gold_standard_loop()` / `gold_standard_certify()` — `git pull --rebase` immediately before pushing pulled in fresh commits from shard-6/shard-9/shard-11/shard-14, confirming other sessions are actively mid-flight on other counties right now. Per PARALLEL-FLEET RULES, only the two per-county `pencil_dod_evaluate_county` evaluations above are reported; fleet-wide certification is left to a close-out session that can confirm no other shard is running.

## Shipped

Commit `d10fa574` on `main` (direct push, no PR, per SHIP-TO-MAIN MANDATE):
- `migrations/20260720e_gold_standard_shard8_marion_g_b2_parking_backfill.sql`
- `migrations/20260720f_gold_standard_shard8_nassau_i_zoning_substrate.sql`
- `scripts/shard8_nassau_bf_realauction_pw_harvest.py`

Both migrations applied live to Supabase project `mocerqjnksmhcjzxrewo` during this session (not just committed — executed, per SHIP GATE).
