# CONSENT / COMPLIANCE AUDIT — every capture point on biddeed.ai

Date: 2026-09-07 · Issue: [#20081](https://github.com/breverdbidder/cli-anything-biddeed/issues/20081) · Owner: Ariel Shapira

## Context and purpose

On 2026-09-05, `biddeed-daily-digest.yml` was found to have been emailing every `lead_profiles` row with an address — no consent filter — daily since at least 2026-08-24 (61 addressable, 2 consented, 6 previously unsubscribed). Fixed under #20034 (verified below, still live at HEAD). This audit's job is to prove that *class* of defect — an automated send reaching a non-consented address — is gone everywhere, not just in that one workflow.

**Result: it is not gone everywhere.** The digest fix itself holds, but three other capture points and one other live cron write to or read from `lead_profiles`/consent columns with materially weaker guarantees than the pattern #20034 established. None of these has resulted in an observed non-consented send in production as of this audit (all row-count and cron-history evidence below), but the code paths exist and are live today. Findings are ranked by severity; every claim below is either a live PostgREST query with its output shown, or a direct file:line quote. PII is masked throughout — no email address appears unmasked below.

---

## Findings, ranked

### F1 — CRITICAL: `insert_reel_lead` hardcodes consent to `true` in the RPC body, with no consent parameter in its signature at all

- **Where:** `POST /deal/:county/:case/lead` (the deal-page lead form, both postsale and presale templates) → `src/worker.js:3790` → RPC `public.insert_reel_lead` → live definition `supabase/migrations/20260903g_reel_landing_sticky_wiring.sql:74-131`.
- **Evidence:** the SQL body sets `email_consent = true, email_consent_at = now(), marketing_consent = true, marketing_consent_at = now()` unconditionally, on every call, regardless of anything the visitor did or didn't check. The function's own parameter list — `p_email, p_case_number, p_county, p_utm_source, p_utm_medium, p_utm_campaign, p_source, p_visitor_id` — has no consent boolean to even pass in.
- **What the user sees:** nothing. Both `/deal/:county/:case` templates (`src/worker.js:5510-5518` postsale, `:5680-5689` presale) render an email input, hidden fields, and a submit button — no checkbox, no "I agree," no link to `/terms`/`/privacy`/`/disclaimer` anywhere on either template.
- **Why this is the same defect class as the digest bug:** a row this RPC inserts is functionally indistinguishable, from the digest script's point of view, from a row where a real person actually opted in — `email_consent=true`/`marketing_consent=true` is exactly the predicate `biddeed-daily-digest.cjs` (and `countdown_reengagement_send.py`, see F4) filter *on*. This capture point silently manufactures consented-looking rows.
- **Live impact today:** COULD NOT fully isolate `source='reel'`/`source='presale_deal'` rows from the 61 email-present `lead_profiles` rows without a column this audit didn't query; the source-breakdown query (below) shows 1 row with `source='reel'`. Low volume today; the defect is structural, not (yet) a large blast radius.

### F2 — CRITICAL: the site's own `/unsubscribe` link does not feed the two suppression tables `#20034` created

- **Where:** `src/worker.js:3170-3194` → RPC `public.upsert_lead_consent` (`src/worker.js:3176-3180`, body `{p_email, p_marketing_consent: false, p_source: 'unsubscribe_link'}`).
- **Evidence:** `public.upsert_lead_consent` **has no migration file anywhere in this repo** (repo-wide grep of `supabase/migrations/*.sql` for `upsert_lead_consent` returns zero `CREATE FUNCTION` hits). Its behavior was confirmed live via a disposable probe call (address created and deleted in the same session; `lead_profiles` count verified back to 365 afterward) — the function updates `lead_profiles.marketing_consent = false` only. It does **not** insert into `email_opt_outs` or `email_suppressions`, the two tables #20034 added specifically so that a suppression survives independent of whatever `lead_profiles.marketing_consent` says.
- **Why this matters:** `email_opt_outs` has exactly **6 rows**, all `source='unsubscribe_link_backfill'`, all timestamped `2026-09-05T14:20:51Z` — a single one-time backfill INSERT at the moment #20034 shipped. Zero rows have landed there in the 2 days since, meaning **zero live one-click unsubscribes have been verified to actually reach the new suppression table** — every real-world click on the unsubscribe link since #20034 shipped has gone through `upsert_lead_consent`, which (per the black-box test above) only touches `lead_profiles`, not `email_opt_outs`.
- **Consequence:** the digest script's own consent gate (`email_opt_outs`/`email_suppressions` check, `biddeed-daily-digest.cjs`) does not see anyone who unsubscribes today unless `upsert_lead_consent` also flips `marketing_consent=false` on the same row the digest query reads from `lead_profiles` directly (which its black-box behavior does do) — so the digest itself is probably still safe. But `countdown_reengagement_send.py` (F4) checks `email_consent` only, and `upsert_lead_consent` writes to `marketing_consent`, not `email_consent` — meaning a user who clicks unsubscribe may still be eligible for the countdown re-engagement send. **Not verified as an active leak; verified as a structural gap between the unsubscribe mechanism and one of the two live consent columns the site's own sends key off.**

### F3 — HIGH: `/chat/lead` is fed by two callers (blog page, county page) that hardcode `email_consent: true` client-side with zero visible consent UI

- **Where:** blog lead widget (`src/worker.js:6295-6298`, fetch body at `:6309`: `email_consent:true` literal in the JS); county-page lead bar (`src/worker.js:9330-9343`, fetch body at `:9358`: `email_consent: true` literal). Both forms show only an email input and a submit button — no checkbox, no disclosure text.
- **Also on this endpoint:** the confirmation email this triggers (`from: activate@biddeed.ai`, `src/worker.js:4236-4292`) has **no `List-Unsubscribe` header and no unsubscribe link/footer text anywhere in its HTML body** — verified by reading the full template. This is the only outbound send found in this audit with zero opt-out mechanism of any kind, live, triggered by an unauthenticated public form.
- **Contrast:** `/free-report` (below) gates the identical two channels behind real, unbundled checkboxes and a server-enforced "check at least one" rule. `/chat/lead`'s blog/county-page callers should use the same pattern; the RPC and audit-trail plumbing (`sms_consent_events`) already exist for the SMS half of this endpoint, just not the email half.

### F4 — HIGH: a second live daily cron (`countdown-reengagement-send.yml`) checks `email_consent` only — not the two suppression tables #20034 added

- **Where:** `scripts/countdown_reengagement_send.py:266`: `eligible = args.test_email or (lead.get("email") and lead.get("email_consent") is True)`.
- **Evidence:** live daily cron (`countdown-reengagement-send.yml`, `0 13 * * *`), reads `lead_auction_countdown` (143 live rows) joined to `lead_profiles`. `email_opt_outs`/`email_suppressions` are never referenced anywhere in this script (grep confirmed).
- **Why this matters:** this is precisely the gap #20034 closed for the daily digest, re-opened in a second script that reads the same underlying table. If F1 (hardcoded consent on `insert_reel_lead`) and F2 (unsubscribe not reaching the suppression tables) are both true at once, a visitor who submitted a deal-page lead form (auto-consented, F1), then genuinely tried to opt out via `/unsubscribe` (which only flips `marketing_consent`, not `email_consent`, per F2's black-box result), would **still show `email_consent=true`** and remain eligible for this send. This is a plausible, traceable path to the same class of defect #20034 was supposed to close everywhere — not observed as an actual send to an unsubscribed person in this audit (no way to test without sending), but the code path is live today.

### F5 — MEDIUM: `acquisition_cold_email.py` selects `email_consent` in its query but never filters on it

- **Where:** `scripts/acquisition_cold_email.py:272-275` selects `email_consent` from `lead_profiles`; grep of the rest of the file found no predicate that actually uses that column to include/exclude a row.
- **Mitigating factor:** this workflow is `workflow_dispatch`-only (no cron), and its `dry_run` input defaults to `false` per the workflow file — meaning a manual run without specifying `dry_run=true` would perform a real send with no enforced consent filter, but nothing dispatches it automatically today.

### F6 — MEDIUM: no audit-trail row exists for email consent anywhere; `sms_consent_events` (the one audit table that does exist) has never recorded a live row

- **Evidence:** `sms_consent_events` confirmed to exist live (a deliberate bad-column PostgREST query returned `42703 column does not exist` rather than a table-not-found error; a deliberate empty-payload POST returned `23502: null value in column "user_id"`, confirming the schema). Live row count: **0**. Its only INSERT call site in this repo is `src/worker.js:4186-4202`, gated on `if (sms_consent)` inside `/chat/lead` — meaning the one path that's wired to write it has apparently never actually fired in production. There is no equivalent table for email consent anywhere — not for `/free-report`'s real checkbox (despite that RPC's own migration comment citing "TCPA opt-in requirements," `supabase/migrations/20260807_upsert_lead_full_rpc.sql:6`), not for `/chat/lead`, not for `insert_reel_lead`.
- **Consequence:** even where real consent UI exists (`/free-report`), there is currently no way to reconstruct, after the fact, exactly what disclosure text a given user saw and when — only the current boolean state.

### F7 — LOW / not a defect: `/free-report` is the reference-quality capture point site-wide

- **Evidence (verbatim consent copy, `src/worker.js:2240-2242`):**
  ```html
  <label class="consent"><input type="checkbox" name="email_consent" ...> Send me the daily auction digest by email</label>
  <label class="consent"><input type="checkbox" name="sms_consent" ...> Text me urgent auction alerts (SMS)</label>
  <div class="err" id="consent-err">Please check at least one option above.</div>
  ```
  Real RPC parameters (`upsert_lead_full`), server-enforced "at least one" rule, unbundled per-channel checkboxes (this is what "affirmative and unbundled" should look like everywhere). No audit-trail row (F6 applies here too), and the delivery-confirmation page's unsubscribe mention ("You can unsubscribe from any digest email at any time," `src/worker.js:2310`) is plain text, not a hyperlink — a minor UX gap, not a consent-legality gap.

### F8 — LOW: Pioneer waitlist hardcodes `marketing_consent: true` server-side

- **Where:** `POST /pioneers/join`, `src/worker.js:4031-4032`, regardless of any checkbox. The form (`src/worker.js:6113-6127`) has only name/email inputs and a liability disclaimer ("Not legal or financial advice…") — not marketing-consent language.
- **Mitigating factor:** the confirmation email sent to Pioneer signups (`src/worker.js:4050`) is a direct, expected response to a form the user just filled out asking to join a waitlist — this is closer to a transactional confirmation than unsolicited marketing, which is a real distinction under CAN-SPAM (transactional/relationship messages have looser consent requirements than commercial ones). Still recommend a real checkbox for hygiene/consistency with #20034's spirit.

---

## Verified compliant / working as intended

- **`biddeed-daily-digest.cjs` (the #20034 fix) — confirmed live at current HEAD**, not just historically committed. `getLeads()` (`scripts/biddeed-daily-digest.cjs:135-168`) filters `lead_profiles` on `NOT stage='unsubscribed' AND email IS NOT NULL AND (email_consent=true OR marketing_consent=true)`, subtracts `email_opt_outs ∪ email_suppressions`, and has an independent-recount hard-fail guard: `if (consented.length > consentedCount) throw new Error('REFUSING TO SEND...')`. Live cron: `0 22 * * *`.
- **`/subscribe`, `/subscribe/checkout`** — Stripe paid-checkout only, no `lead_profiles` write, no consent claim to make.
- **`/support`, `/alerts` (this repo's view)** — both fully proxied to biddeed-web; no lead-capture code exists in this repo for either route.
- **No SMS/Twilio send code exists anywhere in this repo** (grep for `twilio|\.sms\(|sendSMS|sms_api|TWILIO_`, zero hits across `src/`, `scripts/`, `supabase/functions/`, `.github/workflows/`) — the FTSA/TCPA phone-consent columns and the `sms_consent_events` table exist, but nothing in this codebase currently sends an SMS to act on that consent, live or otherwise.
- **`seller_digest_enrichment.py`** — explicitly marked "not for delivery to any third party" in its own PDF-render code (`seller_digest_pdf_render.py:172`); no send capability exists in this script at all.
- **B2B-only / no-homeowner-contact posture** — repo-wide, no code path targets a homeowner directly; `winnerdata-daily-winner-ff-digest.yml`/`winnerdata-ff-send-approved.yml` resolve their recipient to an internal team member (`get_producer_email()`), gated by `classify_recipient()` to sandbox/internal/producer domains — not a homeowner or a bidder.

---

## Live DB verification (all queries run 2026-09-07, all counts exact, no PII shown)

```
GET lead_profiles?select=id                                        → 365 total rows
GET lead_profiles?select=id&email=not.is.null                      → 61 rows with an email
GET lead_profiles?...&or=(email_consent.eq.true,marketing_consent.eq.true)&email=not.is.null
                                                                     → 2 rows (matches #20034 spec's claimed live count exactly)
GET lead_profiles?...&email_consent=eq.true&email=not.is.null      → 2
GET lead_profiles?...&marketing_consent=eq.true&email=not.is.null  → 2  (same 2 rows, both flags)
GET lead_profiles?...&stage=eq.unsubscribed                        → 0 rows
GET email_opt_outs?select=id                                       → 6 rows, all source=unsubscribed_link_backfill, all timestamped 2026-09-05T14:20:51Z
GET email_suppressions?select=id                                   → 21 rows, resend_synced=true on 21/21
GET sms_consent_events?select=id                                   → 0 rows (table confirmed to exist via schema-error probes; see F6)
```

Source breakdown of the 61 email-present `lead_profiles` rows (group-by, exact): `skip_trace_pipeline` 32 · `auction_llc_expansion` 14 · `unsubscribe_link` 6 · `allowed_emails` 3 · `voice_gate` 3 · `test` 1 · `support_escalation` 1 · `reel` 1.

Only **2 of 365** rows carry real, affirmative consent today. The other 359 are B2B/skip-trace/LLC-expansion contacts with no consent claim at all (correctly excluded by every consent-gated send this audit reviewed) or the 6 backfilled unsubscribe rows.

---

## TCPA/FTSA and CAN-SPAM summary

- **TCPA/FTSA (phone-shaped):** no live SMS-send code exists in this repo (verified above), so there is currently no active phone-outreach compliance surface to violate. The one audit-trail table built for this purpose (`sms_consent_events`) is correctly wired at its one call site but has never fired — recommend a synthetic end-to-end test the next time SMS sending is actually built, not before.
- **CAN-SPAM (email-shaped):** the digest (#20034) is compliant (opt-in gate + suppression list + hard-fail regression guard). `/chat/lead`'s `activate@biddeed.ai` confirmation send (F3) is the one finding in this audit that most resembles a CAN-SPAM gap on its own — no unsubscribe mechanism in a commercial email is the core requirement CAN-SPAM imposes, independent of consent-gating on the front end.
- **B2B-only compliance line (Winner Data canon):** no homeowner contact, no foreclosure-relief marketing, and no compensation tied to a homeowner outcome were found anywhere in this repo's send paths — confirmed by the recipient-resolution logic cited above (internal team members / bidders / self-serve leads only, never a homeowner/defendant/auction subject).

---

## Recommended follow-up (not fixed this session — see rationale)

Per M5 (scope discipline) and the pattern set by `docs/spec/20029.md` (which found the *original* digest gap and explicitly declined to bundle a same-session fix into an unrelated issue), the findings above are **RPC/schema/cron changes**, not copy edits — they don't belong in this content-and-consent-audit issue's PR-per-repo copy scope, and each is consequential enough (touches a production RPC signature or a live cron's filter logic) to deserve its own reviewed issue rather than a same-session patch. Recommended priority order for follow-up issues:

1. **F1** — add a real consent parameter to `insert_reel_lead` and real consent UI to both `/deal/:county/:case` templates (currently the only capture point with literally zero user-facing consent language).
2. **F2** — make `upsert_lead_consent` also write to `email_opt_outs`/`email_suppressions` (or have every consent-gated sender check `lead_profiles.marketing_consent` directly, closing the gap without a second write path) — and file `upsert_lead_consent`'s definition into a migration, since it currently exists live with no source-controlled origin in this repo.
3. **F4** — add the `email_opt_outs`/`email_suppressions` check to `countdown_reengagement_send.py`, matching the digest's pattern exactly.
4. **F3** — replace the two hardcoded `email_consent:true` client-side literals (blog, county page) with a real checkbox, and add a `List-Unsubscribe` header + footer link to the `activate@biddeed.ai` template.
5. **F6** — extend the audit-trail pattern (`sms_consent_events`) to cover email consent, at minimum for `/free-report`'s real checkbox.
6. **F5, F8** — lower priority; F5 has no live trigger today, F8 is a transactional-message edge case.

This session logged a summary of F1/F2/F4 (the three findings with a live, unattended trigger — F1 fires on every deal-page lead submission, F2/F4 fire daily via cron) to `public.agent_ops_log` per M4, tagged `severity='blocker'`, `dispatch_id='20081'`.
