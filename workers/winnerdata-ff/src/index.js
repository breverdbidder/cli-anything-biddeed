/**
 * Winner Data FF Worker — workers/winnerdata-ff/src/index.js
 * Built 2026-08-24 per issue #19392 comments 5390376020 (routes/security spec)
 * and 5390411245 (deploy pipeline). Single-tenant v1 — see issue for the
 * explicitly out-of-scope multi-tenant/orgs spec.
 *
 * Architecture cloned from src/worker.js (worker-biddeed-staging): plain
 * Cloudflare Worker, server-rendered HTML, no build step, no framework. The
 * only difference from that reference is how the DB is reached — see the
 * DB ACCESS note below.
 *
 * DB ACCESS: the issue spec assumed raw PostgREST table reads against a
 * `winnerdata` schema, gated by RLS, using an embedded anon key (same as
 * SUPABASE_KEY at src/worker.js:37). Two things about that turned out not to
 * hold, both live-verified before writing this file:
 *   1. At the time this file was written (2026-08-24) the schema rename to
 *      `winnerdata` had not landed yet — the real schema was still
 *      `summitleads`. Issue #19486 (2026-08-26) finished that rename live
 *      (`ALTER SCHEMA summitleads RENAME TO winnerdata`); scripts/
 *      winnerdata_pipeline.py and pipelines/winnerdata/momentum_delivery.py
 *      now correctly hardcode winnerdata.* too.
 *   2. `winnerdata` (formerly `summitleads`) cannot be exposed via
 *      PostgREST for this project — a Management API db_schema PATCH is
 *      accepted and reads back correctly, but the live gateway never
 *      reflects it (tried: plain wait, explicit project restart, NOTIFY
 *      pgrst reload; each retried, none took). This is a pre-existing,
 *      already-documented limitation independent of the schema's name, not
 *      something the 2026-08-26 rename changed either way.
 * Fix: public schema SECURITY DEFINER RPC functions (ff_healthz,
 * ff_portal_leads, ff_get_lead, ff_upsert_response, ff_record_bind — see
 * supabase/migrations/20260824_winnerdata_ff_worker_rpc.sql), called via
 * /rest/v1/rpc/<fn> with the same embedded anon key pattern. The function
 * body is the access boundary: org_id is validated inside every function
 * against the one live tenant before touching winnerdata.* — a mismatched
 * org_id returns zero rows, proven live via curl before this Worker was
 * written (pasted in the issue completion comment). RLS policies also exist
 * on the underlying tables as defense-in-depth for if/when direct exposure
 * is ever fixed, but are not the active boundary today.
 *
 * lead_properties does not exist as a table — spec's other wrong assumption.
 * The real per-lead property/auction join is winnerdata.v_producer_intake
 * (added 2026-08-23), which ff_get_lead / ff_portal_leads read from.
 */

import TEMPLATE_A from '../../../templates/FF_TEMPLATE_A_AUCTION_SALES.html';
import TEMPLATE_B from '../../../templates/FF_TEMPLATE_B_HOMEOWNER.html';

const SUPABASE_URL = 'https://mocerqjnksmhcjzxrewo.supabase.co';
// Anon key — safe to embed in source, same as src/worker.js:37. RLS/RPC
// validation (not secrecy of this key) is the actual access boundary.
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1MzI1MjYsImV4cCI6MjA4MDEwODUyNn0.ySFJIOngWWB0aqYra4PoGFuqcbdHOx1ZV6T9-klKQDw';
// Single live tenant (winnerdata.organizations, verified 2026-08-24). v1 is
// explicitly single-tenant scope — the Worker never accepts org_id from the
// client; every RPC call uses this constant.
const ORG_ID = '032f4717-545f-4a18-b48b-28ea4257699d';

const BANNER = {
  tax_deed: { cls: 'tax_deed', label: 'TAX DEED SALE' },
  foreclosure: { cls: 'foreclosure', label: 'FORECLOSURE SALE' },
};

// issue #19434: MLS-sourced leads have no auction.sale_type, so the old
// `BANNER[auction.sale_type] || not_established` fallback mislabeled every
// MLS lead "SALE TYPE NOT ESTABLISHED" (implies unknown, not "not an
// auction"). Keyed by lead_source_type instead for these two.
const MLS_BANNER = {
  mls_active: { cls: 'mls_active', label: 'ACTIVE LISTING' },
  mls_pending: { cls: 'mls_pending', label: 'PENDING LISTING' },
};

// DOR_UC labels + commercial-prefix rule, ported from
// scripts/portfolio_fact_finder_render.py's DOR_UC_MAP / COMMERCIAL_DOR_PREFIXES
// so the chat-built portfolio FFs and this Worker apply identical labels.
const DOR_UC_LABELS = {
  '000': 'Vacant Residential', '001': 'Single Family', '002': 'Mobile Home',
  '003': 'Multi-Family <10', '004': 'Condo', '005': 'Co-op', '006': 'Retirement',
  '007': 'Misc Residential', '008': 'Multi-Family 10+', '009': 'Residential Common',
  '010': 'Vacant Commercial', '011': 'Retail', '012': 'Mixed Use', '017': 'Office',
  '018': 'Professional Service', '019': 'Hotel/Motel', '021': 'Light Industrial',
  '022': 'Heavy Industrial', '027': 'Auto Service', '028': 'Parking',
};
const COMMERCIAL_DOR_PREFIXES = ['01', '02'];

async function rpc(fn, body) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`rpc ${fn} failed: ${res.status} ${text}`);
  }
  return res.json();
}

function money(n) {
  if (n === null || n === undefined) return 'Not established';
  return `$${Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function esc(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function computeFlags(lead, parcel) {
  const flags = [];
  if (parcel.eff_yr_blt && parcel.eff_yr_blt < 1990) {
    flags.push('Pre-1990 construction — 4-point inspection required');
  }
  if (parcel.dor_uc === '004' || parcel.dor_uc === '008') {
    flags.push('DOR use code indicates commercial — not eligible for DP3');
  }
  if (parcel.dor_uc === '002') {
    flags.push('DOR use code indicates mobile/manufactured home');
  }
  if (parcel.no_res_unt && parcel.no_res_unt >= 3) {
    flags.push('3+ residential units — umbrella policy recommended');
  }
  if (parcel.act_yr_blt && parcel.eff_yr_blt && parcel.act_yr_blt !== parcel.eff_yr_blt) {
    flags.push('New construction / major renovation — consider builders risk');
  }
  const ownerOccupied = parcel.own_addr1 && parcel.phy_addr1 && parcel.own_addr1 === parcel.phy_addr1;
  if (ownerOccupied) {
    flags.push('Owner-occupied — HO3, not DP3');
  }
  if (!lead.contact_email) {
    flags.push('No email on file — phone-only contact');
  }
  if (!flags.length) flags.push('No underwriting flags triggered');
  return flags.map((f) => `<li>${esc(f)}</li>`).join('');
}

// issue #19434: Property Profile block on Template B now branches on
// lead_source_type instead of always assuming auction-sourced data. Default
// stays 'auction' when data.lead_source_type is absent so the 22 existing
// auction-track leads (none of which set this field) render byte-identical
// rows to before this change -- only an explicit 'mls_active'/'mls_pending'
// switches to the MLS block. Template A is untouched (still hardcodes its
// own auction-only block) since it never receives MLS-sourced leads.
function profileRow(label, value) {
  return `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`;
}

function auctionProfileRows({ saleTypeLabel, auctionDate, daysSinceAuction, soldAmount, caseNumber, parcelId, ctRecordingDate }) {
  return [
    profileRow('Sale Type', saleTypeLabel),
    profileRow('Auction Date', auctionDate),
    profileRow('Days Since Auction', daysSinceAuction),
    profileRow('Sold Amount', soldAmount),
    profileRow('Case Number', caseNumber),
    profileRow('Parcel', parcelId),
    profileRow('Certificate-of-Title Recording Date', ctRecordingDate),
  ].join('\n      ');
}

function mlsProfileRows(mls, parcelId) {
  return [
    profileRow('MLS Status', mls.status || 'Not established'),
    profileRow('List Date', mls.list_date || 'Not established'),
    profileRow('List Price', mls.list_price !== null && mls.list_price !== undefined ? money(mls.list_price) : 'Not established'),
    profileRow('MLS Number', mls.mls_number || 'Not established'),
    profileRow('Days on Market', mls.days_on_market ?? 'Not established'),
    profileRow('Parcel', parcelId || 'Not established'),
  ].join('\n      ');
}

function callScript(lead, auction) {
  const days = auction.auction_date
    ? Math.floor((Date.now() - Date.parse(auction.auction_date)) / 86400000)
    : null;
  return [
    auction.case_number ? `Certificate of title recorded, case ${auction.case_number}.` : 'Certificate of title recorded.',
    days !== null ? `${days} days ago.` : null,
    auction.sold_amount ? `Winning bid was ${money(auction.sold_amount)}.` : null,
    `Calling ${esc(lead.contact_name || lead.entity_name)} re: property insurance on the new acquisition.`,
  ].filter(Boolean).join(' ');
}

// issue P0 (2026-08-26) Gap 2: "one lead = one buyer NAME regardless of
// property count" (Ariel, Aug 23 2026, #19392 comment 5390376020).
// ff_get_lead's `portfolio` array (winnerdata.owner_portfolio, keyed by
// normalized entity_name) carries every property this buyer holds, not just
// the one they won at auction. When that array has 2+ rows it IS the
// property list; otherwise fall back to the single parcel/auction object
// ff_get_lead already returned -- either way callers get one unified
// `properties` array so table-building and cross-sell logic never branch
// on portfolio-vs-single.
function buildProperties(data) {
  const portfolio = Array.isArray(data.portfolio) ? data.portfolio : [];
  if (portfolio.length >= 2) {
    return portfolio.map((p) => ({
      address: p.address,
      county: p.county,
      dor_uc: p.dor_uc,
      no_buldng: p.no_buldng,
      jv: p.jv,
      av_sd: p.av_sd,
      lnd_val: p.lnd_val,
      acquisition_source: p.acquisition_source,
      case_number: p.case_number,
    }));
  }
  const parcel = data.parcel || {};
  const auction = data.auction || {};
  return [{
    address: auction.property_address || parcel.phy_addr1,
    county: auction.county,
    dor_uc: parcel.dor_uc,
    no_buldng: null,
    jv: parcel.jv,
    av_sd: parcel.av_sd,
    lnd_val: parcel.lnd_val,
    acquisition_source: 'auction_win',
    case_number: auction.case_number,
  }];
}

// issue P0 Gap 3: cross-sell doctrine, ported from
// scripts/portfolio_fact_finder_render.py's bundle_doctrine() so this
// Worker and the chat-built portfolio FFs apply the identical rule.
// SCOPE BOUNDARY (Aug 25 2026): property insurance only -- no auto/vehicle
// cross-sell, ever. Coastal/flood is deliberately NOT included here: unlike
// the Python script's batch run, this Worker has no per-request access to
// flood_zones (real polygon coverage only exists for Brevard as of
// 2026-08-25) -- omitting it is honest; a fabricated flood flag would not be.
function crossSellNotes(properties) {
  const notes = [];
  const count = properties.length;
  if (count >= 2) {
    notes.push(`${count} properties on file for this buyer — umbrella liability conversation warranted (2+ property trigger).`);
  }
  if (count >= 5) {
    notes.push(`${count} properties — master policy / scheduled-property conversation warranted (5+ property trigger).`);
  }
  const commercial = properties.filter((p) => {
    const prefix = (p.dor_uc || '').slice(0, 2);
    return COMMERCIAL_DOR_PREFIXES.includes(prefix) || (p.no_buldng || 0) >= 3;
  });
  if (commercial.length) {
    notes.push(`${commercial.length} propert${commercial.length === 1 ? 'y is' : 'ies are'} commercial-use or 3+ buildings — commercial BOP conversation warranted.`);
  }
  return notes;
}

function crossSellSectionHtml(properties, isTemplateA) {
  const notes = crossSellNotes(properties);
  if (!notes.length) return '';
  const items = notes.map((n) => `<li>${esc(n)}</li>`).join('');
  const tag = isTemplateA ? 'section' : 'div';
  const cls = isTemplateA ? 'cross' : 'block cross';
  return `<${tag} class="${cls}">\n    <h2>Cross-Sell Notes</h2>\n    <ul>${items}</ul>\n  </${tag}>`;
}

function propertyTableRows(properties) {
  return properties.map((p) => {
    const useLabel = DOR_UC_LABELS[p.dor_uc] || (p.dor_uc ? `DOR-${esc(p.dor_uc)}` : 'Not established');
    const tag = p.acquisition_source === 'auction_win' ? 'Auction Win' : 'Prior Holding';
    const countyLabel = p.county ? esc(String(p.county).replace(/_/g, ' ')) : 'Unknown county';
    return `<tr>
        <td>${esc(p.address) || 'Address unknown'}<div class="ptable-sub">${countyLabel} County &middot; ${esc(tag)}</div></td>
        <td>${esc(useLabel)}</td>
        <td>${money(p.jv)}</td>
        <td>${money(p.av_sd)}</td>
        <td>${esc(p.case_number) || '&mdash;'}</td>
      </tr>`;
  }).join('\n      ');
}

function propertySectionHeading(properties, auctionDateLabel) {
  if (properties.length > 1) {
    return `Property Portfolio &mdash; ${properties.length} Properties on File`;
  }
  return `Subject Property &mdash; Auction Win ${auctionDateLabel}`;
}

function propertyTotalsLine(properties) {
  const totalJv = properties.reduce((sum, p) => sum + (typeof p.jv === 'number' ? p.jv : 0), 0);
  const counties = Array.from(new Set(properties.map((p) => p.county).filter(Boolean)));
  const propertyWord = properties.length === 1 ? 'property' : 'properties';
  const countyWord = (counties.length || 1) === 1 ? 'county' : 'counties';
  return `${properties.length} ${propertyWord} across ${counties.length || 1} ${countyWord} &middot; total Just Value ${money(totalJv)}`;
}

function buyerOfRecordRows(lead, properties) {
  const totalJv = properties.reduce((sum, p) => sum + (typeof p.jv === 'number' ? p.jv : 0), 0);
  const rows = [
    ['Buyer of Record', lead.entity_name],
    ['Contact Name', lead.contact_name],
    ['Product Line', lead.product_line],
    ['Properties on File', String(properties.length)],
    ['Total Just Value', money(totalJv)],
  ];
  return rows.map(([label, val]) => `<tr><td class="label">${esc(label)}</td><td class="val">${esc(val) || 'Not established'}</td></tr>`).join('\n      ');
}

function contactRows(lead) {
  const phone = lead.contact_phone ? `<a href="tel:${esc(lead.contact_phone)}">${esc(lead.contact_phone)}</a>` : 'Not on file';
  const email = lead.contact_email ? `<a href="mailto:${esc(lead.contact_email)}">${esc(lead.contact_email)}</a>` : 'Not on file';
  const rows = [
    ['Phone', phone],
    ['Email', email],
    ['Consent Status', esc(lead.consent_status) || 'none'],
  ];
  return rows.map(([label, val]) => `<div class="contact-row"><span class="contact-label">${esc(label)}</span><span class="contact-value">${val}</span></div>`).join('\n      ');
}

function contactStatusLabel(consentStatus) {
  return consentStatus && consentStatus !== 'none' ? esc(consentStatus).toUpperCase() : 'PROSPECT — NO CONSENT ON FILE';
}

function contactComplianceNote(consentStatus) {
  return consentStatus && consentStatus !== 'none'
    ? 'Consent on file for this contact -- see responses log for detail.'
    : 'No outbound-contact consent on file. Producer contact only; do not use this data for direct-to-consumer solicitation.';
}

function renderFF(data) {
  const lead = data;
  const auction = data.auction || {};
  const parcel = data.parcel || {};
  const responses = data.responses || {};

  const ownerOccupied = parcel.own_addr1 && parcel.phy_addr1 && parcel.own_addr1 === parcel.phy_addr1;
  const template = ownerOccupied ? TEMPLATE_B : TEMPLATE_A;

  const leadSourceType = data.lead_source_type === 'mls_active' || data.lead_source_type === 'mls_pending'
    ? data.lead_source_type
    : 'auction';
  const banner = leadSourceType === 'auction'
    ? (BANNER[auction.sale_type] || { cls: 'not_established', label: 'SALE TYPE NOT ESTABLISHED' })
    : MLS_BANNER[leadSourceType];
  const bldgVal = parcel.bldg_val;
  const coverageA = bldgVal !== null && bldgVal !== undefined ? bldgVal * 1.25 : null;

  const nameParts = (lead.contact_name || lead.entity_name || '').split(' ');
  const firstName = nameParts[0] || '';
  const lastName = nameParts.slice(1).join(' ') || '';

  // Verification badge is mandatory and never blank -- ff_get_lead's
  // `verification` object always resolves to a badge + reason (see
  // supabase/migrations/20260824_ff_verification_badge_rpc.sql), but this
  // Worker still defaults defensively in case an older cached RPC result
  // (or a lead_id predating that migration) lacks the key.
  const verification = data.verification || {};
  const verified = verification.badge === 'VERIFIED';
  const appraiserLink = verification.appraiser_url
    ? `<a href="${esc(verification.appraiser_url)}" target="_blank" rel="noopener">View county property appraiser record &rarr;</a>`
    : '<span>No property appraiser URL on file for this county.</span>';

  // issue #19434 requirement 1: producer_name/agency_name are hard-required
  // on every seller FF -- fail closed rather than render with a blank
  // producer/agency. Currently always the dogfood-stage constants below, but
  // the check stays live so a future per-org value can never silently blank.
  const producerName = 'Mariam Shapira';
  const agencyName = 'Protection Partners';
  if (!producerName.trim() || !agencyName.trim()) {
    throw new Error('producer_name and agency_name are required and cannot be blank');
  }

  const mls = data.mls || {};
  const propertyProfileRows = leadSourceType === 'auction'
    ? auctionProfileRows({
        saleTypeLabel: esc(auction.sale_type) || 'Not established',
        auctionDate: esc(auction.auction_date) || 'Not established',
        daysSinceAuction: auction.auction_date
          ? Math.floor((Date.now() - Date.parse(auction.auction_date)) / 86400000)
          : 'Not established',
        soldAmount: money(auction.sold_amount),
        caseNumber: esc(auction.case_number) || 'Not established',
        parcelId: esc(lead.parcel_id),
        ctRecordingDate: esc(responses.ct_recording_date) || 'Not yet recorded',
      })
    : mlsProfileRows(mls, esc(lead.parcel_id));

  const values = {
    lead_id: lead.lead_id,
    entity_name: esc(lead.entity_name),
    first_name: esc(firstName),
    last_name: esc(lastName),
    mailing_address: esc(parcel.own_addr1),
    risk_address_full: esc(auction.property_address || parcel.phy_addr1),
    producer_name: producerName,
    prepared_date: new Date().toISOString().slice(0, 10),
    agency_name: agencyName,
    case_number: esc(auction.case_number),
    parcel_id: esc(lead.parcel_id),
    // issue P0 Gap 4 (2026-08-26): county_just_value and assessed_value used
    // to both read fp.jv -- fl_parcels carries a distinct av_sd (assessed
    // value) column that was simply never wired here. No fallback to jv when
    // av_sd is null (that would silently reintroduce the same conflation) --
    // "Not established" is the honest value per money()'s existing contract.
    county_just_value: money(parcel.jv),
    assessed_value: money(parcel.av_sd),
    land_value: money(parcel.lnd_val),
    building_value: money(bldgVal),
    coverage_a: money(coverageA),
    construction_type: esc(parcel.const_clas) || 'Not established',
    policy_type: ownerOccupied ? 'HO3' : 'DP3',
    banner_class: banner.cls,
    banner_label: banner.label,
    sale_type_label: esc(auction.sale_type) || 'Not established',
    auction_date: esc(auction.auction_date) || 'Not established',
    sold_amount: money(auction.sold_amount),
    opening_bid: money(auction.opening_bid),
    prior_owner: esc(parcel.own_name) || 'Not established',
    ct_recording_date: esc(responses.ct_recording_date) || '',
    days_since_auction: auction.auction_date
      ? Math.floor((Date.now() - Date.parse(auction.auction_date)) / 86400000)
      : 'Not established',
    date_of_birth: esc(responses.date_of_birth) || '',
    roof_shape: esc(responses.roof_shape) || 'Collect on call',
    underwriting_flags: computeFlags(lead, parcel),
    call_script: esc(callScript(lead, auction)),
    verify_badge_class: verified ? 'verified' : 'not-verified',
    verify_badge_label: verified ? 'VERIFIED' : 'NOT VERIFIED',
    verify_reason: esc(verification.reason) || 'No property appraiser cross-verification available for this county.',
    appraiser_link: appraiserLink,
    property_profile_rows: propertyProfileRows,
  };

  // issue P0 Gap 2/3 (2026-08-26): unified properties array drives both the
  // portfolio table (Template A) and cross-sell doctrine (both templates).
  // properties.length === 1 for the ~all-leads-today case where
  // ff_get_lead's `portfolio` has fewer than 2 rows -- crossSellNotes()
  // naturally emits nothing for a single non-commercial property, so this
  // doesn't change existing single-property output except adding the (empty)
  // {{cross_sell_section}} placeholder.
  const properties = buildProperties(data);
  values.property_section_heading = propertySectionHeading(properties, values.auction_date);
  values.property_rows = propertyTableRows(properties);
  values.property_totals_line = propertyTotalsLine(properties);
  values.buyer_of_record_rows = buyerOfRecordRows(lead, properties);
  values.contact_rows = contactRows(lead);
  values.contact_status_label = contactStatusLabel(lead.consent_status);
  values.contact_compliance_note = contactComplianceNote(lead.consent_status);
  values.cross_sell_section = crossSellSectionHtml(properties, template === TEMPLATE_A);

  return template.replace(/{{(\w+)}}/g, (_, key) => (values[key] !== undefined ? values[key] : ''));
}

function jsonResponse(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

async function handlePortal() {
  const leads = await rpc('ff_portal_leads', { p_org_id: ORG_ID });
  const rows = leads.map((l) => `
    <tr>
      <td><a href="/ff/${l.lead_id}">${esc(l.property_address || l.entity_name)}</a></td>
      <td>${esc(l.entity_name)}</td>
      <td>${esc(l.contact_phone) || '—'}</td>
      <td>${esc(l.sale_type) || '—'}</td>
      <td>${l.days_since_auction ?? '—'}</td>
      <td>${esc(l.consent_status)}</td>
      <td>${l.is_bound ? 'Bound' : '—'}</td>
    </tr>`).join('');

  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Winner Data Portal</title>
<style>
  body{font-family:Arial,Helvetica,sans-serif;background:#faf9f5;color:#141413;margin:0;padding:1.5rem}
  table{width:100%;border-collapse:collapse;background:#fff}
  th,td{padding:.5rem .75rem;border-bottom:1px solid #b0aea5;text-align:left;font-size:.9rem}
  th{color:#d97757;text-transform:uppercase;font-size:.75rem}
  a{color:#141413}
</style></head><body>
<h1>Winner Data — Protection Partners Portal</h1>
<table>
  <thead><tr><th>Property</th><th>Buyer</th><th>Phone</th><th>Sale Type</th><th>Days Since Auction</th><th>Consent</th><th>Bind</th></tr></thead>
  <tbody>${rows}</tbody>
</table>
</body></html>`;
  return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8' } });
}

async function handlePortalBind(request) {
  const body = await request.json().catch(() => ({}));
  if (!body.lead_id) return jsonResponse({ ok: false, error: 'lead_id required' }, 400);
  const result = await rpc('ff_record_bind', {
    p_org_id: ORG_ID,
    p_lead_id: body.lead_id,
    p_premium_cents: body.premium_cents ?? null,
    p_product_line: body.product_line ?? null,
  });
  return jsonResponse(result, result.ok ? 200 : 400);
}

async function handleFF(leadId) {
  const data = await rpc('ff_get_lead', { p_org_id: ORG_ID, p_lead_id: leadId });
  if (!data) return new Response('Not found', { status: 404 });
  return new Response(renderFF(data), { headers: { 'content-type': 'text/html; charset=utf-8' } });
}

async function handleFFSubmit(leadId, request) {
  const form = await request.formData();
  const fields = ['date_of_birth', 'roof_shape', 'ct_recording_date', 'occupancy', 'call_notes'];
  for (const field of fields) {
    const value = form.get(field);
    if (value === null || value === '') continue;
    await rpc('ff_upsert_response', {
      p_org_id: ORG_ID,
      p_lead_id: leadId,
      p_property_id: null,
      p_field: field,
      p_value: String(value),
      p_updated_by: 'portal',
    });
  }
  if (form.get('consent_obtained') === 'true') {
    await rpc('ff_upsert_response', {
      p_org_id: ORG_ID,
      p_lead_id: leadId,
      p_property_id: null,
      p_field: 'consent_obtained',
      p_value: 'true',
      p_updated_by: 'portal',
    });
    await rpc('ff_upsert_response', {
      p_org_id: ORG_ID,
      p_lead_id: leadId,
      p_property_id: null,
      p_field: 'consent_timestamp',
      p_value: new Date().toISOString(),
      p_updated_by: 'portal',
    });
  }
  return Response.redirect(new URL(`/ff/${leadId}`, 'https://ff.winnerdataai.com').toString(), 303);
}

async function handleHealthz() {
  const data = await rpc('ff_healthz', {});
  return jsonResponse(data);
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const { pathname } = url;

    try {
      if (pathname === '/healthz') return handleHealthz();
      if (pathname === '/portal' && request.method === 'GET') return handlePortal();
      if (pathname === '/portal/bind' && request.method === 'POST') return handlePortalBind(request);

      const ffMatch = pathname.match(/^\/ff\/([0-9a-fA-F-]{36})$/);
      if (ffMatch && request.method === 'GET') return handleFF(ffMatch[1]);
      if (ffMatch && request.method === 'POST') return handleFFSubmit(ffMatch[1], request);

      return new Response('Not found', { status: 404 });
    } catch (err) {
      return jsonResponse({ ok: false, error: String(err) }, 500);
    }
  },
};
