// GTM-22 S5 REPORT ENGINE — Plaintiff Discount Index band (issue #20043
// item 7, BidDeed-only ML band).
//
// Thesis (Ariel): lenders/servicers write off non-performing assets on
// their own fiscal calendars and let properties go to third parties at
// deeper discounts in those windows. This is a scoreboard, not a model —
// decision-support copy only, never "this bank will discount".
//
// Reads public.plaintiff_discount_index (materialized view,
// supabase/migrations/20260906d_plaintiff_discount_index_20043.sql) and
// public.v_plaintiff_discount_rank, keyed on the case's plaintiff_norm.
import { get as defaultGet } from '../supabase.js';

const MIN_N_FOR_RATIOS = 3;

export async function buildPlaintiffDiscountBand(auction, { get = defaultGet } = {}) {
  const plaintiffNorm = auction.plaintiff_norm || null;

  if (!plaintiffNorm) {
    return {
      section_key: 'plaintiff_discount_index',
      available: false,
      n: 0,
      reason: 'Pending — no plaintiff on file for this case (plaintiff_norm not populated)',
    };
  }

  const [allTimeRows, quarterRows, rankRows] = await Promise.all([
    get(`plaintiff_discount_index?period_type=eq.all_time&plaintiff_norm=eq.${encodeURIComponent(plaintiffNorm)}&select=*`).catch(() => []),
    get(`plaintiff_discount_index?period_type=eq.quarter&plaintiff_norm=eq.${encodeURIComponent(plaintiffNorm)}&select=*&order=quarter.desc&limit=1`).catch(() => []),
    get(`v_plaintiff_discount_rank?plaintiff_norm=eq.${encodeURIComponent(plaintiffNorm)}&select=rank_by_discount`).catch(() => []),
  ]);

  const allTime = allTimeRows[0] || null;
  const currentQuarter = quarterRows[0] || null;
  const n = Number(allTime?.n_third_party_sales) || 0;

  if (n < MIN_N_FOR_RATIOS) {
    return {
      section_key: 'plaintiff_discount_index',
      available: false,
      plaintiff_norm: plaintiffNorm,
      n,
      reason: `Pending — fewer than ${MIN_N_FOR_RATIOS} observed third-party sales for this plaintiff`,
    };
  }

  return {
    section_key: 'plaintiff_discount_index',
    available: true,
    plaintiff_norm: plaintiffNorm,
    n,
    median_sold_to_judgment: allTime.median_sold_to_judgment != null ? Number(allTime.median_sold_to_judgment) : null,
    min_sold_to_judgment: allTime.min_sold_to_judgment != null ? Number(allTime.min_sold_to_judgment) : null,
    third_party_share: allTime.third_party_share != null ? Number(allTime.third_party_share) : null,
    quarter_of_sale: (currentQuarter && Number(currentQuarter.n_third_party_sales) >= MIN_N_FOR_RATIOS)
      ? {
          quarter: currentQuarter.quarter,
          n: Number(currentQuarter.n_third_party_sales),
          median_sold_to_judgment: currentQuarter.median_sold_to_judgment != null ? Number(currentQuarter.median_sold_to_judgment) : null,
        }
      : { available: false, reason: `Pending — fewer than ${MIN_N_FOR_RATIOS} observed third-party sales for this plaintiff this quarter` },
    rank_among_n_gte_3: rankRows[0]?.rank_by_discount != null ? Number(rankRows[0].rank_by_discount) : null,
    note: 'Decision-support scoreboard from BidDeed\'s own auction outcome data — not a prediction that this plaintiff will discount this specific case.',
  };
}
