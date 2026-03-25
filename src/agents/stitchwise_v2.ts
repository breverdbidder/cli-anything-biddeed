#!/usr/bin/env node
/**
 * StitchWise V2 Agent — Programmatic Google Stitch Integration
 * cli-anything harness: cli_anything.stitchwise
 * 
 * Pipeline: BrandKit → PromptOptimize → StitchGenerate → Score → Export
 */

import { Stitch, StitchToolClient } from "@google/stitch-sdk";
import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";

// ─── Config ───────────────────────────────────────────────────────
const BRAND_KIT = {
  primary: "#1E3A5F",   // Navy
  accent: "#F59E0B",    // Orange CTA
  bg: "#020617",        // Slate-950
  font: "Inter",
  name: "BidDeed.AI / ZoneWise.AI"
};

const MAX_RETRIES = 3;
const OUTPUT_DIR = join(process.cwd(), "stitch-output");

// ─── Stitch Client ───────────────────────────────────────────────
function getClient(): Stitch {
  const apiKey = process.env.STITCH_API_KEY;
  if (!apiKey) {
    console.error("❌ STITCH_API_KEY not set. Generate at stitch.withgoogle.com → Settings → API Keys");
    process.exit(1);
  }
  const client = new StitchToolClient({
    apiKey,
    baseUrl: "https://stitch.googleapis.com/mcp",
    timeout: 300_000,
  });
  return new Stitch(client);
}

// ─── Brand-Aware Prompt Builder ──────────────────────────────────
function buildStitchPrompt(userRequest: string): string {
  return `Design a modern, professional UI with these brand requirements:
- Primary color: ${BRAND_KIT.primary} (navy blue) for headers, nav, key elements
- Accent color: ${BRAND_KIT.accent} (warm orange) for CTAs, highlights, interactive elements  
- Background: ${BRAND_KIT.bg} (dark slate) with appropriate contrast
- Font: ${BRAND_KIT.font} (clean, modern sans-serif)
- Style: Minimalist, high-contrast, premium feel. Similar to Claude AI or Manus AI split-screen layout.
- Mobile-first responsive design
- Subtle animations (hover states, transitions, micro-interactions)
- NO generic AI/SaaS aesthetic. Make it distinctive.

User request: ${userRequest}

Generate a complete, polished screen ready for production export.`;
}

// ─── Core Pipeline ───────────────────────────────────────────────
interface StitchResult {
  projectId: string;
  screenId: string;
  htmlUrl: string;
  imageUrl: string;
  attempt: number;
}

async function generateDesign(
  sdk: Stitch,
  projectTitle: string,
  prompt: string
): Promise<StitchResult> {
  // Create project
  console.log(`🎨 Creating Stitch project: ${projectTitle}`);
  const projectResult = await sdk.callTool("create_project", {
    title: projectTitle,
  });
  const projectId = projectResult?.projectId || projectResult?.id;
  console.log(`✅ Project created: ${projectId}`);

  // Generate with retries
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    console.log(`🔄 Generation attempt ${attempt}/${MAX_RETRIES}`);
    try {
      const project = sdk.project(projectId);
      const screen = await project.generate(prompt);
      
      const htmlUrl = await screen.getHtml();
      const imageUrl = await screen.getImage();

      console.log(`✅ Screen generated successfully`);
      return {
        projectId,
        screenId: screen.id || "unknown",
        htmlUrl,
        imageUrl,
        attempt,
      };
    } catch (err: any) {
      console.error(`⚠️ Attempt ${attempt} failed: ${err.message}`);
      if (attempt === MAX_RETRIES) throw err;
    }
  }
  throw new Error("All generation attempts failed");
}

async function downloadArtifact(url: string, outputPath: string): Promise<void> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);
  const content = await response.text();
  writeFileSync(outputPath, content, "utf-8");
  console.log(`📥 Downloaded: ${outputPath}`);
}

// ─── CLI Entry Point ─────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === "--help") {
    console.log(`
StitchWise V2 — Programmatic Google Stitch Agent
Usage:
  stitchwise generate <project-name> <prompt>    Generate a new design
  stitchwise list                                 List all projects
  stitchwise export <project-id> <screen-id>     Export screen HTML
  stitchwise dashboard <project-name>            Generate admin dashboard
  stitchwise landing <project-name>              Generate landing page

Env: STITCH_API_KEY (required)
    `);
    return;
  }

  const sdk = getClient();
  if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });

  switch (command) {
    case "generate": {
      const projectName = args[1] || "BidDeed Design";
      const userPrompt = args.slice(2).join(" ") || "A professional SaaS dashboard";
      const stitchPrompt = buildStitchPrompt(userPrompt);
      
      console.log(`\n🚀 StitchWise V2 — Generating: ${projectName}\n`);
      const result = await generateDesign(sdk, projectName, stitchPrompt);
      
      // Download artifacts
      const htmlPath = join(OUTPUT_DIR, `${projectName.replace(/\s+/g, "-")}.html`);
      const imgPath = join(OUTPUT_DIR, `${projectName.replace(/\s+/g, "-")}.png`);
      await downloadArtifact(result.htmlUrl, htmlPath);
      await downloadArtifact(result.imageUrl, imgPath);
      
      console.log(`\n✅ DONE — Output: ${OUTPUT_DIR}`);
      console.log(`   HTML: ${htmlPath}`);
      console.log(`   Screenshot: ${imgPath}`);
      console.log(`   Project ID: ${result.projectId}`);
      console.log(`   Attempts: ${result.attempt}/${MAX_RETRIES}`);
      break;
    }

    case "list": {
      const projects = await sdk.projects();
      console.log("\n📋 Stitch Projects:\n");
      for (const p of projects) {
        console.log(`  ${p.id} — ${p.title}`);
      }
      break;
    }

    case "export": {
      const projectId = args[1];
      const screenId = args[2];
      if (!projectId || !screenId) {
        console.error("Usage: stitchwise export <project-id> <screen-id>");
        process.exit(1);
      }
      const project = sdk.project(projectId);
      const screens = await project.screens();
      const screen = screens.find((s: any) => s.id === screenId);
      if (!screen) {
        console.error(`Screen ${screenId} not found`);
        process.exit(1);
      }
      const html = await screen.getHtml();
      const outPath = join(OUTPUT_DIR, `export-${screenId}.html`);
      await downloadArtifact(html, outPath);
      console.log(`✅ Exported: ${outPath}`);
      break;
    }

    case "dashboard": {
      const name = args[1] || "Admin Dashboard";
      const prompt = buildStitchPrompt(`
        Admin dashboard with:
        - Revenue tracking chart (line graph, monthly)
        - Email waitlist table with name, email, date columns
        - Calendar widget for scheduled meetings
        - SEO keyword performance panel
        - AI chatbot widget in bottom-right corner
        - Dark theme matching brand colors
        - Responsive: desktop split-screen, mobile stacked
      `);
      const result = await generateDesign(sdk, name, prompt);
      const htmlPath = join(OUTPUT_DIR, `${name.replace(/\s+/g, "-")}.html`);
      await downloadArtifact(result.htmlUrl, htmlPath);
      console.log(`\n✅ Dashboard generated: ${htmlPath}`);
      break;
    }

    case "landing": {
      const name = args[1] || "Landing Page";
      const prompt = buildStitchPrompt(`
        Landing page with:
        - Hero section with animated gradient background
        - Value proposition headline with accent color CTA button
        - 3-column feature grid with icons
        - Social proof / testimonials section
        - Pricing comparison table
        - Footer with newsletter signup
        - Smooth scroll animations on entry
        - Mobile-first, single column on small screens
      `);
      const result = await generateDesign(sdk, name, prompt);
      const htmlPath = join(OUTPUT_DIR, `${name.replace(/\s+/g, "-")}.html`);
      await downloadArtifact(result.htmlUrl, htmlPath);
      console.log(`\n✅ Landing page generated: ${htmlPath}`);
      break;
    }

    default:
      console.error(`Unknown command: ${command}. Run --help for usage.`);
      process.exit(1);
  }
}

main().catch((err) => {
  console.error(`❌ Fatal: ${err.message}`);
  process.exit(1);
});
