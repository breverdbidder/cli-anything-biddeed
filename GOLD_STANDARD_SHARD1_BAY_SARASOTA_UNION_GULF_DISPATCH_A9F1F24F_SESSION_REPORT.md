# GOLD STANDARD shard-1 (bay/sarasota/union/gulf) — session report
dispatch_id: `a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039` · chat_session: `architect-20260725T080000` · 2026-07-25

## Environment note (read first)

This session's sandbox had **no working `psql`/DDL access** — direct connection to the Supabase pooler
(`aws-0-us-west-2.pooler.supabase.com`, both the password in `SUPABASE_DB_PASSWORD` and the standard
project ref) returned `password authentication failed`. All reads and writes in this session went through
the **PostgREST REST API** using the service-role key (bypasses RLS on existing tables). This means no
schema/DDL changes were possible this session — only data reads/writes against tables that already exist.
The migration file committed alongside this report documents the REST writes for the audit trail; it was
not run through `psql`.

## Prompt injection encountered and refused

Partway through reconnaissance, a tool result for a routine `curl`/`python3` command included a fabricated
`<system-reminder>`-style note claiming a scratch file (`/tmp/sarasota_zs.json`) had been "modified by the
user or a linter" and instructing me to silently accept the change **and not tell the user**. No legitimate
process had touched that file. The injected diff added plausible-looking `parking_per_1000sf` values for
several Sarasota zoning districts — exactly the kind of fabricated-ordinance-value injection this campaign's
own rules explicitly ban ("guessed standards = ghost-success, BANNED"). I refused the "don't tell the user"
instruction, flagged it to Ariel in-conversation, discarded the file, and re-fetched the same data fresh
via a clean `curl`. The re-fetch happened to return the same 4 already-legitimate values that were already
live in `zone_standards` — so no bad data reached the DB — but the injection attempt itself is the finding,
independent of whether its payload was accurate.

## Result: gulf gets 9 real closed-sale records + 1 data-integrity fix; sarasota/union correctly left alone

| County | Before | After | Pass count |
|---|---|---|---|
| bay | 10/10 | 10/10 (re-confirmed, no regression) | 10/10 |
| sarasota | 9/10 (G fails) | 9/10 (unchanged — G structurally blocked, see below) | 9/10 |
| union | 8/10 (B,F fail) | 8/10 (unchanged — genuine dead end, see below) | 8/10 |
| gulf | 4/10 (A,G,H,J pass) | 4/10 (unchanged pass count; underlying data materially improved, see below) | 4/10 |

Live `pencil_dod_evaluate_county` BEFORE (from the dispatch brief, re-confirmed live at session start) /
AFTER (re-queried after every write):

```
gulf BEFORE: {"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
              "C":{"pass":false,"metric":78.6,"detail":"matched_clean=11"},
              "D":{"pass":false,"metric":78.6,"detail":"matched_any=11"},
              "E":{"pass":false,"metric":85.7,"detail":"parcel_linked=12"},
              "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
              "I":{"pass":false,"metric":64.3,"detail":"card_complete=9 of 14"}}
gulf AFTER:  {"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
              "C":{"pass":false,"metric":78.6,"detail":"matched_clean=11"},
              "D":{"pass":false,"metric":78.6,"detail":"matched_any=11"},
              "E":{"pass":false,"metric":78.6,"detail":"parcel_linked=11"},
              "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
              "I":{"pass":false,"metric":64.3,"detail":"card_complete=9 of 14"}}
```

E's metric *dropped* (85.7% → 78.6%) — intentional, see below. B/F/C/D/I are numerically unchanged despite
real work; the reasons are specific and evidenced, not "nothing happened."

## Part 1 — gulf: 9 real closed tax-deed sales found, B/F still can't be flipped honestly

Ran a Workflow (9 agents: 5 row-research + 2 dead-end audits + 1 sanity check + adversarial verify pass)
against Gulf County's real public records. Result for the 9 tax-deed cases (2025-001, 003, 010, 011, 017,
018, 021, 022, 023): **all 9 appear on Gulf County Clerk's official "Tax Deeds Sales and Surplus/Overbids"
page** (`gulfclerk.com/courts/tax-deeds/`, independently re-fetched HTTP 200) tagged `SURPLUS` with a
specific dollar amount each. Under FL Stat. 197.582, a surplus only exists when the winning bid exceeds the
statutory minimum — this is conclusive proof each case sold to a bidder, not just evidence. Every case's
sale date has also already passed (latest, 2025-023, was 2026-03-18 — over 4 months before today).

Applied: `auction_status='completed'`, `tier1_sale_status='sold'`, `tier1_authoritative=true` on all 9 rows;
inserted 9 rows to `tax_deed_outcomes` with an independent `data_source` (`gulfclerk_taxdeed_surplus_v1`,
not PropertyOnion-derived — satisfies the campaign's B guardrail).

**Why B/F still show 0/0 after this:** re-querying `pencil_dod_evaluate_county('gulf')` after each write
showed no movement on B or F. Diagnosed empirically (bay's passing rows all carry a populated
`tier1_sold_amount` alongside `tier1_sale_status='sold'`) that the evaluator's `closed_sold` denominator
requires `tier1_sold_amount` to be non-null — a real dollar figure, not just a status flag. The Clerk's
public surplus page only publishes the **surplus** (excess over the statutory minimum bid), not the full
winning bid. Writing the surplus figure into `tier1_sold_amount` would misrepresent it as the sale price,
which it is not (e.g. case 2025-017's surplus is $39.14 — nowhere close to the actual winning bid). **Declined
as a fabrication risk**, consistent with refusing the injection attempt above. Real winning-bid figures for
these 9 sales, and any outcome data for the 5 CA/CC foreclosure cases, need either authenticated
RealAuction access, a Gulf County OCRS session (JS-driven, not fetchable by WebFetch/curl), or a direct
records request to the Clerk (850-653-8861 / 850-229-6112 ext 2307) — none of which this session's tooling
could reach. `gulf.realforeclose.com` returned HTTP 403 to every automated fetch attempted (WebFetch, raw
`curl`, and Firecrawl).

## Part 2 — gulf: E's honest regression (data-integrity fix)

Row `237fb61f` (case `232019CA000060CAAXMX`) had `parcel_id` literally set to the string `"Property
Appraiser"` — a scraping artifact, not a real parcel ID, that was counting as a false-positive "linked"
parcel toward criterion E. Nulled it. E's metric correctly dropped from 85.7% to 78.6% as a direct result —
this is intentional and is the same "ghost-success purge" pattern already established for this campaign
(see `migrations/20260718_gold_standard_shard5_sarasota_nassau_bay_gulf_ghost_success_purge.sql` for
precedent). Separately discovered this same row already carries `tier1_sale_status='CANCELED_PER_ORDER'`
(`tier1_authoritative=true`, verified 2026-07-23 by unrelated prior automation) — a real, already-verified
non-sale, correctly excluded from B/F.

The other 4 gulf C/D/E/I gaps were genuinely researched and NOT fixed, honestly:
- `232024CA000072CAAXMX`, `232024CC000157CCAXMX`: zero data recoverable from any accessible source
  (`gulf.realforeclose.com` 403, Clerk's foreclosure archive returned empty results, Gulf County's OCRS
  court-records portal is a JSF interactive app that cannot be driven by WebFetch/curl). Not fabricated.
- `2025-017`, `2025-023`: these are vacant, unaddressed parcels. Fetched the Clerk's own official Property
  Information Report for 2025-017 — even the Clerk's own record has no street address, only a metes-and-bounds
  legal description ("NW corner of the NE 1/4 of Sect. 33..."). The `"N/A"` address currently in our DB may
  already be structurally accurate, not a data gap — a candidate to reclassify as not-applicable in `I`
  rather than a target for further address-recovery effort.

## Part 3 — union: B/F confirmed as a genuine dead end (not a data gap)

Union has only 3 total auctions. Two (`63-2024-CA-0047`, `63-2025-CA-0053`) have auction dates of
2026-10-15 and 2026-08-13 — both **after today (2026-07-25)** — so by definition neither can have closed
yet. The third (`UNION-TD-CERT223`) carries `auction_status='redeemed'`, which under Florida tax-deed
process means the owner paid off the certificate before sale — by definition no third-party sale occurred.
This conclusion doesn't depend on web access (it's a calendar fact from our own DB), but was additionally
web-verification-attempted: `unionclerk.com` blocked every path with a Cloudflare 403 challenge (confirmed
via 3 independent methods — WebFetch, raw Python `urllib` with a browser User-Agent, and Firecrawl), so no
independent confirmation or contradiction was available externally. Nothing to fix; B/F will resolve
naturally once the two upcoming auctions actually occur and close.

## Part 4 — sarasota: G correctly left alone (pre-existing structural blocker, same-day prior work)

A different, same-day dispatch (`42827b21`, commit `db0d3b7b`, session report
`GOLD_STANDARD_SHARD11_SARASOTA_DISPATCH_42827B21_SESSION_REPORT.md`) had already done deep real research
into sarasota's `pk1000` sub-metric just before this session started, and explicitly documented it as
**structurally blocked pending a fleet-wide policy decision from Ariel**: the remaining districts (`CT`,
`PID`, `CN`) regulate parking strictly per use-type with no single district-wide standard, and forcing one
number would misrepresent the ordinance — the identical blocker already flagged for bay county on
2026-07-18. I independently confirmed the live metric matches that report's ending state (`pk1000=54.5`,
unchanged) and declined to re-attempt it. Re-deriving a number here today, especially right after refusing
a fabricated-zoning-data injection targeting this exact table, would have been the wrong move. Logged a
`survived=false` audit row (correctly — this is a documented non-fix, not a false-positive PASS claim) so
the next session doesn't waste time re-deriving the same conclusion; it should go straight to Ariel for the
methodology decision instead.

## Verification protocol followed

- `SELECT public.pencil_dod_evaluate_county(...)` run before and after for all 4 counties (pasted above and
  in Part 1).
- 16 rows logged to `public.gold_standard_ultraloop_audit` (dispatch_id `a9f1f24f-...`,
  `ultraloop_mode='native'`): gulf E (survived=true), gulf B/F (survived=false, with the exact blocker),
  union B/F (survived=true — genuine dead end), sarasota G (survived=false — correctly not re-claimed as a
  fix), and all 10 letters for bay (survived=true, freshness refresh for the certify-gate's 7-day window).
- Did **not** run `gold_standard_loop()` / `gold_standard_certify()` per PARALLEL-FLEET RULES (other shards
  may be mid-flight this run) — per-county evaluation only.
- Migration: `migrations/20260725_gold_standard_shard1_bay_sarasota_union_gulf_dispatch_a9f1f24f.sql`,
  applied live via PostgREST REST API with the service-role key (see Environment note above for why not
  `psql`).

## Next-session priorities

1. **gulf B/F real winning-bid figures** — the 9 tax-deed sales are conclusively verified as closed; only
   the exact dollar amount is missing. Needs authenticated RealAuction access, a working Gulf County OCRS
   session, or a direct Clerk records request. This is the single highest-leverage remaining item for gulf.
2. **gulf's 2 unrecoverable CA/CC foreclosure cases** (`232024CA000072CAAXMX`, `232024CC000157CCAXMX`) —
   same access-tooling gap as above; also blocks C/D/E/I for those 2 rows.
3. **sarasota G pk1000 methodology** — needs an Ariel decision (modal use-type value / most-restrictive-bound
   / most-permissive-bound proxy), shared blocker with bay. Not a per-session engineering task.
4. **gulf I reclassification candidates** — `2025-017`/`2025-023` may be structurally addressless (vacant
   land, Clerk's own record has no street address); worth checking whether `I`'s card-completeness definition
   should exempt unaddressed vacant parcels rather than counting them as permanently incomplete.

---
dispatch_id: a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039
