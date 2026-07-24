# Gold Standard shard-7 — polk — 2nd firing addendum

dispatch_id: `ddf3c638-aced-44ab-898b-49503ca9eec6` (same dispatch_id as the original session)
loop run: 6253
county: polk (only county in this shard's assignment)
mode: manual live re-verification (no ultracode fan-out this firing — see reasoning below)

## Context

This dispatch fired a second time with an identical brief (same C/D FAIL 94.8% baseline, same
dispatch_id) as the session already closed out in
`GOLD_STANDARD_SHARD7_POLK_DISPATCH_DDF3C638_SESSION_REPORT.md` (commit `091df3ad`, merged same
day). That session found the brief's baseline stale, confirmed live polk was already 10/10, ran a
20-agent ultracode adversarial re-verification of all 10 letters, and logged fresh
`gold_standard_ultraloop_audit` rows for every letter.

## What this firing did

1. Re-ran `pencil_dod_evaluate_county('polk')` live (fresh call, not reused from memory):
   **identical to the prior session's AFTER snapshot** — 10/10, all metrics unchanged
   (C=99.3, D=99.3, etc.), `auctions_total=695`. No drift.
2. Queried `gold_standard_ultraloop_audit` for polk: all 10 letters carry `survived` rows dated
   **2026-07-24** (today) — inside the 7-day certify-gate freshness window. Certify gate is
   already satisfied; no new audit rows needed this firing.
3. Given no letter is failing and the audit evidence is fresh, did not re-run the full 20-agent
   ultraloop workflow a second time in the same day for the same unchanged result — that would be
   duplicate work burning budget for zero new information (Cost Discipline / Karpathy K2).
   Instead, spent the firing on **deepening the one open residual item** flagged by the prior
   session's closeout: the J-letter's 102 placeholder `bid_decisions` rows.

## J placeholder residual — deepened root-cause (new this firing)

Prior session knew: 102/679 polk `bid_decisions` rows carry a hardcoded `arv=200000.0,
max_bid=80000.0` fallback, unchanged since a 2026-07-02 audit finding. It correctly flagged this
as out of polk-only scope and did not investigate further.

This firing traced **why** those 102 rows can never self-heal via the existing per-minute comps
batch (`gen_valuations_comps_batch()`, cron 109 — not modified, per guardrail):

- All 102 placeholder rows share one `created_at` batch stamp (2026-06-19 11:23:30, pipeline
  `v14.0_heuristic`, `arv_source='default_200k'`) — a single historical run that fell back for
  these specific parcels.
- `gen_valuations_comps_batch()` sources comps from `public.fl_parcels` (FL DOR statewide NAL
  data), joined by `parcel_id`. Polk's `fl_parcels` rows use the **FL DOR NAL dashed format**
  (e.g. `01-38-37-000-000-00010-8`).
- `multi_county_auctions.parcel_id` (and the copied `bid_decisions.parcel_id`) for polk is stored
  in the **Polk Property Appraiser's own undashed numbering** (e.g. `232704000730`,
  `313109000000`) — a different ID scheme entirely.
- Verified live: **0 of the 102** placeholder parcel_ids match `fl_parcels.parcel_id` in any form
  (checked directly, not via a derived join). This is a permanent scheme mismatch, not a
  transient "batch hasn't reached it yet" gap — the comps batch will never pick these up as
  written.
- Checked for an alternate same-scheme comps source to route around the mismatch:
  `sample_properties` has **0 rows for co_no=53** (Polk); `parcel_zones` carries zoning only, no
  sale/value columns. Neither is a usable substitute today.

**Conclusion:** fixing this requires either (a) a verified Polk-PA-numbering → FL-DOR-NAL
crosswalk (I have no confirmed conversion rule for Polk's scheme — guessing one would be
fabrication, explicitly banned), or (b) ingesting a new Polk-native comps source with real sale
prices. Both are new-data-source builds, not a same-session backfill, and match the brief's own
framing of J-generator quality work as "a separate, larger, cross-county initiative." No fix was
attempted — Honesty Protocol: BLANK > WRONG, no speculative crosswalk shipped.

## Verification (Honesty Protocol tags)

- polk 10/10 live, no drift from prior session: **VERIFIED** (fresh RPC call, timestamped output
  above, matches prior session's closing snapshot exactly).
- Audit-table freshness (all 10 letters dated 2026-07-24): **VERIFIED** (direct query against
  `gold_standard_ultraloop_audit`, pasted above).
- J placeholder scheme-mismatch root cause (0/102 match `fl_parcels`): **VERIFIED** (direct SQL
  join, zero matches).
- No writes made this firing — every query was `SELECT`. No migrations, no `bid_decisions`
  updates, no audit-log inserts (none needed; existing rows are still fresh).

## Residual / next-session priority (updated)

- J placeholder cleanup (102/679 polk rows) now has a precise, actionable root cause instead of
  an unexplained "unchanged count": **Polk PA parcel-numbering scheme is incompatible with the
  FL DOR NAL scheme the comps batch reads from.**
- Probed the live Polk Property Appraiser site (`www.polkflpa.gov`, formerly polkpa.org,
  redirect confirmed) this firing: it has a "Parcel ID" search field (`txtsearchRE_id` /
  `ctl00$mainCopy$searchRE_id` on `CamaDisplay.aspx`) documented to accept the **undashed**
  parcel number with a tooltip reading "Enter only the numbers without hyphens" — i.e. the same
  scheme already stored in `multi_county_auctions.parcel_id`/`bid_decisions.parcel_id` for polk.
  This means **no DOR-NAL crosswalk is needed** — Polk's own site should resolve these 102
  parcels directly by the ID we already have. **VERIFIED**: confirmed the exact field name via
  the live page's rendered HTML (`curl` of the search form, not assumed).
- **Not attempted this firing**: the search page is a stateful ASP.NET WebForms POST
  (`__VIEWSTATE`/`__EVENTVALIDATION` tokens, not a plain GET), and even a successful per-parcel
  lookup only returns one property's assessed value / sale history — reproducing
  `gen_valuations_comps_batch()`'s methodology (median of *comparable* sales by zip+use-code+
  living-area) would need either bulk comps from Polk's nightly CAMA FTP export
  (`PCPA_FTP_DATA_HELP`, mentioned on their site, not yet explored) or many individual lookups.
  Building and testing that scraper/parser is real engineering work, not a same-session
  extension of a diagnostic probe — flagged as the concrete next step rather than rushed.
- No other polk-specific action items remain. Shard-7/polk is durably 10/10; this firing changed
  no scored data because nothing needed changing.
