# Vendor Management Policy

**Effective:** August 3, 2026 · **Owner:** Ariel Shapira
AI-generated PBC draft — for CPA/ISO auditor review, not a finished attestation.

## 1. Sub-Processor Register

The authoritative, currently-live-verified list of sub-processors is
`docs/security/VENDOR_SUB_PROCESSOR_LIST.md` (last reviewed 2026-08-03, every
vendor security page HTTP-checked live at 200). This policy governs how that
list is maintained; the list itself is the evidence artifact.

## 2. New Vendor Onboarding

Before any new vendor is given access to customer data or added to the
processing path:
1. Confirm the vendor publishes a SOC 2 Type II report or ISO 27001
   certificate on its own trust page — link it, don't take a sales rep's word.
2. Record purpose, data handled, location, and trust-page URL in
   `VENDOR_SUB_PROCESSOR_LIST.md`.
3. If the vendor will touch customer PII, Ariel must approve before the
   integration ships.

`app.mindstudio.ai` is documented as a **non**-sub-processor (allow-listed
outbound link domain only, no customer data flows to it) — an example of the
distinction this policy draws between "appears in the codebase" and "handles
customer data."

## 3. Annual Review

Minimum cadence: every 6 months (next due February 2027, per the vendor
list's own review-cadence section). Review re-confirms each vendor's
published certification status has not lapsed and re-checks each trust-page
URL is still live.

## 4. Contract Requirements

Vendor agreements must include a breach-notification clause. BidDeed.AI does
not currently maintain signed DPAs with every vendor — most rely on the
vendor's standard terms of service, which is disclosed as the current state
rather than asserted as a stronger contractual posture than exists.

## 5. Approval Gate

No vendor with access to customer PII is added to the processing path without
Ariel's explicit approval — there is no other approver, since Everest Capital
USA has zero employees.
