# Gold Standard Shard-12 — Collier County — 2nd Firing Addendum

**Dispatch ID:** `9d04299e-3c67-4ccf-8550-3e0e3272c0f1`
**County:** collier (1-county shard)
**Date:** 2026-07-20
**Relationship to prior firing:** continuation of `GOLD_STANDARD_SHARD12_COLLIER_DISPATCH_9D04299E_SESSION_REPORT.md` (2026-07-19), which left "G — FAR + parking for C-1/C-4/C-5/I" as the #1 item for a future session.

## BEFORE State (fresh query, this session, before any change)

```json
{
  "county": "collier", "auctions_total": 212,
  "A": { "pass": false, "metric": 0, "detail": "fc=0 td=212" },
  "B": { "pass": true, "metric": 100.0 }, "C": { "pass": true, "metric": 100.0 },
  "D": { "pass": true, "metric": 100.0 }, "E": { "pass": true, "metric": 100.0 },
  "F": { "pass": true, "metric": 100.0 },
  "G": { "pass": false, "metric": 0.0, "detail": "density=84.4 far=0.0 pk1000=0.0" },
  "H": { "pass": true, "metric": 9.3 },
  "I": { "pass": true, "metric": 95.8, "detail": "card_complete=203 of 212" },
  "J": { "pass": true, "metric": 100.0 }
}
```

**Score BEFORE: 8/10** (A, G failing). Note: this is one point higher than the brief's stated 7/10 — the prior firing had already flipped I to pass; the dispatch brief text was stale.

## What this session did

1. **A** — re-verified (3rd independent confirmation: 2026-07-03, 2026-07-18, 2026-07-20) that no online scrapeable auction source exists for Collier. Not attempted. No rows fabricated. Logged as a survived audit claim (the *dead-end finding* survives, not the letter).

2. **G** — ran a 3-strategy multi-modal research workflow (agenda/staff-report search, secondary planning literature, deeper Wayback + alternate-host search) followed by independent adversarial verification of every claim, specifically targeting the residual gap left by the prior firing: max_far and parking_per_1000sf for districts C-1, C-4, C-5, Industrial.
   - Found a genuinely new, live, working path: `api.municode.com`'s underlying JSON API (`/CodesContent`), reachable directly even though the public `library.municode.com` viewer is a dead client-side Angular shell. Independently corroborated with a Wayback Machine snapshot of the original 2004 ordinance PDF that a narrower single-URL Wayback check in the prior session had missed.
   - **C-1 and Industrial**: LDC Sec 4.02.01, Table 2 shows a literal **"None"** in the Floor Area Ratio column for both — a clean, unambiguous "not regulated" finding, confirmed by 2 independent refuters via direct visual read of the rendered table (not trusting garbled OCR text extraction). Applied: `far_regulated = false` for both.
   - **Parking, all 4 districts**: LDC Sec 4.05.04, Table 17 is organized *entirely* by land-use category (Office, Retail, Industrial use/activity, Warehouse, etc.) with **zero rows keyed to any zoning district code**. Confirmed independently by 4 separate refuters, each visually reading all 6 table pages. This means a per-district `parking_per_1000sf` value structurally does not exist in Collier's code — parking depends on the use built on a parcel, not which of these 4 districts it sits in. Applied: `pk1000_regulated = false` for all four.
   - **C-4 and C-5 FAR — explicitly NOT applied.** One research strategy claimed "not_regulated" for all four districts uniformly, and one refuter accepted it for C-4. But an independently-working refuter on the byte-identical C-5 row caught a real problem: the FAR cell for C-4/C-5 is not blank/"None" like the genuinely-unregulated rows — it contains real per-use values ("Hotels .60", "Destination resort .80"), with no footnote marker implying an underlying district-wide "None". Treating that as "not regulated" would have discarded real regulatory data under a category-error label that doesn't actually apply here. **I resolved this direct contradiction between the two refuter verdicts myself** (not by vote-counting) by re-reading both pieces of evidence: the C-5 refuter's reasoning (footnote-marker check, sibling-row comparison) is more rigorous and is treated as authoritative for *both* C-4 and C-5. `max_far` stays NULL for both; `far_regulated` is untouched. This is a genuine residual gap, not a value we could respsonsibly fabricate or flag away.

## AFTER State (fresh query, this session, after migration applied live)

```json
{
  "G": { "pass": false, "metric": 0.0, "detail": "density=84.4 far=0.0 pk1000=" }
}
```

**Score AFTER: 8/10 — unchanged.** G was expected to remain failing and does: `far=0.0%` on the 2 remaining FAR-applicable parcels (C-4, C-5) is the binding constraint in `LEAST(density, far, pk1000)`. `pk1000` correctly became NULL (zero applicable parcels left) rather than an accidental 100/pass — confirmed live that Postgres's `LEAST()` ignores NULL inputs rather than propagating them, so this did not create a false pass via division-by-zero.

**This is an honest data-quality correction, not a claimed fix.** Value: it (a) narrows and more accurately documents G's real gap for Collier (down to exactly 2 districts × 1 field: C-4/C-5 FAR), (b) prevents a future session from re-attempting the now-closed C-1/I FAR and all-4-district parking searches, and (c) surfaces a fleet-relevant structural finding: at least one Municode-hosted FL county's LDC organizes parking requirements entirely by land-use, not by zoning district, which means our `zone_standards.parking_per_1000sf` per-district schema cannot represent that county's actual code for any district — worth checking whether this pattern recurs in other Municode-hosted counties before more sessions chase per-district parking data that may not exist in that shape.

## Ultraloop Audit Verdicts (this session)

```
SELECT letter, survived, created_at FROM gold_standard_ultraloop_audit
WHERE dispatch_id='9d04299e-3c67-4ccf-8550-3e0e3272c0f1' ORDER BY created_at;
```
```json
[
  { "letter": "G", "survived": true, "created_at": "2026-07-19 21:28:14.78+00" },
  { "letter": "I", "survived": true, "created_at": "2026-07-19 21:28:30.64+00" },
  { "letter": "G", "survived": true, "created_at": "2026-07-20 01:24:51.63+00" },
  { "letter": "A", "survived": true, "created_at": "2026-07-20 01:24:52.41+00" }
]
```

## Residual Gaps (honest, left for a future session)

- **G — C-4/C-5 FAR (max_far):** the LDC does regulate FAR for these two districts, but only per-use ("Hotels .60", "Destination resort .80"), not as one district-wide figure our current schema can hold. Options for a future session: (a) accept a schema limitation and leave NULL permanently with this documented reasoning, or (b) if the calling system can be extended, model FAR at the (district, use-type) grain instead of (district) alone for Collier — mirrors how the county's own code is actually structured. Do not flip `far_regulated=false` for either district; that would misrepresent real regulatory text as absent.
- **G — MH/RSF-3/4/5 density:** unchanged from the prior firing, still genuinely unknown (no fixed value found in two sessions of searching).
- **I — Everglades City case 26111, 8 Group-2 no-DOR-match folios:** unchanged, still blocked on the same infrastructure gaps documented in the 2026-07-19 report (JS-gated appraiser site, Firecrawl still out of credits as of this session).
- **A:** verified dead end for the third time. No action recommended absent a new online source surfacing independently, or a FOIA/records-request strategy (out of scope for automated scraping).

## Final Scoreboard

**Collier: 8/10**, unchanged this session (A, G still failing; both correctly stay failing — no fabrication was used to move either).

## Migration Shipped

- `supabase/migrations/20260720_gold_standard_shard12_collier_g_far_pk1000_2nd_firing.sql`
