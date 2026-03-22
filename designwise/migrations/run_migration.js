const { Client } = require("pg");
const fs = require("fs");

async function main() {
  const configs = [
    { label: "Session-5432", host: "aws-0-us-east-1.pooler.supabase.com", port: 5432, user: "postgres.mocerqjnksmhcjzxrewo" },
    { label: "Transaction-6543", host: "aws-0-us-east-1.pooler.supabase.com", port: 6543, user: "postgres.mocerqjnksmhcjzxrewo" },
  ];

  let connected = false;
  let client;

  for (const cfg of configs) {
    client = new Client({
      host: cfg.host,
      port: cfg.port,
      user: cfg.user,
      password: process.env.SUPABASE_DB_PASSWORD,
      database: "postgres",
      ssl: { rejectUnauthorized: false },
      connectionTimeoutMillis: 10000,
    });
    try {
      await client.connect();
      console.log("Connected via " + cfg.label);
      connected = true;
      break;
    } catch (err) {
      console.log("SKIP " + cfg.label + ": " + err.message.slice(0, 100));
      try { await client.end(); } catch (e) {}
    }
  }

  if (!connected) {
    console.error("All connection methods failed");
    process.exit(1);
  }

  const sql = fs.readFileSync("designwise/migrations/001_designwise_tables.sql", "utf8");
  const stmts = sql.split(";").filter(function (s) { return s.trim().length > 10; });
  console.log("Running " + stmts.length + " statements...");

  var ok = 0, skip = 0, fail = 0;
  for (var i = 0; i < stmts.length; i++) {
    try {
      await client.query(stmts[i] + ";");
      var m = stmts[i].match(/public\.(\w+)/i);
      if (m) console.log("  OK: " + m[1]);
      ok++;
    } catch (err) {
      if (err.message.includes("already exists")) {
        skip++;
      } else {
        console.error("  ERR: " + err.message.slice(0, 120));
        fail++;
      }
    }
  }

  console.log("Result: " + ok + " ok, " + skip + " exist, " + fail + " fail");
  await client.end();
  if (fail > 0) process.exit(1);
}

main();
