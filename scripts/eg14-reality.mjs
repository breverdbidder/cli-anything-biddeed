import { chromium } from 'playwright';
import fs from 'fs';

const URL = process.env.URL || 'https://zonewise.ai';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await ctx.newPage();

const consoleErrors = [];
const networkErrors = [];
const tileRequests = [];
const cesiumReqs = [];

page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 200)); });
page.on('pageerror', e => consoleErrors.push('PAGEERROR: ' + e.message.slice(0, 200)));
page.on('requestfailed', req => networkErrors.push(req.url().slice(0, 150) + ' :: ' + (req.failure()?.errorText || '')));
page.on('request', req => {
  const u = req.url();
  if (u.includes('tile.googleapis.com')) tileRequests.push(u.slice(0, 150));
  if (u.includes('cesium')) cesiumReqs.push(u.slice(0, 100));
});

console.log('NAV: ' + URL);
const resp = await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
console.log('HTTP: ' + resp.status());
console.log('TITLE: ' + (await page.title()).slice(0, 80));

await page.waitForTimeout(10000);

const canvases = await page.$$('canvas');
console.log('CANVASES_FOUND: ' + canvases.length);

const heroExists = await page.evaluate(() => {
  return !!document.querySelector('[class*="Hero3D"], [data-component*="hero3d" i], [class*="hero-3d"]');
});
console.log('HERO3D_DOM: ' + heroExists);

const keyInScripts = await page.evaluate(() => {
  for (const s of document.scripts) {
    if (s.textContent && s.textContent.match(/AIzaSy[A-Za-z0-9_-]+/)) {
      return s.textContent.match(/AIzaSy[A-Za-z0-9_-]+/)[0];
    }
  }
  return null;
});
console.log('KEY_IN_SCRIPTS: ' + keyInScripts);

await page.screenshot({ path: '/tmp/reality.png', fullPage: false });
console.log('SCREENSHOT_BYTES: ' + fs.statSync('/tmp/reality.png').size);

console.log('CONSOLE_ERRORS: ' + consoleErrors.length);
consoleErrors.slice(0, 10).forEach((e, i) => console.log('  ERR' + i + ': ' + e));
console.log('NETWORK_ERRORS: ' + networkErrors.length);
networkErrors.slice(0, 10).forEach((e, i) => console.log('  NET' + i + ': ' + e));
console.log('TILE_REQUESTS: ' + tileRequests.length);
tileRequests.slice(0, 5).forEach(t => console.log('  TILE: ' + t));
console.log('CESIUM_REQUESTS: ' + cesiumReqs.length);
cesiumReqs.slice(0, 5).forEach(t => console.log('  CES: ' + t));

await browser.close();

const pass = canvases.length >= 1 && tileRequests.length > 0 && consoleErrors.length === 0;
console.log('REALITY_PASS: ' + pass);
process.exit(pass ? 0 : 1);
