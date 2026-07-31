# Gold Standard Shard-3: martin (dispatch `e26ff1d0-e78b-4a89-8333-34f72589bbf7`, loop run 7726)

## Status: 8/10, unchanged — E/I confirmed genuine dead end (5th consecutive session)

Live `pencil_dod_evaluate_county('martin')` at session start and session end (identical,
confirming zero regression from this session's read-only work):

```
A PASS metric=1     [fc=37 td=1]
B PASS metric=100.0 [verified=1 closed_sold=1]
C PASS metric=97.4  [matched_clean=37]
D PASS metric=97.4  [matched_any=37]
E FAIL metric=92.1  [parcel_linked=35 of 38]
F PASS metric=100.0 [tier1_sold=1 closed_sold=1]
G PASS metric=100.0 [density=100.0]
H PASS metric=0.0   [hours since last_seen]
I FAIL metric=92.1  [card_complete=35 of 38]
J PASS metric=97.4  [deal_complete=37]
```

## E/I: same 3 case numbers as every prior session, 4 new angles tried, all exhausted

The blocker is unchanged from `GOLD_STANDARD_SHARD12_MARTIN_RUN3713`,
`GOLD_STANDARD_SHARD14_MARTIN_DISPATCH_9D22D82F` (+ 2nd firing),
`GOLD_STANDARD_SHARD14_MARTIN_DISPATCH_A9CB3CC1_RUN6288`,
`GOLD_STANDARD_SHARD2_DUVAL_GULF_MARTIN_BAKER_DISPATCH_39C10F58`, and
`GOLD_STANDARD_SHARD7_POLK_MARTIN_DISPATCH_170BE9E2` (+ 2nd firing): 3 rows
(`23001555CCAXMX` personal_property, `25001632CCAXMX`/`25001634CCAXMX` timeshare,
`case_classification_code='NON_REAL_PROPERTY'`) carry `parcel_id IS NULL` with zero
usable metadata (`legal_description`, `plaintiff`, `owner_name`, `bcpao_data` all NULL),
and no `_source` sibling column exists for `case_classification_code` anywhere in the DB —
its provenance is genuinely `UNKNOWN`.

Per HONESTY PROTOCOL guidance against redundant re-investigation, this session did **not**
repeat the 8+ already-exhausted access methods (courthouse CAPTCHA, Landmark Web login
wall, RealForeclose 403, KBForeclosures, exact-string web search, UniCourt 405, Martin PAO
403, Martin ArcGIS). Instead it ran a `Workflow` fan-out of 4 **genuinely new** angles:

1. **Trellis Law** — CONFIRMED Martin County is in Trellis's coverage index
   (`trellis.law/coverage/florida/martin{,/property,/probate,/unclassified}`), but every
   search/case-detail path (homepage, guessed API routes, guessed case-detail URLs) returns
   HTTP 403 behind a Cloudflare bot-challenge — a new, distinct WAF class from the
   CAPTCHA/login walls already documented, but equally impassable by curl/WebFetch.
2. **Landmark Web index/search layer** (distinct from the already-known document-image
   login wall) — CONFIRMED `Search/Index` itself 302-redirects to login; no unauthenticated
   index exists at any guessed guest-search action name (all 404). Independently confirmed
   via `martinclerk.com/335/Records-Search`, which cites Fla. R. Gen. Prac. & Jud. Admin.
   2.420(m)(1) as requiring a formal written-request process — there is no lighter-weight
   public index distinct from the gated document viewer for this county's deployment.
3. **Wayback Machine / archive.today** — CONFIRMED zero archived snapshots exist of any
   case-search or case-detail page for `court.martinclerk.com` or `martin.realforeclose.com`.
4. **FL statewide e-filing portal / judyrecords / unicourt search-results layer** —
   CONFIRMED `myflcourtaccess.com` is filer-only (not a public search surface),
   `judyrecords.com` has zero Florida entries in its sitemap, and `unicourt`'s
   search-results layer (as opposed to the previously-tried guessed detail URL) hits the
   same WAF class already exhausted.

A synthesis pass over all 4 findings, followed by an adversarial-refute step (skipped by
design since the synthesis correctly reported no new-evidence claim to refute), concluded
**`NO_NEW_EVIDENCE`**: no probe retrieved a parcel_id, address, or docket snippet for any of
the 3 case numbers in either direction — nothing proving real-property status, nothing
newly corroborating the existing personal-property/timeshare classification. This is now
the 5th consecutive session reaching the same conclusion; the public-web angle is
structurally exhausted.

## Why no fix was shipped

- **Fabricating a parcel_id** for the 3 rows to force E/I to PASS is the ghost-success
  anti-pattern already purged once from this exact county
  (`GOLD_STANDARD_SHARD12_MARTIN_RUN3713`) — HARD BANNED by canon/Honesty Protocol.
- **Shipping the shard7-drafted evaluator fix** (excluding `NON_REAL_PROPERTY` rows from
  the E/I denominator) remains correctly un-shipped: that same session's follow-up
  provenance investigation concluded `case_classification_code`'s own origin is unverified
  (no `_source` column, no migration/script sets it, no audit-trail entry explains it).
  Building a metric change on top of an unverified label would move the fabrication risk
  up a level, not resolve it — it needs either a verified first-party source or explicit
  architect authorization, and this session obtained neither.

## Actions taken

- Logged a `decision_log` entry (id 680, `task_id=e26ff1d0-...`) documenting the full
  5-session history, the 4 new angles tried, and 3 alternatives explicitly considered and
  rejected, to stop future sessions from re-deriving the same forensics from scratch.
- Wrote the mandatory close-out to `gold_standard_campaign` (id 3412):
  `criteria_passed={A,B,C,D,F,G,H,J: true; E,I: false}`, `exit_reason=
  'blocked_confirmed_dead_end_5th_session'`, `session_end_at` set.
- No writes to `multi_county_auctions`, `pipeline.counties`, or the evaluator function —
  read-only diagnostic + fresh-angle probe only, confirmed via matching before/after
  `pencil_dod_evaluate_county` output above.
- Did not run `gold_standard_loop()`/`gold_standard_certify()` (PARALLEL-FLEET RULES —
  other shards may be mid-flight); reported the single-county evaluation only.

## Recommendation to Ariel/architect

Pick one, since the automated channel is now exhausted 5 times over:

1. Authorize a one-time Martin Clerk manual records request
   (`RecordRequest@martinclerk.com`, ~$1/page) for the 3 case numbers to close the
   provenance gap permanently — the only remaining first-party lever.
2. Explicitly authorize shipping the shard7-drafted `NON_REAL_PROPERTY` denominator
   exclusion on the existing (unverified-provenance) classification as a judgment call.
3. Accept martin as durably capped at 8/10 and pause further shard redispatches for this
   county until (1) or (2) happens — redispatching without new evidence burns session
   budget on a confirmed dead channel, as this session's own probe reconfirmed.

## Honesty markers

- All A-J numbers above are **VERIFIED** — read live from `pencil_dod_evaluate_county`
  at session start and again at session end (identical output pasted above).
- The 4 probe findings are tagged CONFIRMED/UNTESTED/INFERRED by the probing agents
  themselves; no case match was fabricated or asserted without a live HTTP response backing it.
- `case_classification_code='NON_REAL_PROPERTY'` provenance remains explicitly **UNKNOWN** —
  stated as such in the `decision_log` entry, not glossed over.
