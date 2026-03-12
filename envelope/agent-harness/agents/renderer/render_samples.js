/**
 * ============================================================================
 * AGENT 4: VISUAL RENDERER 🎨
 * ============================================================================
 * Mission: Generate 3D envelope render data and sample HTML reports.
 *          Produces static JSON configs that feed the shared React component.
 * 
 * Output: Per-parcel render configs with pre-computed Three.js scene params
 *         for instant loading on BidDeed.AI and ZoneWise.AI frontends.
 * ============================================================================
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");

class VisualRenderer {
  constructor(options = {}) {
    this.inputPath = options.input || "./data/envelope-3d/envelopes_computed.jsonl";
    this.outputDir = options.output || "./reports/envelope-3d/renders/";
    this.sampleCount = parseInt(options.count || "5", 10);
    this.stats = { total: 0, rendered: 0, topHBU: [] };
  }

  /**
   * Convert envelope data to Three.js scene configuration
   */
  generateSceneConfig(envelope) {
    const lotW = envelope.lot_width_ft;
    const lotD = envelope.lot_depth_ft;
    const envW = envelope.buildable_width_ft;
    const envD = envelope.buildable_depth_ft;
    const envH = envelope.effective_height_ft;
    const hw = lotW / 2;
    const hd = lotD / 2;

    return {
      parcel_id: envelope.parcel_id,
      zone_code: envelope.zone_code,
      situs: envelope.situs,
      hbu_score: envelope.hbu_score,
      
      // Camera defaults
      camera: {
        theta: Math.PI / 4,
        phi: Math.PI / 4,
        radius: Math.max(lotW, lotD, envH) * 1.8,
        lookAt: { x: 0, y: envH / 3, z: 0 },
      },
      
      // Lot plane
      lot: {
        width: lotW,
        depth: lotD,
        area_sf: envelope.lot_area_sf,
        color: "#2a4a2a",
        border_color: "#00ff00",
      },
      
      // Setback zones
      setbacks: {
        front: envelope.front_setback_ft,
        side: envelope.side_setback_ft,
        rear: envelope.rear_setback_ft,
        color: "#ff4400",
        opacity: 0.08,
        dash_color: "#ff6600",
      },
      
      // Building envelope
      envelope: {
        width: envW,
        depth: envD,
        height: envH,
        position: {
          x: 0,
          y: envH / 2,
          z: (-hd + envelope.front_setback_ft + hd - envelope.rear_setback_ft) / 2,
        },
        color: "#f59e0b",
        opacity: 0.2,
        wireframe_opacity: 0.6,
      },
      
      // Floor plates
      floors: Array.from({ length: Math.max(0, envelope.effective_floors - 1) }, (_, i) => ({
        y: (i + 1) * 10,
        width: envW - 1,
        depth: envD - 1,
        opacity: 0.05,
      })),
      
      // Height limit marker
      height_limit: {
        height: envelope.max_height_ft,
        color: "#ff0000",
      },
      
      // Metrics overlay
      metrics: {
        buildable_gfa_sf: envelope.buildable_gfa_sf,
        effective_floors: envelope.effective_floors,
        actual_far: envelope.actual_far,
        actual_coverage_pct: envelope.actual_coverage_pct,
        utilization_rate_pct: envelope.utilization_rate_pct,
        envelope_volume_cf: envelope.envelope_volume_cf,
      },
    };
  }

  /**
   * Generate static HTML report for a single parcel envelope
   */
  generateHTMLReport(sceneConfig) {
    const { parcel_id, zone_code, situs, hbu_score, metrics, lot, envelope, setbacks, floors } = sceneConfig;
    
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Envelope: ${parcel_id}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: Inter, system-ui, sans-serif; background: #020617; color: #e2e8f0; }
  .header { background: #1E3A5F; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }
  .header h1 { font-size: 18px; font-weight: 600; }
  .header .badge { background: #F59E0B; color: #020617; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 700; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; padding: 24px; }
  .card { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; }
  .card h3 { color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
  .card .value { font-size: 28px; font-weight: 700; color: #F59E0B; }
  .card .unit { font-size: 14px; color: #64748b; margin-left: 4px; }
  .details { padding: 0 24px 24px; }
  .details table { width: 100%; border-collapse: collapse; }
  .details th { text-align: left; color: #94a3b8; font-size: 12px; padding: 8px; border-bottom: 1px solid #1e293b; }
  .details td { padding: 8px; font-size: 14px; border-bottom: 1px solid #0f172a; }
  .hbu-bar { height: 8px; background: #1e293b; border-radius: 4px; margin-top: 8px; overflow: hidden; }
  .hbu-fill { height: 100%; background: linear-gradient(90deg, #ef4444, #F59E0B, #22c55e); border-radius: 4px; }
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>${parcel_id}</h1>
      <p style="color:#94a3b8;font-size:13px;margin-top:2px">${situs || 'Address pending'} · ${zone_code}</p>
    </div>
    <div class="badge">HBU Score: ${hbu_score}/100</div>
  </div>
  
  <div class="grid">
    <div class="card">
      <h3>Buildable GFA</h3>
      <div class="value">${metrics.buildable_gfa_sf?.toLocaleString()}<span class="unit">sf</span></div>
    </div>
    <div class="card">
      <h3>Effective Floors</h3>
      <div class="value">${metrics.effective_floors}<span class="unit">floors</span></div>
    </div>
    <div class="card">
      <h3>Actual FAR</h3>
      <div class="value">${metrics.actual_far}<span class="unit">x</span></div>
    </div>
  </div>
  
  <div class="details">
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Lot Dimensions</td><td>${lot.width}' × ${lot.depth}' (${lot.area_sf?.toLocaleString()} sf)</td></tr>
      <tr><td>Setbacks (F/S/R)</td><td>${setbacks.front}' / ${setbacks.side}' / ${setbacks.rear}'</td></tr>
      <tr><td>Envelope Dimensions</td><td>${envelope.width}' × ${envelope.depth}' × ${envelope.height}'</td></tr>
      <tr><td>Lot Coverage</td><td>${metrics.actual_coverage_pct}%</td></tr>
      <tr><td>Utilization Rate</td><td>${metrics.utilization_rate_pct}%</td></tr>
      <tr><td>Envelope Volume</td><td>${metrics.envelope_volume_cf?.toLocaleString()} cf</td></tr>
    </table>
    
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-top:16px">Development Potential</h3>
    <div class="hbu-bar"><div class="hbu-fill" style="width:${hbu_score}%"></div></div>
    <p style="color:#64748b;font-size:12px;margin-top:4px">Higher score = more development potential relative to lot size</p>
  </div>
  
  <div style="padding:24px;color:#475569;font-size:11px;text-align:center;border-top:1px solid #1e293b">
    ZoneWise.AI × BidDeed.AI · Envelope Analysis · Generated ${new Date().toISOString().split('T')[0]}
  </div>
</body>
</html>`;
  }

  /**
   * Run the renderer
   */
  async run() {
    console.log("🎨 VISUAL RENDERER — Mission Start");
    
    if (!fs.existsSync(this.inputPath)) {
      console.log(`  ⚠️  No input file: ${this.inputPath}`);
      return this.stats;
    }

    // Read all envelopes and sort by HBU score for top picks
    const envelopes = [];
    const rl = readline.createInterface({
      input: fs.createReadStream(this.inputPath),
      crlfDelay: Infinity,
    });

    for await (const line of rl) {
      if (!line.trim()) continue;
      try {
        const record = JSON.parse(line);
        envelopes.push(record);
        this.stats.total++;
      } catch (err) { /* skip bad lines */ }
    }

    // Sort by HBU score descending, pick top N
    envelopes.sort((a, b) => (b.hbu_score || 0) - (a.hbu_score || 0));
    const samples = envelopes.slice(0, this.sampleCount);

    // Generate renders
    if (!fs.existsSync(this.outputDir)) fs.mkdirSync(this.outputDir, { recursive: true });

    for (const envelope of samples) {
      const sceneConfig = this.generateSceneConfig(envelope);
      
      // Write scene config JSON
      const jsonPath = path.join(this.outputDir, `${envelope.parcel_id}_scene.json`);
      fs.writeFileSync(jsonPath, JSON.stringify(sceneConfig, null, 2));
      
      // Write HTML report
      const htmlPath = path.join(this.outputDir, `${envelope.parcel_id}_report.html`);
      fs.writeFileSync(htmlPath, this.generateHTMLReport(sceneConfig));
      
      this.stats.rendered++;
      console.log(`  ✅ ${envelope.parcel_id} — HBU: ${envelope.hbu_score} | GFA: ${envelope.buildable_gfa_sf?.toLocaleString()} sf | ${envelope.zone_code}`);
    }

    this.stats.topHBU = samples.map(s => ({
      parcel_id: s.parcel_id,
      hbu_score: s.hbu_score,
      zone_code: s.zone_code,
      gfa: s.buildable_gfa_sf,
    }));

    console.log(`\n🎨 VISUAL RENDERER — Mission Complete`);
    console.log(`   Total envelopes:  ${this.stats.total}`);
    console.log(`   Renders generated: ${this.stats.rendered}`);
    console.log(`   Output:           ${this.outputDir}`);
    
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
  
  const renderer = new VisualRenderer(options);
  renderer.run().catch(console.error);
}

module.exports = { VisualRenderer };
