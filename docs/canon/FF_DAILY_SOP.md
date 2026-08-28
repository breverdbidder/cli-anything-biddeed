# Daily Winner FF — Standard Operating Procedure

**Status:** canonical. Supersedes prior ad-hoc enrichment practice.
**Derived from:** the 2026-08-27 batch (28 leads, 0 → 10 billable, $1,074,500 in sales value).
**Owner:** Ariel Shapira · **Consumer:** Protection Partners, Producer: Mariam Shapira

---

## 0. Non-negotiables

1. **The Daily FF batch for day *N* is built from day *N-1* auction results.** Never query the current date.
2. **B2B only.** Winner Data supplies property and ownership data to licensed agencies. It never contacts property owners and never markets foreclosure relief.
3. **Client-facing FFs never name internal vendors, tools, or issue numbers.** Public government records (state corporate registry, county property roll, court case numbers) are citable. Internal tooling stays in chat and issue threads.
4. **Batch stops at `pending_approval`.** No `sent_at`, no email to the producer, without Ariel's explicit sign-off.
5. **Never fabricate.** A rejected false positive is a success. `UNRESOLVED` is an acceptable, expected outcome.

---

## 1. Pipeline stages

```
county clerk results
   ↓  (1) harvest winning bidder names
   ↓  (2) classify THIRD_PARTY vs PLAINTIFF
   ↓  (3) build batch — third-party winners only
   ↓  (4) identity resolution
   ↓  (5) second-source confirmation      ← MANDATORY
   ↓  (6) compliance screen               ← MANDATORY
   ↓  (7) render FF + QA
   ↓  pending_approval → Ariel → Mariam
```

### Stage 1 — Harvest
Pull winning bidder names for the prior auction date across all counties with SOLD rows.
Report coverage honestly as `X/Y SOLD rows have a bidder name`, with a per-county reason for every gap
(site blocked, name not yet posted, login failed). Never mark unknowns as PLAINTIFF by default.

### Stage 2 — Classify
`tier1_buyer_type` = THIRD_PARTY or PLAINTIFF by matching the bidder against the plaintiff/lender name.
Plaintiff and lender buybacks (Fannie Mae, Rocket, trustee entities, HUD, servicers) are **not** FF leads.
Unknowns stay NULL — they are not guessed into either class.

### Stage 3 — Build
Insert `winnerdata.ff_batch_leads` for THIRD_PARTY winners only, idempotently
(check-before-insert on `case_number` + `batch_date`). Set `ff_batches.lead_count` from the real
inserted count, never from an estimate. **Persist each lead as it resolves** — never gather-then-bulk-write.

### Stage 4 — Identity resolution

Route by buyer type:

| Buyer type | Path to the human |
|---|---|
| **Business entity (LLC/Inc)** | State corporate registry by entity name → registered agent / principal |
| **Individual** | State registry *officer/agent* search by person name → their address; if none, county property roll owner-of-record in the same county |
| **Land trust** | The trust instrument names its trustee in the recorded buyer description → treat the trustee as a person and resolve as above |
| **Nominee-agent entity** | STOP. See §3. |
| **Attorney-as-trustee** | STOP. See §3. |

Rule: **exact-or-near-exact name match, and the result must tie to Florida** (or to the buyer's known
FL mailing address). A cross-state, differently-named, or inactive near-match is a **false positive —
reject it**. Worked example: a business-listing search for "Invictum Investments LLC" returned
"Invictus Growth" in San Mateo, California. Accepting that would have sold a California tech firm's
phone as a Florida auction buyer's contact.

### Stage 5 — Second-source confirmation *(MANDATORY — the tier depends on it)*

An identity asserted by one source is **not** VERIFIED-CROSS-CHECKED. Confirm with an independent
reverse-address / person search and require agreement on **name + address + phone**.

> **Always include the unit/apartment number.** A reverse-address check on `415 E Pine St` returned four
> other residents of the building and produced a false negative that wrongly disqualified a $63,100 FF.
> The same search on `415 E Pine St #724` confirmed the principal outright. Unit-level or it doesn't count.

Tier assignment:

| Evidence | Tier | Score |
|---|---|---|
| Two independent sources agree on name + address + phone | `VERIFIED·CROSS-CHECKED` | 0.94–0.98 |
| Registry + single skip-trace source, no contradiction | `LIKELY·SINGLE-SOURCE` | 0.70–0.90 |
| Surname/family or business-premises corroboration only | `LIKELY·SINGLE-SOURCE` | ~0.85 |
| Second source contradicts, or no person match | **not billable** | ≤0.55 |

### Stage 6 — Compliance screen *(MANDATORY — every supplied line)*

**Enumerate every number on file. Never read only the rank-1 number.**

> Reading only top-ranked numbers wrongly disqualified three FFs worth $593,200. One buyer had 5 lines
> (1 DNC, 4 clear); another had 11 lines (8 DNC, 3 clear); a third had 6 (2 DNC, 4 clear).

Screen each line for all three:
1. **National DNC**
2. **State DNC**
3. **Litigator flag** — TCPA-lawsuit exposure. A litigator-flagged number is withheld even if DNC-clear.

A line is suppliable only when `is_clean = true` **and** `litigator = false`.
The FF lists every clear line individually with its type, and states in red how many lines were
withheld as DNC-listed. If zero lines clear → `CONTACT_ENRICHED_DNC_FLAGGED`: identity is delivered,
telephone outreach is blocked, mail remains available subject to the recipient's own compliance review.

### Stage 7 — Render & QA

Template: `templates/FF_TEMPLATE_A_AUCTION_SALES.html` (SSOT). Do not hand-roll a layout.

Required rows: Buyer/Entity Name · Buyer Type · Mailing/Registered Address · **Principal Home Address**
· Case Number(s) · County · State Filing · Registered Agent (or Trustee of Record) · Principal/Manager
· Identity Confidence · **Verification Path**.

> Mailing/registered address and home address are **different fields**. One buyer registers in Lehigh
> Acres but lives in Bonita Springs; another registers at a Naples business address but lives on Golden
> Gate Blvd. Show both.

Property table carries county appraiser **Just Value** and **Assessed Value** per parcel. Multiple
parcels by one buyer belong in **one** FF with a combined total.

Pre-delivery QA, programmatic:
- [ ] No internal vendor names or issue numbers anywhere in the file
- [ ] No raw HTML entities rendering literally (`&mdash;`, `&middot;`)
- [ ] Every supplied phone appears with its line type and DNC-clear status
- [ ] Reported counts match a live re-query of the database

---

## 2. Status vocabulary

| `qa_status` | Meaning | Billable |
|---|---|---|
| `CONTACT_ENRICHED` | Identity resolved, ≥1 fully compliant line | **Yes** |
| `CONTACT_ENRICHED_DNC_FLAGGED` | Identity resolved, all lines blocked | No — intelligence only |
| `IDENTITY_ONLY_PARTIAL` | Principal named, no contact channel exists | No |
| `UNRESOLVED_NO_AUTHORITATIVE_MATCH` | No defensible identity | No |

---

## 3. Known hard blocks — do not force these

| Block | Why | Only real path |
|---|---|---|
| **Commercial nominee agent** (agent service fronting hundreds of entities at one suite) | A privacy layer, not a person connected to the buyer | Annual report filing image, or recorded deed signature block |
| **Attorney-as-trustee** for an undisclosed beneficiary | Beneficiary protected by the attorney-client relationship; the firm is not the owner | None — correctly unresolvable |
| **Common name, no published address** | Multiple plausible candidates, none tied to the subject property | Reject rather than pick |
| **Person exists, zero phone records** | No contact channel exists in any source | None |

A trust is **not** automatically a hard block: if the instrument names a trustee, that trustee is a
person and is resolvable. Two "unpierceable" land trusts became billable this way.

---

## 4. Economics

Per-lead cost is a few cents — registry lookups and a person trace. **One billable FF covers the entire
day's data spend many times over**, so exhaust the cascade before marking UNRESOLVED. Stop only when
the block is one of the §3 categories, or when the parcel value is low enough that further tracing
cannot pay for itself.

Do not stop mid-cascade to request spend approval for routine per-lead lookups; that authorization is
standing. New paid vendors still require sign-off.

---

## 5. Reporting discipline

Every batch close-out states: leads built, contact-matched, DNC-blocked, identity-only, unresolved —
**re-queried live from the database, never from memory**, with the per-county harvest gap list attached.
A session that reports numbers it did not verify against the database has failed, regardless of exit
status.
