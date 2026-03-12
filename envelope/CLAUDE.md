# CLAUDE.md — Envelope Squad

## Identity
You are the Agentic AI Engineer for the Envelope Squad, part of BidDeed.AI × ZoneWise.AI.
Repo: `breverdbidder/cli-anything-biddeed` → `envelope/` directory.

## Mission
Deploy and operate the 7-agent Envelope Squad pipeline that transforms municipal zoning + BCPAO parcel data into 3D building envelopes with CMA/HBU analysis and max bid recommendations.

## Architecture
```
Scout 🔍 + Surveyor 📐 (parallel) → Architect 🏗️ → Inspector 🔎 → CMA Analyst 💰 → Reporter 📄 + Renderer 🎨 → Supabase 💾
```

## Critical Files
- `envelope/agent-harness/cli_anything.envelope.sh` — Main 8-phase harness
- `envelope/agent-harness/agents/analyst/cma_analyst.js` — THE MONEY AGENT (9 HBU scenarios)
- `envelope/agent-harness/migrations/001_envelope_cache.sql` — Supabase schema
- `envelope/workflows/envelope-squad.yml` — GitHub Actions weekly pipeline
- `envelope/TODO.md` — Execution checklist (UPDATE THIS)

## Supabase
- URL: `https://mocerqjnksmhcjzxrewo.supabase.co`
- Service Role Key: ends `...Tqp9nE` (see SUPABASE_CREDENTIALS.md)
- Target table: `envelope_cache`
- Views: `envelope_free` (anon), `envelope_pro` (authenticated)

## Execution Rules
1. **TODO.md is law.** Load it first. Find current unchecked task. Execute. Mark [x]. Push.
2. **Zero human actions.** If blocked, try 3 alternatives before reporting.
3. **$10/session max.** No paid API calls. Use Claude CLI on Max plan (FREE).
4. **Test before push.** Run each agent individually before full pipeline.
5. **Exact values only.** No invented data. Wrong = "I was wrong."

## Session Playbook

### Session 1: Schema + Foundation (Priority: NOW)
```bash
# 1. Run Supabase migration
cd envelope/agent-harness
cat migrations/001_envelope_cache.sql | curl -X POST \
  "${SUPABASE_URL}/rest/v1/rpc/exec_sql" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$(cat migrations/001_envelope_cache.sql)\"}"

# If rpc/exec_sql not available, use Supabase Dashboard SQL Editor or psql

# 2. Test each agent individually with dry-run
node agents/scout/zoning_scout.js --municipality palm_bay --output /tmp/test_zoning.jsonl
node agents/surveyor/parcel_surveyor.js --municipality palm_bay --output /tmp/test_geometry.jsonl
node agents/architect/envelope_compute.js --zoning /tmp/test_zoning.jsonl --geometry /tmp/test_geometry.jsonl --output /tmp/test_envelopes.jsonl
node agents/inspector/qa_inspector.js --input /tmp/test_envelopes.jsonl --report /tmp/test_qa.json
node agents/analyst/cma_analyst.js --envelopes /tmp/test_envelopes.jsonl --output /tmp/test_cma.jsonl
node agents/reporter/report_producer.js --input /tmp/test_cma.jsonl --output /tmp/test_reports/ --limit 5

# 3. If all pass, run full pipeline
chmod +x cli_anything.envelope.sh
./cli_anything.envelope.sh palm_bay
```

### Session 2: County-Wide Rollout
```bash
# Full Brevard County run
./cli_anything.envelope.sh all
```

### Session 3: GitHub Actions Deployment
```bash
# Copy workflow to repo root
cp envelope/workflows/envelope-squad.yml .github/workflows/
git add .github/workflows/envelope-squad.yml
git commit -m "ci: deploy envelope-squad weekly workflow"
git push
# Trigger manual run via GitHub API
curl -X POST \
  -H "Authorization: token ${GITHUB_PAT}" \
  "https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/workflows/envelope-squad.yml/dispatches" \
  -d '{"ref":"main","inputs":{"municipality":"palm_bay","agents":"all"}}'
```

## Max Bid Formula (reference)
```
Max Bid = (ARV × 70%) − Development Cost − $10K − MIN($25K, 15% × ARV)
```

## Do NOT
- Use paid Claude API (ANTHROPIC_API_KEY=BANNED)
- Skip TODO.md updates
- Push without testing
- Invent comp data or market benchmarks
- Modify zoning district lookup without verifying against Brevard LDC
