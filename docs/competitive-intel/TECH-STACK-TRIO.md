# Tech Stack & Hosting — Algoma vs ZoneWise vs Acres

**Prepared by:** Claude AI Architect (BidDeed.AI) · **Date:** 2026-08-17
**Method:** Algoma + Acres sections are real HTTP/DNS fingerprinting (`curl -sI`, `dig`) — web search is unreliable for "Algoma" (name collision with Algoma Steel) so it was not used as a source here. The ZoneWise section is sourced directly from `breverdbidder/zonewise-web` repo files (package.json, vercel.json, next.config.js), not "detected."

Context: this section did not previously exist for either Algoma or Acres. Issue #19256 ("Full CI v6.5 report + 18-section battle card: Acres.com vs ZoneWise.ai") — referenced as prior art for this task — has zero comments and no related commits/PRs/branches as of this session; its GHA dispatch runs show `conclusion: skipped`. No Acres report or "18-section" template exists anywhere in this repo to extend. The real, pre-existing section structure this task reuses instead is `docs/plans/ALGOMA-CI-REPORT.md` (the actual committed 8-section CI dossier format) and `public/competitors.html` (the actual committed battle-card HTML/CSS, brand-compliant). This doc + the trio HTML below are new artifacts built on that real structure, not a continuation of #19256's (nonexistent) output.

---

## 1. Algoma (algoma.co)

See `docs/plans/ALGOMA-CI-REPORT.md` §2A for the full evidence trail (raw `curl`/`dig` output). Summary:

| Layer | Finding | Confidence |
|---|---|---|
| Marketing site (`www.algoma.co`) | **Squarespace** — `Server: Squarespace` header, `ext-sq.squarespace.com` CNAME, `connect{1,2}.squarespacedns.com` NS delegation, Squarespace IP block | VERIFIED |
| Product app (`app.algoma.co`) | **Static bundle served from Google Cloud Storage** — `Server: UploadServer`, `Via: 1.1 google`, `x-goog-*` object headers | VERIFIED |
| Frontend build | **Vite** production output (`/assets/index-[hash].js` ES module + `/assets/index-[hash].css`, `<div id="root">`) | VERIFIED (Vite) / HYPOTHESIS (React specifically) |
| Backend / API framework | UNKNOWN | client-rendered SPA, no server responses observed |
| Database | UNKNOWN | not observable from frontend fingerprint |
| LLM vendor | UNKNOWN | no model-identifying signal found (prior CI report's "GPT-4 likely" remains INFERRED, unchanged) |

---

## 2. Acres.com

### 2.1 Marketing site — `www.acres.com` / `acres.com` — HubSpot CMS + Cloudflare (VERIFIED)

```
$ curl -sI https://www.acres.com
HTTP/2 200
server: cloudflare
cf-ray: a2cb4da09aa060b7-ORD
cf-cache-status: DYNAMIC
x-hs-hub-id: 22215745
x-hs-portal-id: 22215745
x-hs-content-id: 191104832404
x-hs-prerendered: Tue, 11 Aug 2026 20:31:47 GMT
x-hs-cfworker-meta: {"contentType":"SITE_PAGE","resolver":"PreRenderedContentResolver"}
link: <.../hubfs/hub_generated/template_assets/.../template_main.min.css>; rel=preload...

$ curl -sI https://acres.com
HTTP/2 301
location: https://www.acres.com/
server: cloudflare

$ dig +short acres.com
104.26.8.195 / 104.26.9.195 / 172.67.72.121

$ dig +short NS acres.com
betty.ns.cloudflare.com.
houston.ns.cloudflare.com.
```

The `x-hs-*` header family (hub-id, portal-id, content-id, prerendered, cfworker-meta) is unique to **HubSpot CMS Hub**, and every response carries HubSpot portal ID `22215745`. **VERIFIED: marketing site is HubSpot CMS Hub.** Authoritative DNS (NS records) is Cloudflare, and every response also carries `server: cloudflare` + `cf-ray` — **VERIFIED: Cloudflare sits in front as the edge/proxy layer** for the whole `acres.com` zone.

### 2.2 Blog/content subdomain — `landvalues.acres.com` — also HubSpot (VERIFIED)

```
$ dig +short landvalues.acres.com
22215745.group45.sites.hubspot.net.
group45.sites.hscoscdn40.net.
199.60.103.228 / 199.60.103.28

$ curl -sI https://landvalues.acres.com
HTTP/2 200
server: cloudflare
x-hs-hub-id: 22215745
x-hs-cfworker-meta: {"contentType":"BLOG_LISTING_PAGE",...}
```

CNAME chain resolves through `sites.hubspot.net` → `sites.hscoscdn40.net` (HubSpot's own CDN hostname pattern), same portal ID `22215745`, same Cloudflare edge in front. Same platform as the main marketing site.

### 2.3 Legacy/original product domain — `acrevalue.com` — Django + nginx on AWS (VERIFIED)

"Acres" is the rebrand of **AcreValue**; the original domain still resolves and serves live content directly (not a redirect):

```
$ dig +short acrevalue.com
3.167.163.16 / 3.167.163.7 / 3.167.163.28 / 3.167.163.69   (AWS IP range)

$ curl -sI https://www.acrevalue.com/
HTTP/2 200
server: nginx/1.30.3
x-cache: Miss from cloudfront
x-frame-options: DENY
x-aganalytics-transaction-id: 4a8588ee-07b2-4c3b-b4fe-da2c002375f4
set-cookie: csrftoken=...; SameSite=Lax; Secure

$ curl -s https://www.acrevalue.com/ | grep -o -E "django|csrfmiddlewaretoken|React"
django
csrfmiddlewaretoken
React
```

`csrftoken` as the literal cookie name and `csrfmiddlewaretoken` as a literal form-field string are **Django's own default names** for its CSRF protection — this is a direct framework fingerprint, not an inference. `x-cache: Miss from cloudfront` confirms **AWS CloudFront** in front of an **nginx** origin. The custom `x-aganalytics-transaction-id` header reveals the underlying corporate entity: **AgAnalytics** (Acres/AcreValue's parent/operating company name). React markup is also present, indicating React components are mounted as islands inside server-rendered Django templates — a hybrid, not a pure SPA.

**VERIFIED: acrevalue.com is a Django (Python) application, served by nginx, behind AWS CloudFront, with React UI islands.**

### 2.4 Real interactive product — `maps.acres.com/plat-map/map` — Next.js (VERIFIED)

The homepage links to `auth.acres.com`, whose companion parcel/plat-map tool lives at `maps.acres.com`:

```
$ dig +short maps.acres.com
172.67.72.121 / 104.26.8.195 / 104.26.9.195   (same Cloudflare block as www.acres.com)

$ curl -sI -L https://maps.acres.com/plat-map/map
HTTP/2 200
x-powered-by: Next.js
server: cloudflare
cache-control: private, no-cache, no-store, max-age=0, must-revalidate
link: </_next/static/css/....css>; rel=preload; as="style" [x12]

$ curl -s -L https://maps.acres.com/plat-map/map | grep -o -E "_next/static|webpack"
_next/static
webpack
```

`x-powered-by: Next.js` is a direct, unambiguous framework header. **VERIFIED: the actual interactive parcel/plat-map product runs Next.js**, proxied through the same Cloudflare zone as the marketing site. No `x-vercel-id` header was observed, so this is **not** confirmed as Vercel-hosted — origin compute is hidden behind Cloudflare's proxy (UNKNOWN: AWS / GCP / self-managed).

### 2.5 Auth/API layer — `auth.acres.com` — dedicated JSON API (VERIFIED existence; backend UNKNOWN)

```
$ curl -sI https://auth.acres.com/sessions/whoami
HTTP/2 401
content-type: application/json
access-control-allow-credentials: true
vary: Cookie,Origin
server: cloudflare
```

A 401 with `content-type: application/json` on an unauthenticated session-check endpoint confirms a real, separate JSON REST/session API distinct from the HubSpot marketing layer and the Django legacy app. **UNKNOWN: which backend framework/language powers it** — Cloudflare proxying strips/hides origin-identifying headers.

### 2.6 Acres — summary table

| Layer | Finding | Confidence |
|---|---|---|
| Marketing + blog (`acres.com`, `landvalues.acres.com`) | HubSpot CMS Hub, portal 22215745 | VERIFIED |
| Edge/DNS for whole zone | Cloudflare (NS delegation + `server: cloudflare` on every host) | VERIFIED |
| Legacy product (`acrevalue.com`) | Django (Python) + nginx, behind AWS CloudFront; React islands | VERIFIED |
| Current interactive map product (`maps.acres.com`) | Next.js (`x-powered-by: Next.js`) | VERIFIED |
| Auth/session API (`auth.acres.com`) | Dedicated JSON API, framework unknown | VERIFIED (exists) / UNKNOWN (framework) |
| Compute host for Next.js + auth layers | UNKNOWN | Cloudflare proxy hides origin; no Vercel header seen |
| Database | UNKNOWN | not observable from any frontend fingerprint |

**Read:** Acres is running three product generations simultaneously — a legacy Django/AWS monolith (`acrevalue.com`), a newer Next.js map product (`maps.acres.com`), and a HubSpot marketing/content layer — unified under one Cloudflare-managed DNS zone. This is consistent with a company that grew via the AcreValue→Acres rebrand rather than a clean-sheet rebuild.

---

## 3. ZoneWise.ai — internally known, sourced from repo (not "detected")

Source: `breverdbidder/zonewise-web` — `package.json`, `vercel.json`, `next.config.js`, fetched live via `gh api repos/breverdbidder/zonewise-web/contents/...` this session.

| Layer | Finding | Evidence |
|---|---|---|
| Framework | Next.js **16.1.6**, React 18.3.1, TypeScript | `package.json` `"next": "16.1.6"` |
| Hosting | **Vercel** | `vercel.json` present at repo root (Vercel-schema config: rewrites, security headers); `@vercel/analytics` + `@vercel/speed-insights` packages installed; `next.config.js` rewrites proxy to a companion `zonewise-desktop-viewer.vercel.app` app |
| Auth | **Clerk** | `@clerk/nextjs` 7.0.4, `@clerk/themes` |
| Database / backend | **Supabase** | `@supabase/ssr`, `@supabase/supabase-js` 2.95.3 — project `mocerqjnksmhcjzxrewo.supabase.co` per this repo's own CLAUDE.md |
| Payments | **Stripe** | `stripe` 17.2.0 (server) + `@stripe/stripe-js` 4.8.0 (client) |
| AI | **Anthropic Claude** | `@anthropic-ai/sdk` 0.30.0 |
| Maps / GIS | **Mapbox GL JS** 3.0.0 + **Cesium** 1.115 (3D) + proj4 (reprojection) | `package.json` deps |
| Analytics | **PostHog** | `posthog-js` |
| UI | Radix UI primitives + `class-variance-authority`/`tailwind-merge` (shadcn/ui-style), Framer Motion + GSAP, react-three-fiber/drei/three.js | `package.json` deps |
| CAD/export | dxf-writer, jsPDF, svg2pdf.js | `package.json` deps |
| Security headers | HSTS, `X-Frame-Options: DENY`, COOP/CORP same-origin, restrictive `Permissions-Policy` | `next.config.js` `securityHeaders` array, duplicated in `vercel.json` |
| Testing | Vitest, Playwright, Testing Library, MSW | `package.json` devDependencies |
| Email provider | **UNKNOWN** | No email-sending package (Resend/SendGrid/Nodemailer/etc.) present in `zonewise-web`'s `package.json` dependencies — if email exists, it is not in this repo's frontend deps (possibly a Supabase Edge Function not visible in this file) |

---

## 4. UNKNOWNs — consolidated list (do not treat as gaps in the fingerprinting method; these are things genuinely not observable from HTTP/DNS/markup)

- Algoma app backend framework, API layer, database
- Algoma's exact GCS delivery topology (raw bucket vs. GCLB/Cloud CDN in front)
- Algoma's LLM vendor (prior report's "GPT-4 likely" stays INFERRED)
- Acres `maps.acres.com` and `auth.acres.com` compute host (AWS/GCP/self-managed — hidden behind Cloudflare proxy)
- Acres backend framework for the Next.js + auth layers
- Acres database technology (any layer)
- ZoneWise email-sending provider (not present in `zonewise-web` package.json)

## 5. Non-goals honored

- No BuiltWith-style data pulled from search results — Algoma's algoma.co/Algoma Steel name collision made search unreliable, so this section is 100% `curl`/`dig`/markup evidence.
- No backend/database technology guessed for either external competitor where not observable from the frontend fingerprint — all such items are explicitly marked UNKNOWN above rather than filled in.
