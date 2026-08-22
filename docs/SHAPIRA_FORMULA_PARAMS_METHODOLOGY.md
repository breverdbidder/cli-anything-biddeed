# shapira_formula_params — methodology of record

Recovered from chat-session history 2026-08-21 after a forensic audit found the
Aug 14 recalibration had no trace in the repo. This doc makes the methodology
tracked so it never has to be reconstructed from transcripts again.

## Semantics (formula_v2, foreclosure)

Per county x property_type, derived from multi_county_auctions SOLD outcomes:

- optimal_bid_pct_of_assessed = MEDIAN(tier1_sold_amount / assessed_value)  — where to bid
- bid_floor_pct               = P25 of same ratio  — below this is historically thin
- bid_ceiling_pct             = P75 of same ratio  — above this is historically overpaying
- plaintiff_discount_factor   = 1.0 BY DESIGN for third-party bidders

## Why plaintiff_discount_factor = 1.0 is deliberate (Aug 1 2026 decision)

The $25 S5 report customer IS the third-party bidder. They do not discount their
own bid for plaintiff behavior; competition risk is already priced by the ML
sell-probability adjustment in composer.js (mlAdjusted = base * (0.5 + p*0.5)).
A separate plaintiff discount here would double-count competition risk.

Historical near-zero values (e.g. broward 0.124, polk 0.112, hillsborough 0.147,
circa pre-Aug-14) were garbage from an earlier derivation and caused the
sub-floor-ceiling bug caught live on Hillsborough 292025CA003306A001HC.
The Aug 14 2026 propagation (model_version formula_v2_recal_20260814_propagated_from_marion,
124 rows / 33 counties) replaced them with the 1.0 convention — that write was a
chat-session Supabase write with no repo trace, hence this doc.

DO NOT derive this factor from plaintiff-won clearing/judgment ratios: that
population is selection-biased (plaintiffs keep what nobody outbids) and yields
~0.3-0.6 values that would re-crush ceilings. Verified and rejected 2026-08-21.

## Marion reference row (validated)

county=marion, foreclosure, ALL: 0.676 / 0.514 / 0.900 / 1.000, n=167,
model_version=formula_v2_recal_20260801. The July pre-sale flagship call
(ceiling 82,000, sale 73,501) predates this recal; its effective multiplier
(0.715 x 0.8423 = 0.602) is LOWER than current (0.676), so any post-recal ceiling
drop on the Marion card traces to the value-midpoint/ARV pipeline, not these params.

## Rule going forward

Any write to shapira_formula_params MUST land as a tracked migration or a script
in this repo with an agent_ops_log entry. Chat-session ad hoc writes to this
table are prohibited — they cost a full forensic day to reconstruct.
