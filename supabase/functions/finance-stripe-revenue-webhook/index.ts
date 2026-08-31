// finance-stripe-revenue-webhook -- TODO / NOT DEPLOYED / BLOCKED ON ARIEL
//
// Purpose (once activated): receive Stripe `payment_intent.succeeded` events
// for Protection Partners / Mariam FF invoicing and write a matching
// finance.revenue_ledger row (status='paid', stripe_payment_intent_id set),
// separate from finance.generate_invoice()'s draft/invoiced lifecycle.
//
// This is a SCAFFOLD ONLY. It is not registered with any
// .github/workflows/deploy-*.yml, so it will not go live from a push. Do not
// add a deploy workflow for this function until the two manual gates below
// are closed -- see docs/canon/CFO_BOOKKEEPING_SOP.md section "Manual gates
// (Ariel-only)".
//
// NOT the same integration as supabase/functions/stripe-webhook/ -- that one
// is the live, already-connected BidDeed.AI S5-report checkout pipeline
// (entity_code='biddeed'). This file is a distinct, currently-inert stub for
// the Protection Partners revenue lane (entity_code='protection_partners').
// Do not merge these two -- different products, different Stripe accounts
// most likely, different failure blast radius if one breaks the other.
//
// BLOCKED on (Ariel-only, cannot be done by an agent):
//   1. Ariel connects a Stripe account for Protection Partners billing
//      (Claude.ai Settings > Connectors, or supplies a Stripe secret key +
//      webhook signing secret as a GH secret / Supabase vault entry).
//   2. Ariel decides which Stripe account/mode (live vs Protection Partners'
//      own) this should point at -- do not assume it reuses the BidDeed.AI
//      Stripe account above.
//
// Intended shape once unblocked (do not implement further until #1 and #2
// are closed -- fabricating a "connection" that silently no-ops is worse
// than leaving this flagged, per this task's non-goals):
//
//   1. Verify the Stripe webhook signature using a secret pulled via
//      finance.vault-gated accessor (see CREDENTIAL HANDLING in CLAUDE.md --
//      never inline a raw key, never log it, never echo it).
//   2. On `payment_intent.succeeded`:
//        - look up the finance.revenue_ledger row by
//          stripe_payment_intent_id (set when the invoice/payment link was
//          created) or by metadata.invoice_id
//        - if found: UPDATE status='paid', paid_at=now()
//        - if the referenced finance.invoices row exists: UPDATE its
//          status='paid'/paid_at too
//   3. Never write a NEW revenue_ledger row from this webhook -- revenue
//      rows are created exclusively by the
//      trg_billable_ff_events_revenue_ledger trigger
//      (finance.fn_billable_ff_events_to_revenue_ledger) or by
//      finance.record_expense's revenue-side sibling if one is ever added.
//      This webhook only ever transitions status invoiced -> paid.
//
// export default function handler is intentionally omitted -- there is
// nothing safe to execute yet.
export {};
