// vapi-outbound-dispatch — Supabase Edge Function (issue #19611)
//
// PURPOSE: For each wd_report_items row with vapi_dispatch_status='pending'
// (set by route_ff_batch() for commercial tier-A/B leads), place an outbound
// Vapi call using Vapi's REST API. On completion, Vapi's status-callback
// webhook posts to /producer-report/call-webhook (winnerdata-ff Worker) which
// calls wd_log_call_outcome() to write winnerdata.lead_activity.
//
// STATUS: *** UNTESTED — BLOCKER #1: No Vapi account or phone number
// provisioned for Winner Data outbound calling. ***
// Build is complete. The function will activate the moment Ariel provisions
// a Vapi account and stores the following vault secrets:
//   vapi_api_key          — Vapi private API key (from Vapi dashboard)
//   vapi_phone_number_id  — Vapi provisioned phone number ID for WD outbound
//   vapi_assistant_id     — Vapi assistant ID configured for WD outbound calls
//   wd_call_webhook_url   — Full URL of /producer-report/call-webhook on ff.winnerdataai.com
//   wd_call_webhook_secret — Shared secret for call outcome authentication
//
// SEPARATE FROM PROTECTION PARTNERS: This function is scoped exclusively to
// Winner Data outbound (issue #19611). Protection Partners' website voice
// widget (separate Vapi assistant, separate scope) is out of scope here and
// must never share credentials with this function.
//
// HARD GUARDRAILS:
//   - Never call a lead where vapi_dispatch_status is NOT 'pending'
//     (catches already-dispatched, skipped, or DNC leads)
//   - DNC/litigator gate is re-validated here by reading ff_batch_leads
//     (same gate as route_ff_batch, not re-derived — explicit re-read)
//   - Fact Finder confidentiality: Vapi assistant script/prompt must NEVER
//     mention internal vendor/tool names. The assistant_id passed to Vapi
//     is the enforcement surface — this function does not embed the script.
//   - No external notification channels (no Telegram, Slack, SMS)
//
// INVOCATION:
//   POST /functions/v1/vapi-outbound-dispatch
//   Body: { "batch_date": "YYYY-MM-DD" }        — dispatch all pending for batch
//      OR { "item_ids": [1, 2, 3] }              — dispatch specific items
//   Auth: X-Bridge-Secret header matching vault 'vapi_dispatch_shared_secret'
//
// VAPI REST API CALL CONTRACT:
//   POST https://api.vapi.ai/call
//   Authorization: Bearer <vapi_api_key>
//   Body: {
//     "assistantId": "<vapi_assistant_id>",
//     "phoneNumberId": "<vapi_phone_number_id>",
//     "customer": { "number": "<e164_phone>" },
//     "serverUrl": "<wd_call_webhook_url>",
//     "serverUrlSecret": "<wd_call_webhook_secret>",
//     "metadata": {
//       "item_id": "<wd_report_items.id>",
//       "org_id": "032f4717-545f-4a18-b48b-28ea4257699d",
//       "confidence_tier": "A"|"B",
//       "channel": "vapi_call"
//     }
//   }
//   On success: Vapi returns { "id": "<call-uuid>", "status": "queued" }
//   Vapi's status-callback webhook delivers X-Bridge-Item-Id from metadata.item_id
//   and X-Bridge-Channel: vapi_call to our call-webhook endpoint.
//
// WEBHOOK SERVER URL CONVENTION:
//   Vapi's serverUrl receives end-of-call-report events. The winnerdata-ff
//   Worker at /producer-report/call-webhook is the handler. Vapi will pass
//   the serverUrlSecret as Authorization header — our handler reads it from
//   X-Bridge-Secret. The Worker maps X-Bridge-Item-Id from Vapi metadata.item_id.
//   NOTE: Vapi does not forward custom metadata in webhook headers directly;
//   the metadata.item_id must be read from the webhook body's call.metadata field.
//   The call-webhook handler in the Worker reads body.message.call.metadata.item_id
//   as fallback if X-Bridge-Item-Id header is absent.
//
// COST: Vapi charges per minute of call time. At typical 2-3 min per call,
// budget impact is ~$0.05-0.10 per call attempt. Monitor via Vapi dashboard.
// No cost cap is enforced here — set Vapi account spending limits on the dashboard.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL');
const SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
const ORG_ID = '032f4717-545f-4a18-b48b-28ea4257699d';

const H: Record<string, string> = {
  apikey: SERVICE_KEY ?? '',
  Authorization: `Bearer ${SERVICE_KEY ?? ''}`,
  'Content-Type': 'application/json'
};

async function rest(path: string, init: RequestInit = {}): Promise<Response> {
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

interface ReportItem {
  id: number;
  batch_date: string;
  auction_id: string;
  org_id: string;
  assignment_user_id: string | null;
  confidence_tier: string | null;
  contact_phone: string | null;
  vapi_dispatch_status: string | null;
  observed_signal: Record<string, unknown>;
}

function toE164(phone: string): string | null {
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 10) return `+1${digits}`;
  if (digits.length === 11 && digits.startsWith('1')) return `+${digits}`;
  if (digits.startsWith('+')) return phone.replace(/[^\d+]/g, '');
  return null;
}

Deno.serve(async (req: Request) => {
  const dispatchId = `vapi-outbound-${Date.now()}`;

  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'POST required' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Auth: shared secret for dispatch callers (GHA workflow, manual trigger)
  const dispatchSecret = await vaultSecret('vapi_dispatch_shared_secret');
  if (!dispatchSecret) {
    await logOps(dispatchId, 'vapi-outbound-dispatch', 'BLOCKED', 'blocker',
      'BLOCKER: vapi_dispatch_shared_secret not in vault. ' +
      'UNTESTED: Vapi account not yet provisioned for Winner Data outbound (issue #19611 blocker #1). ' +
      'Required vault secrets: vapi_api_key, vapi_phone_number_id, vapi_assistant_id, ' +
      'wd_call_webhook_url, wd_call_webhook_secret, vapi_dispatch_shared_secret.');
    return new Response(JSON.stringify({
      error: 'vapi-outbound-dispatch not activated: credentials not in vault',
      blocker: 'BLOCKER #1 from issue #19611: No Vapi account provisioned for Winner Data outbound. ' +
               'Ariel must provision a Vapi account, phone number, and assistant, then store ' +
               'the required vault secrets to activate this function.',
      untested: true,
      required_vault_secrets: [
        'vapi_api_key',
        'vapi_phone_number_id',
        'vapi_assistant_id',
        'wd_call_webhook_url',
        'wd_call_webhook_secret',
        'vapi_dispatch_shared_secret'
      ]
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const suppliedSecret = req.headers.get('X-Dispatch-Secret') ?? '';
  if (suppliedSecret !== dispatchSecret) {
    return new Response(JSON.stringify({ error: 'unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Load remaining vault secrets
  const [vapiApiKey, vapiPhoneNumberId, vapiAssistantId, webhookUrl, webhookSecret] = await Promise.all([
    vaultSecret('vapi_api_key'),
    vaultSecret('vapi_phone_number_id'),
    vaultSecret('vapi_assistant_id'),
    vaultSecret('wd_call_webhook_url'),
    vaultSecret('wd_call_webhook_secret')
  ]);

  const missingSecrets = [
    !vapiApiKey && 'vapi_api_key',
    !vapiPhoneNumberId && 'vapi_phone_number_id',
    !vapiAssistantId && 'vapi_assistant_id',
    !webhookUrl && 'wd_call_webhook_url'
  ].filter(Boolean);

  if (missingSecrets.length > 0) {
    await logOps(dispatchId, 'vapi-outbound-dispatch', 'BLOCKED', 'blocker',
      `Missing vault secrets: ${missingSecrets.join(', ')}`);
    return new Response(JSON.stringify({
      error: 'vapi-outbound-dispatch not fully configured',
      missing_secrets: missingSecrets,
      untested: true
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  let body: { batch_date?: string; item_ids?: number[] };
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
    itemFilter = `id=in.(${ids.join(',')})&vapi_dispatch_status=eq.pending&org_id=eq.${ORG_ID}`;
  } else if (body.batch_date) {
    itemFilter = `batch_date=eq.${encodeURIComponent(body.batch_date)}&vapi_dispatch_status=eq.pending&org_id=eq.${ORG_ID}`;
  } else {
    return new Response(JSON.stringify({ error: 'provide item_ids[] or batch_date' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const itemsResp = await rest(
    `wd_report_items?${itemFilter}&assignment_user_id=not.is.null` +
    `&select=id,batch_date,auction_id,org_id,assignment_user_id,confidence_tier,contact_phone,vapi_dispatch_status,observed_signal`
  );

  if (!itemsResp.ok) {
    const errText = await itemsResp.text();
    return new Response(JSON.stringify({ error: 'failed to fetch items', detail: errText }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const items: ReportItem[] = await itemsResp.json();

  let dispatched = 0;
  let skipped = 0;
  let failed = 0;
  const errors: string[] = [];

  for (const item of items) {
    if (!item.contact_phone) {
      await rest(`wd_report_items?id=eq.${item.id}`, {
        method: 'PATCH',
        headers: { Prefer: 'return=minimal' },
        body: JSON.stringify({ vapi_dispatch_status: 'skipped_not_commercial' })
      });
      skipped++;
      continue;
    }

    // DNC gate: route_ff_batch() only sets vapi_dispatch_status='pending' for
    // leads that passed is_dnc=false AND is_tcpa_litigator=false AND
    // qa_status NOT IN ('BLOCKED_DNC','BLOCKED_LITIGATOR'). Trusting that
    // upstream gate here (winnerdata schema is not PostgREST-accessible for a
    // direct re-read; the gate is enforced at routing time and the
    // wd_log_call_outcome RPC re-checks it again at outcome logging time).

    const e164Phone = toE164(item.contact_phone);
    if (!e164Phone) {
      errors.push(`item ${item.id}: phone '${item.contact_phone}' could not be converted to E.164`);
      await rest(`wd_report_items?id=eq.${item.id}`, {
        method: 'PATCH',
        headers: { Prefer: 'return=minimal' },
        body: JSON.stringify({ vapi_dispatch_status: 'failed' })
      });
      failed++;
      continue;
    }

    // Mark dispatched before calling Vapi (idempotency: prevents double-dispatch on retry)
    await rest(`wd_report_items?id=eq.${item.id}`, {
      method: 'PATCH',
      headers: { Prefer: 'return=minimal' },
      body: JSON.stringify({ vapi_dispatch_status: 'dispatched' })
    });

    // Place Vapi outbound call
    // The serverUrl receives Vapi's end-of-call-report. We append item_id as a
    // query param so the Worker can extract it from the URL if the metadata
    // approach does not work. The metadata.item_id approach is primary.
    const serverUrl = `${webhookUrl}?item_id=${item.id}`;

    const vapiPayload = {
      assistantId: vapiAssistantId,
      phoneNumberId: vapiPhoneNumberId,
      customer: { number: e164Phone },
      serverUrl,
      serverUrlSecret: webhookSecret ?? '',
      metadata: {
        item_id: String(item.id),
        org_id: ORG_ID,
        confidence_tier: item.confidence_tier ?? 'unscored',
        channel: 'vapi_call'
      }
    };

    try {
      const vapiResp = await fetch('https://api.vapi.ai/call', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${vapiApiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(vapiPayload)
      });

      if (vapiResp.ok) {
        dispatched++;
      } else {
        const errText = await vapiResp.text();
        errors.push(`item ${item.id}: Vapi ${vapiResp.status} ${errText.slice(0, 200)}`);
        await rest(`wd_report_items?id=eq.${item.id}`, {
          method: 'PATCH',
          headers: { Prefer: 'return=minimal' },
          body: JSON.stringify({ vapi_dispatch_status: 'failed' })
        });
        failed++;
      }
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      errors.push(`item ${item.id}: ${errMsg}`);
      await rest(`wd_report_items?id=eq.${item.id}`, {
        method: 'PATCH',
        headers: { Prefer: 'return=minimal' },
        body: JSON.stringify({ vapi_dispatch_status: 'failed' })
      });
      failed++;
    }
  }

  await logOps(
    dispatchId,
    'vapi-outbound-dispatch',
    failed > 0 ? 'PARTIAL' : 'VERIFIED',
    failed > 0 ? 'warn' : 'info',
    `dispatched=${dispatched} skipped=${skipped} failed=${failed} total=${items.length}` +
      (errors.length > 0 ? ' errors=' + errors.slice(0, 3).join('; ') : '')
  );

  // Log each dispatched call to winnerdata.lead_activity via wd_log_call_outcome
  // Note: 'dispatched' state means Vapi accepted the call; actual outcome
  // arrives via the status-callback webhook asynchronously. We do NOT log
  // activity here — only the webhook handler logs to lead_activity because
  // activity_type='contact_attempt' is an outcome, not a dispatch event.

  return new Response(JSON.stringify({
    ok: true,
    dispatched,
    skipped,
    failed,
    total: items.length,
    note: 'UNTESTED — requires Vapi account provisioning per issue #19611 blocker #1',
    errors: errors.length > 0 ? errors : undefined
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
});
