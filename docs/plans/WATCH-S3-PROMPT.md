# WATCH S3-5: Dashboard Build + Deploy

> **Executor:** Claude Code (autonomous)
> **Input:** WATCH-SPEC.md Section 6 (Dashboard) + WATCH-PLAN.md Sessions 3-5
> **Output:** Live dashboard deployed to Vercel (watch.biddeed.ai)
> **HITL:** ZERO
> **Hosting:** Vercel Pro (PAID account — NOT Cloudflare Pages)

---

## PRE-FLIGHT

```bash
# Verify S1/S2 outputs exist
ls harnesses/watch/src/types.ts harnesses/watch/src/health-scan.ts harnesses/watch/supabase/functions/watch-ingest/index.ts
# Verify node/npm
node --version && npm --version
# Verify env vars
echo "SB_URL: ${SUPABASE_URL:0:20}... ANON: ${SUPABASE_ANON_KEY:0:20}... VERCEL: ${VERCEL_TOKEN:0:10}..."
# Verify Vercel CLI
vercel --version || npm install -g vercel@latest
```

---

## PHASE 1: Scaffold React App (15 min)

### 1.1 Create Vite + React + TypeScript project

```bash
cd harnesses/watch
npm create vite@latest dashboard -- --template react-ts
cd dashboard
npm install
```

### 1.2 Install dependencies

```bash
npm install @supabase/supabase-js recharts lucide-react date-fns
npm install -D tailwindcss @tailwindcss/vite
```

### 1.3 Configure Tailwind v4 with house brand

In `src/styles/globals.css`:
```css
@import "tailwindcss";

:root {
  --color-primary: #1E3A5F;
  --color-accent: #F59E0B;
  --color-bg: #020617;
  --color-surface: #0F172A;
  --color-surface-hover: #1E293B;
  --color-text: #E2E8F0;
  --color-text-muted: #94A3B8;
  --color-success: #22C55E;
  --color-danger: #EF4444;
  --color-warning: #F59E0B;
  --font-sans: 'Inter', system-ui, sans-serif;
}

body {
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
}
```

In `vite.config.ts` add tailwindcss plugin:
```typescript
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

### 1.4 Create `.env` for build

```
VITE_SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co
VITE_SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
```

Use the actual SUPABASE_ANON_KEY from environment. Write it into the .env file.

### 1.5 Supabase client

File: `src/lib/supabase.ts`
```typescript
import { createClient } from '@supabase/supabase-js'
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)
```

**COMMIT:** `feat(watch): scaffold React + Vite + Tailwind dashboard`

---

## PHASE 2: Auth + Layout (20 min)

### 2.1 Auth hook

File: `src/hooks/useAuth.ts`
- Use `supabase.auth.getSession()` on mount
- Listen to `onAuthStateChange`
- Expose: `session`, `user`, `loading`, `signIn(email)`, `signOut()`
- Magic link: `supabase.auth.signInWithOtp({ email })`

### 2.2 Login page

File: `src/components/LoginPage.tsx`
- House brand: dark bg (#020617), navy card, orange CTA button
- Logo: Text "Claude Watch" with eye icon from lucide-react (Eye)
- Subtitle: "Everest Edition — Claude Code Observability"
- Email input + "Send Magic Link" button
- Loading state, success message

### 2.3 Layout with tabs

File: `src/components/Layout.tsx`
- Desktop: Left sidebar (200px) with nav items + main content area
- Mobile (<768px): Bottom tab bar with 3 tabs
- Tabs: 🔴 Live | 📋 Sessions | 🧠 Health
- Active tab: orange accent underline
- Header: "Claude Watch" + user email + sign out

### 2.4 App router

File: `src/App.tsx`
- If not authenticated → LoginPage
- If authenticated → Layout with tab routing (useState, not react-router)
- Default tab: Live

**COMMIT:** `feat(watch): auth flow + responsive layout shell`

---

## PHASE 3: LIVE Tab (30 min)

### 3.1 Realtime hook

File: `src/hooks/useRealtime.ts`
- Subscribe to `postgres_changes` INSERT on `watch_events`
- Subscribe to `postgres_changes` INSERT/UPDATE on `watch_sessions`
- Expose: `activeSessionEvents`, `activeSessions`
- Auto-cleanup subscription on unmount

### 3.2 Active Session Cards

File: `src/components/live/ActiveSessionCards.tsx`
- Grid of cards (1 col mobile, 2 col tablet, 3 col desktop)
- Each card shows: repo name, status badge (green pulse for active), duration (live counter with setInterval), last tool + file, event count
- Click card → select session for event stream
- Empty state: "No active sessions. Claude Code will appear here when running."

### 3.3 Live Event Stream

File: `src/components/live/LiveEventStream.tsx`
- Scrolling list of events for selected session
- Each event: timestamp (relative, e.g. "2s ago"), tool icon (color coded), file_path (truncated), one-line summary
- Tool colors: Write=green, Edit=blue, Bash=orange, Read=gray
- Auto-scroll to bottom on new events
- Max 200 events in view (older ones trimmed from state)

### 3.4 Tool Frequency Chart

File: `src/components/live/ToolFrequencyChart.tsx`
- Recharts horizontal bar chart
- Shows tool distribution for selected session
- Colors match tool colors above
- Compact — fits in a sidebar panel

### 3.5 Sessions data hook

File: `src/hooks/useSessions.ts`
- Fetch active sessions: `supabase.from('watch_sessions').select('*').eq('status', 'active')`
- Fetch session events: `supabase.from('watch_events').select('*').eq('session_id', id).order('ts', { ascending: true })`
- Fetch completed sessions with filters: repo, date range, tool

**COMMIT:** `feat(watch): LIVE tab with Supabase Realtime streaming`

---

## PHASE 4: AUDIT Tab (30 min)

### 4.1 Session Table

File: `src/components/audit/SessionTable.tsx`
- Sortable columns: repo, started_at, duration, event_count, status
- Status badges: active=green, completed=blue, stale=gray
- Tool breakdown shown as mini colored bars
- Click row → expand to timeline view
- Pagination: 20 per page

### 4.2 Session Timeline

File: `src/components/audit/SessionTimeline.tsx`
- Vertical timeline with tool icons on left
- Each node: timestamp, tool_name, file_path, expandable input_data/output_data
- Edit events show inline diff (DiffViewer)
- Color-coded by tool type

### 4.3 Diff Viewer

File: `src/components/audit/DiffViewer.tsx`
- Simple split view: red (removed) / green (added)
- Uses `<pre>` blocks with Tailwind text classes
- No heavy dependency — just string diffing from the diff field in watch_events

### 4.4 Filter Bar

File: `src/components/audit/FilterBar.tsx`
- Repo dropdown (fetch distinct repos from sessions)
- Date range: last 24h / 7d / 30d / custom
- Tool filter: multi-select checkboxes
- File path search input

**COMMIT:** `feat(watch): AUDIT tab with session replay + diff viewer`

---

## PHASE 5: HEALTH Tab (20 min)

### 5.1 Repo Selector

File: `src/components/health/RepoSelector.tsx`
- Horizontal tab bar: All | biddeed-ai | biddeed-ai-ui | cli-anything-biddeed | zonewise-scraper-v4 | zonewise-web
- Scrollable on mobile

### 5.2 Logic File Tree

File: `src/components/health/LogicFileTree.tsx`
- Fetch from watch_health_latest view
- Group by category: prompts → rules → config → docs → state
- Collapsible sections
- Importance badges: 🔴 critical, 🟡 high, ⚪ normal
- Click file → show content_preview + link to GitHub

### 5.3 Health Score Card

File: `src/components/health/HealthScoreCard.tsx`
- Per repo card: total logic files, critical rules count, last scan time
- Color: green if scanned <24h ago, yellow 1-3 days, red >3 days

### 5.4 Change Timeline

File: `src/components/health/ChangeTimeline.tsx`
- Recharts scatter plot or simple dot grid
- X = last 90 days, Y = repos
- Dots colored by importance on dates when files changed
- Hover tooltip: file name + change type

**COMMIT:** `feat(watch): HEALTH tab with CLAUDE.md ecosystem view`

---

## PHASE 6: Build + Deploy to Vercel (15 min)

**IMPORTANT: Deploy to Vercel Pro account. NOT Cloudflare Pages.**

### 6.1 Build production bundle

```bash
cd harnesses/watch/dashboard
npm run build
ls -la dist/
```

Verify dist/ has index.html and assets.

### 6.2 Deploy to Vercel

```bash
cd harnesses/watch/dashboard

# Create Vercel project and deploy
vercel --token $VERCEL_TOKEN --yes --prod \
  --name claude-watch \
  --build-command "npm run build" \
  --output-directory dist \
  --env VITE_SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co \
  --env VITE_SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY
```

### 6.3 Verify deployment

```bash
# Get the deployment URL
DEPLOY_URL=$(vercel ls --token $VERCEL_TOKEN 2>/dev/null | grep claude-watch | head -1 | awk '{print $2}')
echo "Deploy URL: $DEPLOY_URL"

curl -s -o /dev/null -w "%{http_code}" "https://$DEPLOY_URL"
```

Must return 200.

### 6.4 Set custom domain (watch.biddeed.ai)

```bash
vercel domains add watch.biddeed.ai --token $VERCEL_TOKEN
```

If DNS needs updating, note the required records for the Telegram notification.

### 6.5 Create auto-deploy GHA workflow

File: `.github/workflows/deploy-watch-dashboard.yml`

```yaml
name: Deploy Watch Dashboard
on:
  push:
    branches: [main]
    paths: ['harnesses/watch/dashboard/**']
  workflow_dispatch: {}

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install Vercel CLI
        run: npm install -g vercel@latest
      - name: Install and build
        run: |
          cd harnesses/watch/dashboard
          npm ci
          npm run build
        env:
          VITE_SUPABASE_URL: https://mocerqjnksmhcjzxrewo.supabase.co
          VITE_SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
      - name: Deploy to Vercel
        run: |
          cd harnesses/watch/dashboard
          vercel deploy --prod --token ${{ secrets.VERCEL_TOKEN }} --yes
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
```

**COMMIT:** `feat(watch): Vercel deploy + GHA auto-deploy workflow`

---

## PHASE 7: Final verification + push

### 7.1 Verify all files exist

```bash
find harnesses/watch/dashboard/src -name "*.tsx" -o -name "*.ts" | sort
```

Must show all component files from phases 2-5.

### 7.2 Verify build succeeds

```bash
cd harnesses/watch/dashboard && npm run build
echo "Exit code: $?"
```

### 7.3 Verify Vercel is live

```bash
DEPLOY_URL=$(vercel ls --token $VERCEL_TOKEN 2>/dev/null | grep claude-watch | head -1 | awk '{print $2}')
curl -s -o /dev/null -w "%{http_code}" "https://$DEPLOY_URL"
```

### 7.4 Push everything

```bash
cd /opt/biddeed/cli-anything-biddeed
git add -A
git commit -m "feat(watch): v0.1.0 — full dashboard with LIVE/AUDIT/HEALTH tabs, deployed to Vercel"
git push origin main
```

### 7.5 Telegram notification

```bash
DEPLOY_URL=$(vercel ls --token $VERCEL_TOKEN 2>/dev/null | grep claude-watch | head -1 | awk '{print $2}')
curl -sf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=🏔️ Claude Watch Dashboard LIVE at https://${DEPLOY_URL}
✅ LIVE tab: Realtime session monitoring
✅ AUDIT tab: Session replay + diff viewer
✅ HEALTH tab: CLAUDE.md ecosystem status
🎨 House brand applied
📱 Mobile responsive
🚀 Hosted on Vercel Pro
Next: Add DNS record for watch.biddeed.ai if not auto-configured"
```

---

## CONSTRAINTS

- **VERCEL PRO:** Deploy to Vercel, NOT Cloudflare Pages. We have a paid account.
- **HOUSE BRAND:** Navy #1E3A5F, Orange #F59E0B, bg #020617, Inter font. NO other color schemes.
- **ZERO EXTRA COST:** No paid dependencies beyond Vercel Pro (already paid). Supabase free tier handles the data.
- **NO localStorage:** Use React state only. Supabase handles persistence.
- **SINGLE FILE APPROACH:** Inline CSS-in-Tailwind. No separate CSS files except globals.css.
- **MOBILE FIRST:** Test at 375px. Bottom tab nav required.
- **NEVER-LIE:** Show deployment URL output proving Vercel returns 200 before declaring done.
- **GIT HYGIENE:** Commit after each phase. Descriptive messages. Push at end.
