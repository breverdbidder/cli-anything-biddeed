import { chromium } from 'playwright';
import fs from 'fs';

const URL = process.env.URL || 'https://zonewise.ai';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await ctx.newPage();

const consoleErrors = [];
const tileRequests = [];
const tileResponses = [];

page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 200)); });
page.on('pageerror', e => consoleErrors.push('PAGEERROR: ' + e.message.slice(0, 200)));
page.on('request', req => {
  const u = req.url();
  if (u.includes('tile.googleapis.com')) tileRequests.push(u.slice(0, 150));
});
page.on('response', resp => {
  const u = resp.url();
  if (u.includes('tile.googleapis.com')) tileResponses.push(`${resp.status()} ${u.slice(0, 100)}`);
});

console.log('NAV: ' + URL);
const resp = await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
console.log('HTTP: ' + resp.status());

// Take screenshot at 5s, 15s, 30s
await page.waitForTimeout(5000);
await page.screenshot({ path: '/tmp/r5.png', fullPage: false });
const c5 = (await page.$$('canvas')).length;
console.log('T5_CANVASES: ' + c5);

await page.waitForTimeout(10000);
await page.screenshot({ path: '/tmp/r15.png', fullPage: false });
const c15 = (await page.$$('canvas')).length;
console.log('T15_CANVASES: ' + c15);

await page.waitForTimeout(15000);
await page.screenshot({ path: '/tmp/r30.png', fullPage: false });
const c30 = (await page.$$('canvas')).length;
console.log('T30_CANVASES: ' + c30);

// Inspect canvas if exists
if (c30 > 0) {
  const dims = await page.evaluate(() => {
    const c = document.querySelector('canvas');
    return { w: c.width, h: c.height, vis: c.offsetWidth > 0 && c.offsetHeight > 0 };
  });
  console.log('CANVAS_DIMS: ' + JSON.stringify(dims));
}

// Inspect Hero3D presence
const heroInspect = await page.evaluate(() => {
  const all = document.querySelectorAll('*');
  let hero = null;
  for (const el of all) {
    const cls = el.className || '';
    if (typeof cls === 'string' && /Hero3D|hero-?3d|cesium/i.test(cls)) {
      hero = { tag: el.tagName, class: cls.slice(0, 80) };
      break;
    }
  }
  return { found: !!hero, ...hero };
});
console.log('HERO_INSPECT: ' + JSON.stringify(heroInspect));

// HTML title
console.log('TITLE: "' + (await page.title()) + '"');

console.log('TILE_REQUESTS: ' + tileRequests.length);
console.log('TILE_200_RESPONSES: ' + tileResponses.filter(r => r.startsWith('200')).length);
console.log('TILE_4xx_5xx: ' + tileResponses.filter(r => /^[45]/.test(r)).length);
console.log('CONSOLE_ERRORS: ' + consoleErrors.length);

// Categorize errors
const cesiumErrors = consoleErrors.filter(e => /cesium|tile|3d/i.test(e));
const clerkErrors = consoleErrors.filter(e => /clerk/i.test(e));
const other = consoleErrors.filter(e => !/cesium|tile|3d|clerk/i.test(e));
console.log('  CESIUM_RELATED: ' + cesiumErrors.length);
console.log('  CLERK_RELATED: ' + clerkErrors.length);
console.log('  OTHER: ' + other.length);

await browser.close();

// Verdict for POINT 11 only (feature functional)
const point11 = c30 >= 1 && tileRequests.length > 0 && tileResponses.filter(r => r.startsWith('200')).length > 0 && cesiumErrors.length === 0;
console.log('POINT_11_FEATURE_FUNCTIONAL: ' + point11);

const sizes = {
  t5: fs.statSync('/tmp/r5.png').size,
  t15: fs.statSync('/tmp/r15.png').size,
  t30: fs.statSync('/tmp/r30.png').size
};
console.log('SCREENSHOT_SIZES: ' + JSON.stringify(sizes));

process.exit(point11 ? 0 : 1);
