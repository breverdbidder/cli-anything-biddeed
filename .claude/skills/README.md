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

---

# Vendored agent skills — coreyhaines31/marketingskills

Vendored from [`coreyhaines31/marketingskills`](https://github.com/coreyhaines31/marketingskills)
(`d4ff28a9c8d56c06809860bf2800d4f5224b52db`, 2026-09-01), MIT. License in
`LICENSE-marketingskills`. Full ranked candidate table (repo/stars/license/verdict) and the
existing-skill inventory used for the collision check are in `docs/spec/19766.md`.

Context: issue #19766 asked for the useful half of AgentsKit's paid ($49-79) Marketing Kit
(https://agentskit.co), reproduced at $0 from its underlying MIT/Apache-2.0 open-source pool.
`coreyhaines31/marketingskills` turned out to cover all twelve target categories from that issue
in one MIT repo — one skill per category, each with its own `references/` and `evals/evals.json`
(the upstream repo's own eval philosophy, independent of ours) — so no second or third source was
needed to hit the category list. Repos found for individual categories (SEO, GEO/AEO, cold email,
copywriting) were consistently smaller, staler, or narrower than the matching skill already inside
this pack; see the spec file for the specific alternates and why each lost.

## Installed (14 skills, one per marketing category + 2 SEO sub-forms)

| Skill | Category | Trigger highlights |
|---|---|---|
| `ai-seo` | (a) GEO/AEO AI-search optimization | AEO, GEO, LLMO, "optimize for ChatGPT/Perplexity/Claude", AI citations, llms.txt |
| `offers` | (b) offers & guarantees / pricing psychology | offer design, guarantee, value stack, scarcity/urgency, grand slam offer |
| `cold-email` | (c) cold email + email sequences | cold outreach, SDR email, follow-up sequence, "nobody's replying" |
| `launch` | (d) launch plan / campaign brief | product launch, Product Hunt, GTM plan, beta/waitlist |
| `copy-editing` | (e) brand voice / copy QA | copy review, tighten this up, sharpen messaging, content refresh |
| `seo-audit` | (f) SEO audit + programmatic SEO | technical SEO, "why am I not ranking", core web vitals, crawl errors |
| `programmatic-seo` | (f) SEO audit + programmatic SEO | template pages at scale, location/comparison pages, pSEO |
| `cro` | (g) CRO / landing page | conversion rate optimization, landing page feedback, form abandonment |
| `churn-prevention` | (h) churn prevention / retention | cancel flow, save offer, dunning, involuntary churn, win-back |
| `attribution` | (i) attribution / RevOps | attribution model, first/last-touch, "dashboards disagree", incrementality |
| `revops` | (i) attribution / RevOps | lead scoring/routing, MQL/SQL, marketing-to-sales handoff |
| `lead-magnets` | (j) lead magnets | gated content, content upgrade, ebook/checklist, opt-in |
| `public-relations` | (k) PR | press outreach, HARO/Qwoted, newsjacking, podcast guest prep |
| `directory-submissions` | (l) directory submissions | Product Hunt/BetaList/G2 listings, backlinks, launch directories |

Zero trigger collisions with the pre-existing pack (49 skills as of 2026-09-03): none of those
skills touch marketing/GTM copy, SEO, email outreach, PR, or revenue-ops territory — `exa-discovery`
is the only adjacent one (GTM *research*, i.e. finding data sources, not writing GTM *content*), and
its trigger list (exa search, county GIS, discovery harness) doesn't overlap any skill above. Full
comparison method in `docs/spec/19766.md`.

**Zero-HITL adaptation:** each upstream skill's "gather this context (ask if not provided)" /
"ask the user these N questions" step was rewritten to "infer from repo/session context, tag the
assumption `INFERRED` per Honesty Protocol, don't block on a question nobody will answer" — this
runs in headless `claude -p` dispatches with no human attached, same rationale as the wizard/
writing-for-agents adaptation above. Every installed `SKILL.md` also got a one-line Everest-context
pointer under its title: MANDATE M3 (no vendor/tool/internal-ID names in client-facing output —
these skills can produce cold emails, press pitches, and launch copy that reaches real people).

## Not installed from this repo

The remaining ~35 skills in `coreyhaines31/marketingskills` (ads, analytics, social, paywalls,
onboarding, signup, pricing, emails, schema, video, image, popups, events, referrals, aso,
influencer-marketing, community-marketing, competitor-profiling, competitors, ad-creative,
content-strategy, customer-research, marketing-ideas, marketing-loops, marketing-plan,
marketing-psychology, marketing-council, product-marketing, prospecting, sales-enablement,
free-tools, co-marketing, sms, ab-testing, site-architecture) were left out on purpose: the issue
asked for the best ONE skill per named category, not the whole kit, and the engineering-kit
equivalent of "install everything" is explicitly a non-goal. Nearest-neighbour collisions worth
naming if any of these are added later: `marketing-plan` vs `writing-plans` (planning-doc format
would need reconciling), `customer-research` vs `brainstorming` (both do intent-gathering
up front).

## Maintenance

Same rule as above: these are ours to edit once vendored. Pull upstream changes by diffing against
the pinned SHA. Do not run any upstream `validate-skills.sh` / update script against this directory.
