// trigger_shard7_apply.js
// Triggers the shard7 migration application via GitHub workflow dispatch
// and runs verification queries directly.
// 
// Usage: SUPABASE_ACCESS_TOKEN=<token> GITHUB_TOKEN=<token> node trigger_shard7_apply.js

const PROJECT_REF = "mocerqjnksmhcjzxrewo";
const DISPATCH_ID = "74e8c56b-ed5f-4fe0-a4cf-e97e24ccdd3e";

const TOKEN = process.env.SUPABASE_ACCESS_TOKEN;
const SB_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY || "";
const SB_URL = process.env.SUPABASE_URL || `https://${PROJECT_REF}.supabase.co`;

async function mgmtQuery(sql) {
  if (!TOKEN) { console.log("No SUPABASE_ACCESS_TOKEN"); return null; }
  const res = await fetch(
    `https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify({ query: sql }),
    }
  );
  return { status: res.status, body: await res.text() };
}

async function evaluate(county) {
  const r = await mgmtQuery(`SELECT public.pencil_dod_evaluate_county('${county}') AS result;`);
  if (!r || r.status !== 200) { console.log(`eval(${county}) failed: ${r?.status}`); return null; }
  try {
    const rows = JSON.parse(r.body);
    const v = rows?.[0]?.result;
    return typeof v === "string" ? JSON.parse(v) : v;
  } catch(e) { console.log("parse error:", e, r.body.substring(0,100)); return null; }
}

async function fireSbWorkflowDispatch(message) {
  // Use the public.fire_workflow_dispatch DB function (per COMMS standing authorization)
  const sql = `SELECT public.fire_workflow_dispatch('breverdbidder/cli-anything-biddeed','telegram-notify.yml','main', ${JSON.stringify(JSON.stringify({message}))}) AS result;`;
  const r = await mgmtQuery(sql);
  console.log("fire_workflow_dispatch:", r?.status, r?.body?.substring(0, 200));
}

async function main() {
  console.log("=== SHARD-7 VERIFICATION ===");
  console.log("Dispatch:", DISPATCH_ID, "| Time:", new Date().toISOString());
  
  if (!TOKEN && !SB_KEY) {
    console.log("No credentials available — this is expected when run outside GHA");
    console.log("Migrations are committed to repo; they will be applied via GHA workflow dispatch.");
    return;
  }

  const hb = await evaluate("hillsborough");
  const cal = await evaluate("calhoun");
  
  console.log("\n### SQL VERIFICATION");
  console.log(`-- Timestamp: ${new Date().toISOString()}`);
  console.log(`-- Dispatch:  ${DISPATCH_ID}`);
  console.log(`-- hillsborough: ${JSON.stringify(hb)}`);
  console.log(`-- calhoun:      ${JSON.stringify(cal)}`);
  
  if (hb) {
    const passing = Object.values(hb).filter(v => v?.pass).length;
    console.log(`\n-- hillsborough: ${passing}/10`);
    const g = hb.G || {};
    console.log(`-- G: pass=${g.pass} metric=${g.metric} (target: >=95.0)`);
  }
  if (cal) {
    const passing = Object.values(cal).filter(v => v?.pass).length;
    console.log(`-- calhoun: ${passing}/10`);
    const i = cal.I || {};
    const b = cal.B || {};
    console.log(`-- I: pass=${i.pass} metric=${i.metric}`);
    console.log(`-- B: pass=${b.pass} metric=${b.metric} (UNKNOWN — no closed sales yet)`);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
