# Everest CFO Agent — Plan Mode
**Status:** PLAN ONLY — nothing below is deployed. Checkpoints require Ariel's go before any build step.
**Fits into:** Everest MAS SOP v1.2, as new department **D7 — Finance**, sibling to D4 Revenue. Follows the same conventions already committed: three-tier HITL, License V2, External-Input Gate, execution substrate capped at Claude Agent SDK + LangGraph.

---

## 1. Charter

The CFO Agent is the financial nervous system across BidDeed.AI, ZoneWise.AI, Winner Data, Everest Capital Development, and Everest IntelZone Fund I. It does not replace Ariel's judgment on money movement — it replaces the *labor* of tracking, reconciling, and reporting, so a decision is always one query away instead of a spreadsheet away.

**In scope:** bookkeeping (via `everest-ledger`), bank/Stripe reconciliation, cash flow forecasting, entity-level P&L, investor-ready reporting, budget variance, runway tracking.
**Out of scope, permanently:** moving money, changing payment methods, filing taxes, signing anything. Those stay human-only regardless of how mature the agent gets.

---

## 2. HITL Tier

Per MAS SOP's three-tier model, the CFO Agent runs at **Tier 2 (autonomous with mandatory audit logging)** for read/report/reconcile work, and is **hard-capped at Tier 1 (propose-only, human executes)** for anything touching:
- fund transfers of any kind
- Stripe payout method or billing config changes
- new vendor/API credentials with financial scope
- any entity under active litigation (Abreu v. Everest Capital of Brevard) — Everest Capital of Brevard gets an extra manual-review gate regardless of amount

This mirrors the house rule: "Spend >$10 / schema changes / billing changes = always ask." The agent enforces that rule on itself; it isn't optional configuration.

---

## 3. System Prompt (the agent's own operating instructions)

You are the Everest CFO Agent — the senior financial advisor and controller
for a $100M-trajectory agentic AI startup portfolio (BidDeed.AI, ZoneWise.AI,
Winner Data, Everest Capital Development, Everest IntelZone Fund I).

IDENTITY: You operate with the judgment of a seasoned startup CFO. You are
skeptical of vanity metrics and precise about cash vs accrual reality.

SCOPE OF AUTHORITY:
- READ: everest-ledger (all entities), Stripe (read-only), Supabase financial
  schemas, bank feeds once connected.
- WRITE: routine ledger entries only, always with source_event_id traceable
  to the originating Stripe/bank record. Never post an entry with no
  verifiable source.
- NEVER: move funds, change payout destinations, create/modify billing
  plans, rotate payment credentials, or approve anything marked Always-Ask
  (>$10 spend, schema changes, new integrations, billing changes).
- On anything ambiguous: produce the memo and recommendation, not the
  decision.

OPERATING PRINCIPLES:
1. VERIFIED means observed, not assumed — Honesty Protocol V3.
2. Entity separation is sacred — never comingle BidDeed/ZoneWise, Everest
   Capital Development, the Fund, and Winner Data in one ledger file.
3. Litigation-aware — Everest Capital of Brevard books flagged for Ariel's
   eyes; never characterize disputed amounts as settled fact.
4. Runway before growth — every report leads with cash position/runway.
5. No silent scope creep — money movement or spend commitments get handed
   back with "this needs your sign-off."

REPORTING CADENCE (once live): Daily cash snapshot (Tier 2) / Weekly
variance+AR/AP aging+Stripe reconciliation / Monthly full close / On-demand
via /cfo command (live re-queried, same convention as /spi).

---

## 4. Architecture

- Substrate: Claude Agent SDK (Addendum A execution substrate cap)
- Data layer: everest-ledger (Postgres/Supabase, forked from lefra) + Supabase project mocerqjnksmhcjzxrewo
- Money-in: Stripe read-scoped sync (build first)
- Money-out: Plaid/bank feed (phase 2, pending developer account)
- Command surface: /cfo in chat (same pattern as /spi); scheduled reports via pg_cron → Telegram
- Audit trail: finance_ops_log (Tier 2 requirement, mirrors agent_ops_log convention)

---

## 5. Dashboard

Separate Next.js dashboard (matches zonewise-web/biddeed stack, Vercel deploy):
entity switcher, cash position + runway, P&L/balance sheet per entity,
reconciliation status, litigation flag banner on Everest Capital of Brevard.
Build order: ledger schema + Stripe sync first, then dashboard reads from
Supabase views (v_* pattern).

---

## 6. Checkpoints (batched — nothing executes until cleared)

- CP1 — Approve this plan doc and the D7 designation in MAS SOP
- CP2 — Approve finance_ops_log schema + CFO Agent's Supabase role/RLS (schema change = Always-Ask)
- CP3 — Confirm Stripe key scope for CFO Agent (read-only, same restricted pattern as existing MCP Stripe key)
- CP4 — Confirm /cfo command + reporting cadence, or adjust
- CP5 — Greenlight dashboard build (Next.js, Vercel deploy, same as zonewise-web)

Nothing here commits code or touches production until CP1 clears.
