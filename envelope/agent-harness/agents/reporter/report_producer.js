/**
 * ============================================================================
 * AGENT 7: REPORT PRODUCER 📄
 * ============================================================================
 * Mission: Generate professional CMA + HBU reports as downloadable documents.
 *          Per-parcel CMA one-pagers, batch summaries, auction-day briefs.
 * ============================================================================
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");

class ReportProducer {
  constructor(options = {}) {
    this.cmaPath = options.input || "./data/envelope-3d/cma_reports.jsonl";
    this.outputDir = options.output || "./reports/envelope-3d/cma/";
    this.limit = parseInt(options.limit || "25", 10);
    this.stats = { total: 0, reports: 0, errors: 0 };
  }

  scenarioBar(scenario, maxProfit) {
    const width = maxProfit > 0 ? Math.max(5, (Math.abs(scenario.estimated_profit) / maxProfit) * 100) : 5;
    const color = scenario.estimated_profit > 0 ? "#22c55e" : "#ef4444";
    const bidColor = scenario.max_bid > 0 ? "#F59E0B" : "#64748b";
    return `
    <div style="margin-bottom:12px;padding:12px;background:#0f172a;border-radius:8px;border-left:3px solid ${color}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <strong style="color:#e2e8f0;font-size:14px">${scenario.scenario_name}</strong>
        <span style="color:${color};font-weight:700;font-size:14px">$${scenario.estimated_profit?.toLocaleString()}</span>
      </div>
      <p style="color:#64748b;font-size:11px;margin-bottom:8px">${scenario.scenario_description || ""}</p>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;font-size:12px">
        <div><span style="color:#94a3b8">ARV</span><br><span style="color:#e2e8f0;font-weight:600">$${scenario.arv?.toLocaleString()}</span></div>
        <div><span style="color:#94a3b8">Dev Cost</span><br><span style="color:#e2e8f0;font-weight:600">$${scenario.total_development_cost?.toLocaleString()}</span></div>
        <div><span style="color:#94a3b8">Max Bid</span><br><span style="color:${bidColor};font-weight:700">$${scenario.max_bid?.toLocaleString()}</span></div>
        <div><span style="color:#94a3b8">ROI</span><br><span style="color:${color};font-weight:700">${scenario.roi_pct}%</span></div>
      </div>
      <div style="margin-top:6px;height:4px;background:#1e293b;border-radius:2px">
        <div style="height:100%;width:${width}%;background:${color};border-radius:2px"></div>
      </div>
    </div>`;
  }

  generateParcelReport(cma) {
    const maxProfit = Math.max(...(cma.scenarios || []).map(s => Math.abs(s.estimated_profit || 0)), 1);
    const quality = cma.area_quality || {};
    const rec = cma.scenarios?.[0] || {};
    const confidenceColor = cma.confidence_score >= 70 ? "#22c55e" : cma.confidence_score >= 50 ? "#F59E0B" : "#ef4444";

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>CMA: ${cma.parcel_id}</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:Inter,system-ui,sans-serif;background:#020617;color:#e2e8f0}
  .header{background:#1E3A5F;padding:20px 24px}
  .header h1{font-size:20px;font-weight:700}
  .badge{display:inline-block;padding:4px 12px;border-radius:12px;font-size:11px;font-weight:700}
  .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;padding:0 24px 16px}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px 24px}
  .card{background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:14px}
  .card h3{color:#94a3b8;font-size:10px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
  .card .val{font-size:24px;font-weight:700;color:#F59E0B}
  .section{padding:16px 24px}
  .section-title{color:#F59E0B;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px;border-bottom:1px solid #1e293b;padding-bottom:8px}
  .rec-box{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.3);border-radius:8px;padding:16px;margin:0 24px 16px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;color:#94a3b8;padding:6px 8px;border-bottom:1px solid #1e293b;font-size:11px}
  td{padding:6px 8px;border-bottom:1px solid #0f172a}
</style>
</head>
<body>
<div class="header">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <h1>${cma.parcel_id}</h1>
      <p style="color:#94a3b8;font-size:13px;margin-top:4px">${cma.situs || "Address pending"} · ${cma.zone_code} · ${quality.grade || "B"}-Grade</p>
    </div>
    <div style="text-align:right">
      <span class="badge" style="background:#F59E0B;color:#020617">HBU: ${cma.recommended_hbu_name}</span><br>
      <span class="badge" style="background:${confidenceColor};color:#020617;margin-top:4px">Confidence: ${cma.confidence_score}%</span>
    </div>
  </div>
</div>
<div class="rec-box">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h3 style="color:#F59E0B;font-size:14px;font-weight:700;margin-bottom:4px">RECOMMENDED: ${rec.scenario_name || "N/A"}</h3>
      <p style="color:#94a3b8;font-size:12px">${rec.scenario_description || ""}</p>
    </div>
    <div style="text-align:right">
      <p style="color:#F59E0B;font-size:28px;font-weight:700">$${rec.max_bid?.toLocaleString() || "0"}</p>
      <p style="color:#94a3b8;font-size:11px">MAX BID</p>
    </div>
  </div>
</div>
<div class="grid3">
  <div class="card"><h3>After Repair Value</h3><div class="val">$${cma.estimated_arv?.toLocaleString() || "0"}</div></div>
  <div class="card"><h3>Estimated Profit</h3><div class="val" style="color:${(cma.estimated_profit||0)>0?"#22c55e":"#ef4444"}">$${cma.estimated_profit?.toLocaleString()||"0"}</div></div>
  <div class="card"><h3>ROI</h3><div class="val" style="color:${(rec.roi_pct||0)>20?"#22c55e":"#F59E0B"}">${rec.roi_pct||0}%</div></div>
</div>
<div class="grid2">
  <div class="card"><h3>Property Details</h3>
    <table>
      <tr><td style="color:#94a3b8">Lot Area</td><td style="text-align:right">${cma.lot_area_sf?.toLocaleString()} sf</td></tr>
      <tr><td style="color:#94a3b8">Zone Code</td><td style="text-align:right">${cma.zone_code}</td></tr>
      <tr><td style="color:#94a3b8">Municipality</td><td style="text-align:right">${cma.source_municipality}</td></tr>
      <tr><td style="color:#94a3b8">Area Quality</td><td style="text-align:right">${quality.grade}-Grade${quality.zip?" ("+quality.zip+")":""}</td></tr>
    </table>
  </div>
  <div class="card"><h3>Building Envelope</h3>
    <table>
      <tr><td style="color:#94a3b8">Max GFA</td><td style="text-align:right;color:#F59E0B;font-weight:600">${cma.buildable_gfa_sf?.toLocaleString()} sf</td></tr>
      <tr><td style="color:#94a3b8">Effective Floors</td><td style="text-align:right">${cma.effective_floors}</td></tr>
      <tr><td style="color:#94a3b8">Build Size (rec)</td><td style="text-align:right">${rec.build_size_sf?.toLocaleString()||"N/A"} sf</td></tr>
      <tr><td style="color:#94a3b8">Comps Available</td><td style="text-align:right">${cma.comp_count}</td></tr>
    </table>
  </div>
</div>
<div class="section">
  <div class="section-title">All HBU Scenarios Ranked by Profit Potential</div>
  ${(cma.scenarios||[]).map(s => this.scenarioBar(s, maxProfit)).join("")}
</div>
<div class="section">
  <div class="section-title">Max Bid Formula</div>
  <div class="card" style="font-family:monospace;font-size:13px;color:#94a3b8">
    Max Bid = (ARV × 70%) − Dev Cost − $10K − MIN($25K, 15% × ARV)<br>
    <span style="color:#F59E0B">= ($${rec.arv?.toLocaleString()} × 0.70) − $${rec.total_development_cost?.toLocaleString()} − $10,000 − $${Math.min(25000,Math.round((rec.arv||0)*0.15)).toLocaleString()}</span><br>
    <span style="color:#22c55e;font-weight:700">= $${rec.max_bid?.toLocaleString()}</span>
  </div>
</div>
<div style="text-align:center;padding:16px;color:#475569;font-size:11px;border-top:1px solid #1e293b">
  BidDeed.AI × ZoneWise.AI · CMA · ${new Date().toISOString().split("T")[0]} · Not financial advice.
</div>
</body></html>`;
  }

  generateAuctionBrief(parcels) {
    const rows = parcels.map((p, i) => `
      <tr style="background:${i%2===0?"#0f172a":"#020617"}">
        <td style="padding:8px;font-weight:600">${p.parcel_id}</td>
        <td style="padding:8px;font-size:12px">${p.situs||""}</td>
        <td style="padding:8px">${p.zone_code}</td>
        <td style="padding:8px;color:#F59E0B;font-weight:700">${p.recommended_hbu_name}</td>
        <td style="padding:8px;text-align:right">$${p.estimated_arv?.toLocaleString()}</td>
        <td style="padding:8px;text-align:right;color:#22c55e;font-weight:700">$${p.max_bid_recommended?.toLocaleString()}</td>
        <td style="padding:8px;text-align:center">${p.confidence_score}%</td>
      </tr>`).join("");

    return `<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Auction Day Brief</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:Inter,system-ui,sans-serif;background:#020617;color:#e2e8f0;padding:24px}
  h1{color:#F59E0B;font-size:22px;margin-bottom:4px}
  table{width:100%;border-collapse:collapse;margin-top:16px}
  th{text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px;border-bottom:2px solid #1E3A5F}
</style></head>
<body>
  <h1>🏛️ Auction Day Brief</h1>
  <p style="color:#94a3b8;font-size:13px">${new Date().toLocaleDateString()} · ${parcels.length} properties · BidDeed.AI × ZoneWise.AI</p>
  <table>
    <tr><th>Parcel</th><th>Address</th><th>Zone</th><th>HBU</th><th style="text-align:right">ARV</th><th style="text-align:right">Max Bid</th><th style="text-align:center">Conf</th></tr>
    ${rows}
  </table>
  <p style="margin-top:16px;color:#475569;font-size:11px">Max Bid = (ARV×70%)−DevCost−$10K−MIN($25K,15%×ARV) · Not financial advice.</p>
</body></html>`;
  }

  async run() {
    console.log("📄 REPORT PRODUCER — Mission Start");
    if (!fs.existsSync(this.cmaPath)) { console.log(`  ⚠️  No CMA data: ${this.cmaPath}`); return this.stats; }

    const allCMAs = [];
    const rl = readline.createInterface({ input: fs.createReadStream(this.cmaPath), crlfDelay: Infinity });
    for await (const line of rl) {
      if (!line.trim()) continue;
      try { allCMAs.push(JSON.parse(line)); this.stats.total++; } catch (err) { this.stats.errors++; }
    }

    allCMAs.sort((a, b) => (b.estimated_profit || 0) - (a.estimated_profit || 0));
    const top = allCMAs.slice(0, this.limit);

    if (!fs.existsSync(this.outputDir)) fs.mkdirSync(this.outputDir, { recursive: true });

    for (const cma of top) {
      try {
        fs.writeFileSync(path.join(this.outputDir, `${cma.parcel_id}_cma.html`), this.generateParcelReport(cma));
        this.stats.reports++;
        console.log(`  ✅ ${cma.parcel_id} | ${cma.recommended_hbu_name} | ARV: $${cma.estimated_arv?.toLocaleString()} | Bid: $${cma.max_bid_recommended?.toLocaleString()}`);
      } catch (err) { this.stats.errors++; }
    }

    const briefPath = path.join(this.outputDir, `auction_brief_${new Date().toISOString().split("T")[0]}.html`);
    fs.writeFileSync(briefPath, this.generateAuctionBrief(top));
    console.log(`  📋 Auction brief: ${briefPath}`);

    console.log(`\n📄 REPORT PRODUCER — Mission Complete`);
    console.log(`   Total CMA records: ${this.stats.total}`);
    console.log(`   Reports generated: ${this.stats.reports}`);
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
  new ReportProducer(options).run().catch(console.error);
}

module.exports = { ReportProducer };
