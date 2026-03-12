# TODO.md — Envelope Squad Deployment

## Phase 1: Schema + Foundation
- [ ] Run `001_envelope_cache.sql` migration against Supabase (CREATE TABLE + indexes + RLS + views + functions)
- [ ] Verify `envelope_cache` table exists: `SELECT count(*) FROM envelope_cache`
- [ ] Verify `envelope_free` view works: `SELECT * FROM envelope_free LIMIT 1`
- [ ] Verify `envelope_pro` view works: `SELECT * FROM envelope_pro LIMIT 1`
- [ ] Verify `envelope_stats()` function works
- [ ] Mark harness executable: `chmod +x cli_anything.envelope.sh`

## Phase 2: Agent Testing (Palm Bay — individual agents)
- [ ] Test Agent 1 Scout: `node agents/scout/zoning_scout.js --municipality palm_bay --output /tmp/test_zoning.jsonl`
- [ ] Verify zoning output has records: `wc -l /tmp/test_zoning.jsonl`
- [ ] Test Agent 2 Surveyor: `node agents/surveyor/parcel_surveyor.js --municipality palm_bay --output /tmp/test_geometry.jsonl`
- [ ] Verify geometry output has records: `wc -l /tmp/test_geometry.jsonl`
- [ ] Test Agent 3 Architect: `node agents/architect/envelope_compute.js --zoning /tmp/test_zoning.jsonl --geometry /tmp/test_geometry.jsonl --output /tmp/test_envelopes.jsonl`
- [ ] Verify envelopes computed: `wc -l /tmp/test_envelopes.jsonl`
- [ ] Test Agent 5 Inspector: `node agents/inspector/qa_inspector.js --input /tmp/test_envelopes.jsonl --report /tmp/test_qa.json`
- [ ] Verify QA pass rate >= 70%: `cat /tmp/test_qa.json | jq '.summary.pass_rate'`
- [ ] Test Agent 6 CMA Analyst: `node agents/analyst/cma_analyst.js --envelopes /tmp/test_envelopes.jsonl --output /tmp/test_cma.jsonl`
- [ ] Verify CMA output: `wc -l /tmp/test_cma.jsonl`
- [ ] Test Agent 7 Reporter: `node agents/reporter/report_producer.js --input /tmp/test_cma.jsonl --output /tmp/test_reports/ --limit 5`
- [ ] Verify HTML reports generated: `ls /tmp/test_reports/*.html`
- [ ] Test Agent 4 Renderer: `node agents/renderer/render_samples.js --input /tmp/test_envelopes.jsonl --output /tmp/test_renders/ --count 5`
- [ ] Verify render configs: `ls /tmp/test_renders/*.json`

## Phase 3: Full Pipeline — Palm Bay
- [ ] Run full harness: `./cli_anything.envelope.sh palm_bay`
- [ ] Verify Supabase load: `SELECT count(*) FROM envelope_cache WHERE source_municipality = 'palm_bay'`
- [ ] Verify mission report printed with all 7 agent counts
- [ ] Archive created in `archives/`

## Phase 4: GitHub Actions Deployment
- [ ] Copy workflow: `cp envelope/workflows/envelope-squad.yml .github/workflows/envelope-squad.yml`
- [ ] Commit and push workflow
- [ ] Add secrets if missing: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
- [ ] Trigger manual workflow_dispatch via GitHub API for palm_bay test
- [ ] Verify workflow completes successfully in Actions tab
- [ ] Verify Telegram notification received

## Phase 5: County-Wide Rollout
- [ ] Run `./cli_anything.envelope.sh all`
- [ ] Check `SELECT source_municipality, count(*) FROM envelope_cache GROUP BY source_municipality`
- [ ] Target: 80%+ parcel coverage across Brevard
- [ ] Generate top-25 CMA report set
- [ ] Verify auction day brief HTML renders correctly

## Phase 6: Product Integration
- [ ] Extract shared React component from prototype JSX
- [ ] Add to `breverdbidder/biddeed-ai-ui` as `<BuildingEnvelope3D />`
- [ ] Add to `breverdbidder/zonewise-web` parcel detail view
- [ ] Wire Supabase client to fetch envelope_cache by parcel_id
- [ ] Test on live auction property
