/**
 * ============================================================================
 * LOADER: Supabase Batch Upsert to envelope_cache
 * ============================================================================
 */

const fs = require("fs");
const readline = require("readline");

class SupabaseLoader {
  constructor(options = {}) {
    this.inputPath = options.input || "./data/envelope-3d/envelopes_computed.jsonl";
    this.table = options.table || "envelope_cache";
    this.supabaseUrl = options["supabase-url"] || process.env.SUPABASE_URL;
    this.supabaseKey = options["supabase-key"] || process.env.SUPABASE_SERVICE_ROLE_KEY;
    this.batchSize = 500;
    this.stats = { total: 0, upserted: 0, errors: 0 };
  }

  async upsertBatch(records) {
    try {
      const response = await fetch(
        `${this.supabaseUrl}/rest/v1/${this.table}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            apikey: this.supabaseKey,
            Authorization: `Bearer ${this.supabaseKey}`,
            Prefer: "resolution=merge-duplicates",
          },
          body: JSON.stringify(records),
        }
      );

      if (!response.ok) {
        const err = await response.text();
        throw new Error(`HTTP ${response.status}: ${err}`);
      }

      this.stats.upserted += records.length;
    } catch (err) {
      console.error(`  ❌ Batch upsert failed: ${err.message}`);
      this.stats.errors += records.length;
    }
  }

  mapRecord(raw) {
    return {
      parcel_id: raw.parcel_id,
      zone_code: raw.zone_code,
      front_setback_ft: raw.front_setback_ft,
      side_setback_ft: raw.side_setback_ft,
      rear_setback_ft: raw.rear_setback_ft,
      max_height_ft: raw.max_height_ft,
      max_lot_coverage: raw.max_lot_coverage,
      far: raw.far,
      lot_width_ft: raw.lot_width_ft,
      lot_depth_ft: raw.lot_depth_ft,
      buildable_gfa_sf: raw.buildable_gfa_sf,
      envelope_height_ft: raw.effective_height_ft,
      effective_floors: raw.effective_floors,
      computed_at: raw.computed_at || new Date().toISOString(),
      source_municipality: raw.source_municipality,
    };
  }

  async run() {
    console.log("💾 SUPABASE LOADER — Mission Start");
    console.log(`   Table: ${this.table}`);
    console.log(`   URL: ${this.supabaseUrl}`);

    if (!fs.existsSync(this.inputPath)) {
      console.log(`  ⚠️  No input: ${this.inputPath}`);
      return this.stats;
    }

    const rl = readline.createInterface({
      input: fs.createReadStream(this.inputPath),
      crlfDelay: Infinity,
    });

    let batch = [];

    for await (const line of rl) {
      if (!line.trim()) continue;
      try {
        const record = JSON.parse(line);
        batch.push(this.mapRecord(record));
        this.stats.total++;

        if (batch.length >= this.batchSize) {
          await this.upsertBatch(batch);
          process.stdout.write(`\r   Loaded: ${this.stats.upserted} / ${this.stats.total}`);
          batch = [];
          await new Promise(r => setTimeout(r, 100));
        }
      } catch (err) { /* skip */ }
    }

    if (batch.length > 0) {
      await this.upsertBatch(batch);
    }

    console.log(`\n\n💾 SUPABASE LOADER — Mission Complete`);
    console.log(`   Total:    ${this.stats.total}`);
    console.log(`   Upserted: ${this.stats.upserted}`);
    console.log(`   Errors:   ${this.stats.errors}`);

    return this.stats;
  }
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const options = {};
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i]?.replace(/^--/, "");
    options[key] = args[i + 1];
  }
  new SupabaseLoader(options).run().catch(console.error);
}

module.exports = { SupabaseLoader };
