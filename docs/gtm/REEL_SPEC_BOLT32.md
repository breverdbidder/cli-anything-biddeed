# BidDeed Reel Spec — bolt32 (32-second BoltMotivation-technique edit)

Every BidDeed reel is built to a fixed 32-second length using a
story-arc-with-hard-timings technique reverse-engineered from a
high-performing Shorts creator's public output (40 shorts sampled,
14K-27M views each). The core mechanic: a ~30s video with an average view
duration over 60 seconds is being watched roughly twice — the video loops
and the viewer rewatches it. The edit is built to make that loop natural,
not to trick the platform.

## T1 — Title

Curiosity-gap title, third person, never explains, ends with an ellipsis
("…") then exactly two emoji from a fixed vocabulary: 😳 😱 🥹 🤯 🥶 😰 ❤️
💔 🏆 👀.

Protagonist is always **the property**, **a bidder**, **the bank**, or
**the county** — never a person's name. Stakes must be concrete: a dollar
figure, a count, or a superlative. Weak-stakes titles have a low ceiling;
titles with real numbers in them have a much higher one.

Validation (all required):
- Starts uppercase
- 20-60 characters before the ellipsis
- Ends with the ellipsis then exactly two vocabulary emoji
- No person's name from the property's own case record; no vendor/tool name
- Contains a `$` figure, a count, or a superlative word

Generate 5 candidates per property; use the first one that passes every
check.

## T2 — Story Arc

A protagonist, a stake, a turn, a payoff — not a list of facts. Postsale:
the stake is the sold price vs. the county's assessed value. Presale: the
stake is the opening bid/judgment vs. assessed value and the auction date.

## T3 — Retention Engineering

- The payoff (the number) lands late in the edit, not up front.
- The final beat returns to the exact opening frame — a real frame match,
  so an autoplay loop visibly cuts back to where it started.
- No subscribe/follow call-to-action. No brand card before the final beat.

## T4 — Delivery

Continuous voiceover narration with emotional delivery tags per beat, large
centered captions (3-5 words at a time), a visual change every 2-4 seconds,
music bed under the voice where a licensed track is available.

## Beat Sheet (hard timings)

| Beat | Window | Content |
|---|---|---|
| Hook | 0.0–2.0s | Title spoken verbatim; opening frame = aerial with the parcel boundary; this exact frame returns at the end |
| Setup | 2.0–8.0s | County/city, size, the opening number; a street-level shot |
| Tension | 8.0–20.0s | The value spread, condition notes, comps; several visual cuts |
| Payoff | 20.0–28.0s | The number — sold price/value-band delta or bid-vs-assessed gap; the largest caption in the edit |
| Loop line | 28.0–31.0s | One line restating the hook as a callback |
| End | 31.0–32.0s | Returns to the opening frame; small wordmark + QR |

Total: 32.000 seconds ±0.1s.

## Sale-Type-Specific Data-Quality Rules (issue #19794, CMO Factory CP3c-D)

Florida tax-deed sales are **absolute auctions**: there is no plaintiff or
lender able to credit-bid and reclaim the property the way a foreclosure
bank can. Every tax_deed row that closes to a genuine third-party buyer is
therefore a real transaction by construction, once you have confirmed a
sale to a third party actually happened.

- A `tax_deed` row with `sale_result = 'SOLD_THIRD_PARTY'` (or the schema's
  own verified-outcome override, `tier1_sale_status = 'SOLD'`) and a real
  `sold_amount`/`tier1_sold_amount` > 0 does **not** need the
  `winning_bidder`-ambiguity check that a `foreclosure` row needs — there is
  no lender able to be the buyer of record instead of a third party, so
  that specific ambiguity cannot arise for a tax deed.
- This is **not** the same thing as "any tax_deed row with a status is a
  sale." A tax certificate applicant/holder CAN still end up owning the
  property when nobody outbids the minimum required bid (raw status
  "SOLD APPLICANT" / "SOLD_PLAINTIFF" in this schema) — that is a real,
  distinct, non-third-party outcome and must still be excluded from reel
  candidates, exactly as `SOLD_PLAINTIFF` is excluded on the foreclosure
  side. So does a redeemed certificate (owner paid off the debt before
  auction — no sale occurred at all) or a still-scheduled/pending auction.
  Do not conflate "tax deed needs no winning-bidder check" with "tax deed
  needs no sale-happened check" — they are different checks; only the first
  is waived.
- `opening_bid` / `base_bid` / `po_opening_bid` are the certificate's
  minimum required bid, published before the auction — never treat these as
  `sold_amount`. Live-verified 2026-09-03: for case 2026-0083TD (Walton),
  `opening_bid` was $2,103.10 while the schema's own re-verified
  `tier1_sold_amount` was $2,700 — real bidding happened above the minimum,
  and using `opening_bid` as the sale price would have understated it.
- `public.clerk_ssot_sale_rows` (the calendar-parity SSOT) carries no price
  or parcel column of its own — it must be joined to
  `public.multi_county_auctions` on `(case_number, county)` to get
  `sold_amount`/`parcel_id`/`property_address`/`assessed_value`. See
  `scripts/biddeed_reels_clerk_ssot_taxdeed_backfill.py` for the
  qualifying-candidate query and `docs/spec/19794.md` for the live
  join-rate/schema evidence this was derived from.

## Discount-Pct vs Dollar-Delta Archetype Framing (issue #19794 step 6)

`agents/reel_studio/hook_writer.py::recommend_framing_archetype()` computes,
per property, `dollar_delta = assessed_value - sold_amount` and
`pct_below_assessed = dollar_delta / assessed_value * 100`, then biases one
of the K archetype slots toward whichever framing the property's OWN
numbers support — never asserted from `sale_type` alone:

- `dollar_delta >= $115,000` -> `shock_number` (the big-number story)
- `pct_below_assessed >= 65%` -> `hidden_value_reveal` (the big-discount story)
- neither bar cleared -> no bias; falls through to unbiased random selection

Thresholds are the top-quartile (p75) of `pct_below_assessed`/`dollar_delta`
across every genuinely-sold `multi_county_auctions` row (`sale_result =
'SOLD_THIRD_PARTY'` or `tier1_sale_status = 'SOLD'`, `assessed_value >
$500`), both sale types combined, re-derived live 2026-09-03 (n=2,303):
p75 `pct_below_assessed` = 65.6%, p75 `dollar_delta` = $115,460.

**This corrects, not confirms, this issue's own stated calibration.** The
issue assumed tax deed "usually wins" on discount percentage. Live
per-sale-type numbers say the opposite at the p75 mark:

| sale_type   | n (genuinely sold, w/ assessed) | p75 pct_below_assessed | p75 dollar_delta |
|---|---|---|---|
| tax_deed    | 826  | 46.8% | $5,500 |
| foreclosure | 1,477 | 79.6% | $149,900 |

Foreclosure leads on BOTH axes at this percentile in this dataset — tax
deed's typical (median) sale is close to assessed value (median
sold/assessed ratio 108.3%, i.e. near or slightly above assessed), not the
~40%-of-assessed the issue cited. `bank_vs_house` remains a valid discount-
framing option per the issue text but is deliberately not force-picked by
`recommend_framing_archetype()` — it has its own hard precondition
(confirmed bank/lender plaintiff, see `check_archetype_data_match`) that
this function has no visibility into.

## Measurement

The public reel player emits watch-progress events (play, 25%, 50%, 75%,
100%, loop) so an internal average-view-duration proxy exists independent
of any third-party platform analytics. A reel template is promotable to the
next factory checkpoint only once its median viewer reaches 100% watch-
through (or loops) across at least 20 real plays.

## Methodology Note — reconciling the issue's ~40%/~61% figures (issue #19794, addendum)

A second, concurrent #19794 dispatch (see "Discount-Pct vs Dollar-Delta Archetype Framing"
above) computed p75 `pct_below_assessed` per-row and found foreclosure leading tax_deed on
discount percentage, apparently contradicting the issue's own claim that tax deed "usually wins"
on discount percentage. Both results are correct — they answer different questions:

- **Per-row percentile** (p75 of `pct_below_assessed` computed per row, above): answers "what
  does a top-quartile SALE look like." Dominated by tax deed's own bimodal distribution — a large
  share of tax_deed certs sell near or above assessed value (median sold/assessed ratio ~108%),
  pulling the percentile view toward foreclosure.
- **Ratio of averages** (`avg(sold_amount) / avg(assessed_value)`, i.e. "if you summed every
  dollar sold and every dollar assessed, what's the ratio"): reproduces the issue's own headline
  numbers exactly — foreclosure 60.5% (avg sold $161,208 / avg assessed $266,540), tax_deed 39.9%
  (avg sold $17,263 / avg assessed $43,241), both VERIFIED live 2026-09-03 against the same
  `multi_county_auctions` sold-row population. This is portfolio-level economics (aggregate
  dollars at stake), not a statement about the typical individual sale.

Neither methodology is wrong; they measure different things and a reader citing "tax deed sells
at ~40% of assessed value" should know that is the aggregate-dollar view, not the typical-sale
view. `recommend_framing_archetype()`'s p75-per-row thresholds are the correct choice for a
per-property archetype bias (it is scoring one property against the population of individual
sales, not aggregate portfolio economics) — this note exists so the two numbers in this file
don't read as contradictory without explanation.
