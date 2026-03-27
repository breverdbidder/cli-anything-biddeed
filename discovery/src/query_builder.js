/**
 * query_builder.js — Mode-specific Exa query templates
 * Generates optimized search queries per mode + county
 */

const ZONEWISE_TEMPLATES = [
  { template: '{county} County {state} GIS parcel map portal', classification: 'GIS_PORTAL' },
  { template: '{county} County {state} zoning ordinance map', classification: 'ZONING_PDF' },
  { template: '{county} County {state} property appraiser website', classification: 'APPRAISER' },
  { template: '{county} County {state} building permits portal', classification: 'PERMIT_PORTAL' },
  { template: '{county} County {state} land development code', classification: 'ZONING_PDF' },
];

const AUCTION_TEMPLATES = [
  { template: '{county} County {state} foreclosure auction calendar schedule', classification: 'AUCTION_CALENDAR' },
  { template: '{county} County {state} clerk of court official records search', classification: 'CLERK_SEARCH' },
  { template: '{county} County {state} tax deed sale online', classification: 'TAX_PORTAL' },
  { template: '{county} County {state} lis pendens search', classification: 'LIEN_SEARCH' },
  { template: '{county} County {state} property lien search portal', classification: 'LIEN_SEARCH' },
];

const GTM_TEMPLATES = [
  { template: '{vertical} {state}', classification: 'COMPANY', category: 'company' },
];

const STATE_NAMES = {
  FL: 'Florida', GA: 'Georgia', TX: 'Texas', CA: 'California',
  NY: 'New York', NC: 'North Carolina', SC: 'South Carolina'
};

function buildQueries(mode, params) {
  const { county, state = 'FL', vertical } = params;
  const stateName = STATE_NAMES[state] || state;
  
  let templates;
  switch (mode) {
    case 'zonewise': templates = ZONEWISE_TEMPLATES; break;
    case 'auction': templates = AUCTION_TEMPLATES; break;
    case 'gtm': templates = GTM_TEMPLATES; break;
    default: throw new Error(`Unknown mode: ${mode}`);
  }

  return templates.map(t => {
    const query = t.template
      .replace('{county}', county || '')
      .replace('{state}', stateName)
      .replace('{vertical}', vertical || '')
      .trim();

    const searchOpts = {
      numResults: 10,
      highlightChars: 500
    };

    // Boost official sources for GIS/government data
    if (mode === 'zonewise' || mode === 'auction') {
      // Don't restrict to .gov only — many FL counties use .com/.org
      // But we'll rank .gov/.us higher in filter_rank.js
    }

    if (t.category) {
      searchOpts.category = t.category;
    }

    return {
      query,
      expectedClassification: t.classification,
      searchOpts,
      mode,
      county,
      state
    };
  });
}

function estimateCost(queries) {
  // $0.005 per neural search + $0.001 per page highlight × 10 results
  const perQuery = 0.005 + (0.001 * 10);
  return {
    queryCount: queries.length,
    estimatedCost: (queries.length * perQuery).toFixed(4),
    perQueryCost: perQuery.toFixed(4)
  };
}

module.exports = { buildQueries, estimateCost, ZONEWISE_TEMPLATES, AUCTION_TEMPLATES };
