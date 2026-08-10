# GOLD STANDARD shard-4: gilchrist + holmes (dispatch `de923487-ea69-4b13-bfc6-3344879a793a`, loop run 10213)

## Result summary

No letter flipped PASS this session. One verified data-quality correction applied and confirmed live. Everything else was genuinely exhausted, not skipped — see evidence below and `supabase/migrations/20260810_gold_standard_shard4_gilchrist_holmes_de923487_session.sql`.

## gilchrist (8/10, unchanged)

| Before (brief) | After (live, session end) |
|---|---|
| E FAIL 57.1% (parcel_linked=8) | E FAIL 57.1% (parcel_linked=8) |
| I FAIL 57.1% (card_complete=8 of 14) | I FAIL 57.1% (card_complete=8 of 14) |

6th+ consecutive session hitting the same wall for the 6 pre-sale foreclosure cases with no address/parcel. Re-verified live today: FL GIO ArcGIS `CO_NO=21` queries time out (>2min, 6 owner-name variants tried), `gilchrist.fl.us`/GIS subdomains are Cloudflare-gated or unreachable, Firecrawl account is at -9/1000 credits (exhausted). No fabricated writes.

## holmes (6/10, unchanged pass-count; 1 data-quality fix)

| Before (brief) | After (live, session end) |
|---|---|
| B FAIL null (verified=0 closed_sold=0) | B FAIL null (unchanged) |
| C FAIL 61.5% (matched_clean=8) | C FAIL 61.5% (unchanged) |
| D FAIL 61.5% (matched_any=8) | D FAIL 61.5% (unchanged) |
| F FAIL null (tier1_sold=0 closed_sold=0) | F FAIL null (unchanged) |

Root cause found this session: `closed_sold=0` because zero holmes rows have `sold_amount` — Holmes County Clerk runs tax-deed and foreclosure sales **in person only** with no online results/outcome page (confirmed via the clerk's own site text). The one channel that could supply independently-sourced outcomes — `myfloridacounty.com/orisearch/30` (Official Records search) — is Cloudflare Turnstile-gated on the query step, same sitekey (`0x4AAAAAAA64PTBePmuGbrkR`) already confirmed blocking Hamilton county's identical search in a prior session. GovEase/TaxSmartWeb don't cover Holmes. Wayback Machine has no capture of the relevant July 2026 window.

**Fix applied:** row `3ca8afb6-fe6d-4c71-bf8a-51df49eebfc3` (TODAR) had a stale `auction_date` of 2026-07-23 (already past). Live re-fetch of `holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/` today confirms this case is genuinely still upcoming, continued to **August 27, 2026** (judgment $104,852.69 and parcel_id 0936.01-004-00C-008.000 both exact matches to our DB, confirming this is the same case, not a coincidental name match). Corrected via PostgREST PATCH, verified via round-trip read. Does not move any A–J letter (none reference `auction_date`) but is a real, sourced correction.

Two of three synthetic `HOLMES-LEGACY-<uuid>` case-number rows (GILLIS AMBER & ERIC, JOHNSON JEFFERY) remain unresolved to real court case numbers — both have aged off the live foreclosure calendar, and UniCourt/Trellis.law/CourtListener/floridapublicnotices.com all failed to surface them.

## ULTRACODE workflow

Ran a 3-agent research fan-out (Wayback/newspaper-archive sweep, court-record aggregator sweep for the 2 unresolved case numbers, alternate ORI/qpublic access-path probe) followed by 3 independent adversarial verifiers. **All 3 verifiers returned NO ACTIONABLE FINDING.** One verifier caught and flagged a hallucinated address fabricated by its own research agent — discarded, never written to the DB. No claim survived review, so no additional writes were made beyond the one TODAR correction.

## Verification protocol (pasted live output)

```
gilchrist final: {"A":{"pass":true,"metric":4},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":false,"metric":57.1},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":57.1},"J":{"pass":true,"metric":100.0}}

holmes final: {"A":{"pass":true,"metric":3},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":61.5},"D":{"pass":false,"metric":61.5},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0}}
```

Identical to session-start baseline for every letter except the auction_date correction (which is outside the A–J metric set). No regression, no fabricated improvement.

## Close-out

- `gold_standard_ultraloop_audit`: 6 rows written (gilchrist E/I, holmes B/C/D/F), all `survived=true` (structural-block reconfirmations, not false claims).
- `gold_standard_campaign` id=4054: `criteria_passed` filled per-county, `exit_reason='timeout'`, `session_end_at` set.

## Next-session levers (not exhausted)

1. A funded Firecrawl account or Turnstile-capable remote browser would unblock **both** counties' hardest letters — gilchrist's qpublic/civitek gates and holmes's myfloridacounty ORI gate are the same class of block.
2. Direct phone/in-person clerk contact (Gilchrist 352-463-3170; Holmes 850-547-1100) would resolve the 6 gilchrist owner-name lookups and the 2 unresolved holmes case numbers directly — outside autonomous scope this session.
3. Retry FL GIO ArcGIS `CO_NO=21` at a different time of day — still inconsistent/timing-out across 2+ sessions, never confirmed as a permanent block.
