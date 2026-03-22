/**
 * PropertySearchGrid.jsx
 * BidDeed.AI — CompetitorLens Agent #14
 *
 * Adapted from Foreclosure.com search interface UX pattern.
 * BidDeed.AI enhancements:
 *   - ML Deal Score per property (replacing simple listing display)
 *   - Max bid calculation display (ARV formula: ARV×70% - Repairs - $10K - MIN($25K,15%×ARV))
 *   - Lien discovery status indicator (clean / risky / unknown)
 *   - Direct link to county auction platform (RealForeclose)
 *   - BID / REVIEW / SKIP action scoring overlay
 *   - ZoneWise zoning overlay (deferred: shown as placeholder)
 *
 * Brand: Navy #1E3A5F · Orange #F59E0B · Background #020617 · Font: Inter
 * Data: Supabase multi_county_auctions + historical_auctions views
 */

import { useState, useEffect, useCallback, useMemo } from 'react';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// ─── CONSTANTS ────────────────────────────────────────────────────────────────

const FORECLOSURE_STAGES = ['All', 'Foreclosure', 'Tax Deed', 'REO', 'Pre-Foreclosure'];
const PROPERTY_TYPES = ['All', 'Single Family', 'Condo', 'Multi-Family', 'Land', 'Commercial'];
const SORT_OPTIONS = [
  { value: 'created_at.desc', label: 'Newest First' },
  { value: 'opening_bid.asc', label: 'Price: Low → High' },
  { value: 'opening_bid.desc', label: 'Price: High → Low' },
  { value: 'bid_score.desc', label: 'Deal Score: Best First' },
  { value: 'sale_date.asc', label: 'Auction Date: Soonest' },
];

const FL_COUNTIES = [
  'All Counties','Brevard','Broward','Duval','Hillsborough','Miami-Dade',
  'Orange','Palm Beach','Pinellas','Polk','Sarasota','Seminole','Volusia',
];

const COUNTY_AUCTION_URLS = {
  Brevard: 'https://www.brevardclerk.us/foreclosure-sales',
  Broward: 'https://broward.realforeclose.com',
  Duval: 'https://duval.realforeclose.com',
  Hillsborough: 'https://hillsborough.realforeclose.com',
  'Miami-Dade': 'https://miamidade.realforeclose.com',
  Orange: 'https://orange.realforeclose.com',
  'Palm Beach': 'https://palmbeach.realforeclose.com',
  Pinellas: 'https://pinellas.realforeclose.com',
  Polk: 'https://polk.realforeclose.com',
  Sarasota: 'https://sarasota.realforeclose.com',
  Seminole: 'https://seminole.realforeclose.com',
  Volusia: 'https://volusia.realforeclose.com',
};

// ─── UTILITY FUNCTIONS ────────────────────────────────────────────────────────

/** BID/REVIEW/SKIP badge config based on ML bid_score */
const getScoreBadge = (score) => {
  if (score === null || score === undefined) {
    return { label: 'UNSCORED', classes: 'bg-slate-700/50 text-slate-400 border border-slate-600' };
  }
  if (score >= 70) return { label: 'BID', classes: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' };
  if (score >= 40) return { label: 'REVIEW', classes: 'bg-amber-500/20 text-amber-400 border border-amber-500/30' };
  return { label: 'SKIP', classes: 'bg-red-500/20 text-red-400 border border-red-500/30' };
};

/** Lien status badge */
const getLienBadge = (status) => {
  const s = (status || 'unknown').toLowerCase();
  if (s === 'clean') return { label: 'CLEAN', classes: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20', icon: '✓' };
  if (s === 'risky') return { label: 'RISKY', classes: 'bg-red-500/10 text-red-400 border border-red-500/20', icon: '⚠' };
  return { label: 'UNKNOWN', classes: 'bg-slate-700/30 text-slate-500 border border-slate-600/30', icon: '?' };
};

/** Foreclosure stage badge */
const getStageBadge = (saleType) => {
  const t = (saleType || '').toLowerCase();
  if (t.includes('tax')) return 'bg-[#1E3A5F]/60 text-blue-300 border-[#1E3A5F]';
  if (t.includes('foreclosure') || t.includes('mtg')) return 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30';
  if (t.includes('reo') || t.includes('bank')) return 'bg-slate-600/40 text-slate-300 border-slate-500';
  return 'bg-slate-700/40 text-slate-400 border-slate-600';
};

/**
 * Max bid formula: (ARV×70%) - Repairs - $10K - MIN($25K, 15%×ARV)
 * Returns null if insufficient data.
 */
const calcMaxBid = (arv, repairsEstimate = 0) => {
  if (!arv || arv <= 0) return null;
  const base = arv * 0.7;
  const dealerMargin = Math.min(25000, arv * 0.15);
  return Math.max(0, base - repairsEstimate - 10000 - dealerMargin);
};

const fmtCurrency = (n) => {
  if (n === null || n === undefined) return '—';
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${n.toLocaleString()}`;
};

const fmtDate = (dateStr) => {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
};

const daysUntil = (dateStr) => {
  if (!dateStr) return null;
  const diff = Math.ceil((new Date(dateStr) - new Date()) / 86_400_000);
  return diff;
};

// ─── SUPABASE FETCH ───────────────────────────────────────────────────────────

async function fetchAuctions({ county, stage, priceMin, priceMax, propertyType, sort, limit = 24, offset = 0 }) {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    return { data: [], error: 'Supabase not configured', total: 0 };
  }

  let params = new URLSearchParams({
    select: 'case_number,parcel_id,property_address,city,county,sale_date,opening_bid,final_price,sale_type,plaintiff,defendant,bid_score,arv_estimate,repairs_estimate,lien_status,created_at',
    order: sort || 'created_at.desc',
    limit: String(limit),
    offset: String(offset),
  });

  if (county && county !== 'All Counties') params.append('county', `eq.${county}`);
  if (stage && stage !== 'All') params.append('sale_type', `ilike.*${stage}*`);
  if (priceMin) params.append('opening_bid', `gte.${priceMin}`);
  if (priceMax) params.append('opening_bid', `lte.${priceMax}`);

  try {
    const resp = await fetch(
      `${SUPABASE_URL}/rest/v1/multi_county_auctions?${params}`,
      {
        headers: {
          apikey: SUPABASE_ANON_KEY,
          Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
          Prefer: 'count=exact',
        },
      }
    );
    const data = await resp.json();
    const total = parseInt(resp.headers.get('content-range')?.split('/')[1] || '0', 10);
    return { data: Array.isArray(data) ? data : [], error: null, total };
  } catch (err) {
    return { data: [], error: err.message, total: 0 };
  }
}

// ─── MOCK DATA (for rendering without Supabase) ───────────────────────────────

const MOCK_PROPERTIES = [
  {
    case_number: 'BR-2024-1234', parcel_id: '24-37-14-00-00234',
    property_address: '1420 Pinewood Dr', city: 'Melbourne', county: 'Brevard',
    sale_date: new Date(Date.now() + 3 * 86400000).toISOString(),
    opening_bid: 145000, final_price: null,
    sale_type: 'Foreclosure', plaintiff: 'US Bank NA', defendant: 'Smith, John',
    bid_score: 82, arv_estimate: 280000, repairs_estimate: 35000, lien_status: 'clean',
  },
  {
    case_number: 'BR-2024-5678', parcel_id: '24-37-21-00-00567',
    property_address: '321 Ocean Ave', city: 'Satellite Beach', county: 'Brevard',
    sale_date: new Date(Date.now() + 7 * 86400000).toISOString(),
    opening_bid: 230000, final_price: null,
    sale_type: 'Tax Deed', plaintiff: 'Brevard County', defendant: 'Jones, Mary',
    bid_score: 58, arv_estimate: 390000, repairs_estimate: 20000, lien_status: 'risky',
  },
  {
    case_number: 'BR-2024-9012', parcel_id: '24-37-28-00-00890',
    property_address: '88 Harbor Blvd', city: 'Cocoa Beach', county: 'Brevard',
    sale_date: new Date(Date.now() + 14 * 86400000).toISOString(),
    opening_bid: 89000, final_price: null,
    sale_type: 'Foreclosure', plaintiff: 'Wells Fargo', defendant: 'Brown, R.',
    bid_score: 35, arv_estimate: 180000, repairs_estimate: 60000, lien_status: 'unknown',
  },
  {
    case_number: 'OC-2024-3345', parcel_id: '29-22-15-00-01122',
    property_address: '5601 Citrus Cir', city: 'Orlando', county: 'Orange',
    sale_date: new Date(Date.now() + 5 * 86400000).toISOString(),
    opening_bid: 175000, final_price: null,
    sale_type: 'Foreclosure', plaintiff: 'Chase Home Finance', defendant: 'Davis, K.',
    bid_score: 76, arv_estimate: 340000, repairs_estimate: 25000, lien_status: 'clean',
  },
  {
    case_number: 'PB-2024-7890', parcel_id: '52-43-40-00-06677',
    property_address: '4412 Palm Way', city: 'Boca Raton', county: 'Palm Beach',
    sale_date: new Date(Date.now() + 10 * 86400000).toISOString(),
    opening_bid: 315000, final_price: null,
    sale_type: 'REO', plaintiff: 'Nationstar Mortgage', defendant: 'Wilson, P.',
    bid_score: 44, arv_estimate: 550000, repairs_estimate: 80000, lien_status: 'risky',
  },
  {
    case_number: 'VL-2024-2233', parcel_id: '73-55-20-00-03344',
    property_address: '202 Atlantic Ave', city: 'Daytona Beach', county: 'Volusia',
    sale_date: new Date(Date.now() + 2 * 86400000).toISOString(),
    opening_bid: 62000, final_price: null,
    sale_type: 'Tax Deed', plaintiff: 'Volusia County', defendant: 'Garcia, L.',
    bid_score: null, arv_estimate: null, repairs_estimate: null, lien_status: 'unknown',
  },
];

// ─── PROPERTY CARD ────────────────────────────────────────────────────────────

function PropertyCard({ property, onViewDetails }) {
  const score = property.bid_score;
  const badge = getScoreBadge(score);
  const lienBadge = getLienBadge(property.lien_status);
  const stageClasses = getStageBadge(property.sale_type);
  const maxBid = calcMaxBid(property.arv_estimate, property.repairs_estimate);
  const daysLeft = daysUntil(property.sale_date);
  const auctionUrl = COUNTY_AUCTION_URLS[property.county];

  const urgencyBanner = daysLeft !== null && daysLeft <= 3
    ? 'border-t-2 border-t-[#F59E0B]'
    : '';

  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg hover:border-slate-600 transition-all duration-200 flex flex-col ${urgencyBanner}`}>
      {/* Score Header */}
      <div className="bg-[#1E3A5F]/30 px-4 py-2 flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badge.classes}`}>
            {badge.label}
            {score !== null && score !== undefined && (
              <span className="ml-1 opacity-75">{score}</span>
            )}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded border ${stageClasses}`}>
            {property.sale_type || 'Unknown'}
          </span>
        </div>
        {daysLeft !== null && (
          <span className={`text-xs font-medium ${daysLeft <= 3 ? 'text-[#F59E0B] font-bold' : 'text-slate-400'}`}>
            {daysLeft === 0 ? 'TODAY' : daysLeft < 0 ? 'PAST' : `${daysLeft}d left`}
          </span>
        )}
      </div>

      {/* Property Info */}
      <div className="p-4 flex-1">
        <div className="mb-3">
          <h3 className="text-slate-50 font-semibold text-sm leading-tight">{property.property_address}</h3>
          <p className="text-slate-400 text-xs mt-0.5">{property.city}, {property.county} County</p>
          <p className="text-[#020617] bg-slate-600 text-slate-300 text-xs mt-1 font-mono px-1.5 py-0.5 rounded inline-block">
            {property.case_number}
          </p>
        </div>

        {/* Price Grid */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <p className="text-slate-500 text-xs uppercase tracking-wide">Opening Bid</p>
            <p className="text-slate-50 font-bold text-base">{fmtCurrency(property.opening_bid)}</p>
          </div>
          <div>
            <p className="text-slate-500 text-xs uppercase tracking-wide">Max Bid</p>
            <p className={`font-bold text-base ${maxBid ? 'text-[#F59E0B]' : 'text-slate-600'}`}>
              {maxBid ? fmtCurrency(maxBid) : '—'}
            </p>
          </div>
          {property.arv_estimate && (
            <div>
              <p className="text-slate-500 text-xs uppercase tracking-wide">ARV Est.</p>
              <p className="text-slate-300 text-sm">{fmtCurrency(property.arv_estimate)}</p>
            </div>
          )}
          {property.repairs_estimate && (
            <div>
              <p className="text-slate-500 text-xs uppercase tracking-wide">Repairs</p>
              <p className="text-slate-300 text-sm">{fmtCurrency(property.repairs_estimate)}</p>
            </div>
          )}
        </div>

        {/* Auction Date */}
        <div className="flex items-center gap-1.5 mb-3 bg-slate-800/50 rounded-lg px-3 py-2">
          <span className="text-slate-400 text-xs">Auction:</span>
          <span className="text-slate-200 text-xs font-medium">{fmtDate(property.sale_date)}</span>
        </div>

        {/* Lien Status */}
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-0.5 rounded border flex items-center gap-1 ${lienBadge.classes}`}>
            <span>{lienBadge.icon}</span>
            <span>Lien: {lienBadge.label}</span>
          </span>
        </div>

        {/* Plaintiff */}
        {property.plaintiff && (
          <p className="text-slate-600 text-xs mt-2 truncate">
            vs. {property.plaintiff}
          </p>
        )}
      </div>

      {/* Action Footer */}
      <div className="px-4 py-3 border-t border-slate-800 flex gap-2">
        <button
          onClick={() => onViewDetails && onViewDetails(property)}
          className="flex-1 bg-[#F59E0B] text-[#020617] font-semibold text-xs py-2 rounded-lg hover:bg-amber-300 transition-colors"
        >
          View Report
        </button>
        {auctionUrl && (
          <a
            href={`${auctionUrl}?case=${encodeURIComponent(property.case_number || '')}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 border border-[#1E3A5F] text-slate-300 font-medium text-xs py-2 rounded-lg hover:bg-[#1E3A5F]/40 transition-colors text-center"
          >
            County Auction ↗
          </a>
        )}
      </div>
    </div>
  );
}

// ─── FILTER PANEL ─────────────────────────────────────────────────────────────

function FilterPanel({ filters, onChange }) {
  return (
    <aside className="w-64 shrink-0 bg-slate-900 border border-slate-800 rounded-xl p-4 h-fit sticky top-4">
      <h2 className="text-slate-50 font-semibold text-sm mb-4">Filter Properties</h2>

      {/* County */}
      <div className="mb-4">
        <label className="text-slate-400 text-xs uppercase tracking-wide mb-1.5 block">County</label>
        <select
          value={filters.county}
          onChange={(e) => onChange({ ...filters, county: e.target.value })}
          className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 focus:border-[#F59E0B] focus:outline-none"
        >
          {FL_COUNTIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Foreclosure Stage */}
      <div className="mb-4">
        <label className="text-slate-400 text-xs uppercase tracking-wide mb-1.5 block">Stage</label>
        <div className="space-y-1.5">
          {FORECLOSURE_STAGES.map((stage) => (
            <label key={stage} className="flex items-center gap-2 cursor-pointer group">
              <input
                type="radio"
                name="stage"
                value={stage}
                checked={filters.stage === stage}
                onChange={() => onChange({ ...filters, stage })}
                className="accent-[#F59E0B]"
              />
              <span className="text-slate-300 text-sm group-hover:text-slate-100">{stage}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Price Range */}
      <div className="mb-4">
        <label className="text-slate-400 text-xs uppercase tracking-wide mb-1.5 block">Price Range</label>
        <div className="flex gap-2">
          <input
            type="number"
            placeholder="Min $"
            value={filters.priceMin || ''}
            onChange={(e) => onChange({ ...filters, priceMin: e.target.value ? Number(e.target.value) : null })}
            className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-2 py-1.5 focus:border-[#F59E0B] focus:outline-none"
          />
          <input
            type="number"
            placeholder="Max $"
            value={filters.priceMax || ''}
            onChange={(e) => onChange({ ...filters, priceMax: e.target.value ? Number(e.target.value) : null })}
            className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-2 py-1.5 focus:border-[#F59E0B] focus:outline-none"
          />
        </div>
      </div>

      {/* Deal Score filter */}
      <div className="mb-4">
        <label className="text-slate-400 text-xs uppercase tracking-wide mb-1.5 block">Min Deal Score</label>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min="0"
            max="100"
            value={filters.minScore || 0}
            onChange={(e) => onChange({ ...filters, minScore: Number(e.target.value) })}
            className="flex-1 accent-[#F59E0B]"
          />
          <span className="text-slate-300 text-sm font-mono w-8 text-right">{filters.minScore || 0}</span>
        </div>
      </div>

      {/* Lien Status */}
      <div className="mb-4">
        <label className="text-slate-400 text-xs uppercase tracking-wide mb-1.5 block">Lien Status</label>
        <div className="space-y-1.5">
          {['All', 'clean', 'risky', 'unknown'].map((s) => (
            <label key={s} className="flex items-center gap-2 cursor-pointer group">
              <input
                type="radio"
                name="lienStatus"
                value={s}
                checked={(filters.lienStatus || 'All') === s}
                onChange={() => onChange({ ...filters, lienStatus: s })}
                className="accent-[#F59E0B]"
              />
              <span className="text-slate-300 text-sm group-hover:text-slate-100 capitalize">{s}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Reset */}
      <button
        onClick={() => onChange({ county: 'All Counties', stage: 'All', priceMin: null, priceMax: null, minScore: 0, lienStatus: 'All' })}
        className="w-full border border-slate-700 text-slate-400 text-xs py-2 rounded-lg hover:border-slate-500 hover:text-slate-200 transition-colors"
      >
        Reset Filters
      </button>
    </aside>
  );
}

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────

export default function PropertySearchGrid() {
  const [filters, setFilters] = useState({
    county: 'All Counties',
    stage: 'All',
    priceMin: null,
    priceMax: null,
    minScore: 0,
    lienStatus: 'All',
  });
  const [sort, setSort] = useState('created_at.desc');
  const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'list'
  const [properties, setProperties] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [useMock, setUseMock] = useState(false);
  const [selectedProperty, setSelectedProperty] = useState(null);

  const PAGE_SIZE = 12;

  const loadProperties = useCallback(async () => {
    setLoading(true);
    setError(null);

    if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
      // Use mock data for development/preview
      setProperties(MOCK_PROPERTIES);
      setTotal(MOCK_PROPERTIES.length);
      setUseMock(true);
      setLoading(false);
      return;
    }

    const result = await fetchAuctions({
      ...filters,
      sort,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    });

    if (result.error) {
      setError(result.error);
      setProperties(MOCK_PROPERTIES);
      setUseMock(true);
    } else {
      setProperties(result.data);
      setTotal(result.total);
      setUseMock(false);
    }
    setLoading(false);
  }, [filters, sort, page]);

  useEffect(() => {
    loadProperties();
  }, [loadProperties]);

  // Client-side filter for mock data
  const displayProperties = useMemo(() => {
    if (!useMock) return properties;
    return properties.filter((p) => {
      if (filters.county !== 'All Counties' && p.county !== filters.county) return false;
      if (filters.stage !== 'All' && !p.sale_type?.toLowerCase().includes(filters.stage.toLowerCase())) return false;
      if (filters.priceMin && p.opening_bid < filters.priceMin) return false;
      if (filters.priceMax && p.opening_bid > filters.priceMax) return false;
      if (filters.minScore > 0 && (p.bid_score === null || p.bid_score < filters.minScore)) return false;
      if (filters.lienStatus !== 'All' && p.lien_status !== filters.lienStatus) return false;
      return true;
    });
  }, [properties, filters, useMock]);

  const exportCSV = () => {
    const rows = [
      ['Case Number', 'Address', 'City', 'County', 'Sale Date', 'Opening Bid', 'Deal Score', 'Max Bid', 'Lien Status'],
      ...displayProperties.map((p) => [
        p.case_number,
        p.property_address,
        p.city,
        p.county,
        fmtDate(p.sale_date),
        p.opening_bid,
        p.bid_score ?? '',
        calcMaxBid(p.arv_estimate, p.repairs_estimate) ?? '',
        p.lien_status ?? '',
      ]),
    ];
    const csv = rows.map((r) => r.map((v) => `"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `biddeed-auctions-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-[#020617] font-inter text-slate-50">
      {/* Header */}
      <header className="bg-[#1E3A5F] border-b border-slate-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-50">Auction Intelligence</h1>
            <p className="text-slate-300 text-sm mt-0.5">ML-scored foreclosure properties — Florida</p>
          </div>
          <div className="flex items-center gap-4">
            {useMock && (
              <span className="text-xs bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-1 rounded">
                Demo Data
              </span>
            )}
            <span className="text-slate-300 text-sm">
              {loading ? '…' : `${displayProperties.length} of ${total || displayProperties.length} properties`}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        <div className="flex gap-6">
          {/* Filter Sidebar */}
          <FilterPanel filters={filters} onChange={(f) => { setFilters(f); setPage(0); }} />

          {/* Results Area */}
          <div className="flex-1 min-w-0">
            {/* Toolbar */}
            <div className="flex items-center justify-between mb-4 gap-3">
              <div className="flex items-center gap-2">
                {/* Sort */}
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 focus:border-[#F59E0B] focus:outline-none"
                >
                  {SORT_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                {/* View toggle */}
                <div className="flex bg-slate-900 border border-slate-700 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setViewMode('grid')}
                    className={`px-3 py-2 text-sm transition-colors ${viewMode === 'grid' ? 'bg-[#1E3A5F] text-slate-50' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    Grid
                  </button>
                  <button
                    onClick={() => setViewMode('list')}
                    className={`px-3 py-2 text-sm transition-colors ${viewMode === 'list' ? 'bg-[#1E3A5F] text-slate-50' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    List
                  </button>
                </div>
                {/* Export */}
                <button
                  onClick={exportCSV}
                  className="border border-slate-700 text-slate-300 text-sm px-3 py-2 rounded-lg hover:border-[#F59E0B] hover:text-[#F59E0B] transition-colors"
                >
                  Export CSV
                </button>
              </div>
            </div>

            {/* Loading */}
            {loading && (
              <div className="flex items-center justify-center py-16">
                <div className="w-8 h-8 border-2 border-[#F59E0B] border-t-transparent rounded-full animate-spin" />
              </div>
            )}

            {/* Error */}
            {!loading && error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm mb-4">
                Data error: {error} — showing demo data
              </div>
            )}

            {/* Grid */}
            {!loading && (
              <div className={
                viewMode === 'grid'
                  ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4'
                  : 'flex flex-col gap-3'
              }>
                {displayProperties.map((p) => (
                  <PropertyCard
                    key={p.case_number || p.parcel_id}
                    property={p}
                    onViewDetails={setSelectedProperty}
                  />
                ))}
              </div>
            )}

            {/* Empty */}
            {!loading && displayProperties.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <p className="text-slate-500 text-lg mb-2">No properties match your filters</p>
                <p className="text-slate-600 text-sm">Try widening your search criteria</p>
              </div>
            )}

            {/* Pagination */}
            {!loading && total > PAGE_SIZE && (
              <div className="flex items-center justify-center gap-3 mt-8">
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-4 py-2 border border-slate-700 text-slate-300 text-sm rounded-lg disabled:opacity-30 hover:border-[#1E3A5F] transition-colors"
                >
                  Previous
                </button>
                <span className="text-slate-400 text-sm">
                  Page {page + 1} of {Math.ceil(total / PAGE_SIZE)}
                </span>
                <button
                  disabled={(page + 1) * PAGE_SIZE >= total}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-4 py-2 border border-slate-700 text-slate-300 text-sm rounded-lg disabled:opacity-30 hover:border-[#1E3A5F] transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Property Detail Modal */}
      {selectedProperty && (
        <div
          className="fixed inset-0 bg-[#020617]/90 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedProperty(null)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-lg w-full shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-slate-50 font-bold text-lg">{selectedProperty.property_address}</h2>
                <p className="text-slate-400 text-sm">{selectedProperty.city}, {selectedProperty.county}</p>
              </div>
              <button onClick={() => setSelectedProperty(null)} className="text-slate-500 hover:text-slate-200 text-xl">×</button>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              {[
                ['Opening Bid', fmtCurrency(selectedProperty.opening_bid)],
                ['Max Bid', fmtCurrency(calcMaxBid(selectedProperty.arv_estimate, selectedProperty.repairs_estimate))],
                ['ARV', fmtCurrency(selectedProperty.arv_estimate)],
                ['Repairs', fmtCurrency(selectedProperty.repairs_estimate)],
                ['Deal Score', selectedProperty.bid_score ?? 'Unscored'],
                ['Auction', fmtDate(selectedProperty.sale_date)],
              ].map(([label, value]) => (
                <div key={label} className="bg-slate-800/50 rounded-lg p-3">
                  <p className="text-slate-500 text-xs mb-1">{label}</p>
                  <p className="text-slate-100 font-semibold">{value}</p>
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                className="flex-1 bg-[#F59E0B] text-[#020617] font-semibold py-3 rounded-xl hover:bg-amber-300 transition-colors"
                onClick={() => setSelectedProperty(null)}
              >
                Full Analysis
              </button>
              {COUNTY_AUCTION_URLS[selectedProperty.county] && (
                <a
                  href={`${COUNTY_AUCTION_URLS[selectedProperty.county]}?case=${encodeURIComponent(selectedProperty.case_number || '')}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 border border-[#1E3A5F] text-slate-200 font-medium py-3 rounded-xl hover:bg-[#1E3A5F]/40 transition-colors text-center"
                >
                  County Auction ↗
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
