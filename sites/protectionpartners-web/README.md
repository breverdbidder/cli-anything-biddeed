# Protection Partners — v1 website

AI-native independent insurance agency site for Mariam Shapira / Protection
Partners (Florida — commercial lines, business auto specialty, personal
lines). Astro (static) + Tailwind v4, deployed to Cloudflare Pages, with a
Cloudflare Pages Function handling the "Get a Quote" intake.

Built inside `cli-anything-biddeed` per the CC dispatch (issue #19405) — a
new standalone repo could not be created from this session. See
**Splitting into its own repo** below for how to extract it later.

## Stack

- **Astro v7** (`output: "static"`) + **Tailwind v4** (`@tailwindcss/vite`)
- **Cloudflare Pages** for hosting; `functions/api/quote.ts` is a Cloudflare
  Pages Function (not an Astro SSR route) — it ships independently of the
  static build and runs on Cloudflare's edge runtime
- **Supabase** (`@supabase/supabase-js`) for the intake table, written only
  from the Pages Function via the service-role key
- **PostHog** analytics, loaded only when `PUBLIC_POSTHOG_KEY` is set
- **Node >= 22.12** required — Astro 7 does not run on Node 20. Use `n 22`
  (or nvm/fnm) if your default Node is older; CI is pinned to Node 22.

## Local development

```bash
cd sites/protectionpartners-web
npm ci
npm run dev        # Astro dev server, pages only — functions/api/quote.ts is NOT served
```

To exercise `functions/api/quote.ts` locally (the actual deploy artifact),
use Wrangler's Pages dev server against a built `dist/`:

```bash
npm run build
cp .dev.vars.example .dev.vars   # fill in real values, never commit .dev.vars
npx wrangler pages dev dist --port 8788
curl -X POST http://127.0.0.1:8788/api/quote -H "Content-Type: application/json" -d '{...}'
```

## Design bar / audit

```bash
npm run build && npm run preview -- --port 4321 &
npm run audit          # scripts/audit-site.mjs against http://localhost:4321
```

Checks all 6 pages at 320/393/768/1440px for horizontal overflow and
console/page JS errors, per the zonewise-web `audit-site.mjs` convention
referenced in issue #19405. Requires Playwright's Chromium browser
(`npx playwright install chromium` once).

## Cloudflare Pages deploy steps (for Ariel)

1. **Create the Pages project** (one-time):
   ```bash
   npx wrangler pages project create protectionpartners-web
   ```
   Or via the Cloudflare dashboard: Workers & Pages → Create → Pages →
   Connect to Git → select `breverdbidder/cli-anything-biddeed`, and set:
   - **Root directory:** `sites/protectionpartners-web`
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
   - **Node version:** 22 (set `NODE_VERSION=22` as an env var if the
     dashboard doesn't auto-detect from `package.json` engines)

2. **Set environment variables** (Pages dashboard → Settings →
   Environment variables → Production, and mirror to Preview):

   | Variable | Required | Notes |
   |---|---|---|
   | `SUPABASE_URL` | Yes | `https://mocerqjnksmhcjzxrewo.supabase.co` |
   | `SUPABASE_SERVICE_ROLE` | Yes | Service-role key. **Secret** — never commit, never put in `wrangler.toml`. This is what lets the Function write past RLS. |
   | `MOMENTUM_DELIVERY_URL` | No | The #19404 delivery bridge endpoint. Absent = the Function skips the forward and logs to console; the lead is still saved. |
   | `VAPI_PUBLIC_KEY` | No | Reserved for the live Vapi web SDK integration. Not wired in this issue — `VoiceWidget.astro` just checks for its presence and logs a console note. Do not set this until Vapi is actually being turned on live. |
   | `PUBLIC_POSTHOG_KEY` | No | PostHog project key. Absent = no analytics snippet is rendered at all (not just disabled). |
   | `PUBLIC_SITE_DOMAIN` | No | Defaults to `protectionpartners.pages.dev`. Set once Ariel picks a real domain — every absolute URL in the site derives from `src/config/site.ts`'s `SITE_DOMAIN`, so this is a one-variable change, not a find-and-replace. |

   Any `PUBLIC_*`-prefixed var is exposed client-side by Astro/Vite (build
   time). Non-`PUBLIC_*` vars (`SUPABASE_SERVICE_ROLE`, `MOMENTUM_DELIVERY_URL`)
   are only readable inside `functions/api/quote.ts` at request time — never
   bundled into client JS.

3. **Deploy:**
   ```bash
   npm run build
   npx wrangler pages deploy dist --project-name=protectionpartners-web
   ```
   Or push to `main` with Git integration connected — Cloudflare rebuilds
   automatically. The `.github/workflows/protectionpartners-web-ci.yml`
   workflow only runs `npm ci && npm run build` as a CI gate; it does not
   deploy (deploy stays inside Cloudflare's own Git integration, or a manual
   `wrangler pages deploy`, per the issue's HITL note on DNS/domain).

4. **Domain binding (HITL — Ariel only):** once a domain is chosen, bind it
   under Pages → Custom domains, and update `PUBLIC_SITE_DOMAIN`. Not done in
   this session per the issue's non-goals (no domain purchase, no DNS
   changes).

## Supabase

Migration: `supabase/migrations/20260824_protection_partners_intake.sql`
(applied live via the Supabase Management API on 2026-08-24 — see issue
#19405 comment for the verification query/output).

Table lives in **`public`**, not `winnerdata` — PostgREST does
not expose the `winnerdata` schema (see
`docs/winnerdata/FF_TO_MOMENTUM_MAPPING.md`), and this is a distinct
website-intake source rather than part of the Winner Data
auction pipeline. RLS is enabled with **zero policies**: anon/authenticated
clients can neither read nor write. `functions/api/quote.ts` is the only
write path, using `SUPABASE_SERVICE_ROLE`, which bypasses RLS.

```sql
create table public.protection_partners_intake (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  payload jsonb not null,
  consent jsonb not null,
  source text not null default 'website',
  status text not null default 'new'
);
```

## FF payload shape

`payload` reuses the `applicant.*` and `property.address` field keys from
`winnerdata/WINNERDATA_QUOTE_REQUEST_TEMPLATE.json` (the auction-investor
edition) so the same keys line up with the mappings already documented in
`docs/winnerdata/FF_TO_MOMENTUM_MAPPING.md` (e.g. `applicant.entity_name.value`
→ NowCerts `commercial_name`/`first_name`+`last_name`). Fields that only make
sense for an auction-won property (`purchase.*`, `buyer_profile.*`) are
dropped — a website lead has no auction context — and a new `quote_request`
block carries the line-of-business-specific fields (vehicles, business
size, home type, etc.) that the auction template has no equivalent for.
`consent` is a separate top-level object (not nested under `compliance` like
the template) holding the TCPA grant, versioned consent text, capture IP,
timestamp, and user agent.

## TCPA consent

Consent language is versioned in `src/config/consent.ts`
(`TCPA_CONSENT_VERSION`). The checkbox is required client-side *and*
enforced server-side in `functions/api/quote.ts` — a request with
`consent.tcpa_given !== true` is rejected with `400` before any DB write.
IP address is captured server-side from `CF-Connecting-IP` (falling back to
`X-Forwarded-For`), never trusted from the client.

## Splitting into its own repo later

```bash
git subtree split --prefix=sites/protectionpartners-web -b protectionpartners-web-split
# push protectionpartners-web-split to a new repo, then reconnect Cloudflare
# Pages' Git integration to the new repo's root instead of this subdirectory.
```

## Non-goals honored in this build

No product-page SEO farm, no blog, no fake testimonials/carrier logos (see
the `[CARRIER LOGOS PENDING APPOINTMENTS]` placeholder on the home page), no
payment collection or bind-claim copy, no domain purchase/DNS changes, no
live Vapi/Sonant integration, no real Momentum API credentials.
