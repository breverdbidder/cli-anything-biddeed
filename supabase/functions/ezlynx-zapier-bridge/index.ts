// ezlynx-zapier-bridge — Supabase Edge Function (issue #19609)
//
// PURPOSE: For each approved ff_batch_leads row that has been routed to a
// producer, POST a structured payload to a Zapier "Catch Hook" webhook URL.
// The Zap maps that payload to an EZLynx "Create Commercial/Personal Prospect"
// or "Add/Update Contact" action via EZLynx's official Zapier app.
//
// WHY ZAPIER (not direct EZLynx REST): EZLynx has no public REST API.
// The only programmatic integration path is the EZLynx Zapier app
// (listed on the EZLynx Marketplace; actions: "Create Commercial Applicant",
// "Create Commercial Prospect", "Add/Update Contact"). This function POSTs
// to a Zapier "Catch Hook" URL; the Zap then maps fields to EZLynx.
//
// STATUS: *** UNTESTED against a real EZLynx account ***
// The function is complete and will send the documented payload shape.
// End-to-end verification of producer-field assignment in EZLynx requires:
//   1. Zapier account connected to Mariam's EZLynx account
//   2. A live Zap created with a "Catch Hook" trigger and EZLynx action
//   3. The webhook URL stored in vault as 'ezlynx_zapier_webhook_url'
//   4. Testing with a real batch against the live Zap
//
// PAYLOAD SHAPE (what the Zap must map to EZLynx fields):
//   {
//     "source": "WinnerData",           -- always; do not expose tool names
//     "prospect_type": "personal"|"commercial",
//     "company_name": string|null,       -- for commercial
//     "first_name": string|null,         -- for personal/individual
//     "last_name": string|null,          -- for personal/individual
//     "property_address": string,
//     "property_city": string|null,
//     "property_state": "FL",
//     "property_county": string,
//     "auction_date": string (ISO date), -- public-record citation
//     "case_number": string|null,        -- public-record citation
//     "sale_type": string|null,          -- "tax_deed" | "foreclosure" | null
//     "purchase_price": number|null,     -- tier1_sold_amount (public record)
//     "assessed_value": number|null,     -- PA record (public record)
//     "year_built": number|null,
//     "sqft_heated": number|null,
//     "dor_use_code": string|null,       -- FL DOR land use code (public record)
//     "dor_use_description": string|null,
//     "producer_name": string|null,      -- assigned producer full_name
//     "producer_email": string|null,     -- for EZLynx producer-assignment field
//     "confidence_tier": "A"|"B"|"C"|"unscored",
//     "portfolio_property_count": number|null,
//     "portfolio_assessed_total": number|null,
//     "umbrella_opportunity": boolean|null,
//     "flood_opportunity": string|null,
//     "wd_item_id": number,              -- public.wd_report_items.id (for callback)
//     "batch_date": string (ISO date)
//   }
//
// FACT FINDER CONFIDENTIALITY: payload never includes internal vendor/tool
// names (no "Tracerfy", "Bright Data", "GitHub issue", "BrightData"). Only
// public-record citations: Sunbiz entity name, DBPR, county records, case
// numbers. This matches the guardrail in issue #19609.
//
// INVOCATION: called by the dispatch-ezlynx-bridge.yml workflow
// (triggered by wd_report_items rows with ezlynx_dispatch_status='pending')
// or by winnerdata.dispatch_ezlynx_bridge() RPC (called from route_ff_batch
// or on-demand per item).
//
// AUTH: shared secret checked against vault 'ezlynx_bridge_shared_secret'.
// Callers (GHA workflow / pg_net) must pass X-Bridge-Secret header.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL');
const SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');

const H = {
  apikey: SERVICE_KEY,
  Authorization: `Bearer ${SERVICE_KEY}`,
  'Content-Type': 'application/json'
};

async function rest(path: string, init: RequestInit = {}) {
  return fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...init,
    headers: { ...H, ...(init.headers as Record<string, string> ?? {}) }
  });
}

async function vaultSecret(name: string): Promise<string | null> {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/vault_secret`, {
    method: 'POST',
    headers: H,
    body: JSON.stringify({ p_name: name })
  });
  if (!r.ok) return null;
  const v = await r.json();
  return typeof v === 'string' ? v : null;
}

async function logOps(dispatchId: string, task: string, status: string, severity: string, evidence: string) {
  await rest('agent_ops_log', {
    method: 'POST',
    headers: { Prefer: 'return=minimal' },
    body: JSON.stringify({
      dispatch_id: dispatchId,
      task,
      status,
      severity,
      evidence: String(evidence).slice(0, 2000)
    })
  }).catch((e: Error) => console.error('logOps failed', e));
}

interface ReportItemRow {
  id: number;
  batch_date: string;
  auction_id: string;
  org_id: string;
  assignment_user_id: string | null;
  confidence_tier: string | null;
  observed_signal: Record<string, unknown>;
  derived_context: Record<string, unknown>;
  ezlynx_dispatch_status: string;
}

interface PortalUserRow {
  full_name: string;
  email: string;
}

function buildZapierPayload(
  item: ReportItemRow,
  producer: PortalUserRow | null
): Record<string, unknown> {
  const obs = item.observed_signal ?? {};
  const derived = item.derived_context ?? {};

  // Determine prospect type from DOR use code
  const dorCode = String(obs['dor_use_code'] ?? '');
  const isCommercial = dorCode.startsWith('1') || dorCode.startsWith('2') ||
                       dorCode.startsWith('3') || dorCode.startsWith('4') ||
                       dorCode.startsWith('5') || dorCode.startsWith('6') ||
                       dorCode.startsWith('7') || dorCode.startsWith('8');
  const prospectType = isCommercial ? 'commercial' : 'personal';

  // Parse name — winning_bidder is the owner name (entity or individual)
  const winningBidder = String(obs['winning_bidder'] ?? '');
  const identityType = String(obs['identity_type'] ?? '');
  let companyName: string | null = null;
  let firstName: string | null = null;
  let lastName: string | null = null;

  if (identityType === 'individual' || prospectType === 'personal') {
    const parts = winningBidder.split(' ');
    firstName = parts[0] ?? null;
    lastName = parts.slice(1).join(' ') || null;
  } else {
    companyName = winningBidder || null;
  }

  return {
    source: 'WinnerData',
    prospect_type: prospectType,
    company_name: companyName,
    first_name: firstName,
    last_name: lastName,
    property_address: obs['property_address'] ?? obs['site_address'] ?? null,
    property_city: obs['site_city'] ?? null,
    property_state: 'FL',
    property_county: obs['county'] ?? null,
    auction_date: obs['auction_date'] ?? null,
    case_number: obs['case_number'] ?? null,
    sale_type: obs['sale_type'] ?? null,
    purchase_price: obs['tier1_sold_amount'] ?? null,
    assessed_value: obs['pa_assessed_value'] ?? null,
    year_built: obs['property_year_built'] ?? null,
    sqft_heated: obs['property_sqft'] ?? null,
    dor_use_code: obs['dor_use_code'] ?? null,
    dor_use_description: obs['dor_use_description'] ?? null,
    producer_name: producer?.full_name ?? null,
    producer_email: producer?.email ?? null,
    confidence_tier: item.confidence_tier ?? 'unscored',
    portfolio_property_count: obs['portfolio_property_count'] ?? null,
    portfolio_assessed_total: obs['portfolio_assessed_total'] ?? null,
    umbrella_opportunity: derived['umbrella_opportunity'] ?? null,
    flood_opportunity: derived['flood_opportunity'] ?? null,
    wd_item_id: item.id,
    batch_date: item.batch_date
  };
}

Deno.serve(async (req: Request) => {
  const dispatchId = `ezlynx-bridge-${Date.now()}`;

  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'POST required' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Auth: shared secret
  const bridgeSecret = await vaultSecret('ezlynx_bridge_shared_secret');
  if (!bridgeSecret) {
    await logOps(dispatchId, 'ezlynx-zapier-bridge', 'BLOCKED', 'blocker',
      'ezlynx_bridge_shared_secret not in vault — add it to activate the bridge');
    return new Response(JSON.stringify({ error: 'bridge not configured: secret missing from vault' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const suppliedSecret = req.headers.get('X-Bridge-Secret') ?? '';
  if (suppliedSecret !== bridgeSecret) {
    return new Response(JSON.stringify({ error: 'invalid secret' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Get Zapier webhook URL
  const zapierWebhookUrl = await vaultSecret('ezlynx_zapier_webhook_url');
  if (!zapierWebhookUrl) {
    await logOps(dispatchId, 'ezlynx-zapier-bridge', 'BLOCKED', 'blocker',
      'BLOCKER: ezlynx_zapier_webhook_url not in vault. ' +
      'Requires: 1) Zapier account connected to Mariam EZLynx account, ' +
      '2) Zap created with Catch Hook trigger + EZLynx action, ' +
      '3) Webhook URL stored in vault as ezlynx_zapier_webhook_url. ' +
      'This is UNTESTED blocker #2 from issue #19609.');
    return new Response(JSON.stringify({
      error: 'bridge not activated: ezlynx_zapier_webhook_url not in vault',
      blocker: 'requires Zapier + EZLynx setup — see issue #19609 blocker #2'
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  let body: { item_ids?: number[]; batch_date?: string };
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'malformed JSON' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Resolve which items to dispatch
  let itemFilter: string;
  if (body.item_ids && Array.isArray(body.item_ids) && body.item_ids.length > 0) {
    const ids = body.item_ids.map((id) => Number(id)).filter((id) => !isNaN(id));
    itemFilter = `id=in.(${ids.join(',')})&ezlynx_dispatch_status=eq.pending`;
  } else if (body.batch_date) {
    itemFilter = `batch_date=eq.${encodeURIComponent(body.batch_date)}&ezlynx_dispatch_status=eq.pending`;
  } else {
    return new Response(JSON.stringify({ error: 'provide item_ids[] or batch_date' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const itemsResp = await rest(
    `wd_report_items?${itemFilter}&assignment_user_id=not.is.null&select=id,batch_date,auction_id,org_id,assignment_user_id,confidence_tier,observed_signal,derived_context,ezlynx_dispatch_status`
  );

  if (!itemsResp.ok) {
    const errText = await itemsResp.text();
    return new Response(JSON.stringify({ error: 'failed to fetch items', detail: errText }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const items: ReportItemRow[] = await itemsResp.json();

  let dispatched = 0;
  let failed = 0;
  const errors: string[] = [];

  for (const item of items) {
    // Look up producer details for this item
    let producer: PortalUserRow | null = null;
    if (item.assignment_user_id) {
      const pResp = await rest(
        `wd_portal_users?id=eq.${item.assignment_user_id}&select=full_name,email&limit=1`
      );
      if (pResp.ok) {
        const pRows: PortalUserRow[] = await pResp.json();
        producer = pRows[0] ?? null;
      }
    }

    const payload = buildZapierPayload(item, producer);

    try {
      const zapResp = await fetch(zapierWebhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (zapResp.ok) {
        await rest(`wd_report_items?id=eq.${item.id}`, {
          method: 'PATCH',
          headers: { Prefer: 'return=minimal' },
          body: JSON.stringify({
            ezlynx_dispatch_status: 'dispatched',
            ezlynx_dispatched_at: new Date().toISOString()
          })
        });
        dispatched++;
      } else {
        const errText = await zapResp.text();
        await rest(`wd_report_items?id=eq.${item.id}`, {
          method: 'PATCH',
          headers: { Prefer: 'return=minimal' },
          body: JSON.stringify({ ezlynx_dispatch_status: 'failed' })
        });
        errors.push(`item ${item.id}: zapier ${zapResp.status} ${errText.slice(0, 200)}`);
        failed++;
      }
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      await rest(`wd_report_items?id=eq.${item.id}`, {
        method: 'PATCH',
        headers: { Prefer: 'return=minimal' },
        body: JSON.stringify({ ezlynx_dispatch_status: 'failed' })
      });
      errors.push(`item ${item.id}: ${errMsg}`);
      failed++;
    }
  }

  await logOps(
    dispatchId,
    'ezlynx-zapier-bridge',
    failed > 0 ? 'PARTIAL' : 'VERIFIED',
    failed > 0 ? 'warn' : 'info',
    `dispatched=${dispatched} failed=${failed} total=${items.length}` +
      (errors.length > 0 ? ' errors=' + errors.slice(0, 3).join('; ') : '')
  );

  return new Response(JSON.stringify({
    ok: true,
    dispatched,
    failed,
    total: items.length,
    note: 'UNTESTED against real EZLynx account — requires Zapier + EZLynx setup per issue #19609 blocker #2',
    errors: errors.length > 0 ? errors : undefined
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
});
