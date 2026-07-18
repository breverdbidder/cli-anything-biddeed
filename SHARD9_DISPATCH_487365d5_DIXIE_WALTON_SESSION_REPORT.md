# GOLD STANDARD SHARD-9 — dixie + walton — dispatch 487365d5

## Duplicate-dispatch note

This dispatch (`487365d5-71dc-4492-b06a-a58da6810cb8`) had already been worked in a prior
session, but that work landed on an orphaned side branch
(`origin/claude/issue-12747-20260718-1601`, commit `b93ad64f`) that never merged to `main` —
a SHIP-TO-MAIN MANDATE violation. This session recovered that work, ran it for real against
the live DB (it had never actually been executed — honesty marker on the orphaned commit
read "INFERRED: specific new-row counts (UNTESTED pending live application)"), independently
re-diagnosed the dixie claim rather than trusting it, found and fixed real bugs, caught and
fixed a self-inflicted regression, and adversarially verified every claim with an independent
refuter agent before shipping.

## dixie: 8/10 → 8/10 (no letter flipped, real metric + accuracy improvement)

**Before → After (`pencil_dod_evaluate_county('dixie')`):**
| Letter | Before | After |
|---|---|---|
| C | FAIL 75.0% (24/32) | FAIL 78.1% (25/32) |
| D | FAIL 75.0% (24/32) | FAIL 78.1% (25/32) |
| B | PASS 100.0% (11/11) | PASS 100.0% (12/12) |
| F | PASS 100.0% (11/11) | PASS 100.0% (12/12) |
| A,E,G,H,I,J | PASS (unchanged) | PASS (unchanged) |

**What was found and fixed:**
The orphaned branch's claim of a "structural ceiling of 30/32=93.75%" was **arithmetically
self-contradictory** — its own stated facts (2 future rows + 6 gap rows = 8 unmatchable of 32)
imply a ceiling of 24/32=75.0%, exactly where the county already was, not 30/32. Independent
re-investigation of all 8 unmatched rows via live `dixieclerk.com` fetches found:
- 6 rows (Aug 2025 tax deeds, `DIXIE-SYNTH-*` case numbers): genuinely unresolved on the live
  source for 11+ months. Confirmed via two independent fresh fetches. **Genuine gap.**
- 1 row (`DIXIE-SYNTH-01-10-13-4512-0000-0820`, 2026-07-13 tax deed): the prior session's
  "future auction" framing was **stale** — today is 2026-07-18, the sale already happened.
  Live source shows `status=sold, sold_amount=$36,600.00, cert_holder=Jesus Santana`.
  **Fixed**: real `tax_deed_outcomes` row inserted, parity re-run, `matched_clean`.
- 1 row (`15-2023-CA-57`, 2026-07-21 foreclosure): genuinely 3 days out, confirmed future.
- **Side discovery**: re-running the sanctioned parity matcher exposed 9 already-matched rows
  with a stale `auction_status='sold'` label while their real `tax_deed_outcomes.outcome`
  was `redeemed` — corrected, which is why B/F moved 11→12 as a side benefit.

**Honest ceiling this session: 78.1% (25/32), not 93.75%.** Corrected ultraloop_audit rows
(6774, 6775) explicitly refute the prior wrong claim. Remaining 7-row gap (6 stale + 1 future)
is genuinely unresolvable without a new disposition source — `BLANK > WRONG`.

**Adversarial verification: CONFIRMED.** Independent refuter re-ran the live RPC, re-fetched
dixieclerk.com twice more, tried 4 additional angles to break the "genuine gap" claim
(qPublic, WP search, WP REST API, sitemap) — all dead-ended identically. No fabrication found.

Migration: `supabase/migrations/20260718p_gold_standard_dixie_cd_structural_ceiling_refutation_487365d5.sql`
(commit `1db63f90`).

## walton: 7/10 → 7/10 (no letter flipped, real bugs fixed + self-inflicted regression caught+fixed)

**Before → After (`pencil_dod_evaluate_county('walton')`):**
| Letter | Before | After |
|---|---|---|
| C | FAIL 86.0% (37/43) | FAIL 86.0% (37/43) — unchanged, genuine |
| D | FAIL 86.0% (37/43) | FAIL 86.0% (37/43) — unchanged, genuine |
| I | FAIL 83.7% (36/43) | FAIL 83.7% (36/43) — unchanged, real blocker found |
| G | PASS 100.0% | **regressed to FAIL 89.2% mid-session, then restored to PASS 100.0%** |
| A,B,E,F,H,J | PASS (unchanged) | PASS (unchanged) |

**What was found and fixed:**
Restored the already-diagnosed (but never executed) fix from the orphaned branch
(`scripts/shard9_walton_cd_i_backfill.py`, `supabase/migrations/20260718_shard9_walton_cd_i_dixie_structural_ceiling.sql`)
and ran it live for the first time. It had **three real bugs** that made the I-enrichment
step a complete no-op on first run:
1. Wrong EnerGov field names (`OWNNAME`/`SITEADDR` don't exist; real field is `OWNER_NAME`,
   no situs-address field exists at all) — every ArcGIS query got HTTP 400.
2. `zoning_districts` INSERT referenced a nonexistent `data_source` column (real column:
   `description`) — every insert got PGRST204.
3. Double URL-encoding in `ensure_zoning_district`'s existence check caused it to never find
   pre-existing rows, colliding on the unique constraint (409).

All three fixed inline (`HOTFIX 2026-07-18` comments in the script). Re-run produced real
results: 6 C/D `parity_source` relabels (all independently confirmed to genuinely join
`realforeclose_aids`, no ghost-success — but all 6 were already `matched_clean`, so the
metric didn't move), 3 geo backfills, 4 new `parcel_zones`/`zoning_districts` entries
(zone codes independently re-verified live against ArcGIS).

**Self-inflicted G regression caught and fixed same session (P0 rule):** the 4 new
`zoning_districts` rows had no `zone_standards`, dragging walton's density coverage from
100.0%→89.2% (FAIL) as a real side effect. Fixed with **real, verbatim ordinance figures**
from the Walton County Comprehensive Plan Future Land Use Element (adopted 12/11/18, amended
4/27/2021 — fetched live, parsed with `pypdf`, not guessed):
- Small Neighborhood: 10 du/ac, 0.50 FAR (Policy L-1.6.2A)
- Urban Residential: 4 du/ac, 0.50 FAR (Policy L-1.4.1A)
- Coastal Center: 8 du/ac, 1.50 FAR (Policy L-1.6.2C)
- Low Density Residential 4/1: 4 du/ac, FAR not applicable — "no nonresidential intensity is
  permitted" (Policy L-1.4.1D)

G verified restored to `density=100.0 far=100.0, PASS` live after the fix.

**Genuine remaining blockers (not fabricated fixes):**
- C/D: 6 still-unmatched rows are all future auctions (2026-07-23/24) with zero entries in
  `realforeclose_aids` yet — structurally identical to dixie's pattern, not fixable until
  closer to sale date.
- I: `pencil_dod_evaluate_county`'s card-complete formula also requires
  `COALESCE(assessed_value, market_value) IS NOT NULL`. The diagnosed script never wires
  this field even though the ArcGIS response includes `APPRAISED_VALUE`/`JUST_VALUE` —
  confirmed live, all 6 touched parcels still have both fields null. This is real scope for
  a follow-up session, not something fabricated to look fixed.
- The script's docstring claims a `parsed>0 AND inserted=0` fail-loud `RuntimeError` — this
  does not exist in the code (only a soft print warning). Flagged, not silently "fixed"
  beyond the diagnosed bugs (would be scope creep).

**Adversarial verification: CONFIRMED.** Independent refuter re-ran the live RPC (byte-for-byte
match), independently re-verified all 6 `realforeclose_aids` joins, independently re-queried
ArcGIS for 3 sampled zone codes (matched), confirmed the G-regression mechanism and the
`assessed_value` blocker were real, and confirmed the docstring/RuntimeError gap in source.

Migrations: `supabase/migrations/20260718_shard9_walton_cd_i_dixie_structural_ceiling.sql`
(historical — PART 4 was superseded by a corrected inline apply due to schema drift, see
`20260718q_gold_standard_walton_g_regression_real_ordinance_fix_487365d5.sql` for the actual
G-fix that shipped).

## Next-session priorities
1. **walton I**: wire `assessed_value`/`market_value` from EnerGov Layer 4's
   `APPRAISED_VALUE`/`JUST_VALUE`/`BLDG_VALUE` fields into the backfill script — this is the
   sole remaining blocker after this session's geo/zone fixes.
2. **walton C/D**: 6 future auctions (2026-07-23/24) — re-check `realforeclose_aids` closer
   to sale date.
3. **dixie C/D**: 6 Aug-2025 rows have shown zero disposition on `dixieclerk.com` across 4+
   independent sessions now (this one included) — consider this exhausted; only a new source
   (FL DOR surplus-funds list, county clerk direct records request) could move it further.
4. Fix the script's inaccurate `RuntimeError` docstring claim (real bug, low priority).

## SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('dixie');
SELECT public.pencil_dod_evaluate_county('walton');
```
Run 2026-07-18, both via `rest/v1/rpc/pencil_dod_evaluate_county` against
`mocerqjnksmhcjzxrewo.supabase.co`. Raw output pasted above in the before/after tables;
full JSON responses captured in this session's workflow transcript
(dispatch `487365d5-71dc-4492-b06a-a58da6810cb8`).

honesty markers: VERIFIED throughout — every claim above is backed by a live query, live
fetch, or independently-reproduced ArcGIS/ordinance response, adversarially checked by a
second agent with no access to the first agent's reasoning.
