import fs from "fs";

// Executes SQL against the live Supabase project via the Management API
// (POST /v1/projects/{ref}/database/query, authed with SUPABASE_ACCESS_TOKEN).
//
// Replaces the old direct-postgres approach (pg client against the pooler
// hosts with SUPABASE_DB_PASSWORD): that password is stale/invalid as of
// 2026-07-03 (confirmed AUTH FAIL against every pooler host/port combo) and
// the "pg" npm package isn't installed at repo root, so the old path was
// dead for every session hitting it. The Management API needs no DB
// password and no extra dependency (fetch is a Node 18+ builtin).
const PROJECT_REF = "mocerqjnksmhcjzxrewo";

async function main() {
  const token = process.env.SUPABASE_ACCESS_TOKEN;
  const file = process.argv[2];
  if (!token) { console.error("SUPABASE_ACCESS_TOKEN not set"); process.exit(1); }
  if (!file) { console.error("Usage: node run_migration.js <file.sql>"); process.exit(1); }
  if (!fs.existsSync(file)) { console.error("File not found: " + file); process.exit(1); }

  const sql = fs.readFileSync(file, "utf8");
  console.log("Running migration file: " + file + " (" + sql.length + " chars)");

  const res = await fetch(
    `https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ query: sql }),
    }
  );

  const text = await res.text();
  if (res.status === 201 || res.status === 200) {
    console.log("OK — result:");
    console.log(text);
    process.exit(0);
  } else {
    console.error("FAIL (status " + res.status + "):");
    console.error(text);
    process.exit(1);
  }
}
main().catch(e => { console.error(e); process.exit(1); });
