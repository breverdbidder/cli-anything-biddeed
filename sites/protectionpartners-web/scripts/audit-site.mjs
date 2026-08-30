#!/usr/bin/env node
// Design-bar audit, per the zonewise-web audit-site.mjs convention (first
// adopted in issue #19405): no horizontal overflow at 320/393/768/1440, no
// JS errors. Page list is derived from agency.config.json's
// lines_of_business so this works unmodified for any generated site.
// Usage: node scripts/audit-site.mjs [baseUrl]  (defaults to http://localhost:4321)
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(readFileSync(path.join(__dirname, "..", "agency.config.json"), "utf-8"));

const baseUrl = process.argv[2] || "http://localhost:4321";
const viewports = [320, 393, 768, 1440];
const pages = [
  "/",
  "/get-a-quote",
  ...config.lines_of_business.map((l) => `/${l.slug}`),
  "/about",
  "/client-service",
];

let failures = 0;

const browser = await chromium.launch();
const context = await browser.newContext();

for (const path_ of pages) {
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => pageErrors.push(err.message));

  const url = `${baseUrl}${path_}`;
  const response = await page.goto(url, { waitUntil: "networkidle" });

  if (!response || response.status() >= 400) {
    console.error(`FAIL ${path_}: HTTP ${response ? response.status() : "no response"}`);
    failures++;
  }

  for (const width of viewports) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(100);
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      return doc.scrollWidth - doc.clientWidth;
    });
    if (overflow > 1) {
      console.error(`FAIL ${path_} @ ${width}px: horizontal overflow of ${overflow}px`);
      failures++;
    } else {
      console.log(`OK   ${path_} @ ${width}px: no horizontal overflow`);
    }
  }

  if (consoleErrors.length > 0) {
    console.error(`FAIL ${path_}: ${consoleErrors.length} console error(s):\n  ${consoleErrors.join("\n  ")}`);
    failures++;
  }
  if (pageErrors.length > 0) {
    console.error(`FAIL ${path_}: ${pageErrors.length} uncaught JS error(s):\n  ${pageErrors.join("\n  ")}`);
    failures++;
  }
  if (consoleErrors.length === 0 && pageErrors.length === 0) {
    console.log(`OK   ${path_}: no JS errors`);
  }

  await page.close();
}

// Negative test (issue #19601 DoD item 4): the Canopy Connect 1-click CTA
// must be visually/structurally dominant over the fallback manual-entry
// form on /get-a-quote -- above the fold at desktop width, and preceding
// the form in vertical document order. Checked as real layout geometry, not
// an assertion about markup order, so a future CSS change that visually
// buries Canopy behind the form fails this check even if the DOM order
// still looks right.
{
  const page = await context.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  const url = `${baseUrl}/get-a-quote`;
  const response = await page.goto(url, { waitUntil: "networkidle" });
  if (!response || response.status() >= 400) {
    console.error(`FAIL /get-a-quote CANOPY DOMINANCE: page did not load (HTTP ${response ? response.status() : "no response"})`);
    failures++;
  } else {
    const ctaBox = await page.$("#canopy-primary-cta");
    const form = await page.$("#quote-form");
    if (!ctaBox || !form) {
      console.error(`FAIL /get-a-quote CANOPY DOMINANCE: #canopy-primary-cta or #quote-form not found in DOM`);
      failures++;
    } else {
      const ctaBox_bb = await ctaBox.boundingBox();
      const form_bb = await form.boundingBox();
      const viewportHeight = 900;
      const aboveFold = ctaBox_bb.y < viewportHeight;
      const precedesForm = ctaBox_bb.y < form_bb.y;
      if (aboveFold && precedesForm) {
        console.log(
          `OK   /get-a-quote CANOPY DOMINANCE: CTA top=${Math.round(ctaBox_bb.y)}px (above ${viewportHeight}px fold), form top=${Math.round(form_bb.y)}px (CTA precedes form by ${Math.round(form_bb.y - ctaBox_bb.y)}px)`
        );
      } else {
        console.error(
          `FAIL /get-a-quote CANOPY DOMINANCE: aboveFold=${aboveFold} (cta.y=${Math.round(ctaBox_bb.y)} vs fold=${viewportHeight}), precedesForm=${precedesForm} (cta.y=${Math.round(ctaBox_bb.y)} vs form.y=${Math.round(form_bb.y)})`
        );
        failures++;
      }
    }
  }
  await page.close();
}

// Negative test (issue #19602 DoD item 2): the secondary/fallback intake
// paths (#intake-fallback-paths -- dec upload / callback / plain form
// entry) must never visually or structurally outrank the Canopy Connect
// primary CTA. Checked as real layout geometry + computed class list, not
// just markup order: the fallback section must start below where the
// Canopy CTA box ends, and must not carry the same brass-accent background
// class the primary CTA uses.
{
  const page = await context.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  const url = `${baseUrl}/get-a-quote`;
  const response = await page.goto(url, { waitUntil: "networkidle" });
  if (!response || response.status() >= 400) {
    console.error(`FAIL /get-a-quote FALLBACK SUBORDINATION: page did not load (HTTP ${response ? response.status() : "no response"})`);
    failures++;
  } else {
    const ctaBox = await page.$("#canopy-primary-cta");
    const fallback = await page.$("#intake-fallback-paths");
    if (!ctaBox) {
      console.error(`FAIL /get-a-quote FALLBACK SUBORDINATION: #canopy-primary-cta not found in DOM`);
      failures++;
    } else if (!fallback) {
      console.log(`OK   /get-a-quote FALLBACK SUBORDINATION: #intake-fallback-paths absent (all fallbacks disabled in config -- nothing to check)`);
    } else {
      const ctaBox_bb = await ctaBox.boundingBox();
      const fallback_bb = await fallback.boundingBox();
      const fallbackClass = (await fallback.getAttribute("class")) || "";
      const startsBelowCta = fallback_bb.y >= ctaBox_bb.y + ctaBox_bb.height;
      const usesAccentBackground = /bg-brass/.test(fallbackClass);
      if (startsBelowCta && !usesAccentBackground) {
        console.log(
          `OK   /get-a-quote FALLBACK SUBORDINATION: cta bottom=${Math.round(ctaBox_bb.y + ctaBox_bb.height)}px, fallback top=${Math.round(fallback_bb.y)}px (follows CTA), class="${fallbackClass}" (no accent background)`
        );
      } else {
        console.error(
          `FAIL /get-a-quote FALLBACK SUBORDINATION: startsBelowCta=${startsBelowCta} (fallback.y=${Math.round(fallback_bb.y)} vs cta.bottom=${Math.round(ctaBox_bb.y + ctaBox_bb.height)}), usesAccentBackground=${usesAccentBackground} (class="${fallbackClass}")`
        );
        failures++;
      }
    }
  }
  await page.close();
}

await browser.close();

if (failures > 0) {
  console.error(`\nAUDIT FAILED: ${failures} issue(s) found.`);
  process.exit(1);
}
console.log("\nAUDIT PASSED: no overflow, no JS errors across all pages/viewports.");
