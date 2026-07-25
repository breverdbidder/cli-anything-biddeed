# GOLD STANDARD SHARD-3: marion, dixie, baker — 2nd firing addendum (271433e2)

- dispatch_id: 271433e2-9df5-4656-be3d-e06d53b6dd0d (same dispatch fired twice same day)
- prior session: `docs/gold-standard-sessions/shard3-marion-dixie-baker-2026-07-25.md`, commit `8828b767`, already SHIPPED to main
- this session: independent 3rd-pass re-verification, no duplicate diagnosis work, no new writes needed

## Why no new fix work this firing

On arrival, `pencil_dod_evaluate_county` live for all three counties matched the prior
same-day session's numbers exactly (marion 10/10, dixie C/D 75.8% FAIL, baker C/D/E/I
20.0% FAIL). Reading that session's report showed it already ran a genuinely
differentiated, multi-method investigation (curl protocol-level reverse-engineering +
live Playwright/Chromium browser automation) and reached an adversarially-verified,
evidence-backed conclusion: both counties' residual gaps are blocked on a **Cloudflare
Turnstile human-verification challenge** gating the Civitek OCRS court-records portal
(`civitekflorida.com/ocrs/county/{02,15}`), plus a standing `FIRECRAWL_API_KEY` credit
exhaustion. Re-running the identical blocked approach would violate cost-discipline and
"one attempt per approach."

## What this firing did instead (fresh, independently verified)

1. Re-ran `pencil_dod_evaluate_county` for all three counties — **zero regression**,
   byte-for-byte match with the prior firing's numbers (except H freshness drift).
2. Re-ran `scripts/shard8_baker_e_parcel_source_gap_diagnostic.py` live against
   `baker.realforeclose.com` — still `has_parcel_value=False`,
   `has_property_address_field=False` for all 3 currently-listed target cases
   (022025CA000148/022026CA000007/022026CA000018CAAXMX). Source-side gap unchanged.
3. Confirmed `FIRECRAWL_API_KEY` is still HTTP 402 (insufficient credits) — control
   call against `https://example.com` fails identically.
4. Confirmed `bakerpa.com` is still HTTP 521 (Cloudflare origin unreachable) —
   unchanged since the original April 2026 diagnostic.
5. Probed **three alternate portals not tried in the immediately-prior firing**, looking
   for a non-Civitek route around the Turnstile gate:
   - `jud3.flcourts.org` (3rd Judicial Circuit, covers dixie) — connection unreachable
     (curl http_code=000).
   - `circuit8.org` (8th Judicial Circuit, covers baker) — HTTP 200 but is a general
     circuit-info site with no case-search capability.
   - `myfloridacounty.com` (statewide official-records index some FL clerks opt into)
     — HTTP 200, but its own footer links to `civiteksolutions.com` confirming it is
     the **same Civitek vendor family** already found Turnstile-gated, and its
     homepage does not list baker or dixie as participating counties.
   All three dead-end; none contradicts or extends the prior firing's blocked
   conclusion.

## Result

No metric movement (correctly — nothing new was found to write). One additional
`gold_standard_ultraloop_audit` row logged (survived=true) documenting this
independent re-confirmation, so the blocked status now has **three** independent
confirmations on record (original April diagnostic, same-day prior firing, this
firing) rather than resting on a single claim.

## Standing blockers (unchanged, still flagged for Ariel)

1. `FIRECRAWL_API_KEY` account-wide credit exhaustion (HTTP 402 on every call).
2. Civitek OCRS Cloudflare Turnstile checkbox gate on `civitekflorida.com/ocrs/county/{02,15}`
   — the only remaining path to unblock dixie's 6 DIXIE-SYNTH rows + case
   `15-2023-CA-57`, and baker's 6 case numbers (12 rows), requires either a human
   manually solving the lookups once, or an explicitly Ariel-authorized CAPTCHA-solving
   integration. Not attempted programmatically per prior firing's guidance.
3. `bakerpa.com` HTTP 521 (origin unreachable) — independent of the Turnstile issue,
   would need to come back online for the fallback lookup path in the original
   diagnostic script's "next-session TODO" to be viable.

No further action recommended for marion/dixie/baker until one of the three blockers
above changes.
