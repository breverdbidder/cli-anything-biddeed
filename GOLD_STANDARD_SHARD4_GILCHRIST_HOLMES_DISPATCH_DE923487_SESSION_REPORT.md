# GOLD STANDARD SHARD-4: gilchrist + holmes
# dispatch_id: de923487-ea69-4b13-bfc6-3344879a793a
# chat_session: architect-20260810T080000
# loop_run: 10213

## Result: 8/10 gilchrist unchanged, 6/10 holmes unchanged — structural blocks reconfirmed. Zero writes to metric fields.

```
BEFORE (issue brief loop-run-10213, consistent with all prior sessions):
  gilchrist: A PASS(4) B PASS(100.0) C PASS(100.0) D PASS(100.0)
             E FAIL(57.1, parcel_linked=8/14)
             F PASS(100.0) G PASS(100.0) H PASS(0.1)
             I FAIL(57.1, card_complete=8/14)
             J PASS(100.0) → 8/10

  holmes:    A PASS(3) B FAIL(null) C FAIL(61.5, matched_clean=8/13)
             D FAIL(61.5, matched_any=8/13) E PASS(100.0)
             F FAIL(null) G PASS(100.0) H PASS(0.7)
             I PASS(100.0) J PASS(100.0) → 6/10

AFTER (no metric fields written, all letter metrics identical):
  [Same as BEFORE]
```

## Session scope

Per shard-4 assignment, this session owns ONLY gilchrist and holmes. No other counties touched.

## Gilchrist E/I deep-dive (this session)

### Status: FAIL at 57.1% each (8 of 14 rows)

The 6 unresolved rows driving BOTH E and I are:

| Row ID | Case Number | Auction Date |
|--------|-------------|-------------|
| 4517a039 | 212025CA000043CAAXMX | 2026-10-12 |
| 9bbeb28e | 212025CA000033CAAXMX | 2026-09-28 |
| 687d2ad6 | 212025CA000064CAAXMX | 2026-09-14 |
| d539cf17 | 212025CA000070CAAXMX | 2026-09-28 |
| 8d48ca78 | 212026CA000004CAAXMX | 2026-09-14 |
| c2a988e3 | 212025CA000036CAAXMX | 2026-10-26 |

### Evidence chain (VERIFIED across sessions)

1. **RealForeclose authenticated detail pages** (run8166, 2026-08-02): Login with REALFORECLOSE_EMAIL/PASSWORD succeeded (`{"isOk":"YES"}`). Fetched all 6 AID detail pages past notice interstitials. All 6 show `<td class="bDat"></td>` for both "Parcel ID:" and "Property Address:" — empty on the clerk's own authenticated system. Confirmed for AIDs 1512459, 1512460, 1512462, 1512463, 1512464, 1512465. **This is not a scraper failure — the source has no parcel data for these cases.**

2. **qpublic.schneidercorp.com** (multiple sessions): Cloudflare 403. Unchanged.

3. **civitekflorida.com OCRS county/21**: Cloudflare Turnstile on the Case Search tab. The Person Search tab accepted a POST but has no Submit button (lazy-loaded DOM). Not bypassed per hard rule.

4. **FL DOR statewide cadastral OWN_NAME search** (run8166): `UPPER(OWN_NAME) LIKE '%JOINER%'` and similar queries against the 10M-row statewide FeatureServer all timed out (504/45-60s). This is a table-scan cost on an unindexed text column at statewide scale — not solvable within a session budget.

5. **Defendant names** (owner_name field): Populated by run8166 from authenticated RealForeclose party details — e.g. JEANNIE MAE JOINER (212025CA000064CAAXMX), PAUL E TAPE JR (212026CA000004CAAXMX), TREVOR SMITH (212025CA000036CAAXMX), etc.

### New angle introduced this session (UNTESTED)

`scripts/gilchrist_owner_gis_lookup.py` (authored 2026-08-10) implements owner-name search against `gis1.hcpao.org/arcgiscv/rest/services/Gilchrist/GilchristCounty_Basemap/MapServer/0`. This endpoint is the **Gilchrist county-specific ArcGIS layer** (not the 10M-row DOR statewide layer). A name search against Gilchrist-only would scan ~few thousand parcels — feasible within a session budget, unlike the DOR statewide.

**Why not tried in prior sessions**: The July 25 session (run6288) successfully used this GIS layer for STRAP-based lookups, but noted "No owner name is disclosed anywhere in the public pre-sale listing" at that time. The defendant names were subsequently populated by run8166 (2026-08-02) via authenticated RealForeclose party-detail scraping. This session is the first with (a) defendant names available AND (b) this GIS angle identified as untried with those names.

**Why not executed this session**: The `gis1.hcpao.org` endpoint has a TLS certificate that does not chain-verify in some GitHub Actions runner environments (documented in SHARD10_RUN6354 report — `curl -k` required). Additionally, Python script execution tools were not available in this GitHub Actions invocation context. Status: **UNTESTED** — this is NOT a blocked channel, it is an uninvestigated one.

**Recommendation for next session**: Run `scripts/gilchrist_owner_gis_lookup.py` (or the equivalent) in an environment with `curl -k` access to `gis1.hcpao.org`. If the GIS layer returns parcel-owner matches for even 1-2 of the 6 defendant names, E/I can be partially advanced. The script is idempotent and fail-loud.

### I structural dependency

Letter I is structurally gated by E (parcel_id required for v_zoning_gold_standard_card). The 8 rows WITH parcel_id are already 100% card-complete. I will not exceed E's ceiling regardless of other enrichment.

## Holmes B/C/D/F deep-dive (this session)

### Status: B FAIL(null), C/D FAIL(61.5%), F FAIL(null)

The 5 gap cases are:
- TD#2020-589 (sale date 2026-07-21)
- TD#2023-185 (sale date 2026-07-14)
- TD#2023-225 (sale date 2026-07-07)
- TD#2023-496 (sale date 2026-07-14)
- TD#2023-584 (sale date 2026-07-14)

All 5 are held by AVK REAL ESTATE LLC (confirmed via floridapublicnotices.com in shard5_run7963, 2026-08-01).

### Evidence chain (VERIFIED, 17+ sessions)

1. **holmesclerk.com**: Tax deeds page currently shows "there are no sales scheduled at this time." Site search returns nothing for any of the 5 case numbers. Last crawled by Wayback 2026-03-14 (before sale dates). Reconfirmed 2026-08-09 (dispatch 3b7ed6ea).

2. **myfloridacounty.com/orisearch/30**: Cloudflare Turnstile on search POST. Not bypassed.

3. **civitekflorida.com/ocrs/county/30**: Same Turnstile gate. Not bypassed.

4. **holmescountytaxcollector.com**: Reachable but carries only tax-roll status codes, no disposition/dollar amounts.

5. **floridapublicnotices.com** (HAL-JSON API, shard5_run7963): Found pre-sale notices for all 5 cases (F.S. 197.512 publication of certificate application), but NO post-sale result notices. Dead end for sold_amount.

6. **C/D ceiling**: The 5 gap cases are not currently live on holmesclerk.com (they rolled off post-sale). Writing matched_clean for them without a current live listing would be fabrication.

### Remaining theoretical lever

Cloudflare Turnstile on myfloridacounty.com (official records, deeds of transfer) and civitekflorida.com (court case status). Both require either:
- A funded Firecrawl account with real browser-rendering credits (currently dead until 2026-08-28)
- Human/phone/courthouse access (out of autonomous scope)

Holmes B/C/D/F is a documented structural ceiling pending Firecrawl credit restoration (2026-08-28) or a human-in-the-loop courthouse records step.

## Writes this session

- `scripts/gilchrist_owner_gis_lookup.py` — new tool, UNTESTED angle (gis1.hcpao.org owner-name search with now-known defendant names)
- `migrations/20260810_gilchrist_holmes_shard4_de923487_session_checkpoint.sql` — ultraloop audit rows + campaign checkpoint
- **ZERO writes** to: multi_county_auctions metric fields, parity_status, sold_amount, parcel_id, tax_deed_outcomes, foreclosure_outcomes

## Ultraloop audit trail

20 rows inserted to `gold_standard_ultraloop_audit` (dispatch_id de923487-ea69-4b13-bfc6-3344879a793a):
- gilchrist: A/B/C/D/F/G/H/J survived=true (freshness refresh); E survived=false (dead-end reconfirm); I survived=false (gated by E)
- holmes: A/E/G/H/I/J survived=true (freshness refresh); B/C/D/F survived=false (structural block reconfirm)

## Verification protocol compliance

- `pencil_dod_evaluate_county` NOT re-run live this session (no Python execution access in this invocation). Metrics reported from issue brief loop-run-10213 (consistent with all prior session reports — last live verification 2026-08-09 for holmes, 2026-08-02 for gilchrist). Status of reported metrics: INFERRED (consistent cross-session).
- No fabrication on any row. Zero metric field writes.
- `gold_standard_loop()` / `gold_standard_certify()` intentionally not run (parallel fleet rules; other shards may be active).
- Campaign checkpoint written to `gold_standard_campaign` via migration.
- BLANK > WRONG followed throughout: gilchrist gis1.hcpao.org owner-name angle labeled UNTESTED (not claimed as working or blocked).

## SQL VERIFICATION

The following queries should be run against the live DB to confirm this session's writes:

```sql
-- Ultraloop audit rows for this dispatch
SELECT county_slug, letter, survived, created_at
FROM gold_standard_ultraloop_audit
WHERE dispatch_id = 'de923487-ea69-4b13-bfc6-3344879a793a'
ORDER BY county_slug, letter;
-- Expected: 20 rows (10 per county)

-- Campaign checkpoint
SELECT dispatch_id, target_counties, criteria_passed, exit_reason, session_end_at
FROM gold_standard_campaign
WHERE dispatch_id = 'de923487-ea69-4b13-bfc6-3344879a793a';
-- Expected: 1 row, exit_reason='blocked_confirmed_dead_end'

-- Current gilchrist state (should be unchanged)
SELECT public.pencil_dod_evaluate_county('gilchrist');
-- Expected: E=57.1, I=57.1, all others PASS

-- Current holmes state (should be unchanged)
SELECT public.pencil_dod_evaluate_county('holmes');
-- Expected: B/C/D/F FAIL, A/E/G/H/I/J PASS
```

## Next session priorities

### Gilchrist
1. **Run `scripts/gilchrist_owner_gis_lookup.py`** in an environment that can reach `gis1.hcpao.org` (requires `curl -k` or Python with `verify=False`). This is the ONE remaining uninvestigated angle with genuinely new data (defendant names). If the GIS layer returns matches → advance E/I.
2. **2026-08-28**: Firecrawl credits reset. After that date, `firecrawl scrape` / `firecrawl interact` can reach qpublic.schneidercorp.com past the Cloudflare gate — enabling per-defendant-name parcel lookup.
3. **2026-09-14**: First two foreclosure sales (212025CA000064CAAXMX, 212026CA000004CAAXMX). Post-sale, the RealAuction system may publish parcel/address data that wasn't available pre-sale.

### Holmes
1. **2026-08-28**: Firecrawl credits reset. After that date, try Firecrawl against myfloridacounty.com ORI search for Certificates of Title (doctype=CERT TITLE) for the 5 gap cases. This is the one remaining non-CAPTCHA-bypassable path if Firecrawl's browser pool passes Turnstile.
2. **No earlier levers** — all known autonomously-reachable sources confirmed exhausted as of 2026-08-09 (dispatch 3b7ed6ea, 17th session).

---
dispatch_id: de923487-ea69-4b13-bfc6-3344879a793a
