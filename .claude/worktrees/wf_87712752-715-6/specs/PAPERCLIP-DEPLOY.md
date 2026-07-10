# PAPERCLIP-DEPLOY.md
# SUMMIT Dispatch Spec — Ship Target #1
# Date: 2026-03-28
# Author: Claude AI Architect
# Executor: Claude Code on Hetzner 87.99.129.125

---

## MISSION

Deploy Paperclip on Hetzner. Create "Everest Capital USA" company with CEO + 1 ZoneWise engineer.
Expose at ops.biddeed.ai via Cloudflare reverse proxy with Access (zero-trust auth).

**Definition of DONE:**
1. `curl https://ops.biddeed.ai` returns Paperclip dashboard
2. "Everest Capital USA" company exists with 2 agents (CEO + ZoneWise Engineer)
3. CEO has completed first task or is actively running
4. Cloudflare Access restricts to ariel@everestcapitalusa.com only
5. Dashboard accessible from mobile

---

## PHASE 1: INSTALL PAPERCLIP (30 min)

### Step 1: Sync fork with upstream
```bash
cd /home/claude
git clone https://github.com/breverdbidder/paperclip.git paperclip-deploy
cd paperclip-deploy
git remote add upstream https://github.com/paperclipai/paperclip.git
git fetch upstream
git merge upstream/master --no-edit
git push origin master
```

### Step 2: Docker deploy
Paperclip supports Docker. Use compose file from repo or create one:

```bash
cd /home/claude/paperclip-deploy

# Check if docker-compose.yml exists in repo
ls docker-compose*.yml 2>/dev/null || echo "Need to create compose file"

# If no compose file, create one:
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  paperclip:
    build: .
    container_name: paperclip-server
    ports:
      - "127.0.0.1:3100:3100"
    volumes:
      - paperclip-data:/root/.paperclip
      - /home/claude:/home/claude
    environment:
      - NODE_ENV=production
      - PAPERCLIP_PUBLIC_URL=https://ops.biddeed.ai
      - PAPERCLIP_ALLOWED_HOSTNAMES=ops.biddeed.ai,localhost
    restart: unless-stopped

volumes:
  paperclip-data:
EOF

docker compose up -d
```

**FALLBACK if Docker fails:** Install directly:
```bash
# Requires Node 20+, pnpm 9.15+
npm install -g pnpm
cd /home/claude/paperclip-deploy
pnpm install
pnpm build
# Run with pm2 for persistence
npm install -g pm2
pm2 start "pnpm start" --name paperclip
pm2 save
```

### Step 3: Verify local
```bash
curl -s http://localhost:3100 | head -20
# Should return HTML (React SPA)
```

---

## PHASE 2: CLOUDFLARE REVERSE PROXY (20 min)

### Step 1: DNS record
```bash
# Add A record: ops.biddeed.ai -> 87.99.129.125
# Proxied (orange cloud) for Cloudflare protection
# Zone: biddeed.ai (already managed in Cloudflare)

curl -X POST "https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records" \
  -H "Authorization: Bearer {CF_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{
    "type": "A",
    "name": "ops",
    "content": "87.99.129.125",
    "proxied": true
  }'
```

### Step 2: Nginx reverse proxy on Hetzner
```bash
# Add nginx config for ops.biddeed.ai
cat > /etc/nginx/sites-available/ops-biddeed << 'EOF'
server {
    listen 80;
    server_name ops.biddeed.ai;

    location / {
        proxy_pass http://127.0.0.1:3100;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # WebSocket support for live agent streaming
        proxy_read_timeout 86400;
    }
}
EOF

ln -sf /etc/nginx/sites-available/ops-biddeed /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### Step 3: Cloudflare Access (zero-trust)
```bash
# Create Access application via API
# Policy: Allow only ariel@everestcapitalusa.com
# Method: One-time PIN (email OTP)

curl -X POST "https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/access/apps" \
  -H "Authorization: Bearer {CF_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{
    "name": "Paperclip Dashboard",
    "domain": "ops.biddeed.ai",
    "type": "self_hosted",
    "session_duration": "24h",
    "policies": [{
      "name": "Ariel Only",
      "decision": "allow",
      "include": [{
        "email": {"email": "ariel@everestcapitalusa.com"}
      }]
    }]
  }'
```

### Step 4: Verify external access
```bash
# From Hetzner:
curl -I https://ops.biddeed.ai
# Should get 302 redirect to Cloudflare Access login
```

---

## PHASE 3: CREATE COMPANY & AGENTS (20 min)

### Step 1: Onboard via API or UI
Paperclip onboarding wizard runs on first visit. If using API:

```bash
PAPERCLIP_URL="http://localhost:3100"

# Create company
curl -X POST "$PAPERCLIP_URL/api/companies" \
  -H "Content-Type: application/json" \
  --data '{
    "name": "Everest Capital USA",
    "description": "AI-powered real estate intelligence ecosystem. Products: BidDeed.AI (foreclosure auctions), ZoneWise.AI (67-county zoning), SwimSquad (athletic tracking). Solo founder Ariel Shapira acts as board. Goal: Ship ZoneWise explorer with live Mapbox map, then expand to full BidDeed pipeline.",
    "settings": {}
  }'
```

### Step 2: Create CEO agent
```json
{
  "name": "Nexus Commander",
  "title": "CEO",
  "adapter": "claude_code",
  "model": "claude-sonnet-4-6",
  "reportsTo": null,
  "capabilities": ["task_assignment", "agent_creation", "project_management"],
  "heartbeat": {
    "enabled": true,
    "frequency": "4h"
  },
  "instructions": {
    "soul": "You are the CEO of Everest Capital USA, an AI-powered real estate intelligence company. You report to the board (Ariel Shapira, solo founder). You own the P&L, strategic direction, and team composition. Default to action. Hold the long view while executing near-term. Protect focus — WIP=1 always. Current ship target: ZoneWise.AI explorer with live Mapbox map. GitHub org: breverdbidder. Infrastructure: Hetzner 87.99.129.125, Supabase, Cloudflare, GitHub Actions.",
    "heartbeat": "On each heartbeat: 1) Check all project status in GitHub repos. 2) Review open issues/PRs. 3) Check if engineers are blocked. 4) Update task status. 5) If morning (9AM EST), generate daily digest. 6) If evening (5PM EST), generate recap. 7) Escalate blockers to board only if stuck after 3 attempts.",
    "tools": "You have access to: GitHub API (PAT in secrets), Supabase (credentials in secrets), Cloudflare API. You can create new agents when needed. You can assign tasks to engineers. You can review and approve PRs."
  }
}
```

### Step 3: Create ZoneWise Engineer
```json
{
  "name": "ZoneWise Dev",
  "title": "Founding Engineer",
  "adapter": "claude_code",
  "model": "claude-sonnet-4-6",
  "reportsTo": "Nexus Commander",
  "capabilities": ["code_execution", "file_management", "git_operations"],
  "heartbeat": {
    "enabled": true,
    "frequency": "8h"
  },
  "instructions": {
    "soul": "You are the founding engineer at Everest Capital USA, focused on ZoneWise.AI. Your primary mission is shipping the ZoneWise explorer — a live Mapbox map at zonewise.ai/explorer showing Florida zoning data. Tech stack: React, Mapbox GL JS, Supabase (fl_counties + county_conquest_status tables), Cloudflare Pages, GitHub Actions. Repo: breverdbidder/zonewise-web. Brand: Navy #1E3A5F, Orange #F59E0B, Inter font, bg #020617. Vercel project: prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E. Mapbox token: ${MAPBOX_TOKEN} (everest18).",
    "heartbeat": "On each heartbeat: 1) Pull latest from zonewise-web repo. 2) Check TODO.md for current task. 3) Execute next unchecked item. 4) Run tests. 5) Commit and push. 6) Update task status. 7) Report blockers to CEO.",
    "tools": "GitHub, Supabase, Cloudflare Pages deployment. Follow CLAUDE.md in repo as root directive."
  }
}
```

### Step 4: Create first task
```json
{
  "title": "Ship ZoneWise Explorer MVP",
  "description": "Deploy a working Mapbox map at zonewise.ai/explorer that displays Florida county boundaries with zoning conquest status. Pull data from Supabase fl_counties table. Use existing Mapbox token. Must be mobile-responsive. Brand colors: Navy #1E3A5F, Orange #F59E0B. Repo: breverdbidder/zonewise-web. This is Ship Target #1 — nothing else until this is LIVE and VERIFIED.",
  "assignee": "ZoneWise Dev",
  "project": "ZoneWise.AI",
  "priority": "critical"
}
```

### Step 5: Add secrets
```bash
# These need to be added via Paperclip UI or API
# CEO and engineers need access to:

# GitHub PAT
GITHUB_TOKEN=${GITHUB_PAT}

# Supabase
SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<from SUPABASE_CREDENTIALS.md>

# Cloudflare
CF_API_TOKEN=<from GitHub secrets>

# Mapbox
MAPBOX_TOKEN=${MAPBOX_TOKEN}
```

---

## PHASE 4: ADD PROJECTS (10 min)

Create 4 projects, each linked to a GitHub repo:

| Project | Repo | Status |
|---------|------|--------|
| ZoneWise.AI | breverdbidder/zonewise-web | Active — Ship Target #1 |
| BidDeed.AI | breverdbidder/brevard-bidder-scraper | Backlog |
| SwimSquad | breverdbidder/swimsquad-ai | Backlog |
| Infrastructure | breverdbidder/cli-anything-biddeed | Backlog |

---

## PHASE 5: ROUTINES (10 min)

| Routine | Frequency | Agent | Description |
|---------|-----------|-------|-------------|
| Morning Digest | Daily 9AM EST | CEO | Check all repos, generate Telegram briefing |
| Evening Recap | Daily 5PM EST | CEO | Summarize day, update daily_checkpoints |
| Security Patrol | Every 4hr | CEO (delegate later) | Scan for leaked secrets, service health |
| Weekly Health | Sunday 9AM | CEO | Repo-forensics, dependency audit |

---

## VERIFICATION CHECKLIST

```bash
# 1. Paperclip server running
curl -s http://localhost:3100/api/health | jq .

# 2. External access (will redirect to CF Access)
curl -I https://ops.biddeed.ai

# 3. Company exists
curl -s http://localhost:3100/api/companies | jq '.[].name'

# 4. Agents exist
curl -s http://localhost:3100/api/companies/{id}/agents | jq '.[].name'

# 5. Task assigned
curl -s http://localhost:3100/api/companies/{id}/issues | jq '.[0].title'
```

**DONE when all 5 return expected values.**

---

## COST ESTIMATE

- Paperclip: FREE (open source, self-hosted)
- Hetzner: Already paid (87.99.129.125)
- Cloudflare: FREE (proxy + Access on free plan for 1 user)
- Claude Code heartbeats: Covered by Max plan subscription
- Total additional cost: $0

---

## NOTES

- Paperclip stores data in embedded PostgreSQL at ~/.paperclip/
- Backup: Add ~/.paperclip/ to Hetzner backup routine
- GStack and Hermes integration deferred to Phase 2 (next week)
- everest-stack repo absorbs into Paperclip skills directory
- This spec supersedes previous SHIP GATE target (zonewise.ai/explorer)
- ZoneWise explorer is now a TASK within Paperclip, not a standalone target
