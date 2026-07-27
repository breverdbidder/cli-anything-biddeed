#!/usr/bin/env node
/**
 * BidDeed.AI — Daily Branded Digest
 * ─────────────────────────────────────────────────────────────────────────────
 * Pulls auction data from Supabase (already scraped by existing workflow)
 * Builds branded HTML (navy + orange, all links → biddeed.ai/chat)
 * Sends personalized email to each lead in lead_profiles
 * Logs delivery to digest_history
 * ─────────────────────────────────────────────────────────────────────────────
 */

const { createClient } = require('@supabase/supabase-js');
const ws = require('ws');
const { Resend }        = require('resend');
const { format, addDays } = require('date-fns');

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false }, global: { fetch: fetch }, realtime: { transport: ws } });
const resend   = new Resend(process.env.RESEND_API_KEY);
const BASE     = 'https://biddeed.ai';
const TODAY    = format(new Date(), 'yyyy-MM-dd');
const LABEL    = format(new Date(), 'EEEE, MMMM d, yyyy');

// ── STEP 1: Pull today's twin snapshot ───────────────────────────────────────
async function getTwinSnapshot() {
  const { data, error } = await supabase
    .from('county_twin_snapshot')
    .select('county, is_gold_standard, fc_upcoming_30d, td_upcoming_30d, total_upcoming_30d, fc_next_auction_date, td_next_auction_date')
    .eq('snapshot_date', TODAY)
    .gt('total_upcoming_30d', 0)
    .order('total_upcoming_30d', { ascending: false });

  if (error || !data?.length) {
    console.log('No snapshot for today — refreshing from multi_county_auctions...');
    // Fallback: query live data
    const { data: live } = await supabase.rpc('refresh_twin_snapshot_direct').catch(() => ({ data: null }));
    return live || [];
  }
  console.log(`✅ Snapshot: ${data.length} counties`);
  return data;
}

// ── STEP 2: Pull top upcoming auctions (Gold Standard, with address) ─────────
async function getTopAuctions(county) {
  const end30 = format(addDays(new Date(), 30), 'yyyy-MM-dd');
  const { data } = await supabase
    .from('multi_county_auctions')
    .select('county, sale_type, auction_date, property_address, opening_bid, assessed_value, case_number, parcel_id')
    .eq('county', county)
    .in('auction_status', ['upcoming', 'scheduled'])
    .gte('auction_date', TODAY)
    .lte('auction_date', end30)
    .not('property_address', 'is', null)
    .not('opening_bid', 'is', null)
    .order('opening_bid', { ascending: false })
    .limit(3);
  return data || [];
}

// ── STEP 3: Pull leads ────────────────────────────────────────────────────────
async function getLeads() {
  if (process.env.TEST_EMAIL) {
    console.log(`🧪 TEST MODE: sending only to ${process.env.TEST_EMAIL}`);
    return [{ id: 'test', email: process.env.TEST_EMAIL, name: 'Ariel', county: 'brevard', stage: 'lead', hooks_triggered: [], messages_count: 0, score: 0, tier: null }];
  }
  const { data, error } = await supabase
    .from('lead_profiles')
    .select('id, email, name, county, stage, hooks_triggered, messages_count, score, tier')
    .not('stage', 'eq', 'unsubscribed')
    .not('email', 'is', null);
  if (error) throw new Error(`Lead fetch failed: ${error.message}`);
  console.log(`✅ Leads: ${data.length} recipients`);
  return data || [];
}

// ── STEP 4: Classify hook ─────────────────────────────────────────────────────
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

// ── STEP 5: Build county table rows ──────────────────────────────────────────
function countyRows(snapshot, leadCounty) {
  const sorted = [...snapshot].sort((a, b) => {
    if (a.county === leadCounty) return -1;
    if (b.county === leadCounty) return 1;
    return b.total_upcoming_30d - a.total_upcoming_30d;
  }).slice(0, 6);

  return sorted.map((c, i) => {
    const bg    = i % 2 === 0 ? '#0F2035' : '#020617';
    const label = c.county.charAt(0).toUpperCase() + c.county.slice(1).replace(/_/g,' ');
    const isMe  = c.county === leadCounty;
    const gold  = c.is_gold_standard;
    const fcNext = c.fc_next_auction_date ? format(new Date(c.fc_next_auction_date), 'MMM d') : '—';
    const tdNext = c.td_next_auction_date ? format(new Date(c.td_next_auction_date), 'MMM d') : '—';
    const next  = c.fc_next_auction_date && c.td_next_auction_date
      ? (c.fc_next_auction_date <= c.td_next_auction_date ? `${fcNext} FC` : `${tdNext} TD`)
      : fcNext !== '—' ? `${fcNext} FC` : `${tdNext} TD`;

    return `
    <tr style="background:${bg};border-top:1px solid #162D4A;${isMe ? 'border-left:3px solid #F59E0B;' : ''}">
      <td style="padding:11px 12px;">
        <div style="color:#e2e8f0;font-size:13px;font-weight:700;">${label}</div>
        <div style="margin-top:3px;">
          ${gold ? '<span style="background:rgba(16,185,129,0.15);color:#10B981;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:600;">✓ Gold</span>' : ''}
          ${isMe ? '<span style="background:rgba(245,158,11,0.15);color:#F59E0B;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:600;margin-left:3px;">YOUR COUNTY</span>' : ''}
        </div>
      </td>
      <td style="padding:11px 8px;text-align:center;"><div style="color:#F59E0B;font-size:17px;font-weight:800;">${c.fc_upcoming_30d||0}</div><div style="color:#475569;font-size:10px;">30d</div></td>
      <td style="padding:11px 8px;text-align:center;"><div style="color:#03B3CB;font-size:17px;font-weight:800;">${c.td_upcoming_30d||0}</div><div style="color:#475569;font-size:10px;">30d</div></td>
      <td style="padding:11px 8px;text-align:center;"><div style="color:#e2e8f0;font-size:11px;font-weight:600;">${next}</div></td>
      <td style="padding:11px 8px;text-align:center;">
        <a href="${BASE}/chat?county=${c.county}&type=foreclosure&ref=email_fc" style="display:inline-block;background:#1E3A5F;color:#F59E0B;border:1px solid rgba(245,158,11,0.3);border-radius:6px;padding:5px 8px;font-size:11px;font-weight:600;text-decoration:none;margin:1px;">FC</a>
        <a href="${BASE}/chat?county=${c.county}&type=tax_deed&ref=email_td" style="display:inline-block;background:#1E3A5F;color:#03B3CB;border:1px solid rgba(3,179,203,0.3);border-radius:6px;padding:5px 8px;font-size:11px;font-weight:600;text-decoration:none;margin:1px;">TD</a>
      </td>
    </tr>`;
  }).join('');
}

// ── STEP 6: Build featured property card ─────────────────────────────────────
function featuredCard(auctions, county) {
  if (!auctions?.length) return '';
  const top = auctions[0];
  const addr = top.property_address?.split(',')[0] || 'FL Property';
  const bid  = top.opening_bid ? `$${Number(top.opening_bid).toLocaleString()}` : '—';
  const asmnt = top.assessed_value ? `$${Number(top.assessed_value).toLocaleString()}` : '—';
  const typeColor = top.sale_type === 'foreclosure' ? '#F59E0B' : '#03B3CB';
  const typeLabel = top.sale_type === 'foreclosure' ? 'Foreclosure' : 'Tax Deed';
  const countyLabel = county.charAt(0).toUpperCase() + county.slice(1).replace(/_/g,' ');
  const chatUrl = `${BASE}/chat?county=${county}&case=${top.case_number}&type=${top.sale_type}&ref=email_featured`;

  return `
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0F2035;border:1px solid #1E3A5F;border-radius:10px;overflow:hidden;margin-top:0;">
    <tr><td style="padding:16px 18px;">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td>
          <div style="color:#94a3b8;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">${countyLabel} · ${typeLabel}</div>
          <div style="color:#e2e8f0;font-size:15px;font-weight:700;margin-top:4px;">${addr}</div>
          ${top.auction_date ? `<div style="color:#475569;font-size:11px;margin-top:2px;">${format(new Date(top.auction_date), 'MMM d, yyyy')}</div>` : ''}
        </td>
        <td width="80" align="right" valign="top">
          <span style="background:${typeColor === '#F59E0B' ? 'rgba(245,158,11,0.15)' : 'rgba(3,179,203,0.15)'};color:${typeColor};border-radius:4px;padding:4px 10px;font-size:11px;font-weight:700;">${typeLabel.toUpperCase().slice(0,2)}</span>
        </td>
      </tr></table>
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
      <div style="margin-top:12px;padding:9px 12px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;color:#94a3b8;font-size:12px;line-height:1.5;">
        Run Shapira S5 to get exact max bid, lien stack, and BID/SKIP verdict for this property.
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;"><tr>
        <td width="48%">
          <a href="${chatUrl}" style="display:block;background:linear-gradient(135deg,#F59E0B,#D97706);color:#020617;font-weight:800;font-size:13px;padding:10px;border-radius:8px;text-align:center;text-decoration:none;">Run S5 Analysis — $25</a>
        </td>
        <td width="4%"></td>
        <td width="48%">
          <a href="${BASE}/chat?county=${county}&view=full_docket&ref=email_docket" style="display:block;background:#1E3A5F;color:#e2e8f0;font-weight:600;font-size:13px;padding:10px;border-radius:8px;text-align:center;border:1px solid #162D4A;text-decoration:none;">Full County Docket</a>
        </td>
      </tr></table>
    </td></tr>
  </table>`;
}

// ── STEP 7: Build hook CTA ────────────────────────────────────────────────────
function hookCTA(hook, lead, snapshot) {
  const county = lead.county || 'florida';
  const cd     = snapshot.find(c => c.county === county);
  const fc     = cd?.fc_upcoming_30d || 0;
  const td     = cd?.td_upcoming_30d || 0;
  const name   = lead.name?.split(' ')[0] || 'there';
  const cLabel = county.charAt(0).toUpperCase() + county.slice(1).replace(/_/g,' ');

  const defs = {
    QUICK_DEMO:  { h:`${fc + td} auctions coming in ${cLabel}`, b:`<strong style="color:#F59E0B">${fc} foreclosures</strong> + <strong style="color:#03B3CB">${td} tax deeds</strong> in the next 30 days. Run one free Shapira preview — see if any are worth bidding on.`, c1:{t:'Try Free Preview',u:`${BASE}/chat?action=preview&county=${county}&ref=email_cta`}, c2:{t:'See Full Docket',u:`${BASE}/chat?view=docket&county=${county}&ref=email_docket`} },
    PROOF:       { h:'The formula held again', b:`Marion County: predicted $82,000 ceiling → sold $73,501. <strong style="color:#10B981">Ceiling held. $8,499 edge confirmed.</strong> Third-party winner, not the bank. That's the Shapira Formula working live.`, c1:{t:'See Full Analysis',u:`${BASE}/chat?hook=PROOF&ref=email_cta`}, c2:{t:'Run Your Property',u:`${BASE}/chat?action=analyze&ref=email_analyze`} },
    PRICING:     { h:'One analysis pays for itself', b:`$25/call. One Shapira analysis that stops a bad bid = $900+ saved minimum. <strong style="color:#F59E0B">Investor tier ($99/mo)</strong> gives you 10 analyses — that's $10 each. Two avoided mistakes per month and it's free.`, c1:{t:'Start $25 Analysis',u:`${BASE}/chat?action=trial&ref=email_cta`}, c2:{t:'Investor $99/mo',u:`${BASE}/chat?action=subscribe&tier=investor&ref=email_investor`} },
    CONVERSION:  { h:`${name}, one step away`, b:`You've been analyzing the right properties. The next auction in your county closes soon. <strong style="color:#F59E0B">Investor tier activates in 2 minutes</strong> — your county's docket is waiting.`, c1:{t:'Activate — $99/mo',u:`${BASE}/chat?action=subscribe&tier=investor&ref=email_convert`}, c2:{t:'View My County',u:`${BASE}/chat?county=${county}&ref=email_county`} },
    FRICTION:    { h:'Something stopped you — let me fix it', b:`You started an analysis but didn't complete it. Most common blocker: "I need one more example." Here's yesterday's Marion result: predicted $82K → sold $73,501. Ceiling held.`, c1:{t:'Continue Where I Left Off',u:`${BASE}/chat?hook=FRICTION&ref=email_friction`}, c2:{t:'Ask a Question',u:`${BASE}/chat?action=ask&ref=email_ask`} },
    SCALE:       { h:'More counties, more deals', b:`You're already subscribed. Pro tier adds <strong style="color:#F59E0B">50 S5 analyses, deal memos, and CMAs</strong> — everything to evaluate an entire county docket in one session.`, c1:{t:'Upgrade to Pro — $199/mo',u:`${BASE}/chat?action=upgrade&tier=pro&ref=email_scale`}, c2:{t:'View Pro Features',u:`${BASE}/chat?view=pricing&ref=email_pricing`} },
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

// ── STEP 8: Assemble email ────────────────────────────────────────────────────
function buildEmail({ lead, hook, snapshot, auctions }) {
  const firstName = lead.name?.split(' ')[0] || 'there';
  const county    = lead.county || 'florida';
  const cd        = snapshot.find(c => c.county === county);
  const fc        = cd?.fc_upcoming_30d || 0;
  const td        = cd?.td_upcoming_30d || 0;

  return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;">${fc} foreclosures + ${td} tax deeds in ${county.replace(/_/g,' ')} — Shapira analysis inside</div>
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
        <div style="margin-top:4px;"><span style="background:rgba(245,158,11,0.15);color:#F59E0B;border:1px solid rgba(245,158,11,0.3);border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600;">24 Gold Standard Counties</span></div>
      </td>
    </tr></table>
  </td></tr>

  <tr><td style="background:#0F2035;padding:14px 32px;border-left:4px solid #10B981;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <div style="color:#10B981;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">✓ Verified Result — Marion County · Jul 20, 2026</div>
        <div style="color:#e2e8f0;font-size:13px;margin-top:3px;line-height:1.5;">Predicted ceiling <strong style="color:#F59E0B;">$82,000</strong> → Sold <strong style="color:#10B981;">$73,501</strong>. Ceiling held. $8,499 edge. 3rd-party confirmed.</div>
      </td>
      <td width="130" align="right" style="vertical-align:middle;padding-left:12px;">
        <a href="${BASE}/chat?hook=PROOF&ref=email_proof" style="display:inline-block;background:linear-gradient(135deg,#F59E0B,#D97706);color:#020617;font-weight:700;font-size:12px;padding:8px 14px;border-radius:8px;text-decoration:none;white-space:nowrap;">Full Analysis →</a>
      </td>
    </tr></table>
  </td></tr>

  <tr><td style="background:#020617;padding:22px 32px 12px;">
    <p style="color:#e2e8f0;font-size:15px;line-height:1.6;margin:0 0 10px;">Hi ${firstName},</p>
    <p style="color:#94a3b8;font-size:14px;line-height:1.6;margin:0;">Your daily twin pipeline — <strong style="color:#F59E0B;">foreclosure + tax deed</strong> auctions across Gold Standard counties. Every link stays inside BidDeed analysis — no external auction platforms.</p>
  </td></tr>

  <tr><td style="background:#020617;padding:4px 32px 0;">
    <div style="border-top:1px solid #1E3A5F;padding-top:16px;margin-bottom:12px;">
      <div style="color:#F59E0B;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">📋 30-Day Auction Pipeline</div>
    </div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1E3A5F;border-radius:10px;overflow:hidden;">
      <tr style="background:#1E3A5F;">
        <td style="padding:9px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;width:23%;">County</td>
        <td style="padding:9px 8px;color:#94a3b8;font-size:10px;font-weight:700;text-align:center;width:14%;">🏦 FC<br/><span style="font-weight:400;font-size:9px;">30d</span></td>
        <td style="padding:9px 8px;color:#94a3b8;font-size:10px;font-weight:700;text-align:center;width:14%;">📋 TD<br/><span style="font-weight:400;font-size:9px;">30d</span></td>
        <td style="padding:9px 8px;color:#94a3b8;font-size:10px;font-weight:700;text-align:center;width:17%;">Next</td>
        <td style="padding:9px 8px;color:#94a3b8;font-size:10px;font-weight:700;text-align:center;width:32%;">Analyze</td>
      </tr>
      ${countyRows(snapshot, county)}
      <tr style="background:#162D4A;border-top:1px solid #1E3A5F;">
        <td colspan="5" style="padding:10px 12px;text-align:center;">
          <a href="${BASE}/chat?view=all_counties&ref=email_all" style="color:#F59E0B;font-size:12px;font-weight:600;text-decoration:none;">View all 24 Gold Standard counties →</a>
        </td>
      </tr>
    </table>
  </td></tr>

  ${auctions?.length ? `
  <tr><td style="background:#020617;padding:20px 32px 0;">
    <div style="border-top:1px solid #1E3A5F;padding-top:16px;margin-bottom:12px;">
      <div style="color:#F59E0B;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">🏠 Featured Property — ${(county.charAt(0).toUpperCase()+county.slice(1).replace(/_/g,' '))} County</div>
    </div>
    ${featuredCard(auctions, county)}
  </td></tr>` : ''}

  <tr><td style="background:#020617;padding:20px 32px 0;">
    <div style="border-top:1px solid #1E3A5F;padding-top:16px;margin-bottom:12px;">
      <div style="color:#F59E0B;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">💡 Your Next Move</div>
    </div>
    ${hookCTA(hook, lead, snapshot)}
  </td></tr>

  <tr><td style="background:#0F2035;border-radius:0 0 12px 12px;padding:18px 32px;margin-top:0;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <div style="color:#475569;font-size:11px;line-height:1.6;">
          <strong style="color:#94a3b8;">BidDeed.AI</strong> · Everest Capital USA<br/>
          Shapira Formula™ · 21,138 auctions · 24 Gold Standard counties<br/>
          All links stay inside <a href="${BASE}" style="color:#F59E0B;text-decoration:none;">biddeed.ai</a>
        </div>
      </td>
      <td width="110" align="right" valign="top">
        <a href="${BASE}/chat?action=unsubscribe&email=${encodeURIComponent(lead.email)}" style="color:#475569;font-size:11px;text-decoration:none;">Unsubscribe</a><br/>
        <a href="${BASE}/chat?ref=email_footer" style="color:#F59E0B;font-size:11px;font-weight:600;text-decoration:none;margin-top:4px;display:block;">Open BidDeed →</a>
      </td>
    </tr></table>
  </td></tr>

</table>
</td></tr></table>
</body></html>`;
}

// ── MAIN ─────────────────────────────────────────────────────────────────────
async function main() {
  console.log(`\n🚀 BidDeed Daily Digest — ${LABEL}\n`);

  const [snapshot, leads] = await Promise.all([getTwinSnapshot(), getLeads()]);

  if (!leads.length) {
    console.log('⚠️ No leads. Add emails to lead_profiles table.');
    return;
  }

  let sent = 0, failed = 0;

  for (const lead of leads) {
    try {
      const hook     = classifyHook(lead);
      const county   = lead.county || 'brevard';
      const auctions = await getTopAuctions(county);
      const html     = buildEmail({ lead, hook, snapshot, auctions });

      const subjects = {
        QUICK_DEMO:  `📋 ${format(new Date(), 'MMM d')} — ${(snapshot.find(c=>c.county===county)?.total_upcoming_30d||0)} auctions in ${county.replace(/_/g,' ')} (FC + TD)`,
        PROOF:       `✓ Ceiling held again — see the Shapira scorecard`,
        PRICING:     `$25 analysis vs $900+ saved — the math works`,
        CONVERSION:  `Your county's next auction closes soon`,
        FRICTION:    `Pick up where you left off — BidDeed.AI`,
        SCALE:       `50 analyses/mo — time to upgrade?`,
      };

      const { data, error } = await resend.emails.send({
        from:    'Ariel @ BidDeed.AI <digest@biddeed.ai>',
        to:      [lead.email],
        subject: subjects[hook] || subjects.QUICK_DEMO,
        html,
        tags: [{ name:'hook', value:hook },{ name:'stage', value:lead.stage||'lead' }],
      });

      if (error) { console.error(`❌ ${lead.email}:`, error); failed++; continue; }

      // Log delivery
      await supabase.from('digest_history').insert({
        user_id:           lead.id,
        digest_date:       TODAY,
        status:            'delivered',
        delivered_at:      new Date().toISOString(),
        insight_sale_type: 'both',
        insight_summary:   `Hook:${hook} ID:${data?.id}`,
      }).catch(() => {});

      // Update lead counters
      await supabase.from('lead_profiles').update({
        messages_count: (lead.messages_count||0) + 1,
        hooks_triggered: [...new Set([...(lead.hooks_triggered||[]), hook])],
        updated_at: new Date().toISOString(),
      }).eq('id', lead.id).catch(() => {});

      console.log(`✅ ${lead.email} | Hook:${hook} | ${data?.id}`);
      sent++;
      await new Promise(r => setTimeout(r, 400)); // rate limit
    } catch(e) {
      console.error(`❌ ${lead.email}:`, e.message);
      failed++;
    }
  }

  console.log(`\n📊 ${sent} sent, ${failed} failed\n`);
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
