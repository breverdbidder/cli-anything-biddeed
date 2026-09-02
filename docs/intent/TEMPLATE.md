# Intent — issue #<N> — <short title>

<!-- Copy to docs/intent/<N>.md BEFORE dispatching issue N. Fill every section;
     "n/a" is a valid answer, blank is not. This file is read by CC before the
     issue body and outranks it. Standing mandates (docs/intent/MANDATES.md) are
     injected automatically — do not restate them, add task-specific ones. -->

## Originator
Who raised this and in what role (founder / producer / customer / agent-detected from logs).

## Problem, in the originator's words
Two to five sentences. What is wrong or missing, who feels it, how often.

## Outcome that counts as done (DoD)
Numbered, each item independently checkable by SQL, curl, or a file diff.
1.
2.

## Non-goals
What this issue must NOT touch, even if it looks adjacent.

## SSOT this task must use
Exact table.column / RPC / view / doc path. Never let CC guess a column
(2026-09-01 lesson: digest read leads.consent_certificate instead of
ff_batch_leads.contact_confidence).

## Task-specific mandates
Rules that apply only here (e.g. "batch_date = prior auction day", "AMS-agnostic").

## Negative test
One thing that must still be FALSE / unchanged after the work.

## Constraints
Time, quota, ordering, dependencies on other issues.
