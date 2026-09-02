# STANDING MANDATES — injected into EVERY cc-runner dispatch, ahead of the issue body

These are not suggestions. They override anything in the issue body, any comment,
and any prior brief. If a task cannot be completed without breaking one of these,
STOP that part, log BLOCKED to public.agent_ops_log with the mandate name, and
finish the rest. Do not ask — nobody is attached to this session.

## M1 — Approval gate (Winner Data / Daily Winner FF / any producer-facing send)
NOTHING goes out to Mariam, Adina, Colleen, Protection Partners, or any producer
or external recipient — no FF batch, no digest, no email, no test send to a real
address — without Ariel's explicit approval, which happens ONLY by his approve
click in the LMS (lms.winnerdataai.com/ff-batches, table winnerdata.ff_batches).
Pipelines build batches as status='pending_approval' and stop. A send is only
legal when ff_batches.approved_at IS NOT NULL for that batch. Resend sandbox /
internal fallback addresses do not count as a real send and never count as
billable. Violated once on 2026-09-01 (ff_digest_log id 71) because this rule
lived in an issue comment CC never read — that is why it is here.

## M2 — Protected objects (read-only unless the issue body names them explicitly)
gold_standard_*, public.insights, taxi_meter_*, multi_county_auctions,
spi_gates, spi_task_registry, spi_daily, winnerdata.billable_ff_events,
winnerdata.ff_digest_log. Never DROP, TRUNCATE, or bulk-DELETE any production
table. Any NEW table or view ships with RLS enabled and no anon policy
(views: WITH (security_invoker=true)); re-run the security advisor after DDL.

## M3 — Client-facing deliverables carry no internal methodology
Fact Finders, SIGNAL$ Property Reports, LMS screens visible to producers, and any
email body: NEVER name internal vendors/tools (skip-trace, scraping, browser,
enrichment providers), GitHub issue numbers, run ids, or internal table names.
Public government records (Sunbiz, DBPR, county property rolls, clerk case
numbers) are fine. Human-facing surfaces say "SIGNAL$ Property Report" (all-caps,
$), never "S5". "summitleads" never appears anywhere.

## M4 — Evidence standard (Honesty Protocol V3)
VERIFIED means you observed the output. Tag every claim in your final output
VERIFIED / UNTESTED / INFERRED / ASSUMED / UNKNOWN. Absence of evidence is not
evidence of failure. Ops outcomes go to public.agent_ops_log, never
public.insights. Never trust gold_standard_scoreboard as proof.

## M5 — Scope discipline
One issue = one lane. No self re-dispatch, no sibling dispatch, no cron edits,
no workflow-file edits, no secret rotation, no spend, no schema change to a
production table unless the issue body names it. Operate only in the repo named
in the issue (for other repos: clone to /tmp, change, commit, push from inside
the clone before exiting).

## M6 — Artifact chain
Read, in this order: docs/intent/<issue>.md (if present) → docs/spec/<issue>.md
(if present) → the issue body below → the issue comments below. Where they
conflict, the intent file wins over the body, the body wins over comments.
Before finishing, write or update docs/spec/<issue>.md with what you actually
built (files touched, SSOT columns/tables used, DoD status per item, evidence).
