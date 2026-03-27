const { Client } = require("pg");
const fs = require("fs");

const hosts = [
  "aws-0-us-west-2.pooler.supabase.com",
  "aws-0-us-east-1.pooler.supabase.com",
  "aws-1-us-east-1.pooler.supabase.com",
  "aws-1-us-west-2.pooler.supabase.com",
];
const ports = [5432, 6543];
const user = "postgres.mocerqjnksmhcjzxrewo";

async function main() {
  const pw = process.env.SUPABASE_DB_PASSWORD;
  const file = process.argv[2];
  if (!pw) { console.error("SUPABASE_DB_PASSWORD not set"); process.exit(1); }
  if (!file) { console.error("Usage: node run_migration.js <file.sql>"); process.exit(1); }
  if (!fs.existsSync(file)) { console.error("File not found: " + file); process.exit(1); }

  let connected = false, client;
  for (const host of hosts) {
    for (const port of ports) {
      client = new Client({ host, port, user, password: pw, database: "postgres", ssl: { rejectUnauthorized: false }, connectionTimeoutMillis: 8000 });
      try {
        await client.connect();
        console.log("Connected: " + host + ":" + port);
        connected = true; break;
      } catch (err) {
        if (err.message.includes("password")) console.log("AUTH FAIL " + host + ":" + port);
        try { await client.end(); } catch (e) {}
      }
    }
    if (connected) break;
  }
  if (!connected) { console.error("All connections failed"); process.exit(1); }

  const sql = fs.readFileSync(file, "utf8");
  
  // Split on semicolons but handle $$ blocks
  const stmts = [];
  let current = "";
  let inDollar = false;
  for (const line of sql.split("\n")) {
    const trimmed = line.trim();
    if (trimmed.startsWith("--") && !inDollar) continue;
    
    if (trimmed.includes("$$") && !inDollar) inDollar = true;
    else if (trimmed.includes("$$") && inDollar) inDollar = false;
    
    current += line + "\n";
    
    if (trimmed.endsWith(";") && !inDollar) {
      if (current.trim().length > 5) stmts.push(current.trim());
      current = "";
    }
  }
  if (current.trim().length > 5) stmts.push(current.trim());

  console.log("Running " + stmts.length + " statements from " + file);
  let ok = 0, skip = 0, fail = 0;
  
  for (const stmt of stmts) {
    const preview = stmt.replace(/\n/g, " ").substring(0, 80);
    try {
      await client.query(stmt);
      console.log("  OK: " + preview);
      ok++;
    } catch (err) {
      const msg = err.message;
      if (msg.includes("already exists") || msg.includes("duplicate")) {
        console.log("  SKIP: " + preview + " (exists)");
        skip++;
      } else {
        console.log("  FAIL: " + preview);
        console.log("    → " + msg.substring(0, 120));
        fail++;
      }
    }
  }

  console.log("\nDone: " + ok + " ok, " + skip + " skipped, " + fail + " failed");
  await client.end();
  process.exit(fail > 0 ? 1 : 0);
}
main().catch(e => { console.error(e); process.exit(1); });
