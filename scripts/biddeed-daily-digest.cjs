#!/usr/bin/env node
/**
 * BidDeed.AI — Daily Branded Digest
 * Node 22+ required (native WebSocket — no ws package needed)
 * Fixed: Aug 3 2026 — removed ws transport, use Node 22 native WebSocket
 */

const { createClient } = require('@supabase/supabase-js');
const { Resend }       = require('resend');
const { format, addDays } = require('date-fns');
const crypto           = require('crypto');

// Node 22 has native WebSocket — createClient works without ws transport
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY,
  { auth: { persistSession: false } }
);
const resend = new Resend(process.env.RESEND_API_KEY);
const BASE   = 'https://biddeed.ai';
const UNSUB_FN_URL = `${process.env.SUPABASE_URL}/functions/v1/email-unsubscribe`;
const TODAY  = format(new Date(), 'yyyy-MM-dd');
const END30  = format(addDays(new Date(), 30), 'yyyy-MM-dd');
const LABEL  = format(new Date(), 'EEEE, MMMM d, yyyy');

// ── GTM-5 (#20034): one-click unsubscribe — HMAC-signed link, no login needed.
// Signature key comes from the same shared secret the email-unsubscribe edge
// function verifies against (cli_anything_shared_secret via the sanctioned
// cli_anything_get_secret() accessor — never held as a raw env var here).
let unsubSecret = null;
async function getUnsubSecret() {
  if (unsubSecret) return unsubSecret;
  const { data, error } = await supabase.rpc('cli_anything_get_secret', { p_name: 'cli_anything_shared_secret' });
  if (error || !data) throw new Error(`Unsubscribe signing secret unavailable: ${error?.message}`);
  unsubSecret = data;
  return unsubSecret;
}
async function unsubscribeUrl(email) {
  const secret = await getUnsubSecret();
  const sig = crypto.createHmac('sha256', secret).update(email.toLowerCase()).digest('hex');
  return `${UNSUB_FN_URL}?email=${encodeURIComponent(email)}&sig=${sig}`;
}

// ── STEP 1: Build twin snapshot from live MCA data ────────────────────────────
async function getTwinSnapshot() {
  console.log('Building county snapshot from live multi_county_auctions...');

  const { data: live, error } = await supabase
    .from('multi_county_auctions')
    .select('county, sale_type, auction_date')
    .in('auction_status', ['upcoming', 'scheduled'])
    .gte('auction_date', TODAY)
    .lte('auction_date', END30);

  if (error || !live?.length) {
    console.log(`Live query returned nothing (${error?.message}), trying stale snapshot...`);
    const { data: stale } = await supabase
      .from('county_twin_snapshot')
      .select('*')
      .order('snapshot_date', { ascending: false })
      .limit(67);
    console.log(`Stale snapshot: ${stale?.length || 0} counties`);
    return stale || [];
  }

  // Aggregate inline
  const map = {};
  for (const row of live) {
    if (!map[row.county]) {
      map[row.county] = { county: row.county, fc_upcoming_30d: 0, td_upcoming_30d: 0, fc_next_auction_date: null, td_next_auction_date: null, is_gold_standard: false };
    }
    const isFC = row.sale_type === 'foreclosure';
    if (isFC) {
      map[row.county].fc_upcoming_30d++;
      if (!map[row.county].fc_next_auction_date || row.auction_date < map[row.county].fc_next_auction_date)
        map[row.county].fc_next_auction_date = row.auction_date;
    } else {
      map[row.county].td_upcoming_30d++;
      if (!map[row.county].td_next_auction_date || row.auction_date < map[row.county].td_next_auction_date)
        map[row.county].td_next_auction_date = row.auction_date;
    }
  }

  // Gold standard flags
  const { data: gold } = await supabase
    .from('gold_standard_scoreboard')
    .select('county_slug, gold_standard')
    .eq('gold_standard', true);
  const goldSet = new Set((gold || []).map(g => g.county_slug));

  const snapshot = Object.values(map).map(c => ({
    ...c,
    total_upcoming_30d: c.fc_upcoming_30d + c.td_upcoming_30d,
    is_gold_standard: goldSet.has(c.county),
  })).filter(c => c.total_upcoming_30d > 0)
    .sort((a, b) => b.total_upcoming_30d - a.total_upcoming_30d);

  console.log(`✅ Snapshot: ${snapshot.length} counties, ${live.length} auctions`);
  return snapshot;
}

// ── STEP 2: Top auctions for county ──────────────────────────────────────────
async function getTopAuctions(county) {
  const { data } = await supabase
    .from('multi_county_auctions')
    .select('county, sale_type, auction_date, property_address, opening_bid, assessed_value, case_number, parcel_id')
    .eq('county', county)
    .in('auction_status', ['upcoming', 'scheduled'])
    .gte('auction_date', TODAY)
    .lte('auction_date', END30)
    .not('property_address', 'is', null)
    .not('opening_bid', 'is', null)
    .order('opening_bid', { ascending: false })
    .limit(3);
  return data || [];
}

// ── STEP 3: Pull leads (GTM-5 #20034 consent gate) ─────────────────────────────
// Recipients = lead_profiles WHERE email IS NOT NULL AND (email_consent OR
// marketing_consent) AND email NOT IN email_opt_outs/email_suppressions.
// unsubscribe_link-sourced rows already carry email_consent=false and
// marketing_consent=false (verified in Supabase), so the consent predicate
// alone excludes them — the opt-out/suppression check is a second,
// independent layer that survives even if a consent flag is ever re-flipped.
async function getOptedOutEmails() {
  const [{ data: optOuts, error: e1 }, { data: suppressed, error: e2 }] = await Promise.all([
    supabase.from('email_opt_outs').select('email'),
    supabase.from('email_suppressions').select('email'),
  ]);
  if (e1) throw new Error(`email_opt_outs fetch: ${e1.message}`);
  if (e2) throw new Error(`email_suppressions fetch: ${e2.message}`);
  return new Set([...(optOuts || []), ...(suppressed || [])].map(r => r.email.toLowerCase()));
}

async function getLeads() {
  if (process.env.TEST_EMAIL) {
    console.log(`TEST MODE → ${process.env.TEST_EMAIL}`);
    return [{ id: 'test', email: process.env.TEST_EMAIL, name: 'Ariel', county: 'brevard', stage: 'lead', hooks_triggered: [], messages_count: 0, score: 0, tier: null }];
  }

  const optedOut = await getOptedOutEmails();

  const { data, error } = await supabase
    .from('lead_profiles')
    .select('id, email, name, county, stage, hooks_triggered, messages_count, score, tier, email_consent, marketing_consent')
    .not('stage', 'eq', 'unsubscribed')
    .not('email', 'is', null)
    .or('email_consent.eq.true,marketing_consent.eq.true');
  if (error) throw new Error(`Lead fetch: ${error.message}`);

  const consented = (data || []).filter(l => !optedOut.has(l.email.toLowerCase()));
  console.log(`✅ Consented leads: ${consented.length} (${(data || []).length} passed DB consent filter, ${(data || []).length - consented.length} excluded by opt-out/suppression list)`);

  // Independent hard-fail check: recipient count must never exceed the
  // consented count. Re-runs the exact same predicate as a second query so a
  // future accidental relaxation of the filter above cannot silently ship.
  const { count: consentedCount, error: e3 } = await supabase
    .from('lead_profiles')
    .select('id', { count: 'exact', head: true })
    .not('email', 'is', null)
    .or('email_consent.eq.true,marketing_consent.eq.true');
  if (e3) throw new Error(`Consent count check: ${e3.message}`);
  if (consented.length > consentedCount) {
    throw new Error(`REFUSING TO SEND: recipient count (${consented.length}) exceeds consented count (${consentedCount}) — consent gate regression`);
  }

  return consented;
}

// ── Hook classifier ───────────────────────────────────────────────────────────
function classifyHook(lead) {
  const hooks = lead.hooks_triggered || [];
  if (lead.tier && lead.tier !== 'free') return 'SCALE';
  if (hooks.includes('FRICTION'))        return 'FRICTION';
  if ((lead.score || 0) >= 70)           return 'CONVERSION';
  if (hooks.includes('PROOF'))           return 'PROOF';
  if (hooks.includes('PRICING'))         return 'PRICING';
  if ((lead.messages_count || 0) === 0)  return 'QUICK_DEMO';
  return 'PROOF';
}

// ── County table rows ─────────────────────────────────────────────────────────
function countyRows(snapshot, leadCounty) {
  const sorted = [...snapshot].sort((a, b) => {
    if (a.county === leadCounty) return -1;
    if (b.county === leadCounty) return 1;
    return b.total_upcoming_30d - a.total_upcoming_30d;
  }).slice(0, 8);

  return sorted.map((c, i) => {
    const bg    = i % 2 === 0 ? '#0F2035' : '#020617';
    const label = c.county.charAt(0).toUpperCase() + c.county.slice(1).replace(/_/g,' ');
    const isMe  = c.county === leadCounty;
    const fcNext = c.fc_next_auction_date ? format(new Date(c.fc_next_auction_date + 'T12:00:00'), 'MMM d') : '—';
    const tdNext = c.td_next_auction_date ? format(new Date(c.td_next_auction_date + 'T12:00:00'), 'MMM d') : '—';
    const next  = c.fc_next_auction_date && c.td_next_auction_date
      ? (c.fc_next_auction_date <= c.td_next_auction_date ? `${fcNext} FC` : `${tdNext} TD`)
      : fcNext !== '—' ? `${fcNext} FC` : `${tdNext} TD`;

    return `
    <tr style="background:${bg};border-top:1px solid #162D4A;${isMe ? 'border-left:3px solid #F59E0B;' : ''}">
      <td style="padding:11px 12px;">
        <div style="color:#e2e8f0;font-size:13px;font-weight:700;">${label}</div>
        <div style="margin-top:3px;">
          ${c.is_gold_standard ? '<span style="background:rgba(16,185,129,0.15);color:#10B981;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:600;">✓ Gold</span>' : ''}
          ${isMe ? '<span style="background:rgba(245,158,11,0.15);color:#F59E0B;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:600;margin-left:3px;">YOUR COUNTY</span>' : ''}
        </div>
      </td>
      <td style="padding:11px 8px;text-align:center;"><div style="color:#F59E0B;font-size:17px;font-weight:800;">${c.fc_upcoming_30d||0}</div><div style="color:#475569;font-size:10px;">FC 30d</div></td>
      <td style="padding:11px 8px;text-align:center;"><div style="color:#03B3CB;font-size:17px;font-weight:800;">${c.td_upcoming_30d||0}</div><div style="color:#475569;font-size:10px;">TD 30d</div></td>
      <td style="padding:11px 8px;text-align:center;"><div style="color:#e2e8f0;font-size:11px;font-weight:600;">${next}</div></td>
      <td style="padding:11px 8px;text-align:center;">
        <a href="${BASE}/chat?county=${c.county}&type=foreclosure&ref=email_fc" style="display:inline-block;background:#1E3A5F;color:#F59E0B;border:1px solid rgba(245,158,11,0.3);border-radius:6px;padding:5px 8px;font-size:11px;font-weight:600;text-decoration:none;margin:1px;">FC</a>
        <a href="${BASE}/chat?county=${c.county}&type=tax_deed&ref=email_td" style="display:inline-block;background:#1E3A5F;color:#03B3CB;border:1px solid rgba(3,179,203,0.3);border-radius:6px;padding:5px 8px;font-size:11px;font-weight:600;text-decoration:none;margin:1px;">TD</a>
      </td>
    </tr>`;
  }).join('');
}

// ── Featured property card ────────────────────────────────────────────────────
function featuredCard(auctions, county, lead) {
  if (!auctions?.length) return '';
  const top = auctions[0];
  const addr = top.property_address?.split(',')[0] || 'FL Property';
  const bid  = top.opening_bid ? `$${Number(top.opening_bid).toLocaleString()}` : '—';
  const asmnt = top.assessed_value ? `$${Number(top.assessed_value).toLocaleString()}` : '—';
  const typeLabel = top.sale_type === 'foreclosure' ? 'Foreclosure' : 'Tax Deed';
  const cLabel = county.charAt(0).toUpperCase() + county.slice(1).replace(/_/g,' ');
  const auctionDate = top.auction_date ? format(new Date(top.auction_date + 'T12:00:00'), 'MMM d, yyyy') : '';

  return `
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0F2035;border:1px solid #1E3A5F;border-radius:10px;overflow:hidden;">
    <tr><td style="padding:16px 18px;">
      <div style="color:#94a3b8;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">${cLabel} · ${typeLabel}${auctionDate ? ' · ' + auctionDate : ''}</div>
      <div style="color:#e2e8f0;font-size:15px;font-weight:700;margin-top:4px;">${addr}</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px;">
        <tr>
          <td width="31%" style="padding:8px;background:#162D4A;border-radius:6px;text-align:center;">
            <div style="color:#475569;font-size:10px;text-transform:uppercase;font-weight:600;">Opening Bid</div>
            <div style="color:#F59E0B;font-size:15px;font-weight:800;margin-top:3px;">${bid}</div>
          </td>
          <td width="4%"></td>
          <td width="31%" style="padding:8px;background:#162D4A;border-radius:6px;text-align:center;">
            <div style="color:#475569;font-size:10px;text-transform:uppercase;font-weight:600;">Assessed</div>
            <div style="color:#e2e8f0;font-size:15px;font-weight:800;margin-top:3px;">${asmnt}</div>
          </td>
          <td width="4%"></td>
          <td width="30%" style="padding:8px;background:#162D4A;border-radius:6px;text-align:center;">
            <div style="color:#475569;font-size:10px;text-transform:uppercase;font-weight:600;">Shapira Ceiling</div>
            <div style="color:#10B981;font-size:13px;font-weight:700;margin-top:5px;">Run S5 →</div>
          </td>
        </tr>
      </table>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;"><tr>
        <td width="100%">
          <a href="${BASE}/?email=${encodeURIComponent(lead.email)}&county=${encodeURIComponent(county)}&ref=email_free_report" style="display:block;background:linear-gradient(135deg,#F59E0B,#D97706);color:#020617;font-weight:800;font-size:14px;padding:12px;border-radius:8px;text-align:center;text-decoration:none;">Get Free ${cLabel} County Report →</a>
        </td>
      </tr></table>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;"><tr>
        <td width="48%">
          <a href="${BASE}/buy-report?county=${county}&case=${top.case_number}&ref=email_s5" style="display:block;background:#1E3A5F;color:#F59E0B;font-weight:700;font-size:12px;padding:9px;border-radius:8px;text-align:center;border:1px solid rgba(245,158,11,0.3);text-decoration:none;">S5 Report — $25</a>
        </td>
        <td width="4%"></td>
        <td width="48%">
          <a href="${BASE}/chat?county=${county}&ref=email_docket" style="display:block;background:#1E3A5F;color:#e2e8f0;font-weight:600;font-size:12px;padding:9px;border-radius:8px;text-align:center;border:1px solid #162D4A;text-decoration:none;">Full County Docket</a>
        </td>
      </tr></table>
    </td></tr>
  </table>`;
}

// ── Hook CTA ──────────────────────────────────────────────────────────────────
function hookCTA(hook, lead, snapshot) {
  const county = lead.county || 'florida';
  const cd = snapshot.find(c => c.county === county);
  const fc = cd?.fc_upcoming_30d || 0;
  const td = cd?.td_upcoming_30d || 0;
  const name = lead.name?.split(' ')[0] || 'there';
  const cLabel = county.charAt(0).toUpperCase() + county.slice(1).replace(/_/g,' ');

  const defs = {
    QUICK_DEMO:  { h:`${fc + td} auctions coming in ${cLabel}`, b:`<strong style="color:#F59E0B">${fc} foreclosures</strong> + <strong style="color:#03B3CB">${td} tax deeds</strong> in the next 30 days.`, c1:{t:'Try Free Preview',u:`${BASE}/chat?county=${county}&ref=email_cta`}, c2:{t:'See Full Docket',u:`${BASE}/chat?county=${county}&ref=email_docket`} },
    PROOF:       { h:'The formula held again', b:`Marion: predicted $82,000 ceiling → sold $73,501. <strong style="color:#10B981">Ceiling held. $8,499 edge.</strong> Third-party confirmed.`, c1:{t:'See Full Analysis',u:`${BASE}/chat?hook=PROOF&ref=email_cta`}, c2:{t:'Run Your Property',u:`${BASE}/chat?ref=email_analyze`} },
    PRICING:     { h:'One analysis pays for itself', b:`$25/call. One Shapira analysis stopping a bad bid = $900+ saved. <strong style="color:#F59E0B">Investor ($99/mo)</strong> = 10 analyses at $10 each.`, c1:{t:'Start $25 Analysis',u:`${BASE}/buy-report?ref=email_cta`}, c2:{t:'Investor $99/mo',u:`${BASE}/subscribe?ref=email_investor`} },
    CONVERSION:  { h:`${name}, one step away`, b:`You've been analyzing the right properties. <strong style="color:#F59E0B">Investor tier activates in 2 minutes.</strong>`, c1:{t:'Activate — $99/mo',u:`${BASE}/subscribe?ref=email_convert`}, c2:{t:'View My County',u:`${BASE}/chat?county=${county}&ref=email_county`} },
    FRICTION:    { h:'Something stopped you — let me fix it', b:`Marion result: predicted $82K → sold $73,501. Ceiling held. $8,499 edge.`, c1:{t:'Continue Analysis',u:`${BASE}/chat?hook=FRICTION&ref=email_friction`}, c2:{t:'Ask a Question',u:`${BASE}/chat?ref=email_ask`} },
    SCALE:       { h:'More counties, more deals', b:`Pro tier: <strong style="color:#F59E0B">50 S5 analyses, deal memos, and CMAs</strong> per month.`, c1:{t:'Upgrade to Pro — $199/mo',u:`${BASE}/subscribe?tier=pro&ref=email_scale`}, c2:{t:'View Pro Features',u:`${BASE}/chat?view=pricing&ref=email_pricing`} },
  };
  const d = defs[hook] || defs.QUICK_DEMO;
  return `
  <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#0F2035,#162D4A);border:1px solid rgba(245,158,11,0.25);border-radius:10px;">
    <tr><td style="padding:20px 22px;">
      <div style="color:#e2e8f0;font-size:15px;font-weight:700;line-height:1.4;">${d.h}</div>
      <div style="color:#94a3b8;font-size:13px;line-height:1.6;margin-top:8px;">${d.b}</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;"><tr>
        <td width="48%"><a href="${d.c1.u}" style="display:block;background:linear-gradient(135deg,#F59E0B,#D97706);color:#020617;font-weight:800;font-size:12px;padding:11px;border-radius:8px;text-align:center;text-decoration:none;">${d.c1.t}</a></td>
        <td width="4%"></td>
        <td width="48%"><a href="${d.c2.u}" style="display:block;background:#1E3A5F;color:#e2e8f0;font-weight:600;font-size:12px;padding:11px;border-radius:8px;text-align:center;border:1px solid #162D4A;text-decoration:none;">${d.c2.t}</a></td>
      </tr></table>
    </td></tr>
  </table>`;
}

// ── Build full HTML email ─────────────────────────────────────────────────────
function buildEmail({ lead, hook, snapshot, auctions, unsubUrl }) {
  const firstName = lead.name?.split(' ')[0] || 'there';
  const county    = lead.county || 'florida';
  const cd        = snapshot.find(c => c.county === county);
  const fc        = cd?.fc_upcoming_30d || 0;
  const td        = cd?.td_upcoming_30d || 0;
  const totalCounties = snapshot.length;
  const totalAuctions = snapshot.reduce((s, c) => s + c.total_upcoming_30d, 0);

  return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>BidDeed.AI — ${LABEL}</title></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;">${fc} FC + ${td} TD in ${county.replace(/_/g,' ')} · ${totalAuctions.toLocaleString()} FL auctions · ${LABEL}</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:20px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <tr><td style="background:#020617;border-radius:12px 12px 0 0;padding:24px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <table cellpadding="0" cellspacing="0"><tr>
          <td style="background:linear-gradient(135deg,#F59E0B,#D97706);border-radius:8px;width:40px;height:40px;text-align:center;vertical-align:middle;">
            <span style="color:#020617;font-weight:900;font-size:14px;">BD</span>
          </td>
          <td style="padding-left:12px;vertical-align:middle;">
            <div style="color:#fff;font-weight:800;font-size:18px;">BidDeed<span style="color:#F59E0B;">.AI</span></div>
            <div style="color:#94a3b8;font-size:11px;">FL Foreclosure + Tax Deed Intelligence</div>
          </td>
        </tr></table>
      </td>
      <td align="right" style="vertical-align:middle;">
        <div style="color:#94a3b8;font-size:12px;">${LABEL}</div>
        <div style="margin-top:4px;"><span style="background:rgba(245,158,11,0.15);color:#F59E0B;border:1px solid rgba(245,158,11,0.3);border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600;">${totalAuctions.toLocaleString()} auctions · ${totalCounties} counties</span></div>
      </td>
    </tr></table>
  </td></tr>

  <tr><td style="background:#0F2035;padding:14px 32px;border-left:4px solid #10B981;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <div style="color:#10B981;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">✓ Verified — Marion County · Jul 20, 2026</div>
        <div style="color:#e2e8f0;font-size:13px;margin-top:3px;">Predicted ceiling <strong style="color:#F59E0B;">$82,000</strong> → Sold <strong style="color:#10B981;">$73,501</strong>. Ceiling held. $8,499 edge. 3rd-party confirmed.</div>
      </td>
      <td width="130" align="right" style="vertical-align:middle;padding-left:12px;">
        <a href="${BASE}/chat?hook=PROOF&ref=email_proof" style="display:inline-block;background:linear-gradient(135deg,#F59E0B,#D97706);color:#020617;font-weight:700;font-size:12px;padding:8px 14px;border-radius:8px;text-decoration:none;">Full Analysis →</a>
      </td>
    </tr></table>
  </td></tr>

  <tr><td style="background:#020617;padding:22px 32px 12px;">
    <p style="color:#e2e8f0;font-size:15px;line-height:1.6;margin:0 0 10px;">Hi ${firstName},</p>
    <p style="color:#94a3b8;font-size:14px;line-height:1.6;margin:0;">Your daily FL auction pipeline — <strong style="color:#F59E0B;">foreclosure + tax deed</strong> side by side.</p>
  </td></tr>

  <tr><td style="background:#020617;padding:4px 32px 0;">
    <div style="border-top:1px solid #1E3A5F;padding-top:16px;margin-bottom:12px;">
      <div style="color:#F59E0B;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">📋 30-Day Auction Pipeline</div>
    </div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1E3A5F;border-radius:10px;overflow:hidden;">
      <tr style="background:#1E3A5F;">
        <td style="padding:9px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;">County</td>
        <td style="padding:9px 8px;color:#94a3b8;font-size:10px;font-weight:700;text-align:center;">🏦 FC</td>
        <td style="padding:9px 8px;color:#94a3b8;font-size:10px;font-weight:700;text-align:center;">📋 TD</td>
        <td style="padding:9px 8px;color:#94a3b8;font-size:10px;font-weight:700;text-align:center;">Next</td>
        <td style="padding:9px 8px;color:#94a3b8;font-size:10px;font-weight:700;text-align:center;">Analyze</td>
      </tr>
      ${countyRows(snapshot, county)}
      <tr style="background:#162D4A;border-top:1px solid #1E3A5F;">
        <td colspan="5" style="padding:10px 12px;text-align:center;">
          <a href="${BASE}/chat?view=all_counties&ref=email_all" style="color:#F59E0B;font-size:12px;font-weight:600;text-decoration:none;">View all ${totalCounties} counties →</a>
        </td>
      </tr>
    </table>
  </td></tr>

  ${auctions?.length ? `
  <tr><td style="background:#020617;padding:20px 32px 0;">
    <div style="border-top:1px solid #1E3A5F;padding-top:16px;margin-bottom:12px;">
      <div style="color:#F59E0B;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">🏠 Featured — ${(county.charAt(0).toUpperCase()+county.slice(1).replace(/_/g,' '))}</div>
    </div>
    ${featuredCard(auctions, county, lead)}
  </td></tr>` : ''}

  <tr><td style="background:#020617;padding:20px 32px 0;">
    <div style="border-top:1px solid #1E3A5F;padding-top:16px;margin-bottom:12px;">
      <div style="color:#F59E0B;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">💡 Your Next Move</div>
    </div>
    ${hookCTA(hook, lead, snapshot)}
  </td></tr>

  <tr><td style="background:#020617;padding:20px 32px 0;">
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1E3A5F;border-radius:10px;">
      <tr><td style="padding:16px 18px;">
        <div style="color:#e2e8f0;font-size:14px;font-weight:600;margin-bottom:4px;">Get your free county report — no credit card needed</div>
        <div style="color:#94a3b8;font-size:12px;line-height:1.5;margin-bottom:10px;">Top 5 upcoming auctions in ${county.replace(/_/g,' ')} County, delivered instantly.</div>
        <a href="${BASE}/free-report?email=${encodeURIComponent(lead.email)}&county=${encodeURIComponent(county)}" style="display:inline-block;background:#F59E0B;color:#020617;font-weight:700;font-size:12px;padding:9px 16px;border-radius:6px;text-decoration:none;">Get My Free Report →</a>
      </td></tr>
    </table>
  </td></tr>

  <tr><td style="background:#0F2035;border-radius:0 0 12px 12px;padding:18px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <div style="color:#475569;font-size:11px;line-height:1.6;">
          <strong style="color:#94a3b8;">BidDeed.AI</strong> · Everest Capital USA · Shapira Formula™<br/>
          <a href="${BASE}" style="color:#F59E0B;text-decoration:none;">biddeed.ai</a>
        </div>
      </td>
      <td width="110" align="right" valign="top">
        <a href="${unsubUrl}" style="color:#475569;font-size:11px;text-decoration:none;">Unsubscribe</a><br/>
        <a href="${BASE}/chat?ref=email_footer" style="color:#F59E0B;font-size:11px;font-weight:600;text-decoration:none;margin-top:4px;display:block;">Open BidDeed →</a>
      </td>
    </tr></table>
  </td></tr>

</table>
</td></tr></table>
</body></html>`;
}

// ── MAIN ──────────────────────────────────────────────────────────────────────
async function main() {
  console.log(`\nBidDeed Daily Digest — ${LABEL}\n`);

  const [snapshot, leads] = await Promise.all([getTwinSnapshot(), getLeads()]);

  if (!snapshot.length) { console.log('No auction data.'); return; }
  if (!leads.length)    { console.log('No leads.'); return; }

  console.log(`Sending to ${leads.length} recipients across ${snapshot.length} counties\n`);

  let sent = 0, failed = 0;

  for (const lead of leads) {
    try {
      const hook     = classifyHook(lead);
      const county   = lead.county || 'brevard';
      const auctions = await getTopAuctions(county);
      const unsubUrl = await unsubscribeUrl(lead.email);
      const html     = buildEmail({ lead, hook, snapshot, auctions, unsubUrl });

      const cd = snapshot.find(c => c.county === county);
      const fc = cd?.fc_upcoming_30d || 0;
      const td = cd?.td_upcoming_30d || 0;
      const subjects = {
        QUICK_DEMO:  `${format(new Date(), 'MMM d')} — ${fc} FC + ${td} TD in ${county.replace(/_/g,' ')}`,
        PROOF:       `Ceiling held again — Marion $82K → $73,501`,
        PRICING:     `$25 analysis vs $900+ saved`,
        CONVERSION:  `${lead.name?.split(' ')[0] || 'Hey'}, your county closes soon`,
        FRICTION:    `Pick up where you left off`,
        SCALE:       `50 analyses/mo — time to upgrade?`,
      };

      const { data, error } = await resend.emails.send({
        from:    'Ariel @ BidDeed.AI <digest@biddeed.ai>',
        to:      [lead.email],
        subject: subjects[hook] || subjects.QUICK_DEMO,
        html,
        headers: {
          'List-Unsubscribe': `<mailto:unsubscribe@biddeed.ai>, <${unsubUrl}>`,
          'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
        },
        tags: [{ name:'hook', value:hook }, { name:'stage', value:lead.stage||'lead' }],
      });

      if (error) { console.error(`FAIL ${lead.email}:`, error.message || JSON.stringify(error)); failed++; continue; }

      // Non-blocking log
      supabase.from('digest_history').insert({
        user_id: lead.id, digest_date: TODAY, status: 'delivered',
        delivered_at: new Date().toISOString(),
        insight_sale_type: 'both', insight_summary: `Hook:${hook} ID:${data?.id}`,
      }).then(() => {}).catch(() => {});

      supabase.from('lead_profiles').update({
        messages_count: (lead.messages_count||0) + 1,
        hooks_triggered: [...new Set([...(lead.hooks_triggered||[]), hook])],
        updated_at: new Date().toISOString(),
      }).eq('id', lead.id).then(() => {}).catch(() => {});

      console.log(`SENT ${lead.email} | ${hook} | ${data?.id}`);
      sent++;
      await new Promise(r => setTimeout(r, 400));
    } catch(e) {
      console.error(`FAIL ${lead.email}:`, e.message);
      failed++;
    }
  }

  console.log(`\nDone: ${sent} sent, ${failed} failed`);
}

main().catch(e => { console.error('Fatal:', e.message); process.exit(1); });
