/**
 * persist.js — Supabase persistence + Firecrawl queue handoff
 * Stores discovery results and updates county_conquest_status
 */

const { createClient } = require('@supabase/supabase-js');

class DiscoveryStore {
  constructor(supabaseUrl, supabaseKey) {
    this.client = createClient(supabaseUrl, supabaseKey);
  }

  async saveResults(results) {
    if (!results.length) return { inserted: 0, errors: [] };

    const rows = results.map(r => ({
      mode: r.mode,
      county: r.county,
      state: r.state || 'FL',
      query: r.query,
      url: r.url,
      title: r.title,
      classification: r.classification,
      confidence: r.confidence,
      highlight_text: (r.highlights || []).slice(0, 3).join(' | '),
      exa_score: r.exa_score,
      firecrawl_status: 'pending',
      cost_dollars: r.cost || 0,
      metadata: {
        search_type: r.searchType,
        highlight_scores: r.highlightScores
      }
    }));

    const { data, error } = await this.client
      .from('discovery_results')
      .upsert(rows, { 
        onConflict: 'mode,county,url',
        ignoreDuplicates: false 
      })
      .select('id, url, classification');

    if (error) {
      console.error('Supabase insert error:', error.message);
      return { inserted: 0, errors: [error.message] };
    }

    return { inserted: data?.length || 0, errors: [] };
  }

  async updateConquestStatus(county, mode) {
    if (mode !== 'zonewise') return;

    const { data: stats } = await this.client
      .from('discovery_results')
      .select('classification')
      .eq('county', county)
      .eq('mode', 'zonewise');

    const hasGIS = stats?.some(s => s.classification === 'GIS_PORTAL');
    const hasAppraiser = stats?.some(s => s.classification === 'APPRAISER');

    if (hasGIS && hasAppraiser) {
      await this.client
        .from('county_conquest_status')
        .update({ 
          discovery_complete: true,
          discovery_date: new Date().toISOString()
        })
        .eq('county_name', county);
    }
  }

  async getCountyStats(county) {
    const { data, error } = await this.client
      .from('discovery_county_stats')
      .select('*')
      .eq('county', county);

    return data || [];
  }

  async getPendingCounties() {
    const { data } = await this.client
      .from('fl_counties')
      .select('county_name, co_no')
      .or('discovery_complete.is.null,discovery_complete.eq.false')
      .order('county_name');

    return data || [];
  }

  async getFirecrawlQueue(limit = 50) {
    const { data } = await this.client
      .from('discovery_results')
      .select('id, url, classification, county, mode')
      .eq('firecrawl_status', 'pending')
      .order('confidence', { ascending: false })
      .limit(limit);

    return data || [];
  }

  async markFirecrawlQueued(ids) {
    const { error } = await this.client
      .from('discovery_results')
      .update({ firecrawl_status: 'queued' })
      .in('id', ids);

    return !error;
  }
}

module.exports = { DiscoveryStore };
