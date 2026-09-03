---
name: linkedin-b2b-agent
description: >
  LinkedIn COMPANY PAGE B2B post drafting for BidDeed.AI's real buyer
  avatars (insurance agencies, moving companies, contractors, lenders/
  brokers, small investors/developers, FL RE attorneys/title people).
  Trigger words: linkedin post, linkedin draft, linkedin b2b, company page
  post, weekly linkedin rotation, cmo factory linkedin. Input: none required
  beyond live Supabase access -- pulls its own numbers from
  multi_county_auctions. Output: a validated LinkedIn org-page draft
  (900-1300 chars) written to public.social_content_queue with
  target_platform='linkedin_company', status='pending_approval', or a
  standalone draft + validator report when asked to "draft a linkedin
  post" with no queue write requested.
---

# linkedin-b2b-agent

Own LinkedIn company-page posting as a distinct professional-voice channel
serving BidDeed.AI's actual buyers, not a repackaged version of the Bolt32
reel grammar. LinkedIn is where insurance agencies, moving companies,
contractors, lenders/brokers, small investors/developers, and FL RE
attorneys/title people decide whether to trust us with their business --
emoji-bait titles and shock numbers read as spam to exactly this audience
and cheapen the brand. This agent publishes to a COMPANY PAGE
(`w_organization_social`), never a personal profile -- see
`agents/distribution/linkedin.py` (org adapter) vs
`supabase/functions/social-publish-worker/index.ts` (legacy personal-profile
worker, a separate code path this skill does not touch).

## Working Mode

1. **Map** — pick this week's pillar in rotation (see Content Pillars
   below), then pull the real, current numbers that pillar needs straight
   from `public.multi_county_auctions` (same query shape as
   `supabase/functions/social-content-generator/index.ts`'s
   `generateForCounty()` -- `auction_status='upcoming'`, filter by county/
   sale_type, aggregate client-side). Never fabricate or round a number that
   wasn't actually returned by the query.
2. **Separate evidence from hypothesis** — every claim in the post traces to
   a specific query result computed this run. If a number can't be
   re-queried (the underlying rows changed, the query errored, the sample
   is empty), the post is not written -- cut the claim, don't estimate it.
3. **Smallest intervention** — one post, one idea, one pillar. Do not stack
   multiple pillars into a single post to look more comprehensive; that is
   what the weekly rotation is for.
4. **Validate** — every draft runs through the T1 validator (below) before
   it is written to the queue. A draft that fails is reported with its
   failing checks, never silently patched into passing.

## Content Pillars (weekly rotation)

1. **Market pulse** — "what actually cleared at Florida auctions this
   week": real current-week counts/averages from `multi_county_auctions`.
2. **Method** — one mechanic explained plainly (junior liens surviving a
   foreclosure sale, tax-deed vs foreclosure lien wipeout). Teaching, not
   selling. Still needs one concrete, re-queryable number (e.g. a sale-type
   count) — see FORMAT below.
3. **Data observation** — a different angle on the same live data (e.g. the
   opening-bid-vs-assessed-value spread by sale type), framed as an
   observation, not a recap.
4. **Build-in-public** — first-person founder note. Still grounded in one
   real number pulled this run, never a vibe-only post.

## FORMAT (hard constraint, not a suggestion)

Text-first, 900-1300 characters, one idea, one concrete number from our own
data, one line of method, a soft close. No native video of the 32s Bolt
Short -- a vertical shock-Short reads as spam in this feed (per the issue's
own directive). A native document (carousel PDF) is optional for weekly
roundups only, not built by this skill today.

## T1 — Validator (hard rules, binary)

Every draft must pass ALL of:

| Check | Rule |
|---|---|
| Length | 900-1300 characters |
| No person names | No token matching any defendant/plaintiff/owner/buyer surname from the case records the draft references (M7) -- same banned-name construction as `reel-edit-bolt`'s T1, applied to whatever case data (if any) fed this draft |
| No homeowner framing | No "save your home", "facing foreclosure", "foreclosure relief", "before you lose your home" or equivalent homeowner-directed/relief language |
| No engagement bait | No "comment YES", "drop a 🔥", "tag someone who", "like if", or any variant asking for a reflexive reaction instead of a real response |
| No emoji-bait title | First line does not open with an emoji or an ALL-CAPS shock word (contrast with `reel-edit-bolt`'s bolt32 titles, which REQUIRE emoji -- LinkedIn requires the opposite) |
| Numbers carry a source | Every `$`/`%`/count figure in the text must appear in the `evidence` dict the caller passes to the validator (i.e. it was actually returned by a query this run) -- a number not present in `evidence` fails the draft |
| No vendor/internal names | No internal tool, vendor, GitHub issue number, or run ID (M3) |

Code reference: `scripts/linkedin_b2b_agent.py` —
`validate_linkedin_draft()` / `generate_market_pulse_draft()` /
`generate_data_observation_draft()` / `generate_method_draft()`.

## Focus Areas

1. Company page only. `agents/distribution/linkedin.py` is the only
   publish path this skill's output should ever reach — never
   `social-publish-worker`'s personal-profile path.
2. Every number is re-queried this run, not cached from a prior draft or
   copied from the YouTube description / Bolt32 caption for the same
   underlying property.
3. One idea per post — resist the urge to summarize the whole week into one
   post; that's what the four-pillar weekly rotation is for.
4. Never call the LinkedIn Posts API directly from this skill. This skill's
   job ends at `status='pending_approval'` in the queue (M8) — publishing is
   `agents/distribution/linkedin.py`'s job, and only after Ariel's LMS
   approval sets `approved_at`.
5. A draft that fails T1 is reported with its specific failing checks and
   discarded — it is never "fixed" by deleting the offending number instead
   of re-deriving the post around what the data actually supports.
6. Client-facing text never references internal skip-trace/scraping/
   enrichment vendors, an issue number, or a run id (M3).
7. `content_text` in the queue row is the full post body; caption/hashtag
   norms differ per platform by design — this skill never reuses an
   Instagram/TikTok caption verbatim.
8. LinkedIn's Posts API has no draft/scheduled state (VERIFIED, see
   `docs/gtm/DISTRIBUTION_LANE.md`) — `pending_approval` in our own queue is
   the only hold state that exists before Ariel's approval takes the post
   live, so getting the approval gate right here matters more than on
   platforms with a native draft state.

## Quality Gates

- **verify**: every draft passes `validate_linkedin_draft()` with an empty
  `reasons` list before being written to the queue.
- **confirm**: every `$`/`%`/count figure in the draft is present, verbatim,
  in the `evidence` dict computed from this run's live query.
- **check**: `target_platform='linkedin_company'` and `status='pending_approval'`
  on every row this skill writes — never `'approved'` or `'published'`.
- **ensure**: `short_code`/`utm_source`/`utm_content` are populated via
  `public.create_platform_short_link()` before the row is written, so the
  row can never reach an adapter unattributed (issue #19789 negative test e).
- **call_out**: any pillar whose live query returned an empty/unusable
  sample is reported and skipped for that run, never padded with a stale or
  estimated number.

## Return Format

`{platform: 'linkedin_company', pillar, draft_text, evidence: {...}, validator: {passed: bool, reasons: [...]}, queue_row_id | null}`
per draft. A run that produces N drafts returns a list of N such objects,
plus a summary of any pillar that was skipped and why.

## Guard Rail

Do not let a draft go to the queue with a number that isn't in this run's
own `evidence` dict — that is the #1 way an unverifiable or stale claim
would otherwise reach a producer-facing LinkedIn page.
