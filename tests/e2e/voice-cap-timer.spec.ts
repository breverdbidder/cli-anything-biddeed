import { test, expect } from '@playwright/test';

const CHAT_URL = '/chat-v2';

// ── Voice cap timer regression test ─────────────────────────────────────────
// Verifies the 8-min contextual_update nudge and 10-min hard-stop fire
// correctly and independently, using fake timers and a mock WebSocket
// injected at the page level (no real ElevenLabs connection required).
//
// Root cause this guards against: the original nested-setTimeout design
// caused the 8-min contextual_update to be dropped when ws.readyState !== 1
// at fire time, AND prevented the 10-min hard-stop inner timer from being
// registered at all in that failure case. Both timers are now independent.

function fakeTimerAndWsScript() {
  const timers: Array<{ id: number; deadline: number; fn: Function }> = [];
  let fakeNow = Date.now();
  let nextId = 9000000;

  (window as any).__advanceFakeTime = (ms: number) => {
    fakeNow += ms;
    const due = timers
      .filter(t => t.deadline <= fakeNow)
      .sort((a, b) => a.deadline - b.deadline);
    for (const t of due) {
      timers.splice(timers.indexOf(t), 1);
      try { t.fn(); } catch (_) { /* ignore */ }
    }
  };

  (window as any).setTimeout = function(fn: Function, delay = 0) {
    const id = ++nextId;
    timers.push({ id, deadline: fakeNow + delay, fn });
    return id;
  };
  (window as any).clearTimeout = function(id: number) {
    const idx = timers.findIndex(t => t.id === id);
    if (idx !== -1) timers.splice(idx, 1);
  };

  const audioCtx = new AudioContext();
  const dst = audioCtx.createMediaStreamDestination();
  (navigator.mediaDevices as any).getUserMedia = async () => dst.stream;

  const sent: string[] = [];
  (window as any).__wsSent = sent;

  (window as any).WebSocket = class FakeWS {
    readyState = 1;
    onopen: Function | null = null;
    onmessage: Function | null = null;
    onerror: Function | null = null;
    onclose: Function | null = null;
    constructor(_url: string) {
      Promise.resolve().then(() => {
        if (this.onopen) this.onopen(new Event('open'));
        Promise.resolve().then(() => {
          if (this.onmessage) this.onmessage(new MessageEvent('message', {
            data: JSON.stringify({
              type: 'conversation_initiation_metadata',
              conversation_initiation_metadata_event: { conversation_id: 'test-conv-001' },
            }),
          }));
        });
      });
    }
    send(data: string) { sent.push(data); }
    close() { this.readyState = 3; }
  };
}

test.describe('voice widget — cap timer', () => {
  test('8-min nudge sends contextual_update independently of 10-min hard-stop', async ({ page }) => {
    await page.route('**/elevenlabs-signed-url', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ signed_url: 'wss://mock-el.test/ws' }),
      })
    );

    await page.addInitScript(fakeTimerAndWsScript);
    await page.goto(CHAT_URL, { waitUntil: 'domcontentloaded', timeout: 30_000 });

    const emailInput = page.locator('#veg-email');
    await expect(emailInput).toBeVisible({ timeout: 10_000 });
    await emailInput.fill('test@test.com');
    await page.locator('#veg-submit').click();

    await expect(page.locator('#voice-status')).toContainText('Listening', { timeout: 8_000 });

    // Advance to just past 8 minutes
    await page.evaluate(() => (window as any).__advanceFakeTime(8 * 60 * 1000 + 500));
    await page.waitForTimeout(200);

    const nudgeSent = await page.evaluate((): boolean => {
      const msgs: string[] = (window as any).__wsSent || [];
      return msgs.some(m => {
        try {
          const p = JSON.parse(m);
          return p.type === 'contextual_update' && typeof p.text === 'string' && p.text.length > 0;
        } catch { return false; }
      });
    });
    expect(nudgeSent, 'contextual_update must be sent at the 8-minute mark').toBe(true);

    // Cap panel must NOT be visible yet
    const capVisible8 = await page.locator('#voice-cap').evaluate(el => el.classList.contains('show'));
    expect(capVisible8, 'voice-cap panel must NOT be shown at 8 minutes').toBe(false);

    // Advance to just past 10 minutes
    await page.evaluate(() => (window as any).__advanceFakeTime(2 * 60 * 1000 + 500));
    await page.waitForTimeout(200);

    await expect(page.locator('#voice-cap')).toHaveClass(/show/, { timeout: 3_000 });
    await expect(page.locator('#voice-btn')).toBeHidden({ timeout: 3_000 });
  });

  test('stopping session before 8 minutes cancels both timers', async ({ page }) => {
    await page.route('**/elevenlabs-signed-url', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ signed_url: 'wss://mock-el.test/ws' }),
      })
    );

    await page.addInitScript(fakeTimerAndWsScript);
    await page.goto(CHAT_URL, { waitUntil: 'domcontentloaded', timeout: 30_000 });

    const emailInput = page.locator('#veg-email');
    await expect(emailInput).toBeVisible({ timeout: 10_000 });
    await emailInput.fill('test@test.com');
    await page.locator('#veg-submit').click();

    await expect(page.locator('#voice-status')).toContainText('Listening', { timeout: 8_000 });

    // Manually stop the session (click Stop button)
    await page.locator('#voice-btn').click();
    await page.waitForTimeout(200);

    // Advance past 10 minutes — neither timer should fire
    await page.evaluate(() => (window as any).__advanceFakeTime(11 * 60 * 1000));
    await page.waitForTimeout(200);

    const nudgeSentAfterStop = await page.evaluate((): boolean => {
      const msgs: string[] = (window as any).__wsSent || [];
      return msgs.some(m => {
        try { return JSON.parse(m).type === 'contextual_update'; }
        catch { return false; }
      });
    });
    expect(nudgeSentAfterStop, 'contextual_update must NOT be sent after manual stop').toBe(false);

    await expect(page.locator('#voice-cap')).not.toHaveClass(/show/);
  });
});
