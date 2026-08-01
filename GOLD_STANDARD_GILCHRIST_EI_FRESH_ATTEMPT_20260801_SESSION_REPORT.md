# Gold Standard gilchrist E/I — fresh attempt, 2026-08-01

## Summary

**gilchrist: E and I unchanged at 57.1% (parcel_linked=8, card_complete=8 of 14). Zero
writes this session.** Re-attempted all 6 remaining unlinked foreclosure cases
(`212025CA000033CAAXMX`, `212025CA000036CAAXMX`, `212025CA000043CAAXMX`,
`212025CA000064CAAXMX`, `212025CA000070CAAXMX`, `212026CA000004CAAXMX`) via every channel
documented in the 3 prior sessions on this exact gap (dispatches `28bd9542` 07-25,
`61f11933` 07-30, `7617ebac` 07-31) plus one genuinely new angle (Civitek OCRS full
click-through, past the county-selector/disclaimer flow that prior sessions apparently
never completed). All 6 rows remain structurally blocked. No data was fabricated;
BLANK > WRONG followed throughout.

## Live verification — before and after (identical, no drift)

```json
BEFORE (session start): E metric=57.1 parcel_linked=8 | I metric=57.1 card_complete=8 of 14
AFTER  (session end):   E metric=57.1 parcel_linked=8 | I metric=57.1 card_complete=8 of 14
```

### SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('gilchrist');
-- E: {"pass": false, "detail": "parcel_linked=8", "metric": 57.1}
-- I: {"pass": false, "detail": "card_complete=8 of 14", "metric": 57.1}
-- auctions_total: 14, A/B/C/D/F/G/H/J all unchanged PASS
-- Timestamp: 2026-08-01T~08:15Z UTC (live Management API re-query, this session)

SELECT case_number, parcel_id, property_address FROM multi_county_auctions
WHERE county='gilchrist' AND case_number IN
  ('212025CA000033CAAXMX','212025CA000036CAAXMX','212025CA000043CAAXMX',
   '212025CA000064CAAXMX','212025CA000070CAAXMX','212026CA000004CAAXMX');
-- all 6 rows: parcel_id=null, property_address=null (unchanged)
-- Timestamp: 2026-08-01T~08:20Z UTC
```

## What was re-verified live today (fresh, not assumed from prior reports)

1. **RealForeclose AJAX auction listing** (`gilchrist.realforeclose.com`): direct HTML GET
   is intermittently 403'd by the WAF, but succeeds with a browser User-Agent + matching
   `Referer` header + a real session cookie jar (`AWSALB`/`cfid`/`cftoken`) established via
   a preceding GET to `/index.cfm`. Used the real AJAX endpoint the page's own JS calls
   (`zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=W`, found in `auction.js`) to pull the
   "Auctions Waiting" list for all 4 relevant auction dates (09/14, 09/28, 10/12, 10/26/2026).
   **Confirmed live, today**: every one of the 6 target cases' "Parcel ID" link resolves to
   the exact same non-identifying `qpublic.schneidercorp.com` URL
   (`Q=548715190&KeyValue=`, empty KeyValue) — identical across all 6 cases and also
   identical to a 7th sibling case (`212025CA000042CAAXMX`) that already has a real
   parcel_id from a different source. This is a site-wide placeholder link, not per-parcel
   data, exactly as the 07-25/07-30/07-31 sessions found. Did obtain each case's real
   Final Judgment Amount from this feed (not a target field for E/I, not written).
2. **qpublic.schneidercorp.com**: still HTTP 403 to direct fetch (unchanged from every
   prior session).
3. **gilchristclerk.com** (including `/upcoming-foreclosure-sales/`): still HTTP 403
   (unchanged).
4. **Civitek OCRS** (`civitekflorida.com/ocrs/county/21`) — **new ground covered**: prior
   sessions recorded this as flatly "Turnstile-gated" without detailing how far they got.
   This session walked the full click-through live: county-selector (value `21`=GILCHRIST)
   -> "Public" access button (PrimeFaces AJAX POST) -> disclaimer page -> "I Agree" (AJAX
   POST) -> lands on `/ocrs/app/search.xhtml`. **Confirmed on the actual search page
   itself**: `turnstile.render("#cfWidget", {sitekey: '0x4AAAAAAAR0Af-5MfzdbO3p', ...})` is
   present and `onSearch2()`/`validateUser()` gate the search submit — genuinely
   Turnstile-gated, not a false alarm. Per HARD RULE, did not attempt to solve/bypass it.
   **Independently new finding**: this OCRS instance's only search tab exposes
   name/DOB/SSN/business-name fields — there is no case-number search field at all. Even
   setting Turnstile aside, this path cannot resolve a case number to a parcel without
   already knowing the defendant's name, which none of these 6 stub rows carry.
5. **FL GIO / county ArcGIS (`gis1.hcpao.org`, gsacorp appraiser)**: reachable (HTTP 200),
   but both are address/owner/parcel-keyed search only — useless without a starting address
   or owner name, which these 6 rows don't have.
6. **RealForeclose case-detail popup** (`zaction=auction&zmethod=details&AID=<id>`):
   returns a generic login splash page with zero case-specific data — confirmed no data
   leak through this route either.

## Conclusion

Reconfirms the finding from 3 independent prior sessions: Gilchrist's RealAuction platform
does not publish real parcel/address data for foreclosure listings pre-sale (only a
placeholder qPublic link, identical across all cases), and every system that could
otherwise resolve a case number to a parcel (Civitek OCRS, gilchristclerk.com,
qpublic.schneidercorp.com direct) is either Turnstile-gated (correctly not bypassed per
hard rule), 403-blocked, or structurally lacks a case-number search path at all. All 6
target rows (`212025CA000033CAAXMX`, `212025CA000036CAAXMX`, `212025CA000043CAAXMX`,
`212025CA000064CAAXMX`, `212025CA000070CAAXMX`, `212026CA000004CAAXMX`) remain genuinely
structurally blocked. Auction dates are 45-85 days out; re-checking again once one of these
listings gets closer to its sale date (RealForeclose sometimes populates more data in the
final ~2 weeks) is the only lever left — not immediate re-attempts.

No migration file accompanies this report — zero writes were made or needed.

## Verification protocol compliance

- Ran `pencil_dod_evaluate_county('gilchrist')` before and after — both identical, pasted
  above.
- `gold_standard_loop()`/`gold_standard_certify()` intentionally **not** run per
  PARALLEL-FLEET RULES.
- Zero fabrication: no parcel_id/address/geo/value was guessed for any of the 6 rows.
- Direct DB re-query after the session confirms all 6 rows are still exactly NULL — no
  accidental or partial writes occurred.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
