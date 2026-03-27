/**
 * persist.js — Supabase persistence via curl (DNS workaround)
 */

const { execSync } = require('child_process');

class DiscoveryStore {
  constructor(supabaseUrl, supabaseKey) {
    this.url = supabaseUrl;
    this.key = supabaseKey;
  }

  _rest(method, path, body = null) {
    let cmd = `curl -s -X ${method} '${this.url}/rest/v1/${path}' -H 'apikey: ${this.key}' -H 'Authorization: Bearer ${this.key}' -H 'Content-Type: application/json' -H 'Prefer: return=minimal'`;
    if (body) {
      const jsonStr = JSON.stringify(body).replace(/'/g, "'\\''");
      cmd += ` -d '${jsonStr}'`;
    }
    if (method === 'POST') cmd += ` -H 'Prefer: resolution=merge-duplicates,return=minimal'`;
    const raw = execSync(cmd, { maxBuffer: 5 * 1024 * 1024, timeout: 15000 }).toString().trim();
    if (!raw) return { data: null, error: null };
    try { 
      const d = JSON.parse(raw);
      if (d.code || d.message) return { data: null, error: d };
      return { data: d, error: null };
    } catch { return { data: raw, error: null }; }
  }

  async saveResults(results) {
    if (!results.length) return { inserted: 0, errors: [] };

    const rows = results.map(r => ({
      mode: r.mode,
      county: r.county,
      state: r.state || 'FL',
      query: r.query,
      url: r.url,
      title: r.title || '',
      classification: r.classification,
      confidence: r.confidence,
      highlight_text: (r.highlights || []).slice(0, 3).join(' | ').substring(0, 500),
      exa_score: r.exa_score,
      firecrawl_status: 'pending',
      cost_dollars: r.cost || 0,
    }));

    let inserted = 0;
    const errors = [];
    
    // Insert one at a time to handle conflicts gracefully
    for (const row of rows) {
      const { error } = this._rest('POST', 'discovery_results', row);
      if (error) {
        if (error.code === '23505') { /* duplicate, skip */ }
        else errors.push(error.message || JSON.stringify(error));
      } else {
        inserted++;
      }
    }

    return { inserted, errors };
  }

  async updateConquestStatus(county, mode) { /* handled by CC session */ }
  async getPendingCounties() { return []; }
}

module.exports = { DiscoveryStore };
