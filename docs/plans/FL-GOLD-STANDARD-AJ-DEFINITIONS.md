# FL GOLD STANDARD — A–J LETTER DEFINITIONS & DELIVERABLES

**SSOT:** `public.pencil_dod_criteria` (this doc is generated from it; the table wins on any divergence)
**Gold standard** = all ten PASS · **Certified** = 10/10 on two consecutive scoring runs 12h apart (includes PropertyOnion parity litmus) · **Critical three** = B, I, J

---

## A — Dual-Product Coverage `boolean`
**Definition:** Both foreclosure AND tax-deed auctions present for the county.
**Delivered:** The complete county auction marketplace in one screen. The customer never needs a second source to know what is for sale in the county. BidDeed + ZoneWise are always paired; a county is never gold on one product alone.

## B — Verified Realized Outcomes ⭐ `≥95% of closed`
**Definition:** Share of closed auctions with a realized outcome from an INDEPENDENT authoritative source (clerk/official records). data_source promoted from our own tables or derived from PropertyOnion = hard fail.
**Delivered:** Clerk-verified history of what every closed auction ACTUALLY sold for. The training corpus for the Shapira model and the trust foundation of every number shown. THE moat — Gap B.

## C — Parity Clean `≥95% of auctions`
**Definition:** Auctions matched clean (zero field divergence) against the PropertyOnion litmus.
**Delivered:** Proven field accuracy — case numbers, dates, amounts independently confirmed. The customer can bid off our row without re-checking the county site.

## D — Parity Any `≥95% of auctions`
**Definition:** Auctions locatable in the litmus source (clean or divergent match).
**Delivered:** Proven completeness — nothing sells in the county that BidDeed did not list. Zero blind spots. (For Brevard, foreclosure parity runs against the courthouse calendar — see COUNTY EXCEPTIONS in FL-GOLD-STANDARD-SSOT.md.)

## E — Parcel Linkage `≥95% of auctions`
**Definition:** Auctions joined to a parcel_id.
**Delivered:** Every auction wired to its real parcel — the spine that turns a court docket line into a mappable, zonable, valuable property. Unlocks the map pin, the zoning read, and the property card.

## F — Tier-1 Authoritative Sold Price `≥95% of closed`
**Definition:** Closed auctions carrying a Tier-1 authoritative sold amount (never inferred, never PO).
**Delivered:** The ground-truth price feed: powers CMA Arm-1 (distressed entry comps), model calibration, and the "what did it really go for" answer.

## G — Zoning Gold Standard `≥95%`
**Definition:** Minimum of density / FAR / parking-per-1000 coverage of applicable parcels (the weakest dimension sets the bar).
**Delivered:** ZoneWise zoning intelligence — what can legally be built, demolished, split, or converted. The development-upside dimension no auction list has.

## H — Data Freshness `≤48 hours`
**Definition:** Most recent auction activity timestamp within the SLA.
**Delivered:** A live market, never a stale one. Cancellations and reschedules same-day; the staleness-arbitrage failure mode of frozen competitor feeds is structurally impossible.

## I — PENCIL Property Card Render-Complete ⭐ `≥95% of cards`
**Definition:** The assembled property card carries the full customer-visible set: address + geo (lat/long) + value (assessed/market) + zoning code.
**Delivered:** The card the customer actually opens, rendering complete — map pin, value, zoning — on 95%+ of auctions. The capstone OUTPUT gate: inputs A–H can all pass while the card fails to render; only the rendered card counts.

## J — Shapira Deal Thesis ⭐ `≥95% of auctions`
**Definition:** bid_decisions row carrying the FULL thesis: Distress Triangle (distress_location + distress_property + distress_owner) AND two-arm CMA — Arm-1 cma_distressed (comparable distressed assets sold to third parties → entry basis for max_bid) AND Arm-2 cma_resale (retail ARV from HUD/HH repo, Zillow, Redfin, Realtor.com) — AND Shapira ml_score AND max_bid.
**Delivered:** The investment recommendation itself: equity = resale ARV − max_bid − repairs, with both arms validated. A single-ARV CMA hides the thesis; the spread between the arms IS the product. This is what the customer pays for.

---

## The dependency chain (why the letters are ordered)
A/D give the market → C/F/B give the truth → E gives the spine → G enriches it → I renders it → J monetizes it → H keeps it alive. The critical three (B, I, J) are: the truth moat, the rendered product, and the monetized thesis.
