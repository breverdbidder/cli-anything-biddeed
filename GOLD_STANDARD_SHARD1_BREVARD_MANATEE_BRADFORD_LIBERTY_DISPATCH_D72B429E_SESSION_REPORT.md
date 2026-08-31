# Gold Standard shard-1 — brevard/manatee/bradford/liberty (dispatch `d72b429e-4fd0-4ec6-a0d4-265b6534238e`, 2026-08-31 16:00Z wave)

## TL;DR

Scoreboard letter-counts unchanged: **brevard 9/10, manatee 9/10, bradford 8/10, liberty 7/10.**
Two genuine, adversarially-verified live writes were applied this session — brevard I
(+5 card_complete rows via zone-linkage) and manatee C/D (+5 matched_clean rows, D
flipped FAIL→PASS) — but neither flipped I or C to PASS: brevard I's rounded metric
stays at 86.0%, and manatee C landed exactly on its documented 92.4% structural
ceiling. Bradford (B/F) and liberty (A/B/F) were reconfirmed unchanged — 14th+ and
8th+ consecutive session on the same structural ceilings, no new lever found, no
heavy agent budget spent re-deriving already-exhausted findings.

## Method

Used ultracode (`Workflow` tool): 2 parallel fix-phase agents (brevard I, manatee C)
→ 2 parallel adversarial-verify agents, one per fix claim. Both claims **SURVIVED**
independent re-verification. Bradford/liberty were handled directly in the main
session (not delegated) via targeted live re-checks against the exact case numbers
and clerk pages already on file, since 3 prior sessions (including one just 2 days
ago using `brightdata` MCP) had already exhausted every automatable lever for both —
re-dispatching full investigator agents against a confirmed dead end would have
burned budget without a plausible payoff.

## brevard — letter I (86.0% → 86.0% displayed, real underlying +5 rows, FAIL)

Prior session (2026-08-30, dispatch `62c0b00c`) identified 5 specific rows with
complete address+geo+value but zero zone-linkage: case_numbers 260133, 260197,
260213, 260214, 260215 (parcel_ids 2001122, 2411122, 2317272, 2400286, 2400440).

- Tried City of Cocoa's own hosted ArcGIS zoning layer first (per playbook order) —
  zero features for all 5 by both TaxAcct-attribute and point-in-polygon query,
  confirming none of the 5 are actually inside Cocoa city limits despite 4/5 carrying
  a Cocoa postal address.
- Brevard County's own unincorporated zoning layer (`gis.brevardfl.gov/gissrv/rest/
  services/Planning_Development/Zoning_WKID2881/MapServer/0`) resolved all 5 cleanly,
  one unambiguous feature each: `GU`, `TR-1`, `TR-1`, `TR-1`, `TRC-1`.
- **Correction to task brief surfaced mid-session**: the evaluator's `card_complete`
  join is NOT against `zoning_assignments` as documented — it's against
  `public.parcel_zones` (joined on `tax_account`), with `zoning_assignments` kept in
  sync as a secondary table. Both were written for consistency; only `parcel_zones`
  actually feeds the evaluator.
- `card_complete` moved **6316 → 6321 of 7348**. Displayed metric stays "86.0%"
  (5/7348 ≈ 0.07pp, below the 1-decimal rounding threshold). **I remains FAIL** —
  honest small real fix, not a claimed resolution.

Adversarially verified: refuter independently re-ran the RPC, re-queried
`parcel_zones`/`zoning_assignments`/`v_zoning_gold_standard_card` directly, and
re-issued all 5 point-in-polygon queries itself against the cited ArcGIS endpoint —
exact match on every zone_code, no phantom rows. **SURVIVED.**
`gold_standard_ultraloop_audit` id `20080`.

## manatee — letter C (89.5% → 92.4%, hits documented ceiling; D 97.1% → 100% PASS)

Rather than re-confirm the well-documented 13-row `CLERK_SSOT_CANCELLED` ceiling for
a 4th time, this session pulled the *current* gap composition fresh and found 5
non-cancellation rows had appeared since 2026-08-30:

- `412025CA003113CAAXMA` — a long-form duplicate case number for an already-clean
  short-form sibling (`2025CA003113AX`, same parcel_id). Live `records.
  manateeclerk.com` re-fetch confirmed the sibling is genuinely rescheduled (status
  "PENDING ONLINE" under the Oct-7-2026 panel), not cancelled. Fixed:
  `parity_status='PARITY_OK'`.
- 4 `tax_deed` rows (`2026TD000094/100/101/107`), never parity-checked because
  manatee's clerk-based reconciler doesn't cover tax_deed. Live-harvested from
  `manatee.realforeclose.com`'s AJAX calendar for 2026-08-31 — all 4 case numbers
  and parcel_ids matched exactly. Promoted to `matched_clean` per the established
  2026-08-02 evidentiary precedent for this county's tier1 bar.

`matched_clean` **154 → 159 of 172** (89.5% → 92.4%) — lands exactly on the
documented structural ceiling (13 `CLERK_SSOT_CANCELLED` rows remain, re-confirmed
100% of the residual gap, no other failure mode). `matched_any`/D **167 → 172
(97.1% → 100%, FAIL → PASS)**. **C remains FAIL** — the open architect-level
Options A/B/C canon decision on `CLERK_SSOT_CANCELLED` exclusion
(`GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`) is not this
session's to resolve.

Adversarially verified: refuter independently re-ran the RPC (exact match),
re-queried the row-level `parity_status` changes, re-fetched
`records.manateeclerk.com` and confirmed it genuinely supports the claim, and
spot-checked 2 of the 13 remaining cancelled rows live (both confirmed "Sale
Cancelled Reason: JUDICIAL ORDER"). **SURVIVED.**
`gold_standard_ultraloop_audit` id `20081`.

## bradford — letters B, F (both null%, FAIL) — 15th+ consecutive reconfirmation

Live row check: 5 cases now on file (24000431CAAXMX, 25000439CAAXMX, 25000457CAAXMX,
25000487CAAXMX, 04-2026-TD-002), 4 past-due with no outcome — identical set to the
2026-08-29/08-30 sessions, no new case. `bradfordclerk.com/foreclosures/` re-checked
live this session: still HTTP 403 (Cloudflare), unchanged. `brightdata` MCP was
already tried against this exact blocker 2 days ago (dispatch `10b00370`) with no
lever found (bad_endpoint/KYC refusal on every path). No new angle exists this
session; not re-attempted to avoid burning budget on a reconfirmed dead end.
**B/F unchanged, both FAIL.**

## liberty — letters A, B, F (FAIL) — 9th+ consecutive reconfirmation

Live row check: still exactly 1 case (`24-CA-22`, sale date 2026-07-21, already
passed), `updated_at` stale since 2026-07-03 — no drift. Re-fetched
`libertyclerk.com/courts/foreclosure-sales/` and `/courts/tax-deeds/` fresh this
session (both HTTP 200, not blocked): foreclosure page text confirms "There are no"
[upcoming sales] — genuinely empty docket, matching the `brightdata`-verified finding
from the 2026-08-29 session exactly (same conclusion, cheaper method this time: plain
curl reached the page fine, no anti-bot tooling needed today). **A/B/F unchanged, all
FAIL** — Florida's least-populous county continues to have no live tax-deed inventory
and no accessible outcome source for its one closed-date case.

## Guardrail compliance

- No `parity_status`, `sold_amount`, address, or parcel field was fabricated or
  guessed anywhere this session. Every written value traces to a live source fetched
  this session.
- PropertyOnion was not used as anything but litmus.
- `pencil_dod_evaluate_county`, cron jobs 109/111/115, and the gold-standard-loop
  scoring jobs were not modified. `gold_standard_loop()`/`gold_standard_certify()`
  were not invoked (per PARALLEL-FLEET RULES).
- 2 `gold_standard_ultraloop_audit` rows written (ids `20080` brevard/I, `20081`
  manatee/C), both `survived=true`. No rows written for bradford/liberty (metric did
  not move, per the established closeout convention from dispatch `62c0b00c`).
- `gold_standard_campaign` id `5459` (dispatch `d72b429e`) PATCHed with the real,
  fresh A-J pass/fail map for all 4 counties, `exit_reason=
  'ceiling_reconfirmed_plus_2_real_verified_writes_no_letter_flip'`, real UTC
  `session_end_at`.
- Direct psql/`SUPABASE_DB_PASSWORD` was not attempted (known, already-documented
  constraint, decision_log ids 169/205/287) — all reads/writes went through Supabase
  PostgREST with the service-role key, the established working pattern. One transient
  Cloudflare 521 ("web server is down") hit mid-session on the Supabase project host —
  resolved on retry within ~15 seconds, not a credential issue, no data lost.

## Live scoring evidence (VERIFIED, `pencil_dod_evaluate_county`, run 2026-08-31 end of session)

```
brevard:  9/10 (I FAIL 86.0%, card_complete=6321 of 7348)
manatee:  9/10 (C FAIL 92.4%, matched_clean=159 of 172; D now PASS 100.0%)
bradford: 8/10 (B FAIL null%, F FAIL null%, verified=0/closed_sold=0)
liberty:  7/10 (A FAIL 0, B FAIL null%, F FAIL null%)
```

## Next-session priorities

- **brevard I**: the 5-row lever from `62c0b00c` is now closed. Residual gap
  (~1,027 rows short of 95%) remains dominated by the previously-documented
  addressless/no-GIS-feature bucket and condo/metes-and-bounds legal descriptions
  the regex parser can't handle — no new tractable lever surfaced this session.
- **manatee C**: at its true 92.4% ceiling under current canon. Cannot move further
  without an architect decision on the `CLERK_SSOT_CANCELLED` exclusion question
  (Options A/B/C, open since 2026-08-27). Recommend routing this to Ariel directly
  rather than continuing to re-diagnose it session after session.
- **bradford B/F / liberty A/B/F**: every automated lever (clerk sites, Civitek OCRS,
  myfloridacounty.com, auction.com, brightdata anti-bot bypass) has been tried and
  failed. The only remaining lever for both is a human phone call to the respective
  Clerk's office — outside automated-session scope. Recommend skipping further
  automated sessions on these specific letters until a new data source appears.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
