#!/usr/bin/env node
/**
 * FigmaWise Agent — Figma MCP Integration for DesignWise Squad
 * cli-anything harness: cli_anything.figmawise
 *
 * Uses Figma remote MCP server (https://mcp.figma.com/mcp)
 * Auth: OAuth via claude plugin install figma@claude-plugins-official
 *
 * This agent is designed to be called BY Claude Code which has MCP access.
 * It provides structured prompts and workflows, not direct API calls.
 */

const BRAND_KIT = {
  primary: "#1E3A5F",
  accent: "#F59E0B",
  bg: "#020617",
  font: "Inter",
  name: "BidDeed.AI / ZoneWise.AI",
};

// ─── Figma MCP Tool Prompts ──────────────────────────────────────
// These are structured prompts for Claude Code to execute via Figma MCP

const PROMPTS = {
  extractDesign: (figmaUrl) => `
Use the Figma MCP server to get design context from this file:
${figmaUrl}

Extract:
- Color palette (compare against brand: primary ${BRAND_KIT.primary}, accent ${BRAND_KIT.accent})
- Typography (check for ${BRAND_KIT.font} font)
- Layout structure and spacing
- Component hierarchy

Return as structured JSON.`,

  implementDesign: (figmaUrl) => `
Use the Figma MCP server to implement this design:
${figmaUrl}

Requirements:
- Output: React + Tailwind CSS
- Use brand colors: primary ${BRAND_KIT.primary}, accent ${BRAND_KIT.accent}, bg ${BRAND_KIT.bg}
- Font: ${BRAND_KIT.font}
- Mobile-first responsive
- Accessible (WCAG AA contrast)
- Use Code Connect if available for component reuse`,

  captureToFigma: (localUrl, figmaFileUrl) => `
Use the Figma MCP server to capture live UI to Figma:
1. Start a local server at ${localUrl}
2. Capture the UI
3. Send design layers to: ${figmaFileUrl}
4. Confirm the capture completed`,

  getVariables: (figmaUrl) => `
Use the Figma MCP server to get variables and styles from:
${figmaUrl}

Return: colors, spacing tokens, typography scales, component variants.`,

  brandAudit: (figmaUrl) => `
Use the Figma MCP server to get design context from:
${figmaUrl}

Then audit against brand requirements:
- Primary: ${BRAND_KIT.primary} (navy)
- Accent: ${BRAND_KIT.accent} (orange)
- Background: ${BRAND_KIT.bg} (slate-950)
- Font: ${BRAND_KIT.font}
- Report any deviations`,

  writeComponent: (figmaFileUrl, componentSpec) => `
Use the Figma MCP server to create a new component in:
${figmaFileUrl}

Component spec:
${componentSpec}

Use auto layout, proper naming conventions, and brand variables.`,
};

// ─── CLI Entry Point ─────────────────────────────────────────────
function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === "--help") {
    console.log(`
FigmaWise Agent — Figma MCP Integration
Usage:
  figmawise extract <figma-url>              Extract design context
  figmawise implement <figma-url>            Generate code from design
  figmawise capture <local-url> <figma-url>  Capture live UI to Figma
  figmawise variables <figma-url>            Get design tokens
  figmawise audit <figma-url>                Brand compliance audit
  figmawise write <figma-url> <spec>         Create component in Figma

Note: Requires Figma MCP plugin installed in Claude Code.
Auth: claude plugin install figma@claude-plugins-official
    `);
    return;
  }

  const figmaUrl = args[1];
  if (!figmaUrl && command !== "--help") {
    console.error("Error: Figma URL required. Run --help for usage.");
    process.exit(1);
  }

  let prompt;
  switch (command) {
    case "extract":
      prompt = PROMPTS.extractDesign(figmaUrl);
      break;
    case "implement":
      prompt = PROMPTS.implementDesign(figmaUrl);
      break;
    case "capture":
      const localUrl = figmaUrl;
      const figmaTarget = args[2];
      if (!figmaTarget) {
        console.error("Usage: figmawise capture <local-url> <figma-url>");
        process.exit(1);
      }
      prompt = PROMPTS.captureToFigma(localUrl, figmaTarget);
      break;
    case "variables":
      prompt = PROMPTS.getVariables(figmaUrl);
      break;
    case "audit":
      prompt = PROMPTS.brandAudit(figmaUrl);
      break;
    case "write":
      const spec = args.slice(2).join(" ");
      prompt = PROMPTS.writeComponent(figmaUrl, spec);
      break;
    default:
      console.error(`Unknown command: ${command}. Run --help.`);
      process.exit(1);
  }

  // Output the structured prompt for Claude Code to execute
  console.log("─── FIGMAWISE PROMPT ───");
  console.log(prompt);
  console.log("─── END PROMPT ───");
  console.log(
    "\nPipe this to Claude Code with Figma MCP enabled to execute."
  );
}

main();
