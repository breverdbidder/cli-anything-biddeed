// tests/support-bot.test.js — POST /support/bot (Chatwoot Agent Bot webhook)
// Uses Node's built-in test runner (node:test) — no new dependency. Run with:
//   node --test tests/support-bot.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/worker.js';

const BASE_ENV = {
  CHATWOOT_BOT_TOKEN: 'test-bot-token',
  CHATWOOT_WEBHOOK_SECRET: 'test-webhook-secret',
  CHATWOOT_INBOX_MAP: JSON.stringify({ '101': 'biddeed', '202': 'winnerdata' }),
  CHATWOOT_BASE_URL: 'https://chatwoot.test',
  ROUTER_PROXY_KEY: 'test-router-key',
};

function makeCtx() {
  return { waitUntil: () => {} };
}

function makeRequest(body, { key } = {}) {
  const url = new URL('https://biddeed.ai/support/bot');
  if (key !== null) url.searchParams.set('k', key ?? BASE_ENV.CHATWOOT_WEBHOOK_SECRET);
  return new Request(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// Intercepts every global fetch() call the worker makes and routes it to the
// first matching handler (string = substring match, RegExp = test()). Falls
// through to a generic 200 {ok:true} for anything unmatched (log_worker_error
// etc.) so tests only need to stub what they actually assert on.
function installFetchMock(handlers) {
  const calls = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    calls.push({ url, init });
    for (const [matcher, handler] of handlers) {
      const matches = typeof matcher === 'string' ? url.includes(matcher) : matcher.test(url);
      if (matches) return handler(url, init);
    }
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  };
  return { calls, restore: () => { globalThis.fetch = original; } };
}

function incoming(overrides = {}) {
  return {
    event: 'message_created',
    message_type: 'incoming',
    private: false,
    id: 'msg-default',
    account: { id: 9 },
    inbox: { id: 101 },
    conversation: { id: 55 },
    content: 'hello',
    sender: { name: 'Jane', email: 'jane@example.com' },
    ...overrides,
  };
}

test('ignored events (wrong event / outgoing / private) return {ignored:true}, 200', async () => {
  const { restore } = installFetchMock([]);
  try {
    const cases = [
      { event: 'conversation_status_changed', message_type: 'incoming', private: false },
      incoming({ message_type: 'outgoing' }),
      incoming({ private: true }),
    ];
    for (const body of cases) {
      const res = await worker.fetch(makeRequest(body), BASE_ENV, makeCtx());
      assert.equal(res.status, 200);
      const json = await res.json();
      assert.equal(json.ignored, true);
    }
  } finally { restore(); }
});

test('401 when ?k= is missing or wrong', async () => {
  const { restore } = installFetchMock([]);
  try {
    const wrong = await worker.fetch(makeRequest(incoming(), { key: 'not-the-secret' }), BASE_ENV, makeCtx());
    assert.equal(wrong.status, 401);
    const missing = await worker.fetch(makeRequest(incoming(), { key: null }), BASE_ENV, makeCtx());
    assert.equal(missing.status, 401);
  } finally { restore(); }
});

test('503 when a required Chatwoot secret binding is missing', async () => {
  const { restore } = installFetchMock([]);
  try {
    const env = { ...BASE_ENV, CHATWOOT_BOT_TOKEN: undefined };
    const res = await worker.fetch(makeRequest(incoming()), env, makeCtx());
    assert.equal(res.status, 503);
  } finally { restore(); }
});

test('unknown inbox id escalates without ever calling claude-router', async () => {
  const { calls, restore } = installFetchMock([
    [/functions\/v1\/claude-router/, () => new Response(JSON.stringify({ text: 'should not happen' }), { status: 200 })],
  ]);
  try {
    const body = incoming({ id: 'msg-unknown-inbox', inbox: { id: 999 } });
    const res = await worker.fetch(makeRequest(body), BASE_ENV, makeCtx());
    assert.equal(res.status, 200);
    const json = await res.json();
    assert.equal(json.escalated, true);
    assert.equal(json.reason, 'unknown_inbox');

    assert.ok(!calls.some(c => c.url.includes('claude-router')), 'LLM must not be called for an unknown inbox');
    const chatwootCalls = calls.filter(c => c.url.startsWith(BASE_ENV.CHATWOOT_BASE_URL));
    assert.ok(chatwootCalls.some(c => c.url.includes('/messages')), 'expected an outgoing reply');
    assert.ok(chatwootCalls.some(c => c.url.includes('/toggle_status')), 'expected the conversation to resolve (email was known)');
    const leadCalls = calls.filter(c => c.url.includes('/rest/v1/lead_profiles'));
    assert.equal(leadCalls.length, 1, 'expected the escalation to log a lead via the existing /chat/lead upsert');
    const leadBody = JSON.parse(leadCalls[0].init.body);
    assert.equal(leadBody.source, 'support_escalation');
    assert.equal(leadBody.email, 'jane@example.com');
  } finally { restore(); }
});

test('happy path — claude-router reply (mocked) is relayed to Chatwoot, biddeed inbox', async () => {
  const { calls, restore } = installFetchMock([
    [/functions\/v1\/claude-router/, () => new Response(JSON.stringify({ text: 'A SIGNAL$ Property Report is $25 per property.' }), { status: 200 })],
  ]);
  try {
    const body = incoming({ id: 'msg-happy', content: 'How much is a report?' });
    const res = await worker.fetch(makeRequest(body), BASE_ENV, makeCtx());
    assert.equal(res.status, 200);
    const json = await res.json();
    assert.equal(json.replied, true);
    assert.equal(json.site, 'biddeed');

    const replyCall = calls.find(c => c.url.startsWith(BASE_ENV.CHATWOOT_BASE_URL) && c.url.includes('/messages'));
    assert.ok(replyCall);
    const sent = JSON.parse(replyCall.init.body);
    assert.equal(sent.message_type, 'outgoing');
    assert.match(sent.content, /SIGNAL\$/);
    assert.ok(!calls.some(c => c.url.includes('/toggle_status')), 'happy path must not resolve/close the conversation');
  } finally { restore(); }
});

test('[[HANDOFF]] token in the LLM reply escalates instead of being shown to the user', async () => {
  const { calls, restore } = installFetchMock([
    [/functions\/v1\/claude-router/, () => new Response(JSON.stringify({ text: "I can't guarantee that. [[HANDOFF]]" }), { status: 200 })],
  ]);
  try {
    const body = incoming({ id: 'msg-handoff', content: 'Can you guarantee I will win this specific auction?' });
    const res = await worker.fetch(makeRequest(body), BASE_ENV, makeCtx());
    const json = await res.json();
    assert.equal(json.escalated, true);
    assert.equal(json.reason, 'llm_handoff');

    const replyCall = calls.find(c => c.url.startsWith(BASE_ENV.CHATWOOT_BASE_URL) && c.url.includes('/messages'));
    assert.ok(replyCall);
    const sent = JSON.parse(replyCall.init.body);
    assert.ok(!sent.content.includes('[[HANDOFF]]'), 'the control token must never leak to the customer-visible reply');
    assert.match(sent.content, /leave your email/i);
  } finally { restore(); }
});

test('claude-router non-200 escalates (fail-safe, no reply pretending to be an answer)', async () => {
  const { restore } = installFetchMock([
    [/functions\/v1\/claude-router/, () => new Response('upstream error', { status: 502 })],
  ]);
  try {
    const body = incoming({ id: 'msg-router-down' });
    const res = await worker.fetch(makeRequest(body), BASE_ENV, makeCtx());
    const json = await res.json();
    assert.equal(json.escalated, true);
    assert.equal(json.reason, 'router_failure');
  } finally { restore(); }
});

test('duplicate message.id within the idempotency window is a no-op the second time', async () => {
  const { calls, restore } = installFetchMock([
    [/functions\/v1\/claude-router/, () => new Response(JSON.stringify({ text: 'ok' }), { status: 200 })],
  ]);
  try {
    const body = incoming({ id: 'msg-dup-1' });
    const first = await worker.fetch(makeRequest(body), BASE_ENV, makeCtx());
    assert.equal((await first.json()).replied, true);
    const callsAfterFirst = calls.length;

    const second = await worker.fetch(makeRequest(body), BASE_ENV, makeCtx());
    const secondJson = await second.json();
    assert.equal(secondJson.ignored, true);
    assert.equal(secondJson.duplicate, true);
    assert.equal(calls.length, callsAfterFirst, 'a duplicate message.id must not trigger any new outbound call');
  } finally { restore(); }
});

test('winnerdata inbox prepends the winnerdata_canon_v1 canon to the system prompt', async () => {
  const { calls, restore } = installFetchMock([
    [/rest\/v1\/unified_context/, () => new Response(JSON.stringify([{ content: { moat: 'one resolution event, N verticals' } }]), { status: 200 })],
    [/functions\/v1\/claude-router/, () => new Response(JSON.stringify({ text: 'We are a B2B property-data platform.' }), { status: 200 })],
  ]);
  try {
    const body = incoming({ id: 'msg-winnerdata', inbox: { id: 202 }, content: 'What does Winner Data sell?' });
    const res = await worker.fetch(makeRequest(body), BASE_ENV, makeCtx());
    const json = await res.json();
    assert.equal(json.site, 'winnerdata');

    const routerCall = calls.find(c => c.url.includes('claude-router'));
    assert.ok(routerCall);
    const sent = JSON.parse(routerCall.init.body);
    assert.match(sent.system, /one resolution event, N verticals/);
  } finally { restore(); }
});
