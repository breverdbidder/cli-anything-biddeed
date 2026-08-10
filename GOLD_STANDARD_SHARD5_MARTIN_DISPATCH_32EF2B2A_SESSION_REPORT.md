# Gold Standard Shard-5: martin (dispatch `32ef2b2a-3ee0-4ac9-8209-5ec91a35cf5c`, loop run 10213)

## Status: 8/10, unchanged pass/fail, but E and I both genuinely improved this session

```
Before (dispatch brief):                 After (live, this session):
A PASS metric=1                          A PASS metric=1     [unchanged]
B PASS metric=100.0                      B PASS metric=100.0 [unchanged]
C PASS metric=97.6                       C PASS metric=97.6  [unchanged]
D PASS metric=97.6                       D PASS metric=97.6  [unchanged]
E FAIL metric=85.4 [parcel_linked=35]    E FAIL metric=87.8 [parcel_linked=36]
F PASS metric=100.0                      F PASS metric=100.0 [unchanged]
G PASS metric=100.0                      G PASS metric=100.0 [unchanged]
H PASS metric=0.1                        H PASS metric=0.0-0.1 [unchanged, fresh]
I FAIL metric=85.4 [card_complete=35/41] I FAIL metric=87.8 [card_complete=36/41]
J PASS metric=100.0                      J PASS metric=100.0 [unchanged]
```

Both `pencil_dod_evaluate_county('martin')` snapshots above are live REST RPC calls,
not estimates. A/B/C/D/F/G/H/J detail strings are byte-identical before/after —
zero regression from this session's write.

## Context: this is a known, repeatedly-investigated gap

martin E/I has been investigated 6+ times since 2026-07-18 (most recently dispatch
`643e111c` on 2026-08-09, which reconfirmed the same 6-row gap as "CONFIRMED BLOCKED").
Rather than repeat exhausted forensics, this session:

1. Re-verified live (fresh AJAX harvest against martin.realforeclose.com) that the
   picture is unchanged: 6 rows with `parcel_id IS NULL` out of 41 total auctions.
   3 are `case_classification_code='NON_REAL_PROPERTY'` (timeshare/personal property,
   dead end since 2026-07-18). 3 more (`26000299CAAXMX`, `25000496CAAXMX`,
   `25000102CAAXMX`) show `$0.00` judgment / blank parcel on the RealForeclose
   calendar item — the read every prior session took at face value.
2. Ran a `Workflow` fan-out (2 probe agents + 1 refuter) to adversarially test that
   read before accepting it again. **New finding**: `court.martinclerk.com` has an
   anonymous, non-CAPTCHA-gated `QuickSearch` -> `DetailsSummary` AJAX endpoint
   (distinct from the CAPTCHA-gated document-image viewer previously exhausted) that
   returns real case metadata. All 3 "pre-judgment" cases are actually **CLOSED**
   foreclosure cases with real party names — the RealForeclose calendar stub was
   simply stale/incomplete, not reflective of case status.
3. Used the newly-obtained party names to search `www.pamartinfl.gov`'s real-property
   backend (`/app/search/real-property?format=json&search=<name>` — a plain JSON API
   discovered by reading the site's own webpack bundle, no browser/JS execution
   needed):
   - **`26000299CAAXMX` (Frondorf) → single, unambiguous match.** PIN
     `18-38-41-009-002-00070-8`, 3078 SW Virginia Ave, Palm City FL 34990. Deed
     history (Grantor "Bonnie A & William Frondorf" → Grantee "Natalie I Frondorf")
     matches the case's real plaintiff ("Frondorf as PR for Estate of Dorothy
     Miller, William") and defendant ("Frondorf, Natalie") exactly.
   - `25000102CAAXMX` (O'Neill/Wisnieski, reverse-mortgage estate case) → **no
     confident match**. 36 same-surname candidates in the PA database, none pairing
     the case's 4 named parties (current-owner-of-record data doesn't reach back to
     a deceased original borrower). Left unresolved, not guessed.
   - `25000496CAAXMX` (De La Bahia Condominium Association) → not attempted; that's
     an HOA co-defendant, not the unit owner, and the owner's name is unknown.

## Fix shipped: 1 of 6 gap rows (`26000299CAAXMX`)

- `scripts/shard5_32ef2b2a_martin_e_i_frondorf_fix.py` — patched
  `multi_county_auctions` id `aacd4b1b-775d-4f2a-92c6-edf1c2a268fd`: `parcel_id`,
  `property_address`, `legal_description`, `assessed_value`, `market_value`,
  `latitude`/`longitude`, `city`, `zip`, `property_type`, `bcpao_enriched`,
  `bcpao_url`, `assessed_value_source`. Source: pamartinfl.gov real-property JSON
  API, single record, AIN 29570.
- Inserted `parcel_zones` row (id 857703): `parcel_id=18-38-41-009-002-00070-8`,
  `jurisdiction_id=1331` (Unincorporated Martin County), `zone_code=R-2B`, via a live
  `geoweb.martin.fl.us` ArcGIS point-in-polygon query on the property's centroid —
  single, unanimous feature (OBJECTID 85881). This is what carried letter I forward
  alongside E (`v_zoning_gold_standard_card` requires `parcel_id` to resolve to a
  `zone_code`, not just be non-null in `multi_county_auctions`).
- Patched `plaintiff`/`owner_name` on the same row (previously both NULL) for future
  auditability — the case-party match that justified the parcel identification
  wasn't otherwise recoverable from the DB without re-doing the manual clerk lookup.

Idempotent, guarded (fails loud if the row doesn't match expectations or already has
a `parcel_id`). Applied via PostgREST (service-role key) — direct `psql`/pooler
access was unavailable from this session's sandbox (auth failure on both the pooler
and direct host), consistent with the pattern in `scripts/shard3_martin_run8_cd_stub_promote.py`.

## Adversarial verification

An independent refuter agent (not the agent that wrote the fix) re-ran 5 of 6
verification checks live: re-fetched the PA JSON API (confirmed single match, no
ambiguity), re-ran the ArcGIS zoning query (confirmed single unanimous R-2B
feature), queried the live DB rows directly (confirmed both writes landed exactly
as claimed), re-ran the DoD evaluator before/after (confirmed the score movement
and zero regression elsewhere), and checked for cross-county/cross-letter side
effects (none found). It could not independently reach `court.martinclerk.com`
(hit a CAPTCHA on the path it tried) to confirm the case-party match — the session
lead then closed that gap directly, replicating the exact `QuickSearch` ->
`DetailsSummary` flow the probe agent had used, and confirmed Plaintiff/Defendant
names plus a 9/8/2026 foreclosure-sale event matching the DB's `auction_date`
exactly. **Verdict: SURVIVES**, no fabrication, no regression.

Logged to `gold_standard_ultraloop_audit`: ids 14121 (E), 14122 (I), both
`survived=true` with full `refuter_evidence`.

## Why the other 5 rows were not force-fixed

- **3 `NON_REAL_PROPERTY` rows**: re-probed via 6 additional new angles this session
  (myfloridacounty.com, Daily Court Docket page, Landmark Web official-records index,
  CourtListener/RECAP API, RSS.aspx, 5 case-number format variants against
  `court.martinclerk.com`) — all dead ends, now 17+ exhausted avenues across 6+
  sessions since 2026-07-18. Fabricating a parcel_id here is HARD BANNED by canon.
- **`25000102CAAXMX` (O'Neill)**: genuinely ambiguous in the PA database (36
  candidates, no disambiguating signal). Reporting "not found" honestly per the
  BLANK > WRONG principle rather than picking a plausible-looking candidate.
- **`25000496CAAXMX` (De La Bahia)**: the named defendant is an HOA, not the unit
  owner: the actual owner's identity is unknown and out of scope to guess.

## Recommendation for next session

- The `court.martinclerk.com` anonymous `QuickSearch`/`DetailsSummary` bypass is a
  genuinely new, reusable access path (not previously documented as available) —
  worth trying on OTHER counties/cases with a similar "same-vendor Tyler/Odyssey
  portal" blocker before assuming CAPTCHA-gated.
- `25000102CAAXMX` could potentially be resolved with a Landmark Web
  (`or.martinclerk.com/LandmarkWeb`) search by party name for a recorded Lis Pendens
  or Notice of Foreclosure Sale (that index supports Name search, confirmed
  reachable this session, not queried by name due to session scope) — a genuinely
  new, not-yet-exhausted lever for a future session.
- Max achievable for E/I without new leads on the 3 `NON_REAL_PROPERTY` rows is
  38/41 = 92.7%, still short of the 95% PASS threshold — martin's ceiling on these
  two letters remains structurally capped pending either (a) a Martin Clerk manual
  records request (~$1/page, previously recommended and still unauthorized) or (b)
  explicit architect authorization to exclude `NON_REAL_PROPERTY` rows from the E/I
  denominator (previously drafted, still un-shipped pending provenance verification
  on `case_classification_code`).

## Honesty markers

- All before/after A-J numbers are **VERIFIED** — live REST RPC calls to
  `pencil_dod_evaluate_county`, pasted above.
- The Frondorf parcel/zone match is **VERIFIED** — independently re-fetched by a
  separate refuter agent and by the session lead directly (not merely accepted from
  a single source).
- The case-party match (Frondorf plaintiff/defendant) is **VERIFIED** — fetched
  directly from `court.martinclerk.com`'s live case-details endpoint by the session
  lead, not inferred from the property record alone.
- The O'Neill and De La Bahia non-fixes are reported as **UNKNOWN**, not guessed.
- `gold_standard_campaign` (id 4055) close-out written:
  `criteria_passed={A,B,C,D,F,G,H,J:true; E,I:false}`,
  `exit_reason='partial_fix_shipped_e_i_improved_not_passing'`, `session_end_at` set.
- Did not run `gold_standard_loop()`/`gold_standard_certify()` (PARALLEL-FLEET RULES
  — other shards may be mid-flight); reported the single-county evaluation only.
