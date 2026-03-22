/**
 * AuctionCalendar.jsx
 * BidDeed.AI — CompetitorLens Agent #14
 *
 * Adapted from PropertyOnion auction calendar UX pattern.
 * BidDeed.AI enhancements:
 *   - ML bid_score overlay per date (BID/REVIEW/SKIP badges)
 *   - Color-coded by sale type (foreclosure / tax deed)
 *   - Lien priority warnings per auction
 *   - Max bid estimate inline (ARV formula)
 *   - County multi-select with Brevard default
 *   - Calendar + list view toggle
 *
 * Brand: Navy #1E3A5F · Orange #F59E0B · Background #020617 · Font: Inter
 * Data: Supabase auctions_free view
 */

import { useState, useEffect, useCallback } from 'react';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/** BID/REVIEW/SKIP badge config based on ML bid_score */
const SCORE_BADGE = (score) => {
  if (score === null || score === undefined) return null;
  if (score >= 70) return { label: 'BID', classes: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' };
  if (score >= 40) return { label: 'REVIEW', classes: 'bg-amber-500/20 text-amber-400 border border-amber-500/30' };
  return { label: 'SKIP', classes: 'bg-red-500/20 text-red-400 border border-red-500/30' };
};

/** Sale type badge color */
const SALE_TYPE_COLOR = (type) => {
  if (!type) return 'bg-slate-700 text-slate-300';
  const t = type.toLowerCase();
  if (t.includes('tax')) return 'bg-[#1E3A5F] text-slate-100';
  if (t.includes('foreclosure') || t.includes('mtg')) return 'bg-[#F59E0B]/20 text-[#F59E0B]';
  return 'bg-slate-700 text-slate-300';
};

/** Florida counties list */
const FL_COUNTIES = [
  'Alachua','Baker','Bay','Bradford','Brevard','Broward','Calhoun','Charlotte',
  'Citrus','Clay','Collier','Columbia','DeSoto','Dixie','Duval','Escambia',
  'Flagler','Franklin','Gadsden','Gilchrist','Glades','Gulf','Hamilton','Hardee',
  'Hendry','Hernando','Highlands','Hillsborough','Holmes','Indian River','Jackson',
  'Jefferson','Lafayette','Lake','Lee','Leon','Levy','Liberty','Madison','Manatee',
  'Marion','Martin','Miami-Dade','Monroe','Nassau','Okaloosa','Okeechobee','Orange',
  'Osceola','Palm Beach','Pasco','Pinellas','Polk','Putnam','Saint Johns','Saint Lucie',
  'Santa Rosa','Sarasota','Seminole','Sumter','Suwannee','Taylor','Union','Volusia',
  'Wakulla','Walton','Washington',
];

/** Format date → YYYY-MM-DD */
const toISODate = (d) => d.toISOString().split('T')[0];

/** Get days in a month grid (6 weeks) */
function buildCalendarGrid(year, month) {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const startPad = firstDay.getDay(); // 0=Sun
  const days = [];

  // Padding from previous month
  for (let i = 0; i < startPad; i++) {
    const d = new Date(year, month, -startPad + i + 1);
    days.push({ date: d, currentMonth: false });
  }
  // Current month
  for (let d = 1; d <= lastDay.getDate(); d++) {
    days.push({ date: new Date(year, month, d), currentMonth: true });
  }
  // Trailing padding
  while (days.length % 7 !== 0) {
    const last = days[days.length - 1].date;
    days.push({ date: new Date(last.getTime() + 86400000), currentMonth: false });
  }
  return days;
}

/** Supabase fetch helper */
async function fetchAuctions(startDate, endDate, county) {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    // Dev fallback: return mock data
    return generateMockAuctions(startDate, endDate, county);
  }

  const params = new URLSearchParams({
    sale_date: `gte.${startDate}`,
    select: 'id,case_number,address,city,county,sale_date,sale_type,opening_bid,arv,bid_score,lien_risk',
    order: 'sale_date',
    limit: '500',
  });
  // Append lte filter
  params.append('sale_date', `lte.${endDate}`);
  if (county && county !== 'All Counties') {
    params.append('county', `ilike.%${county}%`);
  }

  try {
    const response = await fetch(
      `${SUPABASE_URL}/rest/v1/auctions_free?${params}`,
      {
        headers: {
          apikey: SUPABASE_ANON_KEY,
          Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
          'Content-Type': 'application/json',
        },
      }
    );
    if (!response.ok) throw new Error(`Supabase error: ${response.status}`);
    return await response.json();
  } catch (err) {
    console.error('[AuctionCalendar] fetch error:', err);
    return [];
  }
}

/** Mock data for local dev without Supabase */
function generateMockAuctions(startDate, endDate, county) {
  const types = ['Foreclosure', 'Tax Deed', 'Mortgage Foreclosure'];
  const cities = ['Melbourne', 'Titusville', 'Cocoa', 'Palm Bay', 'Viera'];
  const auctions = [];
  const start = new Date(startDate);
  const end = new Date(endDate);

  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const dayOfWeek = d.getDay();
    // Auctions typically Mon-Fri
    if (dayOfWeek === 0 || dayOfWeek === 6) continue;
    const count = Math.floor(Math.random() * 8);
    for (let i = 0; i < count; i++) {
      auctions.push({
        id: `mock-${d.toISOString()}-${i}`,
        case_number: `2024-CA-${Math.floor(Math.random() * 9999).toString().padStart(4, '0')}`,
        address: `${Math.floor(Math.random() * 9999)} Mock St`,
        city: cities[Math.floor(Math.random() * cities.length)],
        county: county !== 'All Counties' ? county : 'Brevard',
        sale_date: toISODate(d),
        sale_type: types[Math.floor(Math.random() * types.length)],
        opening_bid: Math.floor(Math.random() * 300000) + 50000,
        arv: Math.floor(Math.random() * 400000) + 100000,
        bid_score: Math.floor(Math.random() * 100),
        lien_risk: Math.random() > 0.7 ? 'HOA_SENIOR' : null,
      });
    }
  }
  return auctions;
}

/** Group auctions array by sale_date string */
function groupByDate(auctions) {
  return auctions.reduce((acc, a) => {
    const key = a.sale_date;
    if (!acc[key]) acc[key] = [];
    acc[key].push(a);
    return acc;
  }, {});
}

/** Compute daily summary stats for calendar cell */
function daySummary(auctions) {
  if (!auctions?.length) return null;
  const avgScore = Math.round(auctions.reduce((s, a) => s + (a.bid_score ?? 0), 0) / auctions.length);
  const hasBid = auctions.some((a) => (a.bid_score ?? 0) >= 70);
  const hasLien = auctions.some((a) => a.lien_risk);
  return { count: auctions.length, avgScore, hasBid, hasLien };
}

// ─── COMPONENTS ───────────────────────────────────────────────────────────────

function ScoreBadge({ score }) {
  const badge = SCORE_BADGE(score);
  if (!badge) return null;
  return (
    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${badge.classes}`}>
      {badge.label}
    </span>
  );
}

function LienBadge() {
  return (
    <span
      className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-900/40 text-red-400 border border-red-700/30"
      title="HOA/Senior lien — verify lien position"
    >
      ⚠ LIEN
    </span>
  );
}

function CalendarCell({ day, auctions, onDayClick, isToday, isSelected }) {
  const summary = daySummary(auctions);
  const dateStr = toISODate(day.date);

  return (
    <button
      onClick={() => onDayClick(day.date, auctions)}
      disabled={!day.currentMonth}
      aria-label={`${dateStr}: ${summary ? summary.count + ' auctions' : 'no auctions'}`}
      className={[
        'relative min-h-[72px] p-1.5 rounded-lg border text-left transition-all',
        'focus:outline-none focus:ring-2 focus:ring-[#F59E0B] focus:ring-offset-1 focus:ring-offset-[#020617]',
        day.currentMonth ? 'cursor-pointer' : 'opacity-30 cursor-default',
        isSelected
          ? 'border-[#F59E0B] bg-[#1E3A5F]/40'
          : summary
          ? 'border-slate-700 bg-slate-900 hover:border-[#1E3A5F] hover:bg-[#1E3A5F]/10'
          : 'border-slate-800/50 bg-slate-900/30 hover:bg-slate-900/50',
        isToday && !isSelected ? 'border-[#F59E0B]/60' : '',
      ].join(' ')}
    >
      {/* Day number */}
      <div className="flex items-center justify-between mb-1">
        <span
          className={[
            'text-xs font-semibold w-6 h-6 flex items-center justify-center rounded-full',
            isToday
              ? 'bg-[#F59E0B] text-[#020617]'
              : day.currentMonth
              ? 'text-slate-300'
              : 'text-slate-600',
          ].join(' ')}
        >
          {day.date.getDate()}
        </span>
        {summary?.hasLien && <LienBadge />}
      </div>

      {/* Auction count + score */}
      {summary && (
        <div className="space-y-0.5">
          <div className="flex items-center gap-1">
            <span className="text-[11px] font-medium text-slate-300">
              {summary.count} auction{summary.count !== 1 ? 's' : ''}
            </span>
            {summary.hasBid && (
              <span className="text-[10px] font-bold text-emerald-400">★</span>
            )}
          </div>
          <ScoreBadge score={summary.avgScore} />
        </div>
      )}
    </button>
  );
}

function AuctionListItem({ auction }) {
  const badge = SCORE_BADGE(auction.bid_score);
  const maxBid =
    auction.arv
      ? Math.round(auction.arv * 0.7 - 10000 - Math.min(25000, auction.arv * 0.15))
      : null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-[#1E3A5F] transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {badge && (
              <span className={`text-xs font-bold px-2 py-0.5 rounded ${badge.classes}`}>
                {badge.label}
              </span>
            )}
            <span className={`text-xs px-2 py-0.5 rounded ${SALE_TYPE_COLOR(auction.sale_type)}`}>
              {auction.sale_type || 'Unknown'}
            </span>
            {auction.lien_risk && <LienBadge />}
          </div>

          <p className="text-sm font-medium text-slate-100 truncate">
            {auction.address}
          </p>
          <p className="text-xs text-slate-400">
            {auction.city}, {auction.county} · Case {auction.case_number}
          </p>
        </div>

        <div className="text-right shrink-0">
          {auction.opening_bid && (
            <div>
              <p className="text-xs text-slate-500">Opening bid</p>
              <p className="text-sm font-semibold text-slate-100">
                ${auction.opening_bid.toLocaleString()}
              </p>
            </div>
          )}
          {maxBid && maxBid > 0 && (
            <div className="mt-1">
              <p className="text-[10px] text-slate-500">Est. max bid</p>
              <p className="text-sm font-bold text-[#F59E0B]">
                ${maxBid.toLocaleString()}
              </p>
            </div>
          )}
          {auction.bid_score !== undefined && auction.bid_score !== null && (
            <div className="mt-1">
              <p className="text-[10px] text-slate-500">ML Score</p>
              <p className="text-sm font-bold text-slate-200">{auction.bid_score}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-16" aria-label="Loading auctions">
      <div className="w-8 h-8 border-2 border-[#1E3A5F] border-t-[#F59E0B] rounded-full animate-spin" />
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-4xl mb-3">⚠️</div>
      <p className="text-slate-300 font-medium mb-1">Failed to load auctions</p>
      <p className="text-slate-500 text-sm mb-4">{message}</p>
      <button
        onClick={onRetry}
        className="bg-[#F59E0B] text-[#020617] font-semibold px-4 py-2 rounded-lg hover:bg-amber-300 transition-colors focus:outline-none focus:ring-2 focus:ring-[#F59E0B]"
      >
        Retry
      </button>
    </div>
  );
}

function EmptyState({ selectedDate }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-4xl mb-3">📅</div>
      <p className="text-slate-300 font-medium mb-1">
        No auctions on {selectedDate ? selectedDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric' }) : 'this date'}
      </p>
      <p className="text-slate-500 text-sm">Select another date or expand your county filter</p>
    </div>
  );
}

// ─── MAIN COMPONENT ────────────────────────────────────────────────────────────

/**
 * AuctionCalendar — BidDeed.AI branded auction calendar
 * Adapted from PropertyOnion calendar UX with ML scoring and lien data
 *
 * @param {{ defaultCounty?: string, defaultView?: 'calendar'|'list' }} props
 */
export default function AuctionCalendar({ defaultCounty = 'Brevard', defaultView = 'calendar' }) {
  const today = new Date();
  const [viewMode, setViewMode] = useState(defaultView); // 'calendar' | 'list'
  const [currentYear, setCurrentYear] = useState(today.getFullYear());
  const [currentMonth, setCurrentMonth] = useState(today.getMonth());
  const [selectedCounty, setSelectedCounty] = useState(defaultCounty);
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedAuctions, setSelectedAuctions] = useState([]);
  const [auctions, setAuctions] = useState([]);
  const [auctionsByDate, setAuctionsByDate] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const calendarDays = buildCalendarGrid(currentYear, currentMonth);
  const startDate = toISODate(calendarDays[0].date);
  const endDate = toISODate(calendarDays[calendarDays.length - 1].date);

  const loadAuctions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAuctions(startDate, endDate, selectedCounty);
      setAuctions(data);
      setAuctionsByDate(groupByDate(data));
    } catch (err) {
      setError(err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, selectedCounty]);

  useEffect(() => {
    loadAuctions();
    setSelectedDate(null);
    setSelectedAuctions([]);
  }, [loadAuctions]);

  const handleDayClick = (date, dayAuctions) => {
    if (!dayAuctions?.length) return;
    setSelectedDate(date);
    setSelectedAuctions(dayAuctions);
    if (window.innerWidth < 768) {
      // Mobile: switch to list view of selected day
      setViewMode('list');
    }
  };

  const prevMonth = () => {
    if (currentMonth === 0) { setCurrentMonth(11); setCurrentYear(y => y - 1); }
    else setCurrentMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (currentMonth === 11) { setCurrentMonth(0); setCurrentYear(y => y + 1); }
    else setCurrentMonth(m => m + 1);
  };

  const monthLabel = new Date(currentYear, currentMonth).toLocaleDateString('en-US', {
    month: 'long', year: 'numeric',
  });

  const displayedAuctions = selectedDate
    ? selectedAuctions
    : auctions.sort((a, b) => new Date(a.sale_date) - new Date(b.sale_date));

  const totalThisMonth = Object.values(auctionsByDate).reduce((s, a) => s + a.length, 0);
  const bidOpportunities = auctions.filter(a => (a.bid_score ?? 0) >= 70).length;

  return (
    <div
      className="min-h-screen bg-[#020617] text-slate-50 font-[Inter,system-ui,sans-serif]"
      role="main"
    >
      {/* ── HEADER ── */}
      <div className="bg-[#1E3A5F] border-b border-[#1E3A5F]/60 px-4 sm:px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-slate-50">
              Auction Calendar
            </h1>
            <p className="text-sm text-slate-300 mt-0.5">
              Florida foreclosure &amp; tax deed auctions · BidDeed.AI intelligence
            </p>
          </div>

          {/* Stats bar */}
          {!loading && (
            <div className="flex gap-4 flex-wrap">
              <div className="text-center">
                <p className="text-xs text-slate-400">This month</p>
                <p className="text-lg font-bold text-slate-100">{totalThisMonth}</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-slate-400">BID opportunities</p>
                <p className="text-lg font-bold text-emerald-400">{bidOpportunities}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 space-y-4">

        {/* ── FILTERS + VIEW TOGGLE ── */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          {/* County selector */}
          <div className="flex items-center gap-2">
            <label htmlFor="county-select" className="text-sm text-slate-400 whitespace-nowrap">
              County
            </label>
            <select
              id="county-select"
              value={selectedCounty}
              onChange={(e) => setSelectedCounty(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-100 text-sm rounded-lg px-3 py-1.5
                         focus:outline-none focus:ring-2 focus:ring-[#F59E0B] focus:border-transparent
                         cursor-pointer"
              aria-label="Filter by county"
            >
              <option value="All Counties">All Counties</option>
              {FL_COUNTIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* View toggle */}
          <div
            className="flex rounded-lg border border-slate-700 overflow-hidden"
            role="group"
            aria-label="View mode"
          >
            {['calendar', 'list'].map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                aria-pressed={viewMode === mode}
                className={[
                  'px-4 py-1.5 text-sm font-medium capitalize transition-colors',
                  'focus:outline-none focus:ring-2 focus:ring-[#F59E0B] focus:ring-inset',
                  viewMode === mode
                    ? 'bg-[#1E3A5F] text-slate-50'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200',
                ].join(' ')}
              >
                {mode === 'calendar' ? '📅 Calendar' : '☰ List'}
              </button>
            ))}
          </div>
        </div>

        {/* ── CALENDAR VIEW ── */}
        {viewMode === 'calendar' && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            {/* Month nav */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
              <button
                onClick={prevMonth}
                aria-label="Previous month"
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-100
                           focus:outline-none focus:ring-2 focus:ring-[#F59E0B] transition-colors"
              >
                ‹
              </button>
              <h2 className="text-base font-semibold text-slate-100">{monthLabel}</h2>
              <button
                onClick={nextMonth}
                aria-label="Next month"
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-100
                           focus:outline-none focus:ring-2 focus:ring-[#F59E0B] transition-colors"
              >
                ›
              </button>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 border-b border-slate-800">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
                <div key={d} className="py-2 text-center text-xs font-medium text-slate-500">
                  {d}
                </div>
              ))}
            </div>

            {/* Calendar grid */}
            {loading ? (
              <LoadingSpinner />
            ) : error ? (
              <ErrorState message={error} onRetry={loadAuctions} />
            ) : (
              <div className="grid grid-cols-7 gap-px bg-slate-800 p-px">
                {calendarDays.map((day, idx) => {
                  const dateKey = toISODate(day.date);
                  const dayAuctions = auctionsByDate[dateKey] || [];
                  const isToday = dateKey === toISODate(today);
                  const isSelected = selectedDate && dateKey === toISODate(selectedDate);
                  return (
                    <CalendarCell
                      key={idx}
                      day={day}
                      auctions={dayAuctions}
                      onDayClick={handleDayClick}
                      isToday={isToday}
                      isSelected={isSelected}
                    />
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── LIST / DETAIL VIEW ── */}
        {(viewMode === 'list' || selectedDate) && (
          <div>
            {/* Selected date header */}
            {selectedDate && (
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-base font-semibold text-slate-100">
                  {selectedDate.toLocaleDateString('en-US', {
                    weekday: 'long', month: 'long', day: 'numeric',
                  })}
                  <span className="ml-2 text-sm font-normal text-slate-400">
                    ({selectedAuctions.length} auction{selectedAuctions.length !== 1 ? 's' : ''})
                  </span>
                </h3>
                <button
                  onClick={() => { setSelectedDate(null); setSelectedAuctions([]); }}
                  className="text-sm text-slate-400 hover:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#F59E0B] rounded px-2 py-1"
                >
                  ✕ Clear
                </button>
              </div>
            )}

            {loading ? (
              <LoadingSpinner />
            ) : error ? (
              <ErrorState message={error} onRetry={loadAuctions} />
            ) : displayedAuctions.length === 0 ? (
              <EmptyState selectedDate={selectedDate} />
            ) : (
              <div className="space-y-3">
                {displayedAuctions.map((auction) => (
                  <AuctionListItem key={auction.id} auction={auction} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── LEGEND ── */}
        <div className="flex items-center gap-4 flex-wrap pt-2 border-t border-slate-800">
          <span className="text-xs text-slate-500">ML Score:</span>
          {[
            { label: 'BID ≥70', cls: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' },
            { label: 'REVIEW 40-69', cls: 'bg-amber-500/20 text-amber-400 border border-amber-500/30' },
            { label: 'SKIP <40', cls: 'bg-red-500/20 text-red-400 border border-red-500/30' },
          ].map(({ label, cls }) => (
            <span key={label} className={`text-xs px-2 py-0.5 rounded font-medium ${cls}`}>
              {label}
            </span>
          ))}
          <span className="text-xs text-slate-500 ml-2">
            ★ = BID opportunity on that date
          </span>
        </div>

        {/* ── CTA ── */}
        <div className="flex justify-center pt-4">
          <a
            href="/dashboard"
            className="bg-[#F59E0B] text-[#020617] font-semibold px-6 py-2.5 rounded-lg
                       hover:bg-amber-300 transition-colors
                       focus:outline-none focus:ring-2 focus:ring-[#F59E0B] focus:ring-offset-2 focus:ring-offset-[#020617]"
          >
            View Full Deal Dashboard →
          </a>
        </div>
      </div>
    </div>
  );
}
