# Vendored agent skills — mattpocock/skills

Vendored from [`mattpocock/skills`](https://github.com/mattpocock/skills) v1.2.3
(`9c9f36ccd3995266cd675468af71639c8dde1ec5`, 2026-08-17), MIT. License in `LICENSE-mattpocock-skills`.

**Only two skills from that repo are installed here.** Three more were evaluated and deliberately
held back because they collide head-on with the pack already in this directory. See below.

## Installed

| Skill | Invocation | Why |
|---|---|---|
| `wizard` | model-auto | Generates an interactive bash script that walks a human through steps only a human can take — logged-in dashboards (Vercel, Clerk, Supabase UI), CI secrets, one-off cutovers. Opens each URL, captures each value, writes to `.env` and `gh secret`, confirms before anything irreversible. **No existing skill covers this**, and it maps directly onto our single biggest structural HITL tax: Claude-in-chat cannot reach anything behind a login. |
| `writing-for-agents` | model-auto | Quality reference for any document an agent consumes. Core concepts: **no-ops** (instructions that cost context every turn without changing behaviour), context pointers, progressive disclosure, single source of truth. We need this because `skill-meta-updater.yml` appends to `CC_META_PROMPT.md ## AUTO-LEARNINGS` with zero HITL and **nothing prunes it** — an automated instruction-debt generator with no counterweight. |

`writing-for-agents` partially overlaps `skill-creator`. They are complementary rather than
competing: `skill-creator` **authors** a new SKILL.md + eval.json pair; `writing-for-agents` is the
**editing and pruning** reference applied to files that already exist, including `CLAUDE.md` and
`AGENTS.md`. If both ever fire on the same request, prefer `skill-creator` for creation and
`writing-for-agents` for revision.

## Evaluated and HELD — direct collisions with the existing pack

Installing these would put two model-auto skills on the same trigger, which is a coin-flip, not a
choice. That is precisely the duplication failure `writing-for-agents` exists to catch, so installing
them alongside it would be self-contradictory.

| Upstream skill | Collides with | Status |
|---|---|---|
| `diagnosing-bugs` | `systematic-debugging` | HELD. Both fire on any bug or unexpected behaviour. Merge candidate: `systematic-debugging` is the incumbent and larger; the one idea worth porting into it is the **tight, red-capable feedback loop** gate — refuse to theorise until you can name one command you have *already run* that goes red on *this* bug. |
| `code-review` | `requesting-code-review` + `receiving-code-review` | HELD. Merge candidate: the **two-axis split** (Standards vs Spec, run as parallel sub-agents, reported separately and never reranked against each other). The Spec axis is the part we actually lack — nothing currently checks a diff against its originating issue, which is the exact failure mode behind `c3d956d8`. |
| `to-tickets` | `writing-plans` + `dispatching-parallel-agents` | HELD. Merge candidate: **blocking edges as first-class ticket metadata**, and the rule that parallel width equals the count of tickets with no blockers. Our SHARD-BY-ISSUE rule is currently prose in `CC_META_PROMPT.md` rather than something enforced at plan-generation time. |

Adapted versions of all three — with the human-approval gates removed and Everest dispatch mapping
added — were prepared and are held pending a merge decision. Do not install them as separate skills.

## Never taking

- `git-guardrails-claude-code` — blocks `git push`, which would sever the dispatch loop.
- `setup-pre-commit` — Husky never fires on the SQL / Contents-API push path.
- `triage` — self-excluding; it is for issues we did not create, and we generate all of ours.
- `setup-matt-pocock-skills` — its output is superseded by `CC_META_PROMPT.md` and `BIDDEED_SSOT.md`.
- `grilling` / `grill-me` / `grill-with-docs` — stop-and-wait by design. Open question, not a no.
- All of `in-progress/`, plus `teach`, `tdd`, `scaffold-exercises`, `migrate-to-shoehorn`.

## Maintenance

These are ordinary files we own and edit; upstream explicitly supports that. Do not run
`npx skills update` against this directory — it does not know about the two-skill subset or the hold
list. Pull upstream changes by diffing against the pinned SHA above.
