---
name: ship-gate
description: Use before any deployment, PR merge, or claiming a feature is complete. Enforces curl proof, WEBSITE_STATE.md update, and TODO.md pre-flight checks. Triggers on: deploy, ship, merge, done, complete, push to production, PR ready, feature done, go live.
---

# Ship Gate

## Role
Own deployment quality as verified-evidence gating, not checklist theater.

## Working Mode
Map deploy scope -> Run pre-flight checks -> Collect evidence -> Gate on pass -> Deploy -> Verify post-deploy.

## Focus Areas
1. Pre-flight checklist -- TODO.md open tasks, test suite status, branch clean
2. Curl verification -- live URL returns expected status code and content
3. WEBSITE_STATE.md -- update with new deployments before marking done
4. 4hr session limit -- flag if session has been running > 4hrs, risk of context drift
5. PR gate -- risk classification (LOW/MEDIUM/HIGH) before merge
6. Rollback readiness -- confirm rollback command exists before deploying
7. Evidence collection -- screenshot, curl output, or GHA run link
8. Zero silent failures -- every failure surface, no "it's probably fine"

## Quality Gates
- verify: Curl to deployed URL returns HTTP 200 (or expected redirect)
- confirm: WEBSITE_STATE.md updated with deployment timestamp and URL
- check: All open TODO.md tasks for this feature are checked [x] with proof
- ensure: Test suite ran this session and output is attached
- call_out: Any TODO.md item marked [x] without evidence in current session

## Output Format
```
Ship Gate Report:
- Tests: [PASS/FAIL] — command: X, result: Y failures
- TODO pre-flight: [PASS/FAIL] — open tasks: X
- Curl: [PASS/FAIL] — URL: X, status: Y, body: Z
- WEBSITE_STATE.md: [UPDATED/MISSING]
- Risk: [LOW/MEDIUM/HIGH]
- Rollback: [READY/MISSING]
Decision: [SHIP / BLOCK]
```

## Constraints
- NEVER mark a deployment done without curl proof
- NEVER merge to main with failing tests
- NEVER skip WEBSITE_STATE.md update for user-facing deployments
- NEVER ship features with open P0/P1 TODO.md tasks in scope
- 4hr session max: if session clock > 4hrs, add mandatory 15min review before shipping

## Guard Rail
Do not issue Ship decision without running curl verification in the current session, even for "quick fixes."
