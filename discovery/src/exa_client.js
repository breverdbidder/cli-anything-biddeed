/**
 * exa_client.js — Exa Search API wrapper with cost tracking
 * Part of cli_anything.discovery harness
 * COST DISCIPLINE: Tracks every penny, enforces $10 session cap
 */

const { execSync } = require('child_process');
const EXA_BASE = 'https://api.exa.ai';

class ExaClient {
  constructor(apiKey, opts = {}) {
    if (!apiKey) throw new Error('EXA_API_KEY required');
    this.apiKey = apiKey;
    this.sessionCost = 0;
    this.sessionCap = opts.sessionCap || 10.0;
    this.requestCount = 0;
    this.rateLimitMs = opts.rateLimitMs || 200;
    this.lastRequest = 0;
  }

  async _throttle() {
    const now = Date.now();
    const elapsed = now - this.lastRequest;
    if (elapsed < this.rateLimitMs) {
      await new Promise(r => setTimeout(r, this.rateLimitMs - elapsed));
    }
    this.lastRequest = Date.now();
  }

  _checkBudget(estimatedCost = 0.01) {
    if (this.sessionCost + estimatedCost > this.sessionCap) {
      throw new Error(
        `COST CAP: Session at $${this.sessionCost.toFixed(4)}, ` +
        `adding $${estimatedCost.toFixed(4)} would exceed $${this.sessionCap} cap. STOPPING.`
      );
    }
  }

  _curlPost(url, body) {
    const jsonStr = JSON.stringify(body).replace(/'/g, "'\\''");
    const cmd = `curl -s -X POST '${url}' -H 'x-api-key: ${this.apiKey}' -H 'Content-Type: application/json' -d '${jsonStr}'`;
    const raw = execSync(cmd, { maxBuffer: 10 * 1024 * 1024, timeout: 30000 }).toString();
    return JSON.parse(raw);
  }

  async search(query, opts = {}) {
    this._checkBudget(0.006);
    await this._throttle();

    const body = {
      query,
      type: opts.type || 'auto',
      numResults: opts.numResults || 10,
      contents: { highlights: { maxCharacters: opts.highlightChars || 500, numSentences: opts.numSentences || 3 } }
    };
    if (opts.includeDomains) body.includeDomains = opts.includeDomains;
    if (opts.excludeDomains) body.excludeDomains = opts.excludeDomains;
    if (opts.category) body.category = opts.category;

    const data = this._curlPost(`${EXA_BASE}/search`, body);

    const cost = data.costDollars?.total || 0;
    this.sessionCost += cost;
    this.requestCount++;

    return {
      results: (data.results || []).map(r => ({
        url: r.url, title: r.title, publishedDate: r.publishedDate,
        highlights: r.highlights || [], highlightScores: r.highlightScores || [],
        text: r.text || '', score: r.score || 0
      })),
      searchType: data.resolvedSearchType || data.searchType,
      cost, sessionCost: this.sessionCost
    };
  }

  async deepSearch(query, opts = {}) {
    this._checkBudget(0.016);
    await this._throttle();

    const body = {
      query, type: 'deep', numResults: opts.numResults || 10,
      contents: { highlights: { maxCharacters: opts.highlightChars || 500 } }
    };
    if (opts.includeDomains) body.includeDomains = opts.includeDomains;

    const data = this._curlPost(`${EXA_BASE}/search`, body);
    const cost = data.costDollars?.total || 0;
    this.sessionCost += cost;
    this.requestCount++;

    return {
      results: (data.results || []).map(r => ({
        url: r.url, title: r.title,
        highlights: r.highlights || [], highlightScores: r.highlightScores || [],
        score: r.score || 0
      })),
      output: data.output, cost, sessionCost: this.sessionCost
    };
  }

  getCostReport() {
    return {
      totalCost: this.sessionCost,
      requestCount: this.requestCount,
      avgCostPerRequest: this.requestCount > 0 
        ? this.sessionCost / this.requestCount : 0,
      budgetRemaining: this.sessionCap - this.sessionCost,
      budgetUsedPct: ((this.sessionCost / this.sessionCap) * 100).toFixed(1)
    };
  }
}

module.exports = { ExaClient };
