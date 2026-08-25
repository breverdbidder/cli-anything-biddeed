# GOLD STANDARD holmes B/F — 18th+ session recheck, dispatch `4cb27213-6fb5-44ee-8eeb-d97c1ccc0808` (2026-08-25)

## Result: zero drift, B/F unchanged — row count grew 13→16, structural block re-confirmed live

```sql
select public.pencil_dod_evaluate_county('holmes');
-- A pass(6) B fail(null, "verified=0 closed_sold=0") C fail(68.8, "matched_clean=11")
-- D fail(68.8, "matched_any=11") E pass(100.0) F fail(null, "tier1_sold=0 closed_sold=0")
-- G pass(100.0) H pass(2.4) I pass(100.0) J pass(100.0)
-- auctions_total=16 (up from 13 at the 17th session, dispatch 3b7ed6ea, 2026-08-09)
```

B and F are **identical in pass/fail and metric** to every session since 2026-07-10, including
the 17th session 16 days ago. C/D moved numerically (61.5%→68.8%) only because the denominator
grew from 13→16 rows while the same 8 `matched_clean` rows carried forward plus the 3 new rows —
not in scope for this dispatch (B/F only), noted here for context only.

## Row-count change since 17th session — CONFIRMED, 3 new rows identified

```sql
select count(*) from multi_county_auctions where county='holmes';  -- 16
```

3 new rows, all `created_at=2026-08-10`, `source_platform='holmes_clerk'`,
`parity_source='holmes_clerk_foreclosure'`, `parity_status='PARITY_OK'`, all `auction_status='scheduled'`:

| case_number | auction_date | status |
|---|---|---|
| PARCEL-1709.00-000-000-015.000 | 2026-10-15 | scheduled |
| PARCEL-0531.03-003-028-007.000 | 2026-08-27 | scheduled |
| PARCEL-0531.04-001-093-001.600 | 2026-09-17 | scheduled |

All 3 are **future-dated foreclosures** — confirmed live present on
`holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/` this session (along with a 4th,
`0936.01-004-00C-008.000`, not yet in our DB). None can have a sale outcome yet, so none can
contribute to B ("verified sales") or F ("tier1_sold") regardless of source availability. This
explains why B/F metrics did not change despite the new rows — they are structurally out of scope
for a "closed sale" metric until their auction dates pass.

## Fresh live re-fetch (2026-08-25, before any write) — CONFIRMED

```
GET https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/            -> fetched live
GET https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/               -> fetched live
GET https://holmesclerk.com/courts/foreclosures-tax-deeds/lands-available-for-taxes/ -> fetched live
GET https://holmesclerk.com/sitemap_index.xml                                      -> fetched live
```

- **Foreclosures page**: lists 4 current parcel IDs (0936.01-004-00C-008.000,
  0531.03-003-028-007.000, 0531.04-001-093-001.600, 1709.00-000-000-015.000). Earliest scheduled
  sale shown: **AUGUST 27, 2026**. Zero sale results near 2026-06-11. Zero of the 16 current
  case numbers/legacy IDs from our DB found (they are stored under placeholder or parcel-ID
  identifiers that don't literally match the page's display format, but the parcel IDs for the 3
  new PARCEL-* rows DO match live).
- **Tax-deeds page**: still empty. Boilerplate text now reads
  `"Updated 7/21/2026 there are no sales scheduled at this time-check here for updates"` — this is
  the page's own self-reported "last updated" stamp (unchanged wording, later date than the
  7/2026-vs-8/2026 phrasing seen in earlier sessions is consistent, not a regression). Zero of the
  10 `TD#*` case numbers present.
- **Lands-available-for-taxes page**: `"UPDATED FEBRUARY 2026-THERE ARE NO LOLA FILES AT THIS
  TIME"`. Zero matches for any case number or parcel ID.
- **Site freshness check**: `sitemap_index.xml` → `post-sitemap.xml` `lastmod=2026-08-20T20:43:17+00:00`,
  **5 days before this session** — confirms the site is actively current, not a stale cache (this
  is a fresher lastmod than the 17th session's 2026-08-04 reading, i.e. the site has published
  something new since, but not a Holmes sale disposition per the content checks above).

## Row `123a1bd5-1ea3-4bb4-98ad-a7fc86853e49` — deep-dived this session (new angle, not tried before)

This is the one `auction_status='completed'` row, `auction_date=2026-06-11` (now **75 days past
sale**), `sold_amount=null`. Full row pulled and cross-checked against `foreclosure_outcomes`:

- **case_number is a synthetic placeholder**: `HOLMES-LEGACY-123a1bd5-1ea3-4bb4-98ad-a7fc86853e49`
  — literally the row's own UUID, assigned at `created_at=2026-06-19`. **No real court case number
  was ever captured at ingestion for this foreclosure.** This makes it unmatchable-by-construction
  against any clerk case-number search (holmesclerk.com's site search, myfloridacounty ORI, civitek
  OCRS all key on case number).
- Underlying real data DOES exist on the row: `plaintiff = "FIRST FEDERAL BANK V. AMBER LYNN
  GILLIS A/K/A AMBER GILLIS, KIMBERLY GILLIS, AND ERIC KEITH GILLIS, ET AL."`,
  `property_address = "1826 BECKWOOD LANE, WESTVILLE. FL 32464"`, `parcel_id =
  "1626.00-000-000-011.000"`.
- **New lever tried this session**: searched `holmesclerk.com/?s=Gillis` (defendant surname, since
  case number is useless) — exact result: `"Nothing was found using your search criteria."` No
  archived/results page exists for this defendant name anywhere on the domain's search index.
- **`foreclosure_outcomes` table check**: exactly 1 Holmes row exists —
  `case_number=HOLMES-LEGACY-123a1bd5...`, `outcome='sold'`, `winning_bid=null`,
  `data_source='holmes_clerk_direct'`, `enriched_at='2026-06-25T16:18:20Z'`. **This row predates
  this session** (created 2 months ago, not written now). It records that a sale outcome label
  exists (`outcome='sold'`) but **the dollar amount was never captured and still isn't recoverable
  live** — the placeholder case number blocks any external re-lookup, and holmesclerk.com's live
  pages show nothing for this property today.
- `tax_deed_outcomes` for holmes: 0 rows (unchanged).

**Conclusion**: the placeholder case_number is confirmed as the root cause making this row
permanently unmatchable by case-number lookup on any downstream source. The only remaining path
(defendant-name site search) was tried fresh this session and returned zero results. B/F's
`closed_sold=0` classification is correct — an `outcome='sold'` label without a dollar amount does
not satisfy the litmus, and no dollar amount is recoverable.

## Writes this session

- 1 `summit_chat_dispatch` row, id `4cb27213-6fb5-44ee-8eeb-d97c1ccc0808`, state `closed` (FK
  target for the audit rows, since this session was not launched via normal SUMMIT dispatch flow).
- 2 `gold_standard_ultraloop_audit` rows (B, F only — per this dispatch's scope), both
  `survived=true`, ids 18002/18003.
- **Zero** writes to `multi_county_auctions`, `tax_deed_outcomes`, `foreclosure_outcomes`, or any
  `parity_status`/`parity_source`/`sold_amount` field. No fabrication.

## Verification

```sql
SELECT public.pencil_dod_evaluate_county('holmes');
-- B fail(null, verified=0 closed_sold=0), F fail(null, tier1_sold=0 closed_sold=0)
-- identical to every session since 2026-07-10, including the 17th session 16 days ago.

SELECT letter, survived, created_at FROM gold_standard_ultraloop_audit
  WHERE dispatch_id = '4cb27213-6fb5-44ee-8eeb-d97c1ccc0808' ORDER BY letter;
-- 2 rows (B, F), both survived=true, created_at 2026-08-25T08:08Z
```

Timestamp UTC: 2026-08-25T08:08Z.

## Recommendation for future sessions

Row count will keep growing as new foreclosures are ingested from holmesclerk.com — check whether
any of the 3 new PARCEL-* rows (or the still-outstanding 5 gap TD# cases) have crossed their sale
date and acquired a disposition before assuming zero drift. The `HOLMES-LEGACY-123a1bd5` row's
placeholder case_number is now confirmed as a structural, not transient, blocker — future sessions
should not re-attempt case-number-based lookups for it; only a defendant-name or address-based
lookup on a non-Turnstile-gated source would work, and none is known to exist. Holmes B/F remains
a documented structural ceiling, now confirmed for the 18th+ time.

---
dispatch_id: 4cb27213-6fb5-44ee-8eeb-d97c1ccc0808
