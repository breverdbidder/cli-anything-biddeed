// GTM-22 S5 REPORT ENGINE — report template loader.
//
// The 18-section card is CONFIGURATION, held in public.s5_report_sections and
// read through public.v_s5_report_template (which joins the UPL liability_note
// from pencil_report_parity_spec so that language has exactly one home).
//
// Deliberate split, because this is a paid and legally-exposed deliverable:
//   - Supabase owns ORDER, LABELS, TITLES, HC MIRRORS, BAND COLOURS and the
//     liability notes. Those can change without a deploy.
//   - Code owns WHAT EACH SECTION RENDERS. A row edit must never be able to
//     change the substance of a customer document without review.
// test/s5-report-golden.test.js binds the two: the renderer's handler set must
// match the template's section_key set exactly, in both directions.
//
// DEFAULT_TEMPLATE mirrors the seeded table and is used when the view is
// unreachable — a paid report must never fail because a config read failed.
import { get as defaultGet } from '../supabase.js';

export const DEFAULT_TEMPLATE = [
  { sort_order: 10,  section_key: 'subject_identification', section_label: '1',     title: 'Subject & Auction Identification',                                   band_color: 'navy',   liability_note: null },
  { sort_order: 20,  section_key: 'value_estimate',         section_label: '2-3',   title: 'BidDeed Value Estimate & Components',                                 band_color: 'navy',   liability_note: 'investor decision-support, explicitly not an appraisal' },
  { sort_order: 30,  section_key: 'market_and_comps',       section_label: '4-7',   title: 'Auction-Cleared Market · Comparable Sales · Comp Stats',              band_color: 'navy',   liability_note: 'investor decision-support, explicitly not an appraisal' },
  { sort_order: 40,  section_key: 'transaction_history',    section_label: '8',     title: 'Transaction History',                                                 band_color: 'navy',   liability_note: null },
  { sort_order: 50,  section_key: 'property_record',        section_label: '9-10',  title: 'Property Record & Listing Details',                                   band_color: 'navy',   liability_note: null },
  { sort_order: 60,  section_key: 'context_layers',         section_label: '11-14', title: 'Context Layers — Neighborhood · Schools · Flood · Market Grade',      band_color: 'navy',   liability_note: null },
  { sort_order: 70,  section_key: 'shapira_ml',             section_label: 'ML',    title: 'Shapira Models — Third-Party Purchase Classifier',                    band_color: 'navy',   liability_note: null },
  { sort_order: 80,  section_key: 'zonewise',               section_label: 'ZW',    title: 'ZoneWise.AI Land & Zoning Intelligence — NO HC EQUIVALENT, THE PAIRING', band_color: 'orange', liability_note: null },
  { sort_order: 90,  section_key: 'bid_card',               section_label: '15',    title: 'Shapira Bid Card — Opinion of Price',                                 band_color: 'navy',   liability_note: 'investor decision-support, explicitly not an appraisal' },
  { sort_order: 100, section_key: 'judgment_encumbrance',   section_label: '16',    title: 'Judgment & Encumbrance Summary',                                      band_color: 'navy',   liability_note: 'THE liability edge: state survival per statute (FS 197.552/713.07), never as owed-amount advice' },
  { sort_order: 110, section_key: 'provenance',             section_label: '17',    title: 'Provenance & Honest Limits',                                          band_color: 'navy',   liability_note: 'frame as "open items to verify," NOT as insured exceptions' },
  { sort_order: 120, section_key: 'auction_outcome',        section_label: '18',    title: 'Auction Outcome & Prediction Scorecard',                              band_color: 'green',  liability_note: null },
];

export async function getReportTemplate({ get = defaultGet } = {}) {
  const rows = await get(
    'v_s5_report_template?select=sort_order,section_key,section_label,title,hc_mirror,band_color,liability_note,parity_status&order=sort_order'
  ).catch(() => null);

  if (!Array.isArray(rows) || rows.length === 0) {
    return { sections: DEFAULT_TEMPLATE, source: 'DEFAULT_TEMPLATE (v_s5_report_template unreachable or empty)' };
  }
  return { sections: rows, source: 'v_s5_report_template' };
}
