/**
 * filter_rank.js — Score, deduplicate, and classify Exa results
 * HIGH_CONFIDENCE: .gov, .us, known FL portals
 */

const KNOWN_FL_PORTALS = {
  'bcpao.us': { classification: 'APPRAISER', confidence: 0.99 },
  'brevardclerk.us': { classification: 'CLERK_SEARCH', confidence: 0.99 },
  'realforeclose.com': { classification: 'AUCTION_CALENDAR', confidence: 0.95 },
  'ocpafl.org': { classification: 'APPRAISER', confidence: 0.99 },
  'myfloridacounty.com': { classification: 'TAX_PORTAL', confidence: 0.90 },
  'myorangeclerk.com': { classification: 'CLERK_SEARCH', confidence: 0.95 },
  'duvalclerk.com': { classification: 'CLERK_SEARCH', confidence: 0.95 },
  'coj.net': { classification: 'GIS_PORTAL', confidence: 0.90 },
  'sjcfl.us': { classification: 'GIS_PORTAL', confidence: 0.90 },
};

const CLASSIFICATION_KEYWORDS = {
  GIS_PORTAL: ['gis', 'parcel', 'map', 'arcgis', 'geoportal', 'mapserver'],
  ZONING_PDF: ['zoning', 'land development', 'ordinance', 'comprehensive plan', 'ldc'],
  CLERK_SEARCH: ['clerk', 'official records', 'court records', 'recording'],
  TAX_PORTAL: ['tax deed', 'tax certificate', 'tax collector', 'delinquent'],
  APPRAISER: ['property appraiser', 'assessed value', 'parcel search', 'bcpao', 'ocpa'],
  PERMIT_PORTAL: ['building permit', 'permit search', 'code enforcement'],
  AUCTION_CALENDAR: ['foreclosure', 'auction', 'sale date', 'realforeclose'],
  LIEN_SEARCH: ['lien', 'lis pendens', 'mortgage', 'judgment'],
  COMPANY: ['company', 'business', 'firm', 'agency', 'services'],
};

function classifyResult(result, expectedClassification) {
  const url = (result.url || '').toLowerCase();
  const title = (result.title || '').toLowerCase();
  const highlights = (result.highlights || []).join(' ').toLowerCase();
  const combined = `${url} ${title} ${highlights}`;

  // Check known portals first
  for (const [domain, info] of Object.entries(KNOWN_FL_PORTALS)) {
    if (url.includes(domain)) {
      return { classification: info.classification, confidence: info.confidence };
    }
  }

  // Score each classification by keyword matches
  let bestClass = expectedClassification || 'OTHER';
  let bestScore = 0;

  for (const [cls, keywords] of Object.entries(CLASSIFICATION_KEYWORDS)) {
    const matches = keywords.filter(kw => combined.includes(kw)).length;
    const score = matches / keywords.length;
    if (score > bestScore) {
      bestScore = score;
      bestClass = cls;
    }
  }

  // Confidence based on domain authority + keyword match
  let confidence = Math.min(bestScore + 0.3, 0.95);
  if (url.match(/\.(gov|us)$/i) || url.match(/\.(gov|us)\//i)) {
    confidence = Math.min(confidence + 0.15, 0.99);
  }

  return { classification: bestClass, confidence: Math.round(confidence * 100) / 100 };
}

function deduplicateResults(allResults) {
  const seen = new Map();
  
  for (const r of allResults) {
    // Normalize URL for dedup
    const normalizedUrl = r.url
      .replace(/^https?:\/\//, '')
      .replace(/^www\./, '')
      .replace(/\/+$/, '')
      .toLowerCase();

    if (!seen.has(normalizedUrl)) {
      seen.set(normalizedUrl, r);
    } else {
      // Keep the one with higher score
      const existing = seen.get(normalizedUrl);
      if ((r.exa_score || 0) > (existing.exa_score || 0)) {
        seen.set(normalizedUrl, r);
      }
    }
  }

  return Array.from(seen.values());
}

function filterAndRank(results, opts = {}) {
  const minScore = opts.minHighlightScore || 0.25;
  
  return results
    .filter(r => {
      // Remove results with very low relevance
      const maxHighlightScore = Math.max(...(r.highlightScores || [0]));
      return maxHighlightScore >= minScore || r.confidence >= 0.80;
    })
    .sort((a, b) => {
      // Primary: confidence (gov sites first)
      if (b.confidence !== a.confidence) return b.confidence - a.confidence;
      // Secondary: exa score
      return (b.exa_score || 0) - (a.exa_score || 0);
    });
}

function processResults(rawResults, expectedClassification) {
  // Classify each result
  const classified = rawResults.map(r => {
    const { classification, confidence } = classifyResult(r, expectedClassification);
    return {
      ...r,
      classification,
      confidence,
      exa_score: Math.max(...(r.highlightScores || [0]))
    };
  });

  // Deduplicate
  const deduped = deduplicateResults(classified);

  // Filter and rank
  return filterAndRank(deduped);
}

module.exports = { processResults, classifyResult, deduplicateResults, filterAndRank, KNOWN_FL_PORTALS };
