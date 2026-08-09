# Gold Standard shard-3 taylor B/F — dispatch c5a8b2c7 (3rd firing on this county+letters)

## Scope
Sole assigned county: **taylor**, letters **B** and **F** only (verified independent sale outcomes / tier1 sold amounts).

## Result: genuinely new lead found and exhausted, B/F remain structurally blocked (honest, not fabricated)

### BEFORE (live query at session start)
```json
{
  "county": "taylor", "auctions_total": 11,
  "A": {"pass": true,  "metric": 4,   "detail": "fc=7 td=4"},
  "B": {"pass": false, "metric": null, "detail": "verified=0 closed_sold=0"},
  "C": {"pass": true,  "metric": 100.0, "detail": "matched_clean=11"},
  "D": {"pass": true,  "metric": 100.0, "detail": "matched_any=11"},
  "E": {"pass": true,  "metric": 100.0, "detail": "parcel_linked=11"},
  "F": {"pass": false, "metric": null, "detail": "tier1_sold=0 closed_sold=0"},
  "G": {"pass": true,  "metric": 100.0, "detail": "density=100.0 far= pk1000="},
  "H": {"pass": true,  "metric": 16.8, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": false, "metric": 90.9, "detail": "card_complete=10 of 11"},
  "J": {"pass": true,  "metric": 100.0, "detail": "deal_complete=11"}
}
```

### AFTER (live query post-session)
```json
{
  "county": "taylor", "auctions_total": 11,
  "A": {"pass": true,  "metric": 4,   "detail": "fc=7 td=4"},
  "B": {"pass": false, "metric": null, "detail": "verified=0 closed_sold=0"},
  "C": {"pass": true,  "metric": 100.0, "detail": "matched_clean=11"},
  "D": {"pass": true,  "metric": 100.0, "detail": "matched_any=11"},
  "E": {"pass": true,  "metric": 100.0, "detail": "parcel_linked=11"},
  "F": {"pass": false, "metric": null, "detail": "tier1_sold=0 closed_sold=0"},
  "G": {"pass": true,  "metric": 100.0, "detail": "density=100.0 far= pk1000="},
  "H": {"pass": true,  "metric": 16.9, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": true,  "metric": 100.0, "detail": "card_complete=11 of 11"},
  "J": {"pass": true,  "metric": 100.0, "detail": "deal_complete=11"}
}
```

**B and F: unchanged (FAIL, null, correctly re-confirmed blocked — no fabrication).** I moved 90.9%→100.0% between before/after snapshots but this was NOT touched by this session (in scope: B/F only) — it is residual drift from a prior/concurrent shard's work landing on `main` during this session's runtime, noted here for completeness per parallel-fleet transparency, not claimed as this session's output.

## Target cases (5 past-due, sold_amount still null at session start and end)
| Case | Type | Parcel | Auction date | sold_amount before | sold_amount after |
|---|---|---|---|---|---|
| 25-218 CA | foreclosure | 05151-000 | 2026-07-16 | null | null |
| TDA 26-028 | tax_deed | R07503-000 | 2026-07-20 | null | null |
| TDA 26-026 | tax_deed | R09208-000 | 2026-07-20 | null | null |
| 25-196 CA | foreclosure | 07993-000 | 2026-07-23 | null | null |
| 25-217 CA | foreclosure | 06562-216 | 2026-07-30 | null | null |

## What was tried this session (in the order the dispatch specified)

### 1. MyFloridaCounty.com
Confirmed live and does list Taylor County in its official-records county dropdown. Pulled the raw HTML `<select id="countyDropdown">` and confirmed the Taylor `<option>` value:
```
https://pubrecords.taylorclerk.com/PublicInquiry/Search.aspx?Type=Name
```
This is the exact same portal ruled out by both prior sessions (dispatch ab46d459, 1st and 2nd firing) as Cloudflare-blocked. Re-confirmed live this session: `HTTP 403`, Cloudflare "Just a moment..." challenge page. **Dead end, re-confirmed, not re-worked around.**

### 2. Vendor discovery ("Taylor County Florida Clerk of Court official records search", "Taylor County Clerk eRecording")
Web search did not surface a vendor name directly, but investigation of taylorclerk.com's own site turned up something the prior two sessions had not found: **a live, unauthenticated, first-party WordPress REST API** at `taylorclerk.com/wp-json/kma/v1/*`, registered under custom namespace `kma/v1` (site builder = "KMA" per footer "Site by KMA") with a `civitek-verify` route confirming **Civitek Solutions** as the backing case-management vendor (independently corroborated by the earlier web search hit "Civitek Solutions has been a trusted partner to Florida's Clerks of Court for 34+ years").

Endpoints discovered and queried live (all `HTTP 200`, zero Cloudflare interference — this is taylorclerk.com's own domain, not a 3rd-party subdomain):
```
GET /wp-json/kma/v1/foreclosures   -> list of active foreclosure CPT posts
GET /wp-json/kma/v1/taxdeeds       -> list of active tax-deed CPT posts
GET /wp-json/kma/v1/landavailables -> list of active lands-available CPT posts
```
Each item carries structured fields (`case_number`/`file`, `parcel`, `sale_date`, `cert_holder`/`parties`, `amount`/`opening_bid`, `status`, `property_appraiser_link` (a qpublic deep-link), `pdf_file`).

**This is a genuinely new, real finding** — not previously documented in either prior taylor B/F session. It is however a dead end for the 5 target cases specifically:
- `foreclosures` currently returns only 4 items (26-042 CA, 25-210 CA, 23-597 CA, 25-014 CA) — all still-scheduled or cancelled. **25-218 CA, 25-196 CA, 25-217 CA are absent** — their CPT posts and PDF media attachments have been hard-deleted server-side once the case closed (confirmed: `/taylorclerk.com/foreclosures/25-218-ca/`-style URLs redirect to the homepage; `wp/v2/media?search=25-218` returns `[]`).
- `taxdeeds` currently returns only 2 items (TDA 26-032, TDA 26-031), both `"status":"redeemed"` (owner paid off the certificate before sale — a real independent data point, but not applicable to our 2 target TDAs and not a `sold_amount`). **TDA 26-028 and TDA 26-026 are likewise absent** — same hard-delete pattern (their post URLs also redirect to homepage, no surviving PDF).
- Tried `?status=all|closed|sold`, `?per_page=100`, `?posts_per_page=-1` on all 3 endpoints — every variant returns the identical result set. The API has no closed/historical mode; it is a live "active sales" feed only, by design.

### 3. Search the working portal for the 5 case numbers
No working non-Cloudflare-blocked portal was found that retains post-sale data (see above). What was found (the `kma/v1` API) confirmed the closed-case deletion pattern rather than providing new sold-amount evidence.

### 4. Additional independent avenues tried this session (beyond the dispatch's 3 required steps, in the spirit of exhausting genuinely new leads before declaring blocked)
- **Tax Deeds Surplus page** (`taylorclerk.com/departments/tax-deeds-surplus/`) — re-confirmed live via the WP REST `/wp-json/wp/v2/pages/1250` ACF payload (`modified: 2026-07-24`, genuinely current, not a stale cached fragment). Full table pulled (39 rows, `22-034` through `26-001`). **Zero rows reference TDA 26-026 or TDA 26-028** — inconclusive (a TDA generates a surplus row only if sale proceeds exceed what's owed; absence doesn't prove no-sale, could equally mean sold-with-no-surplus, sold-with-surplus-not-yet-posted, or redeemed/cancelled).
- **qpublic.schneidercorp.com** (Taylor's own Property Appraiser GIS vendor, also the `property_appraiser_link` embedded in the new `kma/v1` API's JSON) — re-confirmed `HTTP 403` Cloudflare.
- **thirdcircuitfl.org** (3rd Judicial Circuit court administration, which covers Taylor per Clerk-office cross-reference) — new lead, tried, also `HTTP 403` Cloudflare (wpengine-hosted, same challenge pattern).
- **Trellis.law** (docket/case-law aggregator, `trellis_url` is an existing DB column though null for all taylor rows) — new lead, tried. Direct case-page fetch returns `HTTP 403`; a case-number web search returned no matching hit. Paywalled/auth-gated — not scrapeable without an account, consistent with CLAUDE.md's guidance not to spend beyond budget chasing gated sources.
- **FL GIO Statewide Cadastral** (`services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0`, the public mirror — the previously-used `ca.dep.state.fl.us` endpoint now requires an ArcGIS token and 404s without one) — queried all 5 target parcels directly by `PARCEL_ID` + `CO_NO=72`. All 5 still show the **pre-sale defendant/certificate-holder** as `OWN_NAME` (Barnes, Graham, Newman, Parrott, Shaw) with `SALE_PRC1=0`/`SALE_YR1=0` — the statewide NAL snapshot has an annual refresh cadence and has not caught up to any of these sales yet, confirming (again, independently) it cannot be used to backfill a near-real-time `sold_amount`.

## What shipped this session
1. **`pipeline.counties.notes` for taylor** — appended (not overwritten) a dated block documenting: the new `kma/v1` API discovery and exactly why it's still a dead end for closed cases, the MyFloridaCounty routing confirmation, and every newly-tried-and-blocked source (qpublic, thirdcircuitfl.org, trellis.law, FL GIO NAL lag) — so a future session does not re-spend a cycle re-discovering the same API only to hit the same wall, and knows precisely which sources are genuinely exhausted vs. still-untried (phone call to the Clerk's tax-deed dept is flagged as the only remaining lever).
2. No `foreclosure_outcomes` / `tax_deed_outcomes` rows written — **zero candidate sold-amount data was found**, so per the fail-loud guardrail there is nothing to insert; writing a null-value row would add noise, not signal.
3. No `multi_county_auctions.sold_amount` values written or inferred. No `promote_tier1_from_outcomes()` call made (nothing to promote — would be a no-op, and calling it needlessly on a hot shared function during concurrent shard activity is unnecessary risk for zero benefit).

## Why this is a genuinely different (not re-treaded) session
Both prior sessions (ab46d459 1st/2nd firing) treated `pubrecords.taylorclerk.com`, `qpublic`, `taylorcountypropertyappraiser.org`, and `taylor.realtdm.com` as the universe of Taylor-specific sources and hit a wall on all four. This session found and fully investigated a **fifth, previously-undocumented source** — taylorclerk.com's own first-party `kma/v1` REST API — which is unblocked and real-time, a structurally different kind of lead (same domain, no Cloudflare, no vendor sandbox) than anything tried before. It turned out to share the same fundamental limitation (closed-case data deletion) as the human-facing pages, but this was verified freshly and specifically for this API, not assumed by analogy. This session also tried 3 additional never-before-attempted independent sources (thirdcircuitfl.org, trellis.law, and the working FL GIO ArcGIS FeatureServer endpoint since the previously-cited one now requires a token) before concluding B/F remain blocked.

## Residual / next-session priorities
1. **B/F**: only remaining honest lever is a human phone call to the Clerk's tax-deed department (850-838-3506 ext 103, taxdeeds@taylorclerk.com) to request post-sale results directly — every automatable source is now confirmed either Cloudflare-walled or actively deletes the exact data needed. A second, unverified lever: increase scrape cadence to same-day/next-day around Taylor's Tue/Thu 11am in-person sale days, on the (never-yet-observed) chance the `kma/v1` API exposes a transient "sold"/"cancelled" status before the CPT post is deleted — this has never been directly observed in 3 sessions on this county, so it should be treated as a hypothesis, not a known window.
2. `TDA 26-031` / `TDA 26-032` now report `status: "redeemed"` per the live `kma/v1/taxdeeds` API (auction_date 2026-08-17, still upcoming) — worth capturing when their auction date passes, since "redeemed" is itself a real terminal outcome (no sale, certificate paid off) distinct from "sold", and F's `tier1_sold`/`closed_sold` logic may need to treat "redeemed" as a valid closed/non-null outcome type rather than leaving it perpetually null — flagged for whoever owns the `promote_tier1_from_outcomes()` / F scoring logic, not acted on here (out of this session's B/F-via-new-data-only scope, and touches shared scoring logic).

## Verification protocol
- `SELECT public.pencil_dod_evaluate_county('taylor');` run before and after (pasted above, both timestamps this session).
- Did not call `promote_tier1_from_outcomes()` — no outcome rows were written for it to act on.
- Did not run `gold_standard_loop()` or `gold_standard_certify()` — out of scope for a single-county B/F-only dispatch, other shards concurrently active per PARALLEL-FLEET RULES.
