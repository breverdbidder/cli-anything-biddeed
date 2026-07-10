const { Client } = require("pg");
const fs = require("fs");

const hosts = [
  "aws-0-us-east-1.pooler.supabase.com",
  "aws-1-us-east-1.pooler.supabase.com",
  "aws-0-us-east-2.pooler.supabase.com",
  "aws-1-us-east-2.pooler.supabase.com",
  "aws-0-us-west-1.pooler.supabase.com",
  "aws-0-us-west-2.pooler.supabase.com",
];
const ports = [5432, 6543];
const user = "postgres.mocerqjnksmhcjzxrewo";

async function main() {
  const pw = process.env.SUPABASE_DB_PASSWORD;
  if (!pw) { console.error("SUPABASE_DB_PASSWORD not set"); process.exit(1); }

  console.log("Trying " + (hosts.length * ports.length) + " connection combos...");

  let connected = false;
  let client;

  for (const host of hosts) {
    for (const port of ports) {
      const label = host.split(".")[0] + ":" + port;
      client = new Client({
        host, port, user, password: pw, database: "postgres",
        ssl: { rejectUnauthorized: false },
        connectionTimeoutMillis: 5000,
      });
      try {
        await client.connect();
        console.log("✅ CONNECTED via " + label);
        connected = true;
        break;
      } catch (err) {
        var msg = err.message.slice(0, 60);
        if (msg.includes("password")) {
          console.log("AUTH FAIL " + label + " (host correct, password wrong)");
        } else if (msg.includes("Tenant")) {
          // Expected for wrong host
        } else {
          console.log("FAIL " + label + ": " + msg);
        }
        try { await client.end(); } catch (e) {}
      }
    }
    if (connected) break;
  }

  if (!connected) {
    console.error("❌ All combos failed. Check SUPABASE_DB_PASSWORD.");
    process.exit(1);
  }

  // Read and execute migration
  const sql = fs.readFileSync("migrations/20260327_discovery_results.sql", "utf8");
  const stmts = sql.split(";").filter(s => s.trim().length > 10);

  console.log("Running " + stmts.length + " statements...");
  for (const stmt of stmts) {
    const preview = stmt.trim().substring(0, 70).replace(/\n/g, " ");
    try {
      await client.query(stmt);
      console.log("  ✅ " + preview);
    } catch (err) {
      if (err.message.includes("already exists")) {
        console.log("  ⏭️  " + preview + " (already exists)");
      } else {
        console.log("  ❌ " + preview + " → " + err.message.slice(0, 80));
      }
    }
  }

  // Verify
  const res = await client.query("SELECT COUNT(*) as cnt FROM information_schema.tables WHERE table_name = 'discovery_results'");
  console.log(res.rows[0].cnt > 0 ? "\n✅ discovery_results table VERIFIED" : "\n❌ Table not found");

  await client.end();
}

main().catch(e => { console.error(e); process.exit(1); });
