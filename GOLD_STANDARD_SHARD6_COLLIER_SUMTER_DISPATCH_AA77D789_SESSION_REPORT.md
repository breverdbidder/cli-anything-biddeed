# Gold Standard shard-6 — collier, sumter — dispatch aa77d789, loop run 6148

## BEFORE (fresh query, session start)

```json
collier: {"A":{"pass":false,"metric":0,"detail":"fc=0 td=212"}, "B":{"pass":true,"metric":100.0}, "C":{"pass":true,"metric":100.0}, "D":{"pass":true,"metric":100.0}, "E":{"pass":true,"metric":100.0}, "F":{"pass":true,"metric":100.0}, "G":{"pass":false,"metric":0.0,"detail":"density=84.4 far=0.0 pk1000="}, "H":{"pass":true,"metric":0.2}, "I":{"pass":true,"metric":95.8}, "J":{"pass":true,"metric":100.0}}
sumter:  {"A":{"pass":true,"metric":4}, "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"}, "C":{"pass":true,"metric":100.0}, "D":{"pass":true,"metric":100.0}, "E":{"pass":true,"metric":100.0}, "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"}, "G":{"pass":true,"metric":100.0}, "H":{"pass":true,"metric":0.2}, "I":{"pass":false,"metric":90.9,"detail":"card_complete=10 of 11"}, "J":{"pass":true,"metric":100.0}}
```

**Score BEFORE: collier 8/10** (A, G failing) — matches the dispatch brief exactly.
**Score BEFORE: sumter 7/10** (B, F, I failing) — matches the dispatch brief exactly.

## sumter B/F — real win, adversarially verified — 0/0(null) FAIL → 100.0 PASS on both

All 11 sumter auctions have `auction_date` in the past but zero had `sold_amount` populated. Root
cause: sumter is NOT a RealAuction client (`sumter.realforeclose.com` / `sumter.realtaxdeed.com`
both resolve to the generic Realauction.com marketing homepage — confirmed live, `pipeline.counties`
row annotated so future sessions don't re-chase this dead lane). The real source of truth is
sumterclerk.com.

A prior session (`GOLD_STANDARD_SHARD14_SUMTER_DISPATCH_8EE11DD1_REFIRE_ADDENDUM.md`) found
sumterclerk.com's public surplus-funds Google Sheet proves 3 tax-deed sales occurred, but explicitly
declined to compute `winning_bid = opening_bid + surplus`, citing uncertainty over whether Fla. Stat.
197.582 surplus already nets out clerk fees/interest beyond the opening bid.

This session resolved that open question by reading the actual statute text (leg.state.fl.us,
197.582(2)(a): surplus = proceeds in excess of the certificateholder's statutory bid; 197.582(2)(b):
service charges are paid **out of** the already-fixed surplus, not netted before it). Live re-fetched
the surplus CSV (found a 4th matching case, TD-5056, that the prior session missed), cross-checked
`opening_bid`/`parcel_id` against `multi_county_auctions` before writing, and computed:

| case | opening_bid | surplus | winning_bid |
|---|---|---|---|
| TD-5028 | 13,515.69 | 186,371.18 | 199,886.87 |
| TD-5031 | 16,506.04 | 190,366.66 | 206,872.70 |
| TD-5036 | 4,559.56 | 45,365.00 | 49,924.56 |
| TD-5056 | 1,467.39 | 7,476.03 | 8,943.42 |

**Adversarial verification**: an independent refuter subagent (36 tool calls, 5 attempts) re-fetched
the CSV itself, re-read the raw statute HTML, re-queried the live DB, cross-checked property
addresses and plausibility ratios (0.72x–1.80x market value, none flagged), and specifically
investigated a wrinkle it found on its own — TD-5028's CSV row has post-sale claim-deduction lines
($186,371.18 headline minus $8,800 and $5,498.83 = $172,072.35 remaining) — and correctly resolved it
against the statute (headline figure is the sale-day surplus; deductions are later disbursements paid
*from* that surplus, per 197.582(2)(b)). All 5 attempts independently concluded `claim_survives=true`.
The workflow tool crashed on a `StructuredOutput` schema-validation bug after capturing this verdict
(recovered from the raw agent transcript); I independently re-verified the TD-5028 CSV ledger lines
myself afterward and confirm the refuter read them correctly. Logged to `gold_standard_ultraloop_audit`
(mode=`fallback`, ids 9182/9183, survived=true).

Script: `scripts/gold_standard_shard6_run6148_sumter_bf_surplus_derivation.py` (commit `704017aa`).

## sumter I — genuinely blocked (residual)

`card_complete=10 of 11` — the one gap is case `2025-CA-000255` / parcel `D29A024`, missing
`property_address`. Exhausted every source available this session: our own scrape (never captured
one), the original clerk PDF (now 404s), qpublic.schneidercorp.com (403 on every attempt, including
via WebFetch), and FL GIO's own Statewide Cadastral layer (spatial point-intersect DID find the
parcel — `PARCEL_ID=D29A024`, confirming our county's own `co_no=60` differs from FL GIO's internal
`CO_NO=70` for Sumter, worth noting for future sessions — but FL GIO's own `PHY_ADDR1`/`PHY_CITY`
fields are blank for this parcel, consistent with a large vacant/undeveloped tract with no assigned
site address). No fabrication attempted. This is the 5th session (across E and I) to hit essentially
the same wall on this exact case.

## collier G — real win, adversarially verified (partial) — density sub-metric 84.4 → 98.8

The 2nd firing addendum (`GOLD_STANDARD_SHARD12_COLLIER_DISPATCH_9D04299E_2ND_FIRING_ADDENDUM.md`)
left "MH/RSF-3/4/5 density... still genuinely unknown (no fixed value found in two sessions of
searching)" as the explicit residual. This session found it: Collier's own unincorporated LDC
**Sec 2.05.01 "Density Standards and Housing Types"** table states max density directly per district
— confirms the RSF-N naming convention literally **is** the density figure (RSF-3=3, RSF-4=4,
RSF-5=5 du/gross-acre), and MH=7.26 du/gross-acre (required reading the actual table row, since MH
has no self-evident numeric code). I independently re-fetched and parsed the raw table myself with
BeautifulSoup (not trusting the researching agent's transcription) and got an exact match. Confidence:
CONFIRMED (1.0), 4 districts, 22 of the 26 gap-parcels resolved.

Two more districts turned out to belong to **separate incorporated municipalities** with their own
zoning codes (Marco Island, Naples — not Collier County's LDC):

- **Marco Island RSF-3 = 3 du/gross-acre**: `library.municode.com` 403'd for both the original
  researcher and an independent adversarial refuter; sourced via a third-party mirror
  (zoneomics.com) reproducing real section-numbered text (Sec 30-85) with genuine ordinance
  citations. The refuter independently corroborated the RSF-2/3/4=20,000/10,000/7,500 sqft lot-area
  progression against Collier County's own LDC (Marco Island incorporated in 1997 under an amended
  Collier ordinance, explaining the shared numbering). **Survived** adversarial review; left at
  moderate confidence (0.6), not raised to CONFIRMED since no primary-source host was ever directly
  reached.
- **Naples R1-7.5 implied density = 5.8 du/acre — ATTEMPTED, then REVERTED.** Computed from
  min-lot-size (43,560/7,500) since the ordinance states no density figure directly. An independent
  adversarial refuter re-fetched the *same* corroborating mirror and found it explicitly states
  **no density figure is stated or implied** for this district — directly contradicting the
  implied-density methodology — and separately flagged a real conceptual problem: subdivision-yield
  theoretical density is not the same as per-parcel entitlement (a single already-platted auction lot
  yields exactly 1 unit regardless of acreage; presenting 5.8 as `max_density_du_acre` risked
  misleading downstream deal analysis). **Reverted live** to its pre-session NULL state. Logged to
  `gold_standard_ultraloop_audit` (id 9229, survived=false) — a genuine, honestly-documented residual,
  not shipped. This is exactly the kind of false-positive catch the ULTRALOOP adversarial-verify layer
  exists for.

Migration: `supabase/migrations/20260724u_gold_standard_shard6_collier_g_rsf_mh_density.sql`
(commit `8a07d59e`).

**collier G stays FAIL** — `LEAST(density=98.8, far=0.0, pk1000=NULL)` is still gated by `far=0.0`,
the structurally-blocked C-4/C-5 FAR gap the 2nd firing session already fully diagnosed (LDC regulates
FAR per-use, not per-district, for those two districts — genuinely not representable in the current
schema). This is real, verified, honestly-documented progress on a sub-metric that does not (and
should not) flip the letter's pass/fail, matching the same pattern the 2nd firing session reported.

## collier A — re-confirmed dead, 4th independent session

Bounded (~8 min) recheck per the campaign's own instruction not to re-run exhaustive prior searches.
`collier.realforeclose.com` / `collier.realtaxdeed.com` still 302 to the generic realauction.com
homepage (deprovisioned). `collierclerk.com`'s ShowCase calendar is still auth-gated (401 on anonymous
endpoints, confirmed in the 2026-07-18 session too). One genuinely new artifact was checked and ruled
out (a public WordPress events REST/iCal feed — generic clerk-office events, not auction listings).
No fabrication. Recommend not re-investigating again absent a new external signal.

## AFTER (fresh query, post-session)

```json
collier: {"A":{"pass":false,"metric":0,"detail":"fc=0 td=212"}, "B":{"pass":true,"metric":100.0}, "C":{"pass":true,"metric":100.0}, "D":{"pass":true,"metric":100.0}, "E":{"pass":true,"metric":100.0}, "F":{"pass":true,"metric":100.0}, "G":{"pass":false,"metric":0.0,"detail":"density=98.8 far=0.0 pk1000="}, "H":{"pass":true,"metric":0.9}, "I":{"pass":true,"metric":95.8}, "J":{"pass":true,"metric":100.0}}
sumter:  {"A":{"pass":true,"metric":4}, "B":{"pass":true,"metric":100.0,"detail":"verified=4 closed_sold=4"}, "C":{"pass":true,"metric":100.0}, "D":{"pass":true,"metric":100.0}, "E":{"pass":true,"metric":100.0}, "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=4 closed_sold=4"}, "G":{"pass":true,"metric":100.0}, "H":{"pass":true,"metric":0.4}, "I":{"pass":false,"metric":90.9,"detail":"card_complete=10 of 11"}, "J":{"pass":true,"metric":100.0}}
```

## Final Scoreboard

- **collier: 8/10 → 8/10** (A, G still failing — G's density sub-metric moved 84.4→98.8, a real
  verified win that does not flip the LEAST()-gated letter because FAR remains structurally blocked;
  Naples derivation attempted and correctly reverted after refutation).
- **sumter: 7/10 → 9/10** (B, F flipped FAIL→PASS; only I remains, genuinely blocked).

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run this
session (other shards were mid-flight); per-county `pencil_dod_evaluate_county` was used for all
verification, live, before and after every write.

## Migrations / scripts shipped (commits, direct to main)

- `704017aa` — `scripts/gold_standard_shard6_run6148_sumter_bf_surplus_derivation.py` +
  `scripts/gold_standard_shard6_run6148_sumter_bf_realauction_results.py` (negative-result template)
- `8a07d59e` — `supabase/migrations/20260724u_gold_standard_shard6_collier_g_rsf_mh_density.sql`

## Ultraloop audit trail

```
SELECT id, county_slug, letter, survived, created_at FROM gold_standard_ultraloop_audit
WHERE dispatch_id='aa77d789-bbfc-4546-a02e-73e41c1aa44c' ORDER BY created_at;
```
5 rows: sumter B (survived=true), sumter F (survived=true), collier G unincorp-density
(survived=true), collier G Marco-Island-density (survived=true), collier G Naples-density
(survived=false — reverted, not shipped).

## Residual work for next session on these counties

1. **collier G**: C-4/C-5 FAR remains structurally blocked (LDC regulates per-use, not per-district —
   would need a schema change to (district, use-type) grain to close honestly). Naples R1-7.5 density
   remains genuinely unknown (the ordinance states none, and an implied/computed value was tried and
   refuted this session — do not re-attempt the same lot-size-inversion approach without a materially
   different angle).
2. **collier A**: 4th confirmed dead end. Do not re-investigate without a new external signal.
3. **sumter I**: 5th session (across E and I) hitting the same wall on case 2025-CA-000255 / parcel
   D29A024 — no property_address available from any source tried (own scrape, clerk PDF, qpublic,
   FL GIO). Would need a manual case-file lookup or a headless-browser session capable of getting past
   qpublic's bot wall.

---

## REFIRE ADDENDUM (same dispatch aa77d789, ultracode ULTRALOOP workflow, 2026-07-24 ~09:40-09:55Z)

The dispatch fired a second time. Live-verified via `pencil_dod_evaluate_county` before touching anything:
DB state was unchanged from the AFTER block above (collier 8/10, sumter 9/10, no drift/regression from
other shards). Rather than re-derive already-closed work, ran a fresh ULTRALOOP workflow (fan-out
research on genuinely untried angles only + independent adversarial refuter) against the three residuals
flagged above.

**collier G — Naples R1-7.5 density: SHIPPED.** A materially different angle (per residual note #1's own
instruction not to repeat the lot-size-inversion) — City of Naples Comprehensive Plan Future Land Use
Element states a *direct* max density for the "Low Density Residential" FLUE category (0-6 du/net acre,
comp plan pages F.L.U.E. 5 and 17), and the comp plan's own annexation conversion table (F.L.U.E. 25)
states directly "RSF-4 → R1-7.5 → Low Density Residential" — a third, independent textual link the
researching agent hadn't even cited. **Adversarial refuter independently re-fetched the PDF and both
City of Naples ArcGIS REST layers itself**, redid the zoning→FLUE spatial crosswalk properly (all 18
R1-7.5 polygons citywide, area-weighted overlap, not the original's 2 cherry-picked vertex points) —
97.3% of R1-7.5 area falls within Low Density Residential — and returned `survived=true`. Confidence:
CONFIRMED (1.0). Logged to `gold_standard_ultraloop_audit` id 9303.

```sql
-- BEFORE (this refire, fresh query)
collier.G: {"pass":false,"detail":"density=98.8 far=0.0 pk1000=","metric":0.0}
-- AFTER (this refire, fresh query, post-write)
collier.G: {"pass":false,"detail":"density=100.0 far=0.0 pk1000=","metric":0.0}
```

G stays FAIL — correctly gated by the unrelated, already-diagnosed C-4/C-5 FAR structural gap (schema
limitation, out of scope for this fix) — but the density sub-metric is now fully closed (100.0), leaving
FAR as the sole remaining density-adjacent gap for this letter.

Migration: `supabase/migrations/20260724v_gold_standard_shard6_collier_naples_r1_75_density_refire.sql`
(applied live via Supabase REST with the service-role key; `zone_standards` row id 911,
`zoning_district_id=6470`).

**sumter I — still blocked, honestly reconfirmed.** Tried three genuinely new source categories not in
the exhausted list: Sumter County Property Appraiser's own site (sumterpa.com — redirects to the same
already-blocked qPublic), Sumter County's own GIS infrastructure separate from FL GIO statewide
(gis.sumtercountyfl.gov ArcGIS FeatureServer — returned live HTTP 500 server error on every query,
and gisweb.sumtercountyfl.gov's web adaptor reported "could not access any server machines" — a genuine
outage, not a workaround-able block), and Sumter Clerk official/court records search portals
(myfloridacounty.com, civitekflorida.com — both are JS/form-POST driven with no case-number or
parcel-ID search field; a staging mirror 403'd). No new data found. Correctly reported as
`found_new_data=false` — no write attempted, no fabrication. This is an access-limitation finding (the
county GIS being down means the question is unresolved, not confirmed-vacant), distinct from a clean
dead end; worth retrying once gis.sumtercountyfl.gov's FeatureServer is back up, or with a
headless-browser-capable session that can submit the myfloridacounty.com/civitekflorida.com forms.

**collier A — reconfirmed dead, bounded 5-min ping only** (per instruction not to re-investigate
without a new signal). Response codes shifted (403/404 instead of 302/401 seen in the 4th prior check)
but the functional state is unchanged: no usable public/anonymous auction data feed on any of the three
known endpoints. `collierclerk.com`'s old ShowCase app path appears to be gone entirely (site is now
WordPress-based); its own `/foreclosure-sales/` page redirects somewhere but was out of scope for this
bounded check per the residual note's instruction. No new external signal found.

### Updated final scoreboard (this refire)

- **collier: 8/10 → 8/10** (A, G still failing; G density sub-metric closed 98.8→100.0, FAR remains the
  sole blocker).
- **sumter: 9/10 → 9/10** (I still failing, genuinely blocked — reconfirmed via 3 new source attempts,
  none fabricated).

### Ultraloop audit trail (this refire)

```
SELECT id, county_slug, letter, survived, created_at FROM gold_standard_ultraloop_audit
WHERE id = 9303;
```
1 new row: collier G Naples-density-v2 (survived=true, mode=native).

### Residual work for next session (updated)

1. **collier G**: only the C-4/C-5 FAR schema gap remains (density sub-metric now 100.0). Needs a
   (district, use-type) grain change to `zone_standards`/`v_zoning_gold_standard_kpi_v3` to close
   honestly — an architecture change affecting a shared, fleet-wide view; do not attempt without
   confirming no other shard is mid-flight on that view.
2. **collier A**: 5th confirmed dead end. Do not re-investigate without a new external signal.
3. **sumter I**: 6th session hitting this wall — but now with a specific unblock condition: retry once
   `gis.sumtercountyfl.gov/sumtergis/rest/services/DevelopmentServices/DevServices_Parcel2/FeatureServer/0`
   stops 500ing, or with a session that can drive the JS/form-POST search on
   myfloridacounty.com/orisearch/60 or civitekflorida.com/ocrs/county/60.
