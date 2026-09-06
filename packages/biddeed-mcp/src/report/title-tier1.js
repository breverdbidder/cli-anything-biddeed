// GTM-22 S5 REPORT ENGINE — Title Tier 1 (lien search), issue #20045.
//
// Backs SIGNAL$ Property Report §16 Judgment & Encumbrance Summary, Title
// Tier 1: the full recorded-instrument list for a case pulled from the
// county's AcclaimWeb Official Records case-number search. Reads the cached
// result from public.title_tier1_results (written by
// scripts/pre_auction_lien_harvest.py) -- this module NEVER scrapes the
// clerk's site itself, per the issue's own DoD ("so the report reads, never
// re-scrapes on render").
//
// Per-county gating is DATA-DRIVEN, not a hardcoded county allowlist: a
// county with no title_tier1_results rows for this case has simply never
// been harvested, and renders the same "not yet live for this county"
// message regardless of which county it is. This mirrors lien-survival.js's
// existing classify() design (case/parcel presence in lien_results decides
// availability, not a county switch statement).
import { get as defaultGet } from '../supabase.js';

export async function buildLienSearch({ mca_id, county } = {}, { get = defaultGet } = {}) {
  if (!mca_id) {
    return {
      available: false, county_supported: false,
      reason: `Title Tier 1 not yet live for ${county || 'this county'}`,
      items: [], n_items: 0, as_of_date: null,
    };
  }

  const rows = await get(
    `title_tier1_results?mca_id=eq.${mca_id}&select=instrument_type,recording_date,book_page,instrument_number,direct_name,indirect_name,amount,status,source,fetched_at&order=recording_date.asc`
  ).catch(() => null);

  if (!rows || rows.length === 0) {
    return {
      available: false, county_supported: false,
      reason: `Title Tier 1 not yet live for ${county || 'this county'}`,
      items: [], n_items: 0, as_of_date: null,
    };
  }

  const asOfDay = rows.reduce((max, r) => (r.fetched_at && r.fetched_at > (max || '') ? r.fetched_at : max), null)?.slice(0, 10) || null;

  // A single NO_DOCUMENTS_FOUND marker row (see harvest script) means a real
  // search ran and found zero recorded instruments for this case -- distinct
  // from "never harvested at all" (the county_supported=false branch above).
  if (rows.length === 1 && rows[0].instrument_type === 'NO_DOCUMENTS_FOUND') {
    return {
      available: true, county_supported: true, searched: true,
      reason: `No instruments found in Official Records search as of ${asOfDay} — verify`,
      items: [], n_items: 0, as_of_date: asOfDay, source: rows[0].source,
    };
  }

  const items = rows.map(r => ({
    instrument_type: r.instrument_type || 'Pending — not on file',
    recording_date: r.recording_date,
    book_page: r.book_page || 'Pending — not on file',
    instrument_number: r.instrument_number || null,
    creditor: r.direct_name || 'Pending — not on file',
    debtor_or_grantee: r.indirect_name || null,
    amount: typeof r.amount === 'number' && r.amount > 0 ? r.amount : null,
    status: r.status,
    source: r.source,
  }));

  return {
    available: true, county_supported: true, searched: true,
    items, n_items: items.length, as_of_date: asOfDay,
  };
}
