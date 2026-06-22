#!/usr/bin/env node
'use strict';
/**
 * BCPAO folio->PIN harvester (Playwright + Cloudflare bypass)
 *
 * Reads queued accounts from bcpao_fetch_jobs, resolves each via
 * bcpao.us API (called from inside the Playwright browser context to
 * inherit Cloudflare clearance cookies), writes results to
 * brevard_folio_pin_bridge, then calls bcpao_folio_drain() to push
 * resolved PINs back into multi_county_auctions.
 *
 * Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
 */

const { chromium } = require('@playwright/test');

const SUPABASE_URL = (process.env.SUPABASE_URL || '').replace(/\/$/, '');
const SUPABASE_KEY  = process.env.SUPABASE_SERVICE_ROLE_KEY || '';

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required');
  process.exit(1);
}

const BATCH_SIZE    = 50;
const RATE_DELAY_MS = 2200;   // 1 req / ~2 sec
const MAX_RETRIES   = 3;
const BCPAO_BASE    = 'https://bcpao.us';

// ── Supabase REST ─────────────────────────────────────────────────────────────

async function sbFetch(path, method = 'GET', body = null, extra = {}) {
  const headers = {
    apikey:        SUPABASE_KEY,
    Authorization: `Bearer ${SUPABASE_KEY}`,
    'Content-Type': 'application/json',
    ...extra,
  };
  const opts = { method, headers };
  if (body !== null) opts.body = JSON.stringify(body);
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, opts);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Supabase ${method} ${path}: HTTP ${res.status} — ${txt.slice(0, 300)}`);
  }
  const txt = await res.text();
  return txt ? JSON.parse(txt) : null;
}

async function getQueuedBatch() {
  return sbFetch(
    `bcpao_fetch_jobs?status=eq.queued&order=account&limit=${BATCH_SIZE}&select=account`
  );
}

async function markDone(account, pin) {
  return sbFetch(
    `bcpao_fetch_jobs?account=eq.${encodeURIComponent(account)}`,
    'PATCH',
    { status: 'done', parcel_id: pin, done_at: new Date().toISOString() },
    { Prefer: 'return=minimal' }
  );
}

async function markEmpty(account) {
  return sbFetch(
    `bcpao_fetch_jobs?account=eq.${encodeURIComponent(account)}`,
    'PATCH',
    { status: 'empty', done_at: new Date().toISOString() },
    { Prefer: 'return=minimal' }
  );
}

async function markFailed(account, err) {
  const errStr = String(err).slice(0, 400);
  // Try with last_error column; fall back if column not yet in schema cache
  try {
    return await sbFetch(
      `bcpao_fetch_jobs?account=eq.${encodeURIComponent(account)}`,
      'PATCH',
      { status: 'failed', last_error: errStr, done_at: new Date().toISOString() },
      { Prefer: 'return=minimal' }
    );
  } catch (e) {
    if (e.message.includes('PGRST204') || e.message.includes('last_error')) {
      return sbFetch(
        `bcpao_fetch_jobs?account=eq.${encodeURIComponent(account)}`,
        'PATCH',
        { status: 'failed', done_at: new Date().toISOString() },
        { Prefer: 'return=minimal' }
      );
    }
    throw e;
  }
}

async function upsertBridge(folio, pin) {
  return sbFetch(
    'brevard_folio_pin_bridge',
    'POST',
    { folio, resolved_pin: pin, match_method: 'bcpao_playwright' },
    { Prefer: 'resolution=ignore-duplicates,return=minimal' }
  );
}

async function callDrain() {
  return sbFetch('rpc/bcpao_folio_drain', 'POST', {});
}

// ── PIN extraction ────────────────────────────────────────────────────────────

// Brevard PIN pattern: "23-3627-00-56-00000.0" or "23 3627 00 56"
const PIN_RE = /\b\d{2}[-\s]\d{4}[-\s][A-Z0-9]{2}[-\s][A-Z0-9*]+[-\s][A-Z0-9.]+\b/i;

/**
 * Try to resolve a PIN for the given account using the browser context.
 *
 * Avoids page.evaluate() entirely (Playwright 1.58 argument handling can be
 * unpredictable). Uses:
 *   Strategy 1: context.request.get() for the JSON API (inherits CF cookies)
 *   Strategy 2: page.goto() + Playwright locators for DOM extraction
 */
async function resolvePin(page, account) {
  const ctx = page.context();

  // Strategy 1: getpin JSON API via Node.js APIRequestContext (uses browser cookies)
  try {
    const resp = await ctx.request.get(
      `${BCPAO_BASE}/api/search/getpin?acctno=${account}`,
      { headers: { Accept: 'application/json' } }
    );
    if (resp.ok()) {
      const ct = resp.headers()['content-type'] || '';
      if (ct.includes('json')) {
        const data = await resp.json();
        const pin = data.pin || data.parcelID || data.parcelId
                 || data.ParcelID || data.parcel_id || data.parcelNumber;
        if (pin && String(pin).trim()) return String(pin).trim();
      }
    }
  } catch (e) {
    console.log(`  ${account}: API strategy failed (${e.message.slice(0, 60)}), trying DOM...`);
  }

  // Strategy 2: navigate to Property Details and read the rendered DOM with locators
  await page.goto(`${BCPAO_BASE}/Property/Details#acct=${account}`, {
    waitUntil: 'networkidle',
    timeout: 30_000,
  });
  await page.waitForTimeout(1500);

  // Try CSS selectors that BCPAO uses for the parcel number field
  const candidates = [
    '#parcelNumber',
    '[data-field="parcelID"]',
    '.parcel-id',
    '[class*="parcel-number"]',
    'dt:has-text("Parcel") + dd',
    'th:has-text("Parcel") + td',
  ];
  for (const sel of candidates) {
    const loc = page.locator(sel).first();
    const txt = await loc.textContent({ timeout: 2000 }).catch(() => null);
    if (txt && /^\d{2}[-\s]/.test(txt.trim())) return txt.trim();
  }

  // Fallback: grep the page body text via page.content() (avoids evaluate)
  const html = await page.content();
  const m = html.match(PIN_RE);
  return m ? m[0] : null;
}

// ── CF warm-up ────────────────────────────────────────────────────────────────

async function warmupCloudflare(page) {
  console.log('Warming up Cloudflare clearance via bcpao.us ...');
  await page.goto(BCPAO_BASE, { waitUntil: 'domcontentloaded', timeout: 30_000 });

  const title = await page.title();
  if (/just a moment|checking your browser/i.test(title)) {
    console.log('  CF challenge detected — waiting up to 15s...');
    // Wait for title to change from CF challenge page (poll without waitForFunction)
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(1000);
      const t = await page.title();
      if (!/just a moment|checking your browser/i.test(t)) break;
    }
  }
  await page.waitForTimeout(1000);
  console.log(`  CF warm-up done (title: "${await page.title()}")`);
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-blink-features=AutomationControlled',
    ],
  });

  const context = await browser.newContext({
    userAgent:    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport:     { width: 1920, height: 1080 },
    locale:       'en-US',
    timezoneId:   'America/New_York',
    extraHTTPHeaders: { 'Accept-Language': 'en-US,en;q=0.9' },
  });

  const page = await context.newPage();
  await warmupCloudflare(page);

  let totalDone    = 0;
  let totalEmpty   = 0;
  let totalFailed  = 0;
  let batchNum     = 0;

  while (true) {
    const batch = await getQueuedBatch();
    if (!batch || batch.length === 0) {
      console.log('\nNo more queued accounts.');
      break;
    }
    batchNum++;
    console.log(`\nBatch #${batchNum}: ${batch.length} accounts`);

    for (const job of batch) {
      const account = job.account;
      let pin      = null;
      let lastErr  = null;

      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
          pin = await resolvePin(page, account);
          lastErr = null;
          break;
        } catch (e) {
          lastErr = e;
          console.log(`  ${account}: attempt ${attempt}/${MAX_RETRIES} error — ${e.message}`);
          if (attempt < MAX_RETRIES) {
            await page.waitForTimeout(RATE_DELAY_MS * attempt);
            // Re-warm CF before retrying
            await warmupCloudflare(page).catch(() => {});
          }
        }
      }

      if (pin) {
        await upsertBridge(account, pin);
        await markDone(account, pin);
        console.log(`  ${account} -> ${pin}`);
        totalDone++;
      } else if (lastErr) {
        await markFailed(account, lastErr.message || String(lastErr));
        console.error(`  ${account}: FAILED — ${lastErr.message}`);
        totalFailed++;
      } else {
        await markEmpty(account);
        console.log(`  ${account}: no PIN found (empty)`);
        totalEmpty++;
      }

      await page.waitForTimeout(RATE_DELAY_MS);
    }

    console.log(`  Batch #${batchNum} done | done=${totalDone} empty=${totalEmpty} failed=${totalFailed}`);
  }

  console.log(`\nHarvest complete: done=${totalDone} empty=${totalEmpty} failed=${totalFailed}`);

  // Push resolved PINs into multi_county_auctions.parcel_id
  console.log('\nRunning bcpao_folio_drain()...');
  try {
    const drained = await callDrain();
    console.log(`Drain: ${JSON.stringify(drained)} MCA rows updated`);
  } catch (e) {
    console.error(`Drain failed: ${e.message}`);
  }

  await browser.close();

  if (totalDone === 0 && totalEmpty === 0) {
    console.error('WARNING: zero accounts resolved — BCPAO response format may have changed');
    process.exit(1);
  }
}

main().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
