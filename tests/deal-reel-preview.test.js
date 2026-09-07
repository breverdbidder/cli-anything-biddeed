// tests/deal-reel-preview.test.js — issue #20077 P0: signed-out visitors must
// never see the "PREVIEW — pending approval, not yet public" banner, and the
// returning-visitor county chip must never name a county other than the page
// they're currently on. Uses Node's built-in test runner, same pattern as
// tests/support-bot.test.js. Run with:
//   node --test tests/deal-reel-preview.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import worker from '../src/worker.js';

const ENV = {};

function makeCtx() {
  return { waitUntil: () => {} };
}

// Mirrors tests/support-bot.test.js's installFetchMock: routes every global
// fetch() call the worker makes to the first matching handler.
function installFetchMock(handlers) {
  const original = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    for (const [matcher, handler] of handlers) {
      const matches = typeof matcher === 'string' ? url.includes(matcher) : matcher.test(url);
      if (matches) return handler(url, init);
    }
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  };
  return { restore: () => { globalThis.fetch = original; } };
}

function reelFixture(overrides = {}) {
  return {
    id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
    status: 'posted',
    phase: 'postsale',
    county: 'martin',
    case_number: '25001204CAAXMX',
    short_code: 'O7EPH7',
    short_url: 'biddeed.ai/r/O7EPH7',
    sale_type: 'foreclosure',
    sold_amount: 826200,
    assessed_value: 700000,
    delta_pct: 18,
    condition_json: {},
    auction_date: '2026-08-01',
    property_address: '123 Main St',
    archetype: 'shock_number',
    video_v2_url: 'https://example.test/reel.mp4',
    aerial_tight_url: 'https://example.test/aerial.png',
    ...overrides,
  };
}

function rpcMock(rpcName, body) {
  return [new RegExp(`rest/v1/rpc/${rpcName}$`), () => new Response(JSON.stringify(body), { status: 200 })];
}

// Bare "PREVIEW" also matches CSS class names (.deal-preview-banner,
// .reels-preview-banner) that are always in the stylesheet whether or not
// the banner div renders — assert on the actual visible banner copy instead.
function hasVisiblePreviewBanner(body) {
  return body.includes('PREVIEW — pending approval, not yet public') || body.includes('PREVIEW MODE');
}

test('signed-out /deal/:county/:slug 404s a pending_approval row with no preview param — never leaks PREVIEW', async () => {
  const { restore } = installFetchMock([rpcMock('get_reel_landing', reelFixture({ status: 'pending_approval' }))]);
  try {
    const req = new Request('https://biddeed.ai/deal/martin/25001204caaxmx');
    const res = await worker.fetch(req, ENV, makeCtx());
    assert.equal(res.status, 404);
    const body = await res.text();
    assert.ok(!hasVisiblePreviewBanner(body), 'response must never render the PREVIEW banner for a signed-out request');
  } finally { restore(); }
});

test('a malformed ?preview= value does not bypass the pending_approval gate', async () => {
  const { restore } = installFetchMock([rpcMock('get_reel_landing', reelFixture({ status: 'pending_approval' }))]);
  try {
    const req = new Request('https://biddeed.ai/deal/martin/25001204caaxmx?preview=not-a-uuid');
    const res = await worker.fetch(req, ENV, makeCtx());
    assert.equal(res.status, 404);
  } finally { restore(); }
});

test('a valid ?preview=<uuid> renders the PREVIEW banner for the pending row', async () => {
  const reel = reelFixture({ status: 'pending_approval' });
  const { restore } = installFetchMock([rpcMock('get_reel_landing', reel)]);
  try {
    const req = new Request(`https://biddeed.ai/deal/martin/25001204caaxmx?preview=${reel.id}`);
    const res = await worker.fetch(req, ENV, makeCtx());
    assert.equal(res.status, 200);
    const body = await res.text();
    assert.ok(body.includes('PREVIEW — pending approval, not yet public'));
  } finally { restore(); }
});

test('an approved deal page never renders PREVIEW', async () => {
  const { restore } = installFetchMock([rpcMock('get_reel_landing', reelFixture({ status: 'posted' }))]);
  try {
    const req = new Request('https://biddeed.ai/deal/martin/25001204caaxmx');
    const res = await worker.fetch(req, ENV, makeCtx());
    assert.equal(res.status, 200);
    const body = await res.text();
    assert.ok(!hasVisiblePreviewBanner(body));
  } finally { restore(); }
});

test('signed-out /reels/:code 404s a pending_approval reel with no preview param', async () => {
  const { restore } = installFetchMock([rpcMock('get_reel_by_code', reelFixture({ status: 'pending_approval' }))]);
  try {
    const req = new Request('https://biddeed.ai/reels/O7EPH7');
    const res = await worker.fetch(req, ENV, makeCtx());
    assert.equal(res.status, 404);
  } finally { restore(); }
});

// ── County chip guard (Martin page + stale Lee visit history) ──────────────
// dealPageStickyScript() isn't exported, so this extracts and executes the
// actual inline <script> the route emits (same bytes that ship to a real
// browser) inside a minimal document/localStorage/fetch shim, rather than
// re-implementing the guard logic and testing a copy of it.
function extractStickyScript(html) {
  const scripts = html.match(/<script>[\s\S]*?<\/script>/g) || [];
  const match = scripts.find(s => s.includes('bd_vid'));
  assert.ok(match, 'expected the visitor sticky-layer <script> to be present');
  return match.slice('<script>'.length, -'</script>'.length);
}

async function runStickyScript(scriptSrc, visitorResponse) {
  const store = {};
  const greeting = { textContent: '', style: {} };
  const sandbox = {
    localStorage: {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = v; },
    },
    document: {
      querySelectorAll: () => [],
      getElementById: (id) => (id === 'bd-greeting' ? greeting : null),
    },
    fetch: () => Promise.resolve({ json: () => Promise.resolve(visitorResponse) }),
  };
  vm.createContext(sandbox);
  vm.runInContext(scriptSrc, sandbox);
  // Flush the fetch().then().then() microtask chain before asserting.
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
  return greeting;
}

test('county chip renders nothing on a Martin page when the visitor history is stale Lee data', async () => {
  const { restore } = installFetchMock([rpcMock('get_reel_landing', reelFixture({ status: 'posted', county: 'martin' }))]);
  try {
    const req = new Request('https://biddeed.ai/deal/martin/25001204caaxmx');
    const res = await worker.fetch(req, ENV, makeCtx());
    const html = await res.text();
    const script = extractStickyScript(html);
    const greeting = await runStickyScript(script, {
      ok: true,
      returning: true,
      properties_viewed_count: 7,
      first_county: 'lee',
    });
    assert.equal(greeting.textContent, '', 'chip must stay empty when the chip county differs from the page county');
    assert.notEqual(greeting.style.display, 'block');
  } finally { restore(); }
});

test('county chip renders when the visitor history county matches the current page', async () => {
  const { restore } = installFetchMock([rpcMock('get_reel_landing', reelFixture({ status: 'posted', county: 'martin' }))]);
  try {
    const req = new Request('https://biddeed.ai/deal/martin/25001204caaxmx');
    const res = await worker.fetch(req, ENV, makeCtx());
    const html = await res.text();
    const script = extractStickyScript(html);
    const greeting = await runStickyScript(script, {
      ok: true,
      returning: true,
      properties_viewed_count: 4,
      first_county: 'martin',
    });
    assert.equal(greeting.textContent, '3 more Martin auctions since you were here');
    assert.equal(greeting.style.display, 'block');
  } finally { restore(); }
});
