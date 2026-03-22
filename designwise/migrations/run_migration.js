const { Client } = require("pg");
const fs = require("fs");

async function main() {
  // Try all possible pooler hostnames - project may be on aws-0 OR aws-1
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
  const pw = process.env.SUPABASE_DB_PASSWORD;

  console.log("Trying " + (hosts.length * ports.length) + " connection combos...");

  let connected = false;
  let client;

  for (const host of hosts) {
    for (const port of ports) {
      const label = host.split(".")[0] + ":" + port;
      client = new Client({
        host: host,
        port: port,
        user: user,
        password: pw,
        database: "postgres",
        ssl: { rejectUnauthorized: false },
        connectionTimeoutMillis: 5000,
      });
      try {
        await client.connect();
        console.log("CONNECTED via " + label + " (" + host + ")");
        connected = true;
        break;
      } catch (err) {
        var msg = err.message.slice(0, 60);
        if (msg.includes("password")) {
          console.log("AUTH FAIL " + label + " (host correct, password wrong)");
        } else if (msg.includes("Tenant")) {
          // Expected for wrong host, skip silently
        } else {
          console.log("FAIL " + label + ": " + msg);
        }
        try { await client.end(); } catch (e) {}
      }
    }
    if (connected) break;
  }

  if (!connected) {
    console.error("All " + (hosts.length * ports.length) + " combos failed. Check pooler hostname in Supabase dashboard.");
    process.exit(1);
  }

  var sql = fs.readFileSync("designwise/migrations/001_designwise_tables.sql", "utf8");
  var stmts = sql.split(";").filter(function (s) { return s.trim().length > 10; });
  console.log("Running " + stmts.length + " statements...");

  var ok = 0, skip = 0, fail = 0;
  for (var i = 0; i < stmts.length; i++) {
    try {
      await client.query(stmts[i] + ";");
      var m = stmts[i].match(/public\.(\w+)/i);
      if (m) console.log("  OK: " + m[1]);
      ok++;
    } catch (err) {
      if (err.message.includes("already exists")) { skip++; }
      else { console.error("  ERR: " + err.message.slice(0, 120)); fail++; }
    }
  }
  console.log("Done: " + ok + " ok, " + skip + " exist, " + fail + " fail");
  await client.end();
  if (fail > 0) process.exit(1);
}
main();
