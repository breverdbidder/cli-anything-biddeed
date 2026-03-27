#!/usr/bin/env node
/**
 * cli_anything.discovery — Shared Exa semantic search harness
 * Usage:
 *   node index.js zonewise --county "Orange" --state FL
 *   node index.js auction --county "Brevard" --state FL
 *   node index.js gtm --vertical "FL title companies" --max 25
 *   node index.js zonewise --batch
 *   node index.js zonewise --county "Duval" --dry-run
 */

const { ExaClient } = require('./exa_client');
const { buildQueries, estimateCost } = require('./query_builder');
const { processResults } = require('./filter_rank');
const { DiscoveryStore } = require('./persist');

const EXA_API_KEY = process.env.EXA_API_KEY;
const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

function parseArgs(argv) {
  const args = { mode: argv[2] };
  for (let i = 3; i < argv.length; i++) {
    switch (argv[i]) {
      case '--county': args.county = argv[++i]; break;
      case '--state': args.state = argv[++i]; break;
      case '--vertical': args.vertical = argv[++i]; break;
      case '--max': args.max = parseInt(argv[++i]); break;
      case '--batch': args.batch = true; break;
      case '--dry-run': args.dryRun = true; break;
      case '--cost-estimate': args.costEstimate = true; break;
      case '--deep': args.deep = true; break;
    }
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv);
  const startTime = Date.now();

  if (!['zonewise', 'auction', 'gtm'].includes(args.mode)) {
    console.error('Usage: discovery <zonewise|auction|gtm> [options]');
    console.error('  --county "Name"   Target county');
    console.error('  --state XX        State code (default: FL)');
    console.error('  --batch           Process all pending counties');
    console.error('  --dry-run         Show cost estimate only');
    console.error('  --deep            Use Exa deep search (slower, better)');
    console.error('  --vertical "X"    GTM mode: target vertical');
    process.exit(1);
  }

  if (!EXA_API_KEY) {
    console.error('❌ EXA_API_KEY not set');
    console.error('   Get one at https://dashboard.exa.ai');
    console.error('   Free: $10 credits. Pro: $49/mo.');
    process.exit(1);
  }

  const exa = new ExaClient(EXA_API_KEY);
  const store = SUPABASE_KEY ? new DiscoveryStore(SUPABASE_URL, SUPABASE_KEY) : null;
  if (!store) console.warn('⚠️  No SUPABASE_SERVICE_ROLE_KEY — results will not persist');

  // Build county list
  let counties = [];
  if (args.batch && store) {
    counties = await store.getPendingCounties();
    console.log(`📋 Batch: ${counties.length} pending counties`);
  } else if (args.county) {
    counties = [{ county_name: args.county }];
  } else if (args.mode === 'gtm') {
    counties = [{ county_name: null }];
  } else {
    console.error('❌ Provide --county "Name" or --batch');
    process.exit(1);
  }

  // Dry run
  const allQueries = counties.flatMap(c =>
    buildQueries(args.mode, { county: c.county_name, state: args.state, vertical: args.vertical })
  );
  const estimate = estimateCost(allQueries);

  if (args.dryRun) {
    console.log('\n--- DRY RUN ---');
    console.log(`mode: ${args.mode}`);
    console.log(`counties: ${counties.length}`);
    console.log(`queries: ${estimate.queryCount}`);
    console.log(`estimated_cost: $${estimate.estimatedCost}`);
    console.log(`per_query: $${estimate.perQueryCost}`);
    console.log(`under_$10_cap: ${parseFloat(estimate.estimatedCost) < 10 ? '✅ YES' : '⚠️ OVER'}`);
    console.log('\nSample queries:');
    allQueries.slice(0, 5).forEach(q => console.log(`  → ${q.query}`));
    return;
  }

  // Execute
  const allResults = [];
  let totalInserted = 0;

  for (const county of counties) {
    const countyName = county.county_name;
    console.log(`\n🔍 ${countyName || args.vertical} (${args.mode})`);

    const queries = buildQueries(args.mode, {
      county: countyName,
      state: args.state || 'FL',
      vertical: args.vertical
    });

    const countyResults = [];

    for (const q of queries) {
      try {
        const response = args.deep
          ? await exa.deepSearch(q.query, q.searchOpts)
          : await exa.search(q.query, q.searchOpts);

        const processed = processResults(response.results, q.expectedClassification);

        const enriched = processed.map(r => ({
          ...r,
          mode: args.mode,
          county: countyName,
          state: args.state || 'FL',
          query: q.query,
          cost: response.cost / Math.max(processed.length, 1),
          searchType: response.searchType
        }));

        countyResults.push(...enriched);
        console.log(`  ✅ "${q.query}" → ${processed.length} results ($${response.cost.toFixed(4)})`);

      } catch (err) {
        if (err.message.startsWith('COST CAP')) {
          console.error(`\n🛑 ${err.message}`);
          // Save what we have before stopping
          break;
        }
        console.error(`  ❌ "${q.query}": ${err.message}`);
      }
    }

    // Deduplicate within county
    const { deduplicateResults } = require('./filter_rank');
    const dedupedCounty = deduplicateResults(countyResults);
    allResults.push(...dedupedCounty);

    // Persist
    if (store && dedupedCounty.length > 0) {
      const { inserted, errors } = await store.saveResults(dedupedCounty);
      totalInserted += inserted;
      if (errors.length) console.error(`  ⚠️ DB: ${errors.join(', ')}`);
      await store.updateConquestStatus(countyName, args.mode);
      console.log(`  💾 Saved ${inserted} results to Supabase`);
    }

    // County summary
    const classifications = {};
    dedupedCounty.forEach(r => {
      classifications[r.classification] = (classifications[r.classification] || 0) + 1;
    });
    console.log(`  📊 ${Object.entries(classifications).map(([k, v]) => `${k}:${v}`).join(' ')}`);
  }

  // Final report
  const costReport = exa.getCostReport();
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  console.log('\n========== DISCOVERY REPORT ==========');
  console.log(`mode:              ${args.mode}`);
  console.log(`counties:          ${counties.length}`);
  console.log(`total_results:     ${allResults.length}`);
  console.log(`db_inserted:       ${totalInserted}`);
  console.log(`exa_requests:      ${costReport.requestCount}`);
  console.log(`exa_cost:          $${costReport.totalCost.toFixed(4)}`);
  console.log(`budget_remaining:  $${costReport.budgetRemaining.toFixed(4)}`);
  console.log(`budget_used:       ${costReport.budgetUsedPct}%`);
  console.log(`elapsed:           ${elapsed}s`);
  console.log('=======================================');

  // Classification breakdown
  const totals = {};
  allResults.forEach(r => { totals[r.classification] = (totals[r.classification] || 0) + 1; });
  console.log('\nClassifications:');
  Object.entries(totals).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => {
    console.log(`  ${k}: ${v}`);
  });

  // Exit code
  process.exit(allResults.length > 0 ? 0 : 1);
}

main().catch(err => {
  console.error(`💥 Fatal: ${err.message}`);
  process.exit(2);
});
