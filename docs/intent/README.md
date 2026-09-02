# docs/intent/ — the first link of the artifact chain

Convention adopted 2026-09-02 (source: Anthropic AI-native SDLC playbook, adapted
to MAS SOP v1.2). Chain: intent → spec → plan → build → test → deploy → maintain.

- `MANDATES.md` — standing rules injected into EVERY cc-runner dispatch, before
  the issue body. Edit this file to add a permanent rule; never rely on an issue
  comment for a rule (CC reads comments only as an appendix, lowest precedence).
- `TEMPLATE.md` — copy to `<issue-number>.md` before dispatch.
- `<issue-number>.md` — the intent for that issue. Read first by the wrapper
  (`.github/workflows/cc-runner-ghonly.yml`, step "Fetch issue brief").
  Precedence: intent file > issue body > issue comments.

Rules:
1. Intent is written by the originator (or by chat-Claude on their behalf) and
   committed BEFORE `fire_workflow_dispatch`. A dispatch without an intent file
   still runs (backward compatible) but the run breadcrumb flags it `intent=missing`.
2. Intent is versioned by git. Do not edit an intent after dispatch; cancel the
   run, edit, redispatch (CC reads once at session start).
3. Agent-originated intents (Sentinel, cc_redispatch_guard triage) use the same
   template with Originator = the agent name and the log evidence pasted in.
4. Machine copy of the mandates lives in public.unified_context key
   `cc_standing_mandates_v1`; the file here is the SSOT, the row mirrors it.
