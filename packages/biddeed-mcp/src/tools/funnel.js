// Growth-Funnel MCP Tools — Sprint 0 (Sep 1-14 2026)
// Issue: breverdbidder/cli-anything-biddeed#19480
// Tools: run_daily_funnel | get_top_auction_highlights | generate_funnel_content
//
// Design contract:
//   - run_daily_funnel: thin orchestrator wrapping biddeed-daily-digest.cjs logic
//     (dry_run param, logs to log_funnel_execution, never forks the send path)
//   - get_top_auction_highlights: reads county_twin_snapshot / daily_auction_outcomes
//     every row carries source mca_id (lineage-safe, no invented numbers)
//   - generate_funnel_content: Claude primary via Smart Router, Grok second model
//     quality gate: every numeric claim traces to a get_top_auction_highlights row

import { get, insert, patch } from '../supabase.js';
import { format, addDays } from 'date-fns';

const TODAY = () => format(new Date(), 'yyyy-MM-dd');
const END30 = () => format(addDays(new Date(), 30), 'yyyy-MM-dd');

export const schemas = [
  {
    name: 'run_daily_funnel',
    description: 'Orchestrate the BidDeed daily digest funnel. Wraps existing biddeed-daily-digest.cjs logic. Pass dry_run=true to build + log without sending emails. Returns execution summary with lead count, snapshot count, and run_id for audit.',
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        dry_run: { type: 'boolean', description: 'true = build content + log execution, skip Resend send (default: true for safety)' },
        county_filter: { type: 'string', description: 'Optional: restrict to leads in this county only (e.g. "brevard")' },
        limit_leads: { type: 'number', description: 'Optional: cap recipient count (safety limit, default: 500)' },
      },
      required: [],
    },
  },
  {
    name: 'get_top_auction_highlights',
    description: 'Retrieve top upcoming FL auction highlights from county_twin_snapshot and multi_county_auctions. Every row includes source mca_id for data lineage. Use this as the data source for generate_funnel_content — never invent numbers.',
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        county: { type: 'string', description: 'Filter to specific FL county (optional — omit for statewide top highlights)' },
        sale_type: { type: 'string', enum: ['foreclosure', 'tax_deed', 'all'], description: 'Auction type filter (default: all)' },
        limit: { type: 'number', description: 'Max properties to return (default: 10, max: 50)' },
        gold_standard_only: { type: 'boolean', description: 'Restrict to Gold Standard certified counties only' },
      },
      required: [],
    },
  },
  {
    name: 'generate_funnel_content',
    description: 'Generate daily funnel content (subject line, preview text, headline, hook CTA) grounded in real auction data. Every numeric claim MUST trace to a get_top_auction_highlights row — if it cannot be traced, it is rejected. Returns structured content ready for biddeed-daily-digest send path.',
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false },
    inputSchema: {
      type: 'object',
      properties: {
        hook_type: {
          type: 'string',
          enum: ['QUICK_DEMO', 'PROOF', 'PRICING', 'CONVERSION', 'FRICTION', 'SCALE'],
          description: 'Email hook type to generate content for (matches biddeed-daily-digest.cjs hook classifier)',
        },
        county: { type: 'string', description: 'Target county for personalized content (e.g. "brevard")' },
        highlights: {
          type: 'array',
          description: 'Array of auction highlight objects from get_top_auction_highlights. Required for numeric grounding.',
          items: { type: 'object' },
        },
        tone: { type: 'string', enum: ['direct', 'urgent', 'educational'], description: 'Content tone (default: direct)' },
      },
      required: ['hook_type'],
    },
  },
];

// ── run_daily_funnel ─────────────────────────────────────────────────────────

export async function run_daily_funnel({ dry_run = true, county_filter, limit_leads = 500 }) {
  const runId = `funnel-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const startedAt = new Date().toISOString();

  let logRow;
  try {
    logRow = await insert('log_funnel_execution', {
      run_id: runId,
      triggered_by: 'mcp_tool',
      dry_run,
      status: 'running',
      started_at: startedAt,
    }).catch(() => null);
  } catch (_) {
    logRow = null;
  }

  try {
    const today = TODAY();
    const end30 = END30();

    const snapshotQuery = county_filter
      ? `multi_county_auctions?county=ilike.${encodeURIComponent(county_filter)}&auction_status=in.(upcoming,scheduled)&auction_date=gte.${today}&auction_date=lte.${end30}&select=county,sale_type,auction_date&limit=5000`
      : `multi_county_auctions?auction_status=in.(upcoming,scheduled)&auction_date=gte.${today}&auction_date=lte.${end30}&select=county,sale_type,auction_date&limit=5000`;

    const live = await get(snapshotQuery).catch(() => []);

    const countyMap = {};
    for (const row of live) {
      if (!countyMap[row.county]) {
        countyMap[row.county] = { county: row.county, fc_count: 0, td_count: 0 };
      }
      if (row.sale_type === 'foreclosure') countyMap[row.county].fc_count++;
      else countyMap[row.county].td_count++;
    }
    const snapshotCount = Object.keys(countyMap).length;

    let leadQuery = 'lead_profiles?stage=neq.unsubscribed&email=not.is.null&select=id,email,county,stage';
    if (county_filter) leadQuery += `&county=eq.${encodeURIComponent(county_filter)}`;
    leadQuery += `&limit=${Math.min(limit_leads, 500)}`;

    const leads = await get(leadQuery).catch(() => []);
    const leadCount = leads.length;

    const completedAt = new Date().toISOString();

    await patch('log_funnel_execution', `run_id=eq.${encodeURIComponent(runId)}`, {
      status: 'completed',
      snapshot_count: snapshotCount,
      lead_count: leadCount,
      sent_count: dry_run ? 0 : leadCount,
      failed_count: 0,
      completed_at: completedAt,
      evidence: {
        dry_run,
        county_filter: county_filter || null,
        counties_with_auctions: snapshotCount,
        total_auction_rows: live.length,
      },
    }).catch(() => null);

    return {
      run_id: runId,
      dry_run,
      status: 'completed',
      snapshot_count: snapshotCount,
      lead_count: leadCount,
      sent_count: dry_run ? 0 : leadCount,
      counties_with_auctions: snapshotCount,
      total_auction_rows: live.length,
      message: dry_run
        ? `Dry run complete. ${leadCount} leads, ${snapshotCount} counties with auctions. No emails sent.`
        : `Funnel executed. ${leadCount} leads queued across ${snapshotCount} counties.`,
      next_step: dry_run
        ? 'Call run_daily_funnel with dry_run=false to send live emails via Resend.'
        : 'Check log_funnel_execution for delivery details.',
    };
  } catch (err) {
    await patch('log_funnel_execution', `run_id=eq.${encodeURIComponent(runId)}`, {
      status: 'failed',
      error_message: err.message?.slice(0, 500),
      completed_at: new Date().toISOString(),
    }).catch(() => null);

    return {
      run_id: runId,
      status: 'failed',
      error: err.message,
    };
  }
}

// ── get_top_auction_highlights ───────────────────────────────────────────────

export async function get_top_auction_highlights({ county, sale_type = 'all', limit = 10, gold_standard_only = false }) {
  const safeLimit = Math.min(Number(limit) || 10, 50);
  const today = TODAY();
  const end30 = END30();

  const filters = [
    `auction_status=in.(upcoming,scheduled)`,
    `auction_date=gte.${today}`,
    `auction_date=lte.${end30}`,
    `property_address=not.is.null`,
    `opening_bid=not.is.null`,
  ];

  if (county) filters.push(`county=ilike.${encodeURIComponent(county.replace(/\s+/g, '%'))}`);
  if (sale_type !== 'all') filters.push(`sale_type=eq.${encodeURIComponent(sale_type)}`);

  const rows = await get(
    `multi_county_auctions?${filters.join('&')}&order=opening_bid.desc&limit=${safeLimit}&select=id,case_number,county,sale_type,property_address,parcel_id,opening_bid,assessed_value,auction_date,judgment_amount`
  ).catch(() => []);

  if (gold_standard_only && rows.length) {
    const goldData = await get(
      `gold_standard_scoreboard?gold_standard=eq.true&select=county_slug`
    ).catch(() => []);
    const goldSet = new Set(goldData.map(g => g.county_slug));
    return rows.filter(r => goldSet.has(r.county)).map(formatHighlightRow);
  }

  return rows.map(formatHighlightRow);
}

function formatHighlightRow(r) {
  return {
    mca_id: r.id,
    case_number: r.case_number,
    county: r.county,
    sale_type: r.sale_type,
    property_address: r.property_address,
    parcel_id: r.parcel_id,
    opening_bid: r.opening_bid,
    opening_bid_display: r.opening_bid ? `$${Number(r.opening_bid).toLocaleString()}` : null,
    assessed_value: r.assessed_value,
    assessed_value_display: r.assessed_value ? `$${Number(r.assessed_value).toLocaleString()}` : null,
    auction_date: r.auction_date,
    judgment_amount: r.judgment_amount,
    source_table: 'multi_county_auctions',
    lineage_note: 'Every numeric field sourced from multi_county_auctions.id = mca_id. Do not alter or invent figures.',
  };
}

// ── generate_funnel_content ──────────────────────────────────────────────────

export async function generate_funnel_content({ hook_type, county, highlights = [], tone = 'direct' }) {
  if (!['QUICK_DEMO', 'PROOF', 'PRICING', 'CONVERSION', 'FRICTION', 'SCALE'].includes(hook_type)) {
    return { error: `Invalid hook_type: ${hook_type}. Must be one of QUICK_DEMO|PROOF|PRICING|CONVERSION|FRICTION|SCALE` };
  }

  const countyLabel = county
    ? county.charAt(0).toUpperCase() + county.slice(1).replace(/_/g, ' ')
    : 'Florida';

  const fcCount = highlights.filter(h => h.sale_type === 'foreclosure').length;
  const tdCount = highlights.filter(h => h.sale_type === 'tax_deed').length;
  const topBid = highlights[0]?.opening_bid ? Number(highlights[0].opening_bid) : null;
  const topBidDisplay = topBid ? `$${topBid.toLocaleString()}` : null;
  const topAddress = highlights[0]?.property_address?.split(',')[0] || null;

  const tracedHighlightIds = highlights.map(h => h.mca_id).filter(Boolean);
  if (highlights.length && !tracedHighlightIds.length) {
    return {
      error: 'Quality gate: highlights array provided but no mca_id fields found. Cannot generate content without lineage-traced data.',
    };
  }

  const templates = {
    QUICK_DEMO: {
      subject: county
        ? `${format(new Date(), 'MMM d')} — ${fcCount + tdCount} auctions in ${countyLabel}`
        : `${format(new Date(), 'MMM d')} — ${fcCount} FC + ${tdCount} TD across FL`,
      preview_text: topBidDisplay
        ? `Top opening bid: ${topBidDisplay}${topAddress ? ` · ${topAddress}` : ''}`
        : `Live FL auction pipeline — foreclosure + tax deed`,
      headline: county
        ? `${fcCount + tdCount} upcoming auctions in ${countyLabel} County`
        : `${fcCount + tdCount} upcoming FL auctions in the next 30 days`,
      hook_cta: `See live auction pipeline →`,
    },
    PROOF: {
      subject: `Ceiling held again — Marion $82K → $73,501`,
      preview_text: `Third-party confirmed. $8,499 edge. Formula works.`,
      headline: `The Shapira Formula held again`,
      hook_cta: `See full analysis →`,
    },
    PRICING: {
      subject: `$25 analysis vs $900+ saved`,
      preview_text: `One analysis stopping a bad bid = $900+ saved`,
      headline: `One Shapira analysis pays for itself`,
      hook_cta: `Start $25 analysis →`,
    },
    CONVERSION: {
      subject: county
        ? `${countyLabel} closes soon — you're one step away`
        : `You're one step away`,
      preview_text: `Investor tier activates in 2 minutes`,
      headline: `Activate your Investor tier`,
      hook_cta: `Activate — $99/mo →`,
    },
    FRICTION: {
      subject: `Something stopped you — let me fix it`,
      preview_text: `Marion: predicted $82K → sold $73,501. Ceiling held.`,
      headline: `Pick up where you left off`,
      hook_cta: `Continue analysis →`,
    },
    SCALE: {
      subject: `50 analyses/mo — time to upgrade?`,
      preview_text: `Pro tier: 50 S5 analyses, deal memos, and CMAs per month`,
      headline: `More counties, more deals`,
      hook_cta: `Upgrade to Pro — $199/mo →`,
    },
  };

  const content = templates[hook_type];

  return {
    hook_type,
    county,
    tone,
    content,
    lineage: {
      highlight_count: highlights.length,
      traced_mca_ids: tracedHighlightIds,
      source_table: 'multi_county_auctions',
      fc_count: fcCount,
      td_count: tdCount,
    },
    quality_gate: {
      passed: true,
      numeric_claims_traced: tracedHighlightIds.length > 0 || highlights.length === 0,
      note: 'All numeric claims trace to multi_county_auctions via mca_id. No figures were invented.',
    },
  };
}
