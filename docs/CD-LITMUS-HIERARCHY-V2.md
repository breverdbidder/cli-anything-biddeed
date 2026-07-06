# C/D LITMUS HIERARCHY V2 — CONSTITUTIONAL SSOT
Directive: Ariel Shapira, 2026-07-06. Supersedes PO-only calendar-parity litmus.
DB SSOT (evaluators MUST read): public.cd_litmus_hierarchy

## Hierarchy
1. PRIMARY — RealAuction official platforms (source of truth re-count vs OUR frozen calendar):
   FC: https://{county}.realforeclose.com | TD: https://{county}.realtaxdeed.com / realtdm.com
2. FALLBACK — FloridaBidder.com (Daveco; CI dossier on file)
3. TERTIARY — PropertyOnion: cross-check ONLY. Structural gaps (hamilton = zero PO rows) NEVER block C/D.
   PO remains NEVER a source for resolution/enrichment/underwriting.

## Invariants (unchanged)
- Frozen-calendar denominator guard: all criteria measure vs auctions_total.
- Calendar-parity pre-cert gate now points at the V2 primary source per county.
- certify() fail-closed: 10/10 + adversarial-survival(7d) + calendar_parity + denominator_integrity.
- HISTORY = MOAT: our depth exceeds every litmus source; on history WE set the litmus.

Implementation: issue #10981 (parity build) + #10985 (certify-tick root cause). Guards registered in cc_redispatch_guard.
