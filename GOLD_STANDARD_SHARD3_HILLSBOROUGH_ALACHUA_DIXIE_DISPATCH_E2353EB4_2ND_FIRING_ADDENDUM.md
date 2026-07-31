# Gold Standard Shard-3 — hillsborough / alachua / dixie — 2nd firing addendum

dispatch_id: e2353eb4-f852-4723-b4b4-aab3cf9c1987 (duplicate dispatch — see below)
chat_session: architect-20260731T080000 (2nd invocation, same UTC day)
loop run: 7622
mode: ULTRALOOP native (Workflow tool, dynamic script — `/effort ultracode` opted in via keyword this firing)

## Duplicate-dispatch finding (VERIFIED at session start)

This exact dispatch was already fully worked earlier today: commit `36e9882e` (report commit `f5f9d213`,
file `GOLD_STANDARD_SHARD3_HILLSBOROUGH_ALACHUA_DIXIE_DISPATCH_E2353EB4_SESSION_REPORT.md`). Live DB state
at this session's start matched that report byte-for-byte (checked via `pencil_dod_evaluate_county` for
all 3 counties before touching anything). Rather than re-run the same fixes and re-claim the same result,
this session used a Workflow fan-out to attempt **genuinely new angles** on every residual gap the morning
session left open, gated by independent adversarial verification before any live write.

## Scoreboard — before (this session) / after

### hillsborough — 10/10, unchanged (certified, frozen scope) — no action
No new work; scope-frozen per `gold_standard_cert_scope` (unchanged since morning check).

### alachua — 8/10, unchanged (E, I reconfirmed still genuinely blocked — 3rd distinct attempt today)
```
E FAIL 82.8 [parcel_linked=48]     I FAIL 82.8 [card_complete=48 of 58]   (byte-identical before/after)
```
3 new source angles tried this session (Clerk case docket, ISOL Real Estate Index — never attempted
before, qpublic.acpafl.org, RealForeclose per-date calendar pages, FL GIO OWN_NAME endpoint tested
directly): all independently blocked (Cloudflare/Turnstile ×2, credential-login ×1, session-gated AJAX,
and — the key new diagnostic — confirmed the FL GIO OWN_NAME lookup was never actually a timeout problem;
the endpoint responds in 1.2s, the real blocker is that **zero owner_name values exist in our DB** for any
of the 10 rows, so there's no input to search with. Also newly confirmed: row `01 2025 CA 003287`'s stored
lat/long resolves to the Alachua County Administration Building (14621-000-000) — a geocoding-fallback
placeholder, not the defendant's real property.
Independent refuter reproduced 6 of 6 sub-claims live; flagged one description-accuracy correction (the
Clerk docket gate is a ColdFusion login+captcha, not literally Cloudflare, as first stated) which does not
change the blocked conclusion.
Audit: `gold_standard_ultraloop_audit` ids **11700** (E), **11701** (I), both `survived=true`.

### dixie — 8/10 → **9/10**, I FIXED (94.1% → 100%), E bonus (97.1% → 100%), C/D unchanged
```
BEFORE: I PASS 94.1 [card_complete=32 of 34]   E PASS 97.1 [parcel_linked=33]
AFTER:  I PASS 100.0 [card_complete=34 of 34]  E PASS 100.0 [parcel_linked=34]
```
**Genuine new fix, adversarially verified before either write was applied:**
1. Resolved `parcel_id='09-10-12-2450-0000-0160'` for case `15-2025-CA-46` via a live FL GIO Statewide
   Cadastral ArcGIS FeatureServer **spatial point-in-polygon query** (a genuinely different method than
   this morning's attribute-match approach) at the row's existing lat/long — JV=114900 exact match to the
   stored `assessed_value`, no boundary ambiguity (confirmed via a tight bounding-box re-query, 16 nearby
   features, only one at the matching value).
2. Root-caused the 2nd residual row (`15-2025-CA-10`, parcel_id already known) via `pg_get_viewdef` on
   `v_zoning_gold_standard_card`: the view is driven FROM `parcel_zones`, and this parcel had zero
   `parcel_zones` rows — not a `zoning_districts` gap as might be assumed.
3. Inserted `parcel_zones` rows for **both** parcels (the newly-resolved one and the already-known one)
   using the exact same `jurisdiction_id=975` (Cross City) / `zone_code='R-1'` / `source='ArcGIS'` fallback
   pattern already applied to all other 32 dixie parcels — not a new or invented pattern.
Independent refuter re-ran the ArcGIS spatial query and the view definition live and reproduced both
results before either statement was applied. **Both writes applied live this session** via the Supabase
Management API (verified via `pencil_dod_evaluate_county` immediately after each write).
Migration: `supabase/migrations/20260731g_shard3_dixie_i_second_firing_parcel_zones_completion.sql`
Audit: ids **11698** (I, survived=true), **11699** (E, survived=true).

**C/D (unchanged, reconfirmed with fresh evidence — 3rd distinct attempt today):**
```
C FAIL 73.5 [matched_clean=25]     D FAIL 73.5 [matched_any=25]     (byte-identical before/after)
```
New finding this session: `dixieclerk.com`'s foreclosure-sales page has **no historical disposition
archive whatsoever** — it publishes only the forward calendar, and case `15-2023-CA-57` has fully dropped
off it (not merely re-dated), so WebFetch/curl cannot distinguish sold/cancelled/continued from this source
at all. The independent refuter went further than the original finding — actually drove the live Civitek
OCRS JSF session past the disclaimer to the real search form and confirmed the Turnstile widget structurally
blocks the single shared submit button for both Person Search and Case Search tabs (not an inference from
this morning, live-confirmed this session). qpublic.schneidercorp.com (Cloudflare 403) and
myfloridacounty.com (no case-number field, session-token-gated) were also tried and independently confirmed
blocked. Structural ceiling remains 32/34 = 94.1% best case (6 SYNTH archival rows + this 1 case).
Audit: ids **11702** (C), **11703** (D), both `survived=true`.

## Net shard scoreboard this firing
- hillsborough: 10/10 (unchanged)
- alachua: 8/10 (unchanged, reconfirmed blocked with new evidence)
- dixie: **9/10** (was 8/10 this morning — I flipped FAIL→PASS, E ticked to 100%, only C/D remain, both
  structurally blocked pending either the owner's Civitek Turnstile resolution or dixieclerk.com publishing
  results)

## Files this session
- `supabase/migrations/20260731g_shard3_dixie_i_second_firing_parcel_zones_completion.sql`
- This addendum.

## Next-session priorities (updated)
1. **dixie C/D**: structural ceiling 94.1% unless Civitek OCRS Turnstile is resolved (out of bounds for an
   agent session — confirmed live this session that even a fully-driven JSF session cannot reach the
   Case Search field without clearing Turnstile) or dixieclerk.com starts publishing a disposition archive
   (confirmed this session it currently has none, by design). A phone call to the Clerk's office
   (352-498-1200) is the only remaining non-technical channel for case `15-2023-CA-57`'s disposition.
2. **alachua E/I**: the real blocker is now precisely diagnosed as missing `owner_name` input, not a
   timeout — a future session should target sourcing defendant/owner names from the original
   `calendar_sweep` ingestion source pages (not re-examined this session) rather than retrying downstream
   lookups (Clerk docket, ISOL, qpublic) that are all independently confirmed credential/Cloudflare-gated
   regardless of input.
3. **dixie J** (flagged, not targeted this shard): still a known live ghost-success per this morning's
   report — unchanged, not touched this session (out of scope).
