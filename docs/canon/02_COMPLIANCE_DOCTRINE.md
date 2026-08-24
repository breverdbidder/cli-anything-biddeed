# CANON 02 — Compliance Doctrine

**Canon overrides any log, memory line, or prior chat.** See [`README.md`](README.md).
Authoritative as of Aug 24 2026, per counsel guidance. Mirrors
`public.unified_context.winnerdata_canon_v1.compliance`.

## The doctrine

**B2B data sales only.** Winner Data sells resolved property signals to
businesses. It does not:

- Contact homeowners
- Run foreclosure or mortgage-relief marketing
- Use save-the-home or cure-default scripts
- Participate in the underlying transaction in any way
- Accept compensation tied to a homeowner's outcome

This must hold across **every surface**: sales materials, data labels,
contracts, invoices, employee instructions, and support interactions. There
is no internal-only exception — an instruction that's fine in a training doc
but would look like homeowner solicitation if a customer saw it is still a
violation.

## Why this specific line

Fixed per-lead / per-decision pricing (see
[`01_WINNER_DATA_CANON.md`](01_WINNER_DATA_CANON.md#pricing)) keeps Winner
Data outside the statutory definition of a regulated foreclosure-rescue
actor. Compensation must never be tied to a homeowner outcome (e.g. "we get
paid if the sale closes on terms favorable to the homeowner") — that is the
trigger condition the statute is built around.

## Statutory hooks (Fla. Stat. § 501.1377)

- **§ 501.1377(2)(b)** — a regulated actor is a "foreclosure-rescue
  consultant": someone who solicits a homeowner for pay in connection with a
  foreclosure. Winner Data does not solicit homeowners at all.
- **§ 501.1377(2)(c)** — a regulated service is stopping or delaying a
  foreclosure, or curing a default. Winner Data does not offer this service
  to anyone, homeowner or otherwise.
- **§ 501.1377(2)(e) / (g)** — "homeowner" is defined as the record title
  owner of property with a recorded lis pendens. Winner Data's subject
  avatars (MLS sellers, auction winners — see
  [`01_WINNER_DATA_CANON.md`](01_WINNER_DATA_CANON.md#subject-avatar)) are
  not contacted, so this definition never becomes operative against Winner
  Data's own conduct — but it is the reason the schema rule below exists:
  once a `foreclosure_status`/distress field exists on a sellable feed, the
  question of who counts as a "homeowner" under this statute becomes live.

## Contract shape

Standard instrument: **Data License Agreement**, not a service or referral
agreement. Required terms:
- Fixed advance fee (never outcome-contingent)
- Prohibited-use clause (no homeowner contact, no foreclosure-rescue use,
  no re-solicitation for compensation tied to outcome)
- No-agency clause (Winner Data is not the customer's agent and does not
  participate in the customer's transaction)
- Customer indemnity
- Support scoped strictly to format, delivery, and data accuracy — never
  scoped to helping the customer contact or negotiate with a homeowner

## Schema rule

**No `distress` / `foreclosure_status` field on any seller feed.** This is
not a UI decision — it is the compliance boundary encoded in the data model.
Adding such a field to a sellable feed would create exactly the kind of
foreclosure-linked data product that turns a B2B data sale into something
that looks like foreclosure-rescue solicitation once resold. If a future
feature seems to need this field, treat that as a signal to re-read this
doctrine and get counsel sign-off before building, not a signal to add the
column.
