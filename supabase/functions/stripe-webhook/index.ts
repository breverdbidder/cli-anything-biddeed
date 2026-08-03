import Stripe from 'npm:stripe@17';
// stripe-webhook v9
// Adds to v8: after mode=report key issuance, also generates and delivers
// the actual S5 PDF report (the $25 purchase was for the report, not just
// the API key). New in v9:
//   1. Reads case_number/county from checkout metadata (v8 never did)
//   2. Calls https://mcp.biddeed.ai/report/pdf with the freshly-issued customer
//      key — same billable pipeline as any other S5 call. Safe against
//      double-charge: checkChargeAllowance only requires stripe_customer_id
//      on file (which handleReportCheckout already sets); recordBilling's
//      Stripe usage-record path only fires for customers with an ACTIVE
//      subscription item, which one-time buyers never have, so it settles
//      as a no-op billing_events row, not a second charge.
//   3. Uploads the PDF to Storage bucket 'exports' at s5/{customer_id}/{mca_id}.pdf
//      (same path convention http.js's storeReportPdfExport already uses for
//      the MCP redelivery side-channel — deliberately not a new convention).
//   4. Inserts s5_pdf_cache, updates report_delivery_queue.report_pdf_url
//      with a 7-day signed URL, sends a separate report-download email
//      (never the API key — that email is unchanged from v8).
// Failures in the report step are caught and logged (report_delivery_queue
// status='failed' + agent_ops_log) but never thrown — a report-generation
// failure must not roll back key issuance or trigger a Stripe retry, which
// would re-bump s5_calls_quota and re-issue a new key on every retry.
// Subscription mode unchanged from v7/v8.
const SUPABASE_URL = Deno.env.get('SUPABASE_URL');
const SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
const MCP_BASE_URL = 'https://mcp.biddeed.ai';
const REPORT_DELIVERY_DISPATCH_ID = 'stripe-webhook-v9-pdf-delivery';
const SIGNED_URL_TTL_SECONDS = 7 * 24 * 60 * 60; // 7 days
const cryptoProvider = Stripe.createSubtleCryptoProvider();
const stripe = new Stripe('sk_unused_signature_only', {
  apiVersion: '2024-06-20'
});
const H = {
  apikey: SERVICE_KEY,
  Authorization: `Bearer ${SERVICE_KEY}`,
  'Content-Type': 'application/json'
};
async function rest(path, init = {}) {
  return fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...init,
    headers: {
      ...H,
      ...init.headers ?? {}
    }
  });
}
async function vaultSecret(name) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/vault_secret`, {
    method: 'POST',
    headers: H,
    body: JSON.stringify({
      p_name: name
    })
  });
  if (!r.ok) return null;
  const v = await r.json();
  return typeof v === 'string' ? v : null;
}
let cachedWebhookSecret = null;
async function webhookSecret() {
  if (cachedWebhookSecret) return cachedWebhookSecret;
  const s = await vaultSecret('stripe_webhook_secret');
  cachedWebhookSecret = s;
  return s;
}
// ----------------------------------------------------------------- key utils
const B62 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
function randKey() {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  let s = '';
  for (const b of bytes)s += B62[b % 62];
  return 'bd_live_' + s;
}
async function sha256Hex(s) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return Array.from(new Uint8Array(d)).map((b)=>b.toString(16).padStart(2, '0')).join('');
}
async function parkPlaintext(customerId, plaintext) {
  await rest('pending_key_delivery', {
    method: 'POST',
    headers: {
      Prefer: 'resolution=merge-duplicates,return=minimal'
    },
    body: JSON.stringify({
      customer_id: customerId,
      plaintext_key: plaintext,
      read_at: null
    })
  });
}
async function issueKey(customerId, tier, stripeCustomerId, forceNew) {
  if (!forceNew) {
    const existing = await rest(`mcp_api_keys?customer_id=eq.${customerId}&active=eq.true&select=key_id&limit=1`);
    if (existing.ok) {
      const rows = await existing.json();
      if (Array.isArray(rows) && rows.length) return null; // already has key
    }
  } else {
    // deactivate existing keys so uniqueness index allows a new one
    await rest(`mcp_api_keys?customer_id=eq.${customerId}&active=eq.true`, {
      method: 'PATCH',
      headers: {
        Prefer: 'return=minimal'
      },
      body: JSON.stringify({
        active: false,
        is_active: false,
        revoked_at: new Date().toISOString()
      })
    });
  }
  const plaintext = randKey();
  const ins = await rest('mcp_api_keys', {
    method: 'POST',
    headers: {
      Prefer: 'return=minimal'
    },
    body: JSON.stringify({
      customer_id: customerId,
      key_prefix: plaintext.slice(0, 14),
      key_hash: await sha256Hex(plaintext),
      server: 'biddeed',
      product: 'biddeed',
      tier,
      active: true,
      is_active: true,
      stripe_customer_id: stripeCustomerId
    })
  });
  if (!ins.ok) {
    if (ins.status === 409) return null; // race backstop
    console.error('key insert failed', ins.status);
    return null;
  }
  await parkPlaintext(customerId, plaintext);
  return plaintext;
}
// ----------------------------------------------------------------- email
async function sendKeyEmail(email, apiKey) {
  try {
    const resendKey = await vaultSecret('resend_api_key');
    const fromAddr = await vaultSecret('resend_from_address');
    if (!resendKey || !fromAddr) return;
    const body = [
      'Your BidDeed.AI API key:',
      '',
      apiKey,
      '',
      'Keep this key private. Use it to access your S5 report at mcp.biddeed.ai',
      '',
      'Get started: https://biddeed.ai/chat',
      '',
      'Informational only — not legal, financial, or investment advice.',
      'BidDeed.AI · Everest Capital USA · https://biddeed.ai/disclaimer'
    ].join('\n');
    await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${resendKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: fromAddr,
        to: [
          email
        ],
        subject: 'Your BidDeed.AI access key',
        text: body
      })
    });
  } catch (e) {
    console.error('sendKeyEmail failed', e);
  }
}
// NEW in v9 — separate report-download email. Deliberately never includes
// the API key (that's sendKeyEmail's job, sent independently).
async function sendReportEmail(email, { caseNumber, county, address, auctionDate, downloadUrl }) {
  const resendKey = await vaultSecret('resend_api_key');
  const fromAddr = await vaultSecret('resend_from_address');
  if (!resendKey || !fromAddr) return { ok: false, error: 'resend_api_key/resend_from_address not configured in vault' };
  const countyLabel = county ? county.charAt(0).toUpperCase() + county.slice(1) : '';
  const body = [
    `Your BidDeed.AI Shapira Report — Case ${caseNumber} (${countyLabel} County, FL)`,
    '',
    address ? `Property: ${address}` : null,
    auctionDate ? `Auction date: ${auctionDate}` : null,
    '',
    `Download your report (link valid 7 days): ${downloadUrl}`,
    '',
    'Informational only — not legal, financial, or investment advice. Verify independently and consult a licensed Florida attorney before bidding.',
    'BidDeed.AI · Everest Capital USA · https://biddeed.ai/disclaimer'
  ].filter((l)=>l !== null).join('\n');
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${resendKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      from: fromAddr,
      to: [
        email
      ],
      subject: `Your BidDeed S5 Report - ${countyLabel} Case ${caseNumber}`,
      text: body
    })
  });
  if (!r.ok) {
    const errText = await r.text();
    return { ok: false, error: `resend send failed: ${errText}`.slice(0, 500) };
  }
  const sent = await r.json().catch(()=>({}));
  return { ok: true, resendId: sent?.id ?? null };
}
// ----------------------------------------------------------------- customer
async function findOrCreateCustomer(email) {
  const r = await rest(`mcp_customers?email=eq.${encodeURIComponent(email)}&select=customer_id`);
  if (r.ok) {
    const rows = await r.json();
    if (Array.isArray(rows) && rows.length) return rows[0].customer_id;
  }
  const ins = await rest('mcp_customers', {
    method: 'POST',
    headers: {
      Prefer: 'return=representation,resolution=merge-duplicates'
    },
    body: JSON.stringify({
      email,
      customer_type: 'human',
      tier_id: 'free',
      active: true
    })
  });
  if (ins.ok) {
    const c = await ins.json();
    const id = Array.isArray(c) ? c[0]?.customer_id : c?.customer_id;
    if (id) return id;
  }
  const re = await rest(`mcp_customers?email=eq.${encodeURIComponent(email)}&select=customer_id`);
  const rows = await re.json();
  if (Array.isArray(rows) && rows.length) return rows[0].customer_id;
  throw new Error('could not find or create customer');
}
async function customerByStripeId(stripeCustomerId) {
  const r = await rest(`mcp_customers?stripe_customer_id=eq.${encodeURIComponent(stripeCustomerId)}&select=customer_id`);
  if (!r.ok) return null;
  const rows = await r.json();
  return rows?.[0]?.customer_id ?? null;
}
// ----------------------------------------------------------------- session complete
async function completeSession(sessionId, stripeCustomerId, stripeSubscriptionId) {
  const sp = {
    status: 'completed',
    completed_at: new Date().toISOString()
  };
  if (stripeCustomerId) sp.stripe_customer_id = stripeCustomerId;
  if (stripeSubscriptionId) sp.stripe_subscription_id = stripeSubscriptionId;
  await rest(`stripe_checkout_sessions?session_id=eq.${encodeURIComponent(sessionId)}`, {
    method: 'PATCH',
    headers: {
      Prefer: 'return=minimal'
    },
    body: JSON.stringify(sp)
  });
}
// ----------------------------------------------------------------- consent
async function writeConsent(email, marketingConsent) {
  try {
    await rest('lead_profiles', {
      method: 'POST',
      headers: {
        Prefer: 'return=minimal,resolution=merge-duplicates'
      },
      body: JSON.stringify({
        email,
        marketing_consent: marketingConsent,
        marketing_consent_at: marketingConsent ? new Date().toISOString() : null,
        source: 'website_checkout',
        stage: 'customer'
      })
    });
  } catch (e) {
    console.error('writeConsent failed', e);
  }
}
// ----------------------------------------------------------------- ops log
async function logOpsResult(task, status, severity, evidence) {
  await rest('agent_ops_log', {
    method: 'POST',
    headers: {
      Prefer: 'return=minimal'
    },
    body: JSON.stringify({
      dispatch_id: REPORT_DELIVERY_DISPATCH_ID,
      task,
      status,
      severity,
      evidence: String(evidence).slice(0, 2000)
    })
  }).catch((e)=>console.error('logOpsResult failed', e));
}
async function reportQueuePatch(sessionId, patch) {
  if (!sessionId) return;
  await rest(`report_delivery_queue?stripe_session_id=eq.${encodeURIComponent(sessionId)}`, {
    method: 'PATCH',
    headers: {
      Prefer: 'return=minimal'
    },
    body: JSON.stringify(patch)
  }).catch((e)=>console.error('report_delivery_queue patch failed', e));
}
// NEW in v9 — generates the actual S5 PDF via the existing billable
// /report/pdf HTTP surface (same pipeline predict_auction_outcome uses:
// cert gate, idempotency, billing), stores it, caches it, emails a
// download link. Never throws — all failures are caught, logged, and
// leave report_delivery_queue in 'failed' with the reason.
async function deliverReportPdf({ sessionId, paymentIntent, caseNumber, county, email, customerId, apiKeyPlaintext }) {
  await reportQueuePatch(sessionId, { status: 'paid', stripe_payment_intent: paymentIntent });
  if (!caseNumber || !county) {
    await reportQueuePatch(sessionId, { status: 'failed', error: 'checkout session missing case_number/county metadata' });
    await logOpsResult('s5_pdf_delivery', 'BLOCKED', 'blocker', `session=${sessionId}: missing case_number/county metadata`);
    return;
  }
  try {
    const auctionRes = await rest(`multi_county_auctions?case_number=eq.${encodeURIComponent(caseNumber)}&county=eq.${encodeURIComponent(county)}&select=id,property_address,auction_date&limit=1`);
    const auctionRows = auctionRes.ok ? await auctionRes.json() : [];
    const auction = auctionRows?.[0];
    if (!auction?.id) {
      await reportQueuePatch(sessionId, { status: 'failed', error: `no multi_county_auctions match for case_number=${caseNumber} county=${county}` });
      await logOpsResult('s5_pdf_delivery', 'BLOCKED', 'blocker', `session=${sessionId} case=${caseNumber}: no matching auction row`);
      return;
    }
    const mcaId = auction.id;
    const pdfRes = await fetch(`${MCP_BASE_URL}/report/pdf?case_number=${encodeURIComponent(caseNumber)}&county=${encodeURIComponent(county)}`, {
      headers: {
        Authorization: `Bearer ${apiKeyPlaintext}`
      }
    });
    if (!pdfRes.ok) {
      const errText = await pdfRes.text();
      await reportQueuePatch(sessionId, { status: 'failed', error: `report/pdf ${pdfRes.status}: ${errText}`.slice(0, 500) });
      await logOpsResult('s5_pdf_delivery', 'BLOCKED', 'blocker', `session=${sessionId} case=${caseNumber}: report/pdf ${pdfRes.status}: ${errText.slice(0, 300)}`);
      return;
    }
    const pdfBytes = new Uint8Array(await pdfRes.arrayBuffer());
    const magic = new TextDecoder().decode(pdfBytes.slice(0, 4));
    if (magic !== '%PDF' || pdfBytes.length === 0) {
      await reportQueuePatch(sessionId, { status: 'failed', error: 'report/pdf returned non-PDF or empty bytes' });
      await logOpsResult('s5_pdf_delivery', 'BLOCKED', 'blocker', `session=${sessionId} case=${caseNumber}: non-PDF/empty response (${pdfBytes.length} bytes)`);
      return;
    }
    const storagePath = `s5/${customerId}/${mcaId}.pdf`;
    const putRes = await fetch(`${SUPABASE_URL}/storage/v1/object/exports/${storagePath}`, {
      method: 'POST',
      headers: {
        apikey: SERVICE_KEY,
        Authorization: `Bearer ${SERVICE_KEY}`,
        'Content-Type': 'application/pdf',
        'x-upsert': 'true'
      },
      body: pdfBytes
    });
    if (!putRes.ok) {
      const errText = await putRes.text();
      await reportQueuePatch(sessionId, { status: 'failed', error: `storage upload ${putRes.status}: ${errText}`.slice(0, 500) });
      await logOpsResult('s5_pdf_delivery', 'BLOCKED', 'blocker', `session=${sessionId} case=${caseNumber}: storage upload ${putRes.status}: ${errText.slice(0, 300)}`);
      return;
    }
    const signRes = await fetch(`${SUPABASE_URL}/storage/v1/object/sign/exports/${storagePath}`, {
      method: 'POST',
      headers: H,
      body: JSON.stringify({
        expiresIn: SIGNED_URL_TTL_SECONDS
      })
    });
    if (!signRes.ok) {
      const errText = await signRes.text();
      await reportQueuePatch(sessionId, { status: 'failed', error: `sign url ${signRes.status}: ${errText}`.slice(0, 500) });
      await logOpsResult('s5_pdf_delivery', 'BLOCKED', 'blocker', `session=${sessionId} case=${caseNumber}: sign url ${signRes.status}: ${errText.slice(0, 300)}`);
      return;
    }
    const signed = await signRes.json();
    if (!signed?.signedURL) {
      await reportQueuePatch(sessionId, { status: 'failed', error: 'sign url response missing signedURL' });
      await logOpsResult('s5_pdf_delivery', 'BLOCKED', 'blocker', `session=${sessionId} case=${caseNumber}: sign url response missing signedURL`);
      return;
    }
    const downloadUrl = `${SUPABASE_URL}/storage/v1${signed.signedURL}`;
    const auctionDate = auction.auction_date ?? null;
    const isOutcomeComplete = auctionDate ? new Date(auctionDate) <= new Date() : false;
    await rest('s5_pdf_cache', {
      method: 'POST',
      headers: {
        Prefer: 'return=minimal'
      },
      body: JSON.stringify({
        mca_id: mcaId,
        customer_id: customerId,
        storage_path: storagePath,
        auction_status_at_generation: isOutcomeComplete ? 'past' : 'upcoming',
        is_outcome_complete: isOutcomeComplete,
        file_size_bytes: pdfBytes.length,
        pdf_version: 1
      })
    }).catch((e)=>console.error('s5_pdf_cache insert failed', e));
    await reportQueuePatch(sessionId, {
      status: 'delivered',
      report_pdf_url: downloadUrl,
      delivered_at: new Date().toISOString()
    });
    const emailResult = await sendReportEmail(email, {
      caseNumber,
      county,
      address: auction.property_address ?? null,
      auctionDate,
      downloadUrl
    });
    if (!emailResult.ok) {
      await logOpsResult('s5_pdf_delivery', 'PARTIAL', 'warn', `session=${sessionId} case=${caseNumber}: report_pdf_url set but report email failed: ${emailResult.error}`);
      return;
    }
    await logOpsResult('s5_pdf_delivery', 'VERIFIED', 'info', `session=${sessionId} case=${caseNumber} customer=${customerId}: storage_path=${storagePath} resend_id=${emailResult.resendId} report_pdf_url set`);
  } catch (e) {
    await reportQueuePatch(sessionId, { status: 'failed', error: `threw: ${e.message}`.slice(0, 500) });
    await logOpsResult('s5_pdf_delivery', 'BLOCKED', 'blocker', `session=${sessionId} case=${caseNumber}: threw: ${e.message}`);
  }
}
// ----------------------------------------------------------------- handlers
async function handleReportCheckout(obj, eventId) {
  // $25 one-time report purchase
  const email = (obj.metadata?.customer_email || obj.customer_email || '').toLowerCase().trim();
  if (!email) return 'report checkout missing email';
  const stripeCustomerId = typeof obj.customer === 'string' ? obj.customer : obj.customer?.id ?? null;
  const marketingConsent = obj.metadata?.marketing_consent === 'true';
  const customerId = await findOrCreateCustomer(email);
  // Bump s5_calls_quota +1, ensure tier >= pro
  const cur = await rest(`mcp_customers?customer_id=eq.${customerId}&select=tier_id,s5_calls_quota,stripe_customer_id`);
  const curRows = cur.ok ? await cur.json() : [];
  const curTier = curRows?.[0]?.tier_id ?? 'free';
  const curQuota = Number(curRows?.[0]?.s5_calls_quota ?? 0);
  const patch = {
    s5_calls_quota: curQuota + 1
  };
  if (stripeCustomerId) patch.stripe_customer_id = stripeCustomerId;
  if (curTier === 'free') patch.tier_id = 'pro';
  await rest(`mcp_customers?customer_id=eq.${customerId}`, {
    method: 'PATCH',
    headers: {
      Prefer: 'return=minimal'
    },
    body: JSON.stringify(patch)
  });
  const effectiveTier = curTier === 'free' ? 'pro' : curTier;
  // Issue fresh key (forceNew=true so /report-success always shows a key)
  const plaintext = await issueKey(customerId, effectiveTier, stripeCustomerId, true);
  // Send email non-blocking
  if (plaintext) sendKeyEmail(email, plaintext);
  // Write consent
  writeConsent(email, marketingConsent);
  // Log subscription event
  await rest('subscription_events', {
    method: 'POST',
    headers: {
      Prefer: 'return=minimal'
    },
    body: JSON.stringify({
      customer_id: customerId,
      event_type: 'report_purchase',
      from_tier: curTier,
      to_tier: effectiveTier,
      mrr_delta_usd: 0,
      stripe_event_id: eventId,
      notes: 'Website $25 S5 report purchase via stripe-webhook v9'
    })
  }).catch(()=>{});
  if (obj.id) await completeSession(obj.id, stripeCustomerId, null);
  // NEW in v9 — generate + deliver the actual PDF. Non-blocking w.r.t. the
  // webhook's own response/activationError: report-generation failures are
  // caught internally and logged, never rethrown here.
  if (plaintext) {
    const paymentIntent = typeof obj.payment_intent === 'string' ? obj.payment_intent : obj.payment_intent?.id ?? null;
    await deliverReportPdf({
      sessionId: obj.id,
      paymentIntent,
      caseNumber: obj.metadata?.case_number ?? null,
      county: obj.metadata?.county ?? null,
      email,
      customerId,
      apiKeyPlaintext: plaintext
    });
  } else {
    await logOpsResult('s5_pdf_delivery', 'BLOCKED', 'blocker', `session=${obj.id}: no fresh key issued (issueKey returned null) — cannot call /report/pdf`);
  }
  return null;
}
async function handleSubscriptionCheckout(obj, eventId) {
  const customerId = obj.metadata?.customer_id ?? null;
  if (!customerId) return 'checkout.session.completed missing metadata.customer_id';
  const tierId = obj.metadata?.tier_id ?? null;
  const stripeCustomerId = typeof obj.customer === 'string' ? obj.customer : obj.customer?.id ?? null;
  const stripeSubscriptionId = typeof obj.subscription === 'string' ? obj.subscription : obj.subscription?.id ?? null;
  const email = (obj.metadata?.customer_email || obj.customer_email || '').toLowerCase().trim();
  const marketingConsent = obj.metadata?.marketing_consent === 'true';
  // Update customer record
  const patch = {};
  if (stripeCustomerId) patch.stripe_customer_id = stripeCustomerId;
  if (tierId) patch.tier_id = tierId;
  if (Object.keys(patch).length) {
    await rest(`mcp_customers?customer_id=eq.${customerId}`, {
      method: 'PATCH',
      headers: {
        Prefer: 'return=minimal'
      },
      body: JSON.stringify(patch)
    });
  }
  const effectiveTier = tierId ?? 'investor';
  const plaintext = await issueKey(customerId, effectiveTier, stripeCustomerId, false);
  if (plaintext && email) sendKeyEmail(email, plaintext);
  if (email) writeConsent(email, marketingConsent);
  if (obj.id) await completeSession(obj.id, stripeCustomerId, stripeSubscriptionId);
  await rest('subscription_events', {
    method: 'POST',
    headers: {
      Prefer: 'return=minimal'
    },
    body: JSON.stringify({
      customer_id: customerId,
      event_type: 'activation',
      from_tier: 'free',
      to_tier: effectiveTier,
      mrr_delta_usd: 0,
      stripe_event_id: eventId,
      notes: 'stripe-webhook v9 subscription activation'
    })
  }).catch(()=>{});
  return null;
}
async function handleActivation(evt) {
  const obj = evt.data?.object;
  if (!obj) return null;
  if (evt.type === 'checkout.session.completed') {
    const mode = obj.metadata?.mode ?? '';
    if (mode === 'report') return handleReportCheckout(obj, evt.id);
    return handleSubscriptionCheckout(obj, evt.id);
  }
  if (evt.type === 'customer.subscription.created' || evt.type === 'customer.subscription.updated') {
    const stripeCustomerId = typeof obj.customer === 'string' ? obj.customer : obj.customer?.id ?? null;
    let customerId = obj.metadata?.customer_id ?? null;
    if (!customerId && stripeCustomerId) customerId = await customerByStripeId(stripeCustomerId);
    if (!customerId) return null;
    const tierId = obj.metadata?.tier_id ?? null;
    const plaintext = await issueKey(customerId, tierId ?? 'investor', stripeCustomerId, false);
    if (plaintext) {
      const cur = await rest(`mcp_customers?customer_id=eq.${customerId}&select=email`);
      const rows = cur.ok ? await cur.json() : [];
      const email = rows?.[0]?.email;
      if (email) sendKeyEmail(email, plaintext);
    }
    return null;
  }
  return null;
}
// ----------------------------------------------------------------- logging
async function alreadyProcessed(eventId) {
  const r = await rest(`stripe_webhook_events?event_id=eq.${eventId}&select=processed`);
  if (!r.ok) return false;
  const rows = await r.json();
  return Array.isArray(rows) && rows.length > 0 && rows[0].processed === true;
}
async function storeEvent(evt, processed, err) {
  const obj = evt.data?.object;
  const sessionId = evt.type.startsWith('checkout.session.') ? obj?.id ?? null : null;
  const row = {
    event_id: evt.id,
    event_type: evt.type,
    session_id: sessionId,
    payload: evt,
    processed,
    processed_at: new Date().toISOString(),
    error: err
  };
  let r = await rest('stripe_webhook_events', {
    method: 'POST',
    headers: {
      Prefer: 'resolution=merge-duplicates,return=minimal'
    },
    body: JSON.stringify(row)
  });
  if (!r.ok) {
    const body = await r.text();
    if (body.includes('23503')) {
      row.session_id = null;
      r = await rest('stripe_webhook_events', {
        method: 'POST',
        headers: {
          Prefer: 'resolution=merge-duplicates,return=minimal'
        },
        body: JSON.stringify(row)
      });
    }
  }
}
Deno.serve(async (req)=>{
  if (req.method !== 'POST') return new Response('method not allowed', {
    status: 405
  });
  const sig = req.headers.get('stripe-signature');
  if (!sig) return new Response('missing stripe-signature', {
    status: 400
  });
  const secret = await webhookSecret();
  if (!secret) return new Response('webhook secret not in vault', {
    status: 500
  });
  const raw = await req.text();
  let evt;
  try {
    evt = await stripe.webhooks.constructEventAsync(raw, sig, secret, undefined, cryptoProvider);
  } catch (e) {
    return new Response(`signature verification failed: ${e.message}`, {
      status: 400
    });
  }
  if (await alreadyProcessed(evt.id)) {
    return new Response(JSON.stringify({
      received: true,
      duplicate: true
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }
  let activationError = null;
  try {
    activationError = await handleActivation(evt);
  } catch (e) {
    activationError = `threw: ${e.message}`;
  }
  await storeEvent(evt, activationError === null, activationError);
  if (activationError) {
    console.error('activation failed', evt.id, evt.type, activationError);
    return new Response(JSON.stringify({
      received: true,
      error: activationError
    }), {
      status: 500,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }
  return new Response(JSON.stringify({
    received: true,
    activated: true
  }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json'
    }
  });
});
