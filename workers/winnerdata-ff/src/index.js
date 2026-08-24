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
 *   1. The schema rename to `winnerdata` never landed — the real schema is
 *      still `summitleads` (scripts/summitleads_pipeline.py, pipelines/
 *      winnerdata/momentum_delivery.py both hardcode summitleads.*).
 *   2. `summitleads` cannot be exposed via PostgREST for this project — a
 *      Management API db_schema PATCH is accepted and reads back correctly,
 *      but the live gateway never reflects it (tried: plain wait, explicit
 *      project restart, NOTIFY pgrst reload; each retried, none took). This
 *      matches summitleads_pipeline.py's own docstring: "PostgREST does not
 *      expose the summitleads schema" — a pre-existing, already-documented
 *      limitation, not something broken by this change.
 * Fix: public schema SECURITY DEFINER RPC functions (ff_healthz,
 * ff_portal_leads, ff_get_lead, ff_upsert_response, ff_record_bind — see
 * supabase/migrations/20260824_winnerdata_ff_worker_rpc.sql), called via
 * /rest/v1/rpc/<fn> with the same embedded anon key pattern. The function
 * body is the access boundary: org_id is validated inside every function
 * against the one live tenant before touching summitleads.* — a mismatched
 * org_id returns zero rows, proven live via curl before this Worker was
 * written (pasted in the issue completion comment). RLS policies also exist
 * on the underlying tables as defense-in-depth for if/when direct exposure
 * is ever fixed, but are not the active boundary today.
 *
 * lead_properties does not exist as a table — spec's other wrong assumption.
 * The real per-lead property/auction join is summitleads.v_producer_intake
 * (added 2026-08-23), which ff_get_lead / ff_portal_leads read from.
 */

import TEMPLATE_A from '../../../templates/FF_TEMPLATE_A_AUCTION_SALES.html';
import TEMPLATE_B from '../../../templates/FF_TEMPLATE_B_HOMEOWNER.html';

const SUPABASE_URL = 'https://mocerqjnksmhcjzxrewo.supabase.co';
// Anon key — safe to embed in source, same as src/worker.js:37. RLS/RPC
// validation (not secrecy of this key) is the actual access boundary.
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1MzI1MjYsImV4cCI6MjA4MDEwODUyNn0.ySFJIOngWWB0aqYra4PoGFuqcbdHOx1ZV6T9-klKQDw';
// Single live tenant (summitleads.organizations, verified 2026-08-24). v1 is
// explicitly single-tenant scope — the Worker never accepts org_id from the
// client; every RPC call uses this constant.
const ORG_ID = '032f4717-545f-4a18-b48b-28ea4257699d';

const BANNER = {
  tax_deed: { cls: 'tax_deed', label: 'TAX DEED SALE' },
  foreclosure: { cls: 'foreclosure', label: 'FORECLOSURE SALE' },
};

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

function renderFF(data) {
  const lead = data;
  const auction = data.auction || {};
  const parcel = data.parcel || {};
  const responses = data.responses || {};

  const ownerOccupied = parcel.own_addr1 && parcel.phy_addr1 && parcel.own_addr1 === parcel.phy_addr1;
  const template = ownerOccupied ? TEMPLATE_B : TEMPLATE_A;

  const banner = BANNER[auction.sale_type] || { cls: 'not_established', label: 'SALE TYPE NOT ESTABLISHED' };
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

  const values = {
    lead_id: lead.lead_id,
    entity_name: esc(lead.entity_name),
    first_name: esc(firstName),
    last_name: esc(lastName),
    mailing_address: esc(parcel.own_addr1),
    risk_address_full: esc(auction.property_address || parcel.phy_addr1),
    producer_name: 'Mariam Shapira',
    prepared_date: new Date().toISOString().slice(0, 10),
    agency_name: 'Protection Partners',
    case_number: esc(auction.case_number),
    parcel_id: esc(lead.parcel_id),
    county_just_value: money(parcel.jv),
    assessed_value: money(parcel.jv),
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
  };

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
