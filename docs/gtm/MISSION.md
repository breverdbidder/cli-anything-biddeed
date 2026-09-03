# MISSION.md

Source: `docs/gtm/META.md` §2, copied verbatim (CMO Factory CP0, issue #19777).
This file is a **protected path** — see `.factory/gtm/locks/floor.json`. The
validator role reads this from `main`, never from a PR branch. A PR that
modifies this file is auto-rejected by `factory/gtm/gate.py`.

## 2. MISSION.md

Product: Winner Data = FL property-data platform layer (10.5M-parcel moat) supplying SIGNAL$ (resolved property signals) to businesses. BidDeed.ai = its auction-intelligence surface (SIGNAL$ Property Report, 18 sections). "We deliver the SIGNAL$. First."

NEVER-list (factory rejects as drift even when well argued):

1. Homeowner contact of any kind (mailers/texts/calls/ads). B2B data sales only.
2. Foreclosure-relief / save-your-home / mortgage-relief messaging in any channel.
3. Naming a buyer, owner, or bidder in any reel, page, caption, post.
4. Vendor/internal-tooling names in public media (Tracerfy, Bright Data, Apify, OpenRouter, ElevenLabs, issue numbers).
5. Insurance-shaped SIGNAL$ to anyone but Protection Partners (exclusive statewide, all lines).
6. External notification/approval channels (Telegram/Slack/SMS). Approvals in LMS + Claude chat only.
7. Unverified numbers in copy ("49,973 outcomes", "82.6% ensemble", county counts not re-queried from v_certified_counties, MRR/ARR projections as fact). Honesty V3 applies to marketing copy.
8. A second dispatcher, CRM, or content queue. Existing tables are SSOT.
9. Paid ads before one confirmed end-to-end purchase (spi_gates.test_purchase open).

## Compliance checks derived from this list (used by `factory/gtm/gate.py`)

`gate.py` runs 6 compliance checks over a given PR/artifact set — the mapping
from NEVER-list items to checks is not 1:1 (items 6, 8, 9 are structural/
process rules enforced by the factory's own architecture — GHA-only dispatch,
single SSOT tables, dial-gated publish — not scannable text patterns):

| # | Check | NEVER-list item(s) | Method |
|---|-------|---------------------|--------|
| 1 | `banned_terms` | #4 vendor names, #7 unverified-number phrasing | regex allow/deny list sourced from this file (§3/§4 below) |
| 2 | `person_name_detector` | #3 naming a buyer/owner/bidder, M7 (MANDATES.md) | NER-lite heuristic + denylist of known case-party name fields |
| 3 | `vendor_name_detector` | #4 | substring match against `VENDOR_NAMES` |
| 4 | `homeowner_contact_scan` | #1, #2 | keyword scan for mailer/text/call/ad copy targeting a homeowner, and foreclosure-relief phrasing |
| 5 | `certified_county_count_match` | #7 (county counts not re-queried) | re-query `public.v_certified_counties` live, compare to any county count literal in the artifact |
| 6 | `insurance_exclusivity_scan` | #5 | flag any insurance-shaped SIGNAL$ copy not scoped to Protection Partners |

### §3 — vendor/internal-tooling names (banned in any public asset)

Tracerfy, Bright Data, Apify, OpenRouter, ElevenLabs, skip-trace, scraping,
browser (as an enrichment method), GitHub issue numbers, run ids, internal
table names, "summitleads", "S5" (must read "SIGNAL$ Property Report").

### §4 — unverified-number patterns (banned unless re-queried live in the same run)

Hardcoded outcome counts, hardcoded ensemble/accuracy percentages, county
counts not sourced from a live `v_certified_counties` query in the same
artifact-generation run, MRR/ARR figures presented as fact rather than
projection.
