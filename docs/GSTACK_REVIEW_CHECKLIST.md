# Fix-First Review Checklist
# Adapted from garrytan/gstack for BidDeed.AI / ZoneWise.AI stack
# Stack: Python · TypeScript · Supabase · Cloudflare · GitHub Actions
# Source: breverdbidder/gstack (MIT License)

## Instructions

Review `git diff origin/main` for the issues below. Cite `file:line` and suggest fixes. Skip anything that's fine. Only flag real problems.

**Two-pass review:**
- **Pass 1 (CRITICAL):** SQL & Data Safety, LLM Output Trust Boundary first. Highest severity.
- **Pass 2 (INFORMATIONAL):** All remaining categories. Lower severity but still actioned.

All findings get action via Fix-First Review: obvious mechanical fixes are applied automatically,
genuinely ambiguous issues are batched into a single user question.

**Output format:**

```
Pre-Landing Review: N issues (X critical, Y informational)

**AUTO-FIXED:**
- [file:line] Problem → fix applied

**NEEDS INPUT:**
- [file:line] Problem description
  Recommended fix: suggested fix
```

If no issues found: `Pre-Landing Review: No issues found.`

Be terse. One line per problem, one line per fix. No preamble, no summaries, no "looks good overall."

---

## Review Categories

### Pass 1 — CRITICAL

#### SQL & Data Safety (Supabase/PostgREST)
- String interpolation in SQL or RPC calls — use parameterized queries (`$1, $2`) or Supabase client `.eq()/.filter()` methods
- TOCTOU races: check-then-insert patterns that should be atomic `INSERT ... ON CONFLICT` or `UPDATE ... WHERE`
- Missing RLS policies on tables accepting user input — every table touching user data needs RLS
- Supabase `.select()` without `.limit()` on large tables — unbounded queries can timeout or OOM
- Direct `.update()` bypassing RLS by using service_role key when anon key would suffice
- N+1 queries: multiple sequential Supabase calls in a loop instead of a single `.in()` or join

#### Race Conditions & Concurrency
- Read-check-write without unique constraint or `ON CONFLICT` — concurrent inserts create duplicates
- Status transitions without atomic `UPDATE ... WHERE old_status = X SET new_status = Y` — concurrent updates can skip or double-apply
- GitHub Actions workflows that read-modify-write the same file without concurrency locks
- Supabase realtime subscriptions that mutate state without idempotency guards
- `innerHTML` or `dangerouslySetInnerHTML` on user-controlled or LLM-generated content (XSS)

#### LLM Output Trust Boundary
- LLM-generated values (emails, URLs, addresses, parcel IDs) written to Supabase without format validation. Add guards: regex for emails, `new URL()` for URLs, `.trim()` before persisting.
- Structured tool output (JSON arrays/objects from LLM) accepted without schema validation (Zod/Pydantic) before database writes
- LLM-generated SQL or RPC names passed directly to Supabase client — whitelist allowed operations
- Firecrawl/scraper output trusted as clean without sanitization before storage

#### Enum & Value Completeness
When the diff introduces a new enum value, status string, tier name, or type constant:
- **Trace it through every consumer.** Read (don't just grep — READ) each file that switches on, filters by, or displays that value. If any consumer doesn't handle the new value, flag it.
- **Check allowlists/filter arrays.** Search for arrays containing sibling values (e.g., if adding "premium" to tiers, find every `["free", "pro"]` and verify "premium" is included).
- **Check switch/if-else chains.** If existing code branches on the enum, does the new value fall through to a wrong default?
- **Check Supabase CHECK constraints.** Does the column have a CHECK constraint that needs updating?

### Pass 2 — INFORMATIONAL

#### Conditional Side Effects
- Code paths that branch on a condition but forget to apply a side effect on one branch (e.g., auction marked as BID but report not generated on one code path)
- Log/Telegram messages that claim an action happened but the action was conditionally skipped

#### Magic Numbers & String Coupling
- Bare numeric literals used in multiple files — should be named constants in a config module
- Error message strings used as query filters elsewhere (grep for the string — is anything matching on it?)
- Hardcoded Supabase table names scattered across files instead of centralized constants

#### Dead Code & Consistency
- Variables assigned but never read
- Version mismatch between PR title and VERSION/CHANGELOG/package.json
- CHANGELOG entries that describe changes inaccurately
- Comments/docstrings that describe old behavior after the code changed
- Unused imports (Python: `import X` never referenced; TS: `import { X }` never used)

#### LLM Prompt Issues
- 0-indexed lists in prompts (LLMs reliably return 1-indexed)
- Prompt text listing available tools/capabilities that don't match what's actually wired up
- Token limits stated in multiple places that could drift
- System prompts with stale model names or outdated API references

#### Test Gaps
- Negative-path tests that assert status but not side effects (Supabase row created? Telegram sent? Report generated?)
- Assertions on string content without checking format (e.g., asserting parcel ID present but not format)
- Missing tests for RLS policy enforcement (test that anon users CANNOT access restricted rows)
- eval.json assertions that test format but not correctness of the output

#### Crypto & Entropy
- `Math.random()` or Python `random.random()` for security-sensitive values — use `crypto.randomUUID()` or `secrets.token_hex()`
- Non-constant-time comparisons (`==`) on API keys, tokens, or secrets — use `hmac.compare_digest()` or `crypto.timingSafeEqual()`
- Supabase service_role key exposed in client-side code or GitHub Actions logs

#### Time Window Safety
- Date-key lookups that assume "today" covers 24h — auction at 11AM only sees midnight→11AM under today's key
- Mismatched time zones between FL (EST) and UTC in Supabase — `timestamptz` vs `timestamp` confusion
- Shabbat window calculations using hardcoded times instead of candle-lighting API

#### Type Coercion at Boundaries
- Values crossing Python→JSON→TypeScript boundaries where type changes (numeric vs string)
- Supabase `.single()` returning `null` vs throwing — inconsistent null handling across codebase
- `parseInt()` without radix or `.toString()` missing on values before JSON serialization

#### Frontend/Cloudflare
- Inline `<style>` blocks re-parsed every render in React components
- O(n*m) lookups in render loops (`.find()` in `.map()` instead of pre-indexed Map/Object)
- Cloudflare Pages environment variables not matching between preview and production
- Missing `loading` states on Supabase async calls — user sees blank/stale data

---

## Severity Classification

```
CRITICAL (highest severity):      INFORMATIONAL (lower severity):
├─ SQL & Data Safety              ├─ Conditional Side Effects
├─ Race Conditions & Concurrency  ├─ Magic Numbers & String Coupling
├─ LLM Output Trust Boundary      ├─ Dead Code & Consistency
└─ Enum & Value Completeness      ├─ LLM Prompt Issues
                                   ├─ Test Gaps
                                   ├─ Crypto & Entropy
                                   ├─ Time Window Safety
                                   ├─ Type Coercion at Boundaries
                                   └─ Frontend/Cloudflare
```

---

## Fix-First Heuristic

Determines whether the agent auto-fixes a finding or asks the user.

```
AUTO-FIX (agent fixes without asking):     ASK (needs human judgment):
├─ Dead code / unused variables            ├─ Security (auth, RLS, XSS, injection)
├─ N+1 queries (batch into .in())         ├─ Race conditions
├─ Stale comments contradicting code       ├─ Design decisions / architecture
├─ Magic numbers → named constants         ├─ Large fixes (>20 lines changed)
├─ Missing LLM output validation           ├─ Enum completeness (cross-file impact)
├─ Version/path mismatches                 ├─ Removing functionality
├─ Unused imports                          ├─ Supabase schema changes
├─ Missing .limit() on queries             └─ Anything changing user-visible behavior
└─ Type coercion fixes (.toString(), etc.)
```

**Rule of thumb:** If the fix is mechanical and a senior engineer would apply it
without discussion, it's AUTO-FIX. If reasonable engineers could disagree, it's ASK.

**Critical findings default toward ASK** (they're inherently riskier).
**Informational findings default toward AUTO-FIX** (they're more mechanical).

---

## Suppressions — DO NOT flag these

- "X is redundant with Y" when the redundancy is harmless and aids readability
- "Add a comment explaining why this threshold/constant was chosen" — thresholds change during tuning, comments rot
- "This assertion could be tighter" when the assertion already covers the behavior
- Suggesting consistency-only changes (wrapping a value in a conditional to match how another constant is guarded)
- "Regex doesn't handle edge case X" when the input is constrained and X never occurs in practice
- Eval threshold changes (max_actionable, min scores) — tuned empirically, change constantly
- Harmless no-ops (e.g., `.filter()` on an array that never contains the filtered value)
- ANYTHING already addressed in the diff you're reviewing — read the FULL diff before commenting
