// apply_shard7_migrations.js
// SHARD-7 dispatch 74e8c56b — Apply hillsborough G + calhoun I migrations
// Usage: SUPABASE_ACCESS_TOKEN=<token> node apply_shard7_migrations.js

import fs from "fs";

const TOKEN = process.env.SUPABASE_ACCESS_TOKEN;
const SB_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY || "";
const SB_URL = process.env.SUPABASE_URL || "https://mocerqjnksmhcjzxrewo.supabase.co";
const PROJECT_REF = "mocerqjnksmhcjzxrewo";
const DISPATCH_ID = "74e8c56b-ed5f-4fe0-a4cf-e97e24ccdd3e";

async function mgmtQuery(sql) {
  if (!TOKEN) {
    console.log("SUPABASE_ACCESS_TOKEN not set — skipping");
    return null;
  }
  const res = await fetch(
    `https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify({ query: sql }),
    }
  );
  const text = await res.text();
  return { status: res.status, body: text };
}

async function sbPost(table, rows) {
  if (!SB_KEY) {
    console.log(`No SB_KEY — skipping POST to ${table}`);
    return null;
  }
  const res = await fetch(`${SB_URL}/rest/v1/${table}`, {
    method: "POST",
    headers: {
      apikey: SB_KEY,
      Authorization: `Bearer ${SB_KEY}`,
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates,return=minimal",
    },
    body: JSON.stringify(rows),
  });
  const text = await res.text();
  return { status: res.status, body: text };
}

async function runMigration(file) {
  if (!fs.existsSync(file)) {
    console.error(`Migration not found: ${file}`);
    return false;
  }
  const sql = fs.readFileSync(file, "utf8");
  console.log(`\nApplying ${file} (${sql.length} chars)...`);
  const r = await mgmtQuery(sql);
  if (!r) return false;
  if (r.status === 200 || r.status === 201) {
    console.log(`OK: ${file}`);
    console.log(r.body.substring(0, 400));
    return true;
  } else {
    console.error(`FAIL (${r.status}): ${r.body.substring(0, 400)}`);
    return false;
  }
}

async function evaluate(county) {
  const r = await mgmtQuery(`SELECT public.pencil_dod_evaluate_county('${county}') AS result;`);
  if (!r || r.status !== 200) return null;
  try {
    const rows = JSON.parse(r.body);
    if (rows && rows[0]) {
      const result = rows[0].result;
      return typeof result === "string" ? JSON.parse(result) : result;
    }
  } catch (e) {
    console.error("Parse error:", e, r.body.substring(0, 200));
  }
  return null;
}

async function logAudit(county, letter, claim, survived, evidence) {
  const row = {
    dispatch_id: DISPATCH_ID,
    ultraloop_mode: "fallback",
    county_slug: county,
    letter,
    claim,
    survived,
    refuter_evidence: JSON.stringify(evidence),
    created_at: new Date().toISOString(),
  };
  const r = await sbPost("gold_standard_ultraloop_audit", [row]);
  if (r) console.log(`Audit ${county}/${letter} survived=${survived}: HTTP ${r.status}`);
}

async function main() {
  console.log("=== SHARD-7 RUN5361 MIGRATION APPLY ===");
  console.log(`Dispatch: ${DISPATCH_ID}`);
  console.log(`Time: ${new Date().toISOString()}`);

  // BEFORE state
  console.log("\n--- BEFORE ---");
  const hbBefore = await evaluate("hillsborough");
  const calBefore = await evaluate("calhoun");
  console.log("hillsborough BEFORE:", JSON.stringify(hbBefore));
  console.log("calhoun BEFORE:     ", JSON.stringify(calBefore));

  // Apply migrations
  const hbOk = await runMigration(
    "supabase/migrations/20260720_gold_standard_shard7_hillsborough_g_far_residual_fix.sql"
  );
  const calOk = await runMigration(
    "supabase/migrations/20260720_gold_standard_shard7_calhoun_i_verify_and_hillsborough_g_fix.sql"
  );

  // AFTER state
  console.log("\n--- AFTER ---");
  const hbAfter = await evaluate("hillsborough");
  const calAfter = await evaluate("calhoun");
  console.log("hillsborough AFTER:", JSON.stringify(hbAfter));
  console.log("calhoun AFTER:     ", JSON.stringify(calAfter));

  // Log audit
  if (hbAfter) {
    const g = hbAfter.G || {};
    await logAudit(
      "hillsborough", "G",
      `far_regulated=false applied to Tampa CN (1861) + Plant City C-1 (1772). G metric: ${g.metric}`,
      g.pass === true && (g.metric || 0) >= 95.0,
      { before: hbBefore?.G, after: g, honesty_marker: "INFERRED", migration_ok: hbOk }
    );
  }

  if (calAfter) {
    const i = calAfter.I || {};
    await logAudit(
      "calhoun", "I",
      `Property card defensive backfill + parcel_zones ensure. I metric: ${i.metric}`,
      i.pass === true && (i.metric || 0) >= 95.0,
      { before: calBefore?.I, after: i, honesty_marker: "VERIFIED (2026-07-19) + INFERRED (centroid)", migration_ok: calOk }
    );
  }

  // SQL VERIFICATION output
  console.log("\n### SQL VERIFICATION");
  console.log(`-- Timestamp: ${new Date().toISOString()}`);
  console.log(`-- Dispatch:  ${DISPATCH_ID}`);
  console.log(`-- Session:   SHARD-7 loop run 5361`);
  console.log();
  console.log("-- hillsborough BEFORE:", JSON.stringify(hbBefore));
  console.log("-- hillsborough AFTER: ", JSON.stringify(hbAfter));
  console.log();
  console.log("-- calhoun BEFORE:", JSON.stringify(calBefore));
  console.log("-- calhoun AFTER: ", JSON.stringify(calAfter));
  
  if (hbAfter) {
    const total = Object.values(hbAfter).filter(v => v && typeof v === "object" && "pass" in v).length;
    const passing = Object.values(hbAfter).filter(v => v && typeof v === "object" && v.pass).length;
    console.log(`\n-- hillsborough: ${passing}/${total}`);
  }
  if (calAfter) {
    const total = Object.values(calAfter).filter(v => v && typeof v === "object" && "pass" in v).length;
    const passing = Object.values(calAfter).filter(v => v && typeof v === "object" && v.pass).length;
    console.log(`-- calhoun:      ${passing}/${total}`);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
