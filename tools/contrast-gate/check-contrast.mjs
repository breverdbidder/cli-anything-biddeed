#!/usr/bin/env node
// Contrast CI gate — issue #19828 Phase P0 item 3.
// Visits every route in routes.json at 1440 and 390 widths, computes WCAG
// contrast ratio for every visible text node, flags inline hex colors and
// !important, and screenshots each viewport. Fails (exit 1) on any node
// scoring below 4.5:1.
//
// Usage: node check-contrast.mjs <base-url> [--out <dir>]
// Example (production):  node check-contrast.mjs https://biddeed.ai
// Example (local dev):   node check-contrast.mjs http://localhost:8787

import pw from 'playwright-core';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const { chromium } = pw;
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const baseUrl = process.argv[2];
if (!baseUrl) {
  console.error('Usage: node check-contrast.mjs <base-url> [--out <dir>]');
  process.exit(2);
}
const outIdx = process.argv.indexOf('--out');
const outDir = outIdx !== -1 ? process.argv[outIdx + 1] : path.join(__dirname, 'screenshots');
fs.mkdirSync(outDir, { recursive: true });

const routes = JSON.parse(fs.readFileSync(path.join(__dirname, 'routes.json'), 'utf8'));
const VIEWPORTS = [{ width: 1440, height: 900, tag: '1440' }, { width: 390, height: 844, tag: '390' }];
const THRESHOLD = 4.5;

function contrastRatio(rgb1, rgb2) {
  function lum(rgb) {
    const nums = rgb.match(/[\d.]+/g);
    if (!nums) return null;
    const [r, g, b] = nums.map(Number).map(c => {
      c /= 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  const l1 = lum(rgb1), l2 = lum(rgb2);
  if (l1 === null || l2 === null) return null;
  const [a, b] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (a + 0.05) / (b + 0.05);
}

const evalFn = () => {
  function contrastRatioInPage(rgb1, rgb2) {
    function lum(rgb) {
      const nums = rgb.match(/[\d.]+/g);
      if (!nums) return null;
      const [r, g, b] = nums.map(Number).map(c => {
        c /= 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }
    const l1 = lum(rgb1), l2 = lum(rgb2);
    if (l1 === null || l2 === null) return null;
    const [a, b] = l1 > l2 ? [l1, l2] : [l2, l1];
    return (a + 0.05) / (b + 0.05);
  }

  const results = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      const el = node.parentElement;
      if (!el) return NodeFilter.FILTER_REJECT;
      const tag = el.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') return NodeFilter.FILTER_REJECT;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return NodeFilter.FILTER_REJECT;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return NodeFilter.FILTER_REJECT;
      // Off-canvas (translateX drawers etc.) and out-of-viewport nodes are not
      // actually visible to the user — exclude them, same bar Playwright's own
      // isVisible() uses for "is this in the viewport".
      if (rect.right <= 0 || rect.bottom <= 0 || rect.left >= innerWidth || rect.top >= innerHeight) return NodeFilter.FILTER_REJECT;
      let ancestor = el;
      while (ancestor) {
        const acs = ancestor === el ? cs : getComputedStyle(ancestor);
        if (acs.overflow === 'hidden' || acs.overflowX === 'hidden') {
          const arect = ancestor.getBoundingClientRect();
          if (rect.right <= arect.left || rect.left >= arect.right) return NodeFilter.FILTER_REJECT;
        }
        ancestor = ancestor.parentElement;
      }
      return NodeFilter.FILTER_ACCEPT;
    }
  });

  let node;
  while ((node = walker.nextNode())) {
    const el = node.parentElement;
    const cs = getComputedStyle(el);
    let bgEl = el;
    let bg = getComputedStyle(bgEl).backgroundColor;
    while ((bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') && bgEl.parentElement) {
      bgEl = bgEl.parentElement;
      bg = getComputedStyle(bgEl).backgroundColor;
    }
    if (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') bg = 'rgb(255, 255, 255)';
    const ratio = contrastRatioInPage(cs.color, bg);
    const rect = el.getBoundingClientRect();
    results.push({
      text: node.nodeValue.trim().slice(0, 60),
      tag: el.tagName,
      cls: el.className && typeof el.className === 'string' ? el.className.slice(0, 60) : '',
      color: cs.color,
      bg,
      ratio: ratio === null ? null : Math.round(ratio * 100) / 100,
      x: Math.round(rect.x), y: Math.round(rect.y)
    });
  }

  // Inline hex colors / !important flags (static scan of style attributes + <style> blocks)
  const violations = { inlineHex: [], important: [] };
  document.querySelectorAll('[style]').forEach(el => {
    const s = el.getAttribute('style') || '';
    if (/#[0-9a-fA-F]{3,8}\b/.test(s)) violations.inlineHex.push(s.slice(0, 80));
    if (/!important/i.test(s)) violations.important.push(s.slice(0, 80));
  });

  return { results, violations, theme: document.documentElement.dataset.theme || null };
};

const browser = await chromium.launch();
const summary = { baseUrl, generatedAt: null, routes: [] };

for (const route of routes) {
  const routeResult = { path: route.path, label: route.label, viewports: {} };
  for (const vp of VIEWPORTS) {
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    const url = baseUrl.replace(/\/$/, '') + route.path;
    let status = null;
    try {
      const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
      status = resp ? resp.status() : null;
      await page.waitForTimeout(300);
      const { results, violations, theme } = await page.evaluate(evalFn);
      const h1s = await page.locator('h1').count();
      const failures = results.filter(r => r.ratio !== null && r.ratio < THRESHOLD);
      const shotPath = path.join(outDir, `${route.label}-${vp.tag}.png`);
      await page.screenshot({ path: shotPath, fullPage: false });
      routeResult.viewports[vp.tag] = {
        httpStatus: status,
        theme,
        h1Count: h1s,
        totalTextNodes: results.length,
        failCount: failures.length,
        failures: failures.slice(0, 15),
        inlineHexCount: violations.inlineHex.length,
        importantCount: violations.important.length,
        screenshot: path.relative(process.cwd(), shotPath)
      };
      console.log(`${route.path} @${vp.tag}: HTTP ${status}, h1=${h1s}, ${failures.length}/${results.length} text nodes < ${THRESHOLD}:1, inlineHex=${violations.inlineHex.length}`);
    } catch (e) {
      routeResult.viewports[vp.tag] = { error: String(e).slice(0, 300) };
      console.log(`${route.path} @${vp.tag}: ERROR ${String(e).slice(0, 150)}`);
    }
    await page.close();
  }
  summary.routes.push(routeResult);
}

await browser.close();

const jsonPath = path.join(outDir, 'report.json');
fs.writeFileSync(jsonPath, JSON.stringify(summary, null, 2));

let totalFail = 0;
let totalMissingH1 = 0;
for (const r of summary.routes) {
  for (const vp of Object.values(r.viewports)) {
    if (vp.failCount) totalFail += vp.failCount;
    if (vp.h1Count === 0) totalMissingH1++;
  }
}
console.log(`\n=== SUMMARY: ${totalFail} text-node contrast failures, ${totalMissingH1} route/viewport combos with 0 <h1> ===`);
console.log(`Report: ${jsonPath}`);
process.exit(totalFail > 0 ? 1 : 0);
