# Greptile AI Code Review Setup

## Status
Integration: **NOT ACTIVE** — awaiting manual GitHub App install by Ariel.
Plan: Starter (Free) — 50 credits/month, unlimited repos, 1 developer.
Repo: breverdbidder/cli-anything-biddeed

## IMPORTANT — corrected from the original plan (2026-08-03)

The original brief for this reconnect specified adding a GitHub Actions workflow
(`.github/workflows/greptile-review.yml`) that calls an action named
`greptile-systems/greptile-review@v1`. That action **does not exist**:

```
$ curl -s https://api.github.com/repos/greptile-systems/greptile-review
{"message":"Not Found","documentation_url":"...","status":"404"}
```

Greptile does not ship a GitHub Action at all. Per Greptile's own docs
(greptile.com/docs/quickstart, greptile.com/docs/code-review-bot/trigger-code-review)
the integration is 100% **GitHub App**-based:

- The org/account installs the **Greptile GitHub App** (github.com/apps/greptile-apps)
  from app.greptile.com, granting it access to selected repos.
- Once a repo is indexed (1-2 hrs for large repos), the app watches PR events
  itself and posts review comments/status checks directly — no workflow file,
  no `on: pull_request` trigger we own, no job that runs on our runners.
- The API key generated at app.greptile.com is used **on Greptile's side**
  (their backend calling GitHub on our behalf). It is never referenced by a
  GitHub Actions workflow and does not belong in `secrets.GREPTILE_API_KEY`
  for a workflow to consume — there's no workflow to consume it.
- Optional per-repo behavior (which PRs get reviewed, branch/label/author
  filters, continuous-review-on-push) is controlled by an optional
  `greptile.json` file at the repo root, not by workflow YAML.

**Because of this, no `.github/workflows/greptile-review.yml` was created.**
Adding one referencing a nonexistent action would fail on every PR permanently
(red X on every PR forever) rather than "fail silently until the secret is
added," which was the original (incorrect) assumption.

## Manual Steps Required (Ariel)

1. Go to https://app.greptile.com and sign in with GitHub.
2. Go to **Code Providers** → **Connect GitHub Cloud** (or **Add Provider** → GitHub).
3. Install the **Greptile GitHub App** on the `breverdbidder` account/org when
   GitHub redirects you to the install screen.
4. Back in Greptile, select the `breverdbidder` org, click **Link**.
5. Select `cli-anything-biddeed` from the repo list, click **Enable**.
6. Wait for initial indexing to finish (1-2 hrs typical for a repo this size).
7. Open a test PR to `main` and confirm Greptile posts a review automatically.

No GitHub secret needs to be added for this repo. No workflow file needs to
be merged for this repo. If Greptile's product changes to require one in the
future, re-verify against their live docs before reintroducing a workflow —
do not restore the `greptile-systems/greptile-review@v1` reference, it was
never a real action.

## Optional: `greptile.json`

Once the app is installed and a first review round-trips successfully, an
optional `greptile.json` can be added at the repo root to scope which PRs get
reviewed (e.g. only PRs to `main`, exclude bot-authored PRs) and to enable
`triggerOnUpdates` for continuous review on new commits. Not created as part
of this task — add only after the App install is confirmed working, since its
schema should be verified against a live Greptile-indexed repo rather than
guessed.

## Credit Budget
- 50 credits/month free
- 1 credit = 1 standard PR review
- 3 credits = 1 TREX review (writes + runs tests)
- Estimated usage: 8-12 PRs/month = well within budget
- Use TREX for: migrations, security changes, billing logic, S5 report engine
- TREX is opt-in per Greptile's dashboard/`greptile.json` — not enabled by
  default, and nothing in this repo turns it on.

## What Greptile Catches
- SQL injection in Supabase queries
- Auth/RLS bypasses before they ship
- Pattern violations (e.g. not using parameterized queries)
- Cross-file inconsistencies CC misses in a single session
- Billing logic regressions
