# Gold Standard shard-2 (duval/gulf/martin/baker) — duplicate re-fire addendum

- dispatch_id: `39c10f58-bd7c-4883-8b08-0dc4d7a4536f`
- chat_session: `architect-20260731T000000`
- date: 2026-07-31
- ultraloop_mode: native (1 Workflow call, 3 independent refutation subagents + synthesis)

## Duplicate re-fire, no rework

This is the same `dispatch_id` and `chat_session` as
`GOLD_STANDARD_SHARD2_DUVAL_GULF_MARTIN_BAKER_DISPATCH_39C10F58_SESSION_REPORT.md`
(commit `60eb5fe9`), which had already landed on main minutes before this
firing started. Per the fleet's duplicate-re-fire convention (see
`162d5ecd`), the primary report was not redone. Instead this firing did two
things: (1) live-reverify zero drift on all 4 counties, (2) run one genuinely
independent ULTRALOOP adversarial pass — not a repeat of the prior session's
research, but fresh subagents specifically tasked with *refuting* the prior
session's "genuinely blocked" conclusions — since the whole point of
fixer != verifier is that a second, differently-directed look can catch
something the first missed.

## Live drift check — zero drift, all 4 counties

Direct `pencil_dod_evaluate_county` re-query for duval/gulf/martin/baker
matched the already-shipped report's AFTER snapshot exactly on every letter
(same `auctions_total`, same pass/fail, same metric to one decimal). No
regression from the growing 05:30Z ingestion cron in the ~2 hours since the
prior firing. duval remains 10/10; gulf 9/10; martin 8/10; baker 6/10 —
unchanged from the just-shipped report.

## ULTRALOOP adversarial refutation pass — result: no metric movement, one important false positive caught

Three independent subagents were each given one residual-blocker claim and
told to try to break it without repeating already-closed levers.

**gulf I — claim SURVIVES (with a correction to how the prior session framed the gap).**
The refuter found FL GIO's Statewide Cadastral FeatureServer returns real
address/value/owner/geometry for both residual parcels (`05762000R`,
`05004050R`) and initially reported this as a new actionable lever. Checked
against the live table before writing anything: `property_address`,
`latitude`, `longitude`, and `assessed_value` were **already populated** on
both rows — this data was not new. Then checked the actual
`pencil_dod_evaluate_county` SQL definition directly (`pg_get_functiondef`):
the `I` criterion requires those 4 fields **plus** a `v_zoning_gold_standard_card`
row with non-null `zone_code` matching the parcel_id/tax_account. Queried
that view for both parcel_ids — **zero rows**. The actual gap is the zoning
link, not property-card data, exactly as the prior 4 sessions concluded
(Port St. Joe zoning has no self-service GIS/API). The refuter's initial
"REFUTED" verdict was a false positive from not checking the real evaluator
logic — caught before anything was written, per Honesty Protocol (no DB
write happened; this section exists to document a refutation attempt that
looked promising and turned out not to hold, so future sessions don't retry
the same dead lead).

**martin E/I — claim neither confirmed nor overturned; new lead flagged for a future session.**
The refuter independently re-verified the 3 rows are genuinely
`case_classification_code=NON_REAL_PROPERTY` (VERIFIED via direct query) and
that `mcpafl.org`/`martinclerk.com` remain 403/CAPTCHA-blocked (matches
prior session). It then researched Fla. Stat. §721.05(34)/(36)/§721.855 and
found Florida law recognizes three distinct legal forms of timeshare
interest — only one of which ("timeshare estate") is deeded real property
with its own parcel; the DB's `timeshare` classification label does not
distinguish which form applies to `25001632CCAXMX` / `25001634CCAXMX`. This
is a real, better-sourced hypothesis than the prior session's dismissal, but
it could not be confirmed without pulling the actual complaint/deed
(blocked by the same 403/CAPTCHA wall). No parcel was found or fabricated.
Flagging as the sharper next lever: if a future session gets past the
CAPTCHA (or a human pulls the deed manually), check whether either
timeshare-labeled case is a deeded timeshare estate before accepting
"no parcel exists."

**baker C/D/E/I — claim SURVIVES, root cause reconfirmed independently.**
The refuter tried `bakerpa.com` (confirmed reachable, not bot-walled — a
correction to the prior session's implication) and the FL Statewide
Cadastral FeatureServer, both VERIFIED live. Both are parcel/name/address-keyed
with zero case-number field, and the 12 blocked rows have null `parcel_id`
**and** null `owner_name`, so there is no seed value to query with. Every
source that could plausibly bridge case_number -> parcel
(`bakerclerk.com/foreclosures`, `/taxdeeds`, `DuProcessWebInquiry`, UniCourt)
returned 403/405/unindexed on independent re-fetch. Root cause reconfirmed
as a structural case_number-to-parcel crosswalk gap, not a single bot-wall.

## No DB writes to `multi_county_auctions`/`parcel_zones` this firing

Zero metric movement was the correct outcome of an honest adversarial check
— one lead looked promising and was disproven before being acted on, one
lead is a genuine open question not yet actionable, and one conclusion was
independently reconfirmed. Per Honesty Protocol, "genuinely blocked, checked
again, still blocked" is a valid result and is not smoothed over into a
false claim of progress.

## Verification evidence

`SELECT county_slug, letter, survived, created_at FROM gold_standard_ultraloop_audit WHERE dispatch_id='39c10f58-bd7c-4883-8b08-0dc4d7a4536f' ORDER BY created_at DESC;`
-> 7 new rows this firing (`created_at` 2026-07-31 02:14:18 UTC), all
`survived=true`: gulf/I, martin/E, martin/I, baker/C, baker/D, baker/E,
baker/I. (duval/I's prior-firing row from 00:22:47 UTC still stands — duval
was not re-audited this firing since the live drift check found it
unchanged and 10/10.)

Live `pencil_dod_evaluate_county` re-check, 2026-07-31 ~02:00Z (all 4
counties, unchanged from the AFTER snapshot in the primary report):

```
duval:  10/10 (auctions_total=697)
gulf:   9/10  (I FAIL 85.7%, card_complete=12 of 14)
martin: 8/10  (E FAIL 92.1% parcel_linked=35; I FAIL 92.1% card_complete=35 of 38)
baker:  6/10  (C/D/E FAIL 20.0%, matched_clean/matched_any/parcel_linked=3; I FAIL 20.0% card_complete=3 of 15)
```

### SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('gulf');
-- I: {"pass":false,"metric":85.7,"detail":"card_complete=12 of 14"} -- unchanged
SELECT parcel_id, tax_account, zone_code FROM v_zoning_gold_standard_card
 WHERE lower(county)='gulf' AND parcel_id IN ('05762000R','05004050R');
-- 0 rows -- confirms the actual I gap is the zoning link, not property-card data
```
Timestamp UTC: 2026-07-31T02:14Z.

## Next-session priorities (supersedes/refines the primary report's list)

- **duval**: none, unchanged from primary report.
- **gulf**: unchanged — the actual gap is the PSJ zoning link (`v_zoning_gold_standard_card` zone_code), not property-card address/geo/value (those are already populated for both residual parcels). Only remaining lever is still the human phone call to City of Port St Joe Planning (850-229-8261).
- **martin**: new, better-sourced lead — check whether `25001632CCAXMX`/`25001634CCAXMX` are deeded timeshare estates (Fla. Stat. §721.05(34), which would carry a real MCPA parcel, likely under the resort/development's master parcel) vs. personal-property/license timeshare interests (no parcel). Requires getting past `mcpafl.org` 403 or `martinclerk.com` CAPTCHA, or a human record pull — not autonomous-session-actionable as-is.
- **baker**: unchanged — structural case_number-to-parcel crosswalk gap reconfirmed by a second independent session; same 4 non-autonomous options as the primary report (human OCRS click-through, formal records request, Baker County Press full-text confirmation, or wait for sale dates to pass).
