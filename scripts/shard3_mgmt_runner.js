#!/usr/bin/env node
// Shard3-6cace789: Apply migrations and capture before/after evaluations
// Uses Management API (same pattern as run_migration.js) + REST API for evaluations

import fs from "fs";

const PROJECT_REF = "mocerqjnksmhcjzxrewo";
const ACCESS_TOKEN = process.env.SUPABASE_ACCESS_TOKEN;
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

const COUNTIES = ["seminole", "hamilton", "union", "flagler", "lake"];
const MIGRATIONS = [
  "migrations/20260801_shard3_6cace789_flagler_g_regression_fix.sql",
  "migrations/20260801b_shard3_6cace789_seminole_i_inline_fix.sql",
  "migrations/20260801c_shard3_6cace789_flagler_cd_i_fix.sql",
  "migrations/20260801d_shard3_6cace789_ultraloop_and_closeout.sql",
];

async function evaluate(county) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county`, {
    method: "POST",
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ county_slug_arg: county }),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`HTTP ${res.status}: ${t.slice(0, 200)}`);
  }
  return res.json();
}

async function runMigration(file) {
  if (!fs.existsSync(file)) {
    console.error(`MISSING: ${file}`);
    return { status: "missing" };
  }
  const sql = fs.readFileSync(file, "utf8");
  console.log(`\nApplying ${file} (${sql.length} chars)...`);
  const res = await fetch(`https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${ACCESS_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query: sql }),
  });
  const text = await res.text();
  console.log(`  Status: ${res.status}`);
  console.log(`  Response: ${text.slice(0, 500)}`);
  return { status: res.status, response: text.slice(0, 500) };
}

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  if (!ACCESS_TOKEN) { console.error("SUPABASE_ACCESS_TOKEN not set"); process.exit(1); }
  if (!SUPABASE_URL) { console.error("SUPABASE_URL not set"); process.exit(1); }
  if (!SUPABASE_KEY) { console.error("SUPABASE_SERVICE_ROLE_KEY not set"); process.exit(1); }

  console.log("=".repeat(60));
  console.log("SHARD3-6cace789 APPLY & VERIFY");
  console.log("=".repeat(60));

  // BEFORE state
  console.log("\n--- BEFORE STATE ---");
  const before = {};
  for (const c of COUNTIES) {
    try {
      before[c] = await evaluate(c);
      console.log(`BEFORE ${c}: ${JSON.stringify(before[c])}`);
    } catch (e) {
      console.log(`BEFORE ${c}: ERROR ${e.message}`);
      before[c] = { error: e.message };
    }
  }

  // Apply migrations in order
  console.log("\n--- APPLYING MIGRATIONS ---");
  const migrationResults = {};
  for (const mf of MIGRATIONS) {
    migrationResults[mf] = await runMigration(mf);
    if (![200, 201].includes(migrationResults[mf].status)) {
      console.log(`  WARNING: Non-200 on ${mf} — continuing anyway`);
    }
    await sleep(2000);
  }

  // AFTER state
  console.log("\n--- AFTER STATE ---");
  const after = {};
  for (const c of COUNTIES) {
    try {
      after[c] = await evaluate(c);
      console.log(`AFTER ${c}: ${JSON.stringify(after[c])}`);
    } catch (e) {
      console.log(`AFTER ${c}: ERROR ${e.message}`);
      after[c] = { error: e.message };
    }
  }

  // Score summary
  console.log("\n--- SCORE MOVEMENT SUMMARY ---");
  for (const c of COUNTIES) {
    const b = before[c] || {};
    const a = after[c] || {};
    if (b.error || a.error) { console.log(`${c}: ERROR in evaluation`); continue; }
    const bPass = Object.values(b).filter(v => v && typeof v === "object" && v.pass).length;
    const aPass = Object.values(a).filter(v => v && typeof v === "object" && v.pass).length;
    const bFail = Object.entries(b).filter(([, v]) => v && typeof v === "object" && !v.pass).map(([k]) => k);
    const aFail = Object.entries(a).filter(([, v]) => v && typeof v === "object" && !v.pass).map(([k]) => k);
    const delta = aPass - bPass;
    console.log(`${c}: ${bPass}/10 -> ${aPass}/10 (${delta >= 0 ? "+" : ""}${delta})`);
    if (bFail.length) console.log(`  was failing: ${bFail.sort().join(", ")}`);
    if (aFail.length) console.log(`  still failing: ${aFail.sort().join(", ")}`);
  }

  // Save results
  const results = { before, migrations: migrationResults, after, ts: new Date().toISOString() };
  fs.writeFileSync("shard3_results.json", JSON.stringify(results, null, 2));
  console.log("\nFull results saved to shard3_results.json");
}

main().catch(e => { console.error(e); process.exit(1); });
