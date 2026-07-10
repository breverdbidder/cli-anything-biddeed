// Claude Watch — File classification utilities
// Adapted from NirDiamant/claude-watch brain-scanner.ts (MIT License)
// Zero shell execution policy: no child_process, no execSync

import type { ClassificationResult, FileCategory, FileImportance } from "../types.js";

// Directories to skip entirely during walk
export const SKIP_DIRS = new Set([
  "node_modules",
  ".git",
  "dist",
  "build",
  ".next",
  "__pycache__",
  ".cache",
  "vendor",
  "coverage",
  ".turbo",
  ".vercel",
  "out",
]);

// Directories that are more likely to contain logic files
export const INTERESTING_DIRS = new Set([
  ".claude",
  "harnesses",
  "prompts",
  "rules",
  "config",
  "docs",
  "scripts",
  "src",
]);

// File patterns for each category — checked against filename (lowercase)
const PROMPT_PATTERNS: RegExp[] = [
  /\.cursorrules$/,
  /\.aiderignore$/,
  /system[-_]?prompt/,
  /prompt[-_]template/,
  /promptlib/,
  /\.prompt\.(txt|md|json)$/,
  /llm[-_]?prompt/,
];

const RULES_PATTERNS: RegExp[] = [
  /^claude\.md$/i,
  /^\.claude\.md$/i,
  /harness\.md$/i,
  /^rules\.(md|txt|json)$/,
  /\.rules\.(md|txt|json)$/,
  /guidelines?\.(md|txt)$/,
  /constraints?\.(md|txt)$/,
  /^instructions\.(md|txt)$/,
  /^context\.(md|txt)$/,
];

const CONFIG_PATTERNS: RegExp[] = [
  /^\.claude\/settings\.json$/,
  /^settings\.json$/,
  /^config\.(json|yaml|yml|toml)$/,
  /^\.env(\.example|\.sample|\.template)?$/,
  /tsconfig.*\.json$/,
  /package\.json$/,
  /pyproject\.toml$/,
  /\.claude\/.*\.json$/,
];

const DOCS_PATTERNS: RegExp[] = [
  /^readme(\.md)?$/i,
  /^changelog(\.md)?$/i,
  /^todo(s)?(\.md)?$/i,
  /^notes?\.(md|txt)$/i,
  /\/docs\//,
  /\/plans?\//,
  /\/specs?\//,
  /^spec\.(md|txt)$/i,
  /^plan\.(md|txt)$/i,
];

const STATE_PATTERNS: RegExp[] = [
  /\.json$/,
  /memory\.(md|json)$/i,
  /state\.(json|yaml|yml)$/,
  /cache\.(json|yaml|yml)$/,
  /checkpoint/,
  /eval\.json$/,
];

// Content signals — words/phrases indicating importance
interface ContentSignal {
  pattern: RegExp;
  signal: string;
  importance: FileImportance;
}

const CONTENT_SIGNALS: ContentSignal[] = [
  { pattern: /\bNEVER\b/g,   signal: "contains NEVER rules",  importance: "critical" },
  { pattern: /\bALWAYS\b/g,  signal: "contains ALWAYS rules", importance: "critical" },
  { pattern: /\bMUST\b/g,    signal: "contains MUST rules",   importance: "high"     },
  { pattern: /\bCRITICAL\b/g,signal: "contains CRITICAL tags",importance: "critical" },
  { pattern: /\bFORBIDDEN\b/g,signal: "contains FORBIDDEN rules",importance: "critical" },
  { pattern: /\bREQUIRED\b/g, signal: "contains REQUIRED rules",importance: "high"  },
  { pattern: /execSync|child_process/g, signal: "shell execution reference", importance: "high" },
];

// Max density threshold for content signals to matter
const SIGNAL_THRESHOLD = 1; // at least 1 match

function matchesPatterns(name: string, patterns: RegExp[]): boolean {
  const lower = name.toLowerCase();
  return patterns.some((p) => p.test(lower));
}

function detectContentSignals(
  content: string
): { signals: string[]; importance: FileImportance } {
  const signals: string[] = [];
  let importance: FileImportance = "normal";

  for (const cs of CONTENT_SIGNALS) {
    const matches = content.match(cs.pattern);
    if (matches && matches.length >= SIGNAL_THRESHOLD) {
      signals.push(cs.signal);
      if (cs.importance === "critical") {
        importance = "critical";
      } else if (cs.importance === "high" && importance !== "critical") {
        importance = "high";
      }
    }
  }

  return { signals, importance };
}

function categorizeByPath(
  relativePath: string
): FileCategory | null {
  // Check path segments for directory hints
  const segments = relativePath.split("/");
  const filename = segments[segments.length - 1];

  // .claude/ directory → config or rules
  if (segments.includes(".claude")) {
    if (filename.endsWith(".json")) return "config";
    if (filename.toLowerCase().endsWith(".md")) return "rules";
  }

  if (matchesPatterns(filename, PROMPT_PATTERNS)) return "prompt";
  if (matchesPatterns(filename, RULES_PATTERNS)) return "rules";
  if (matchesPatterns(relativePath, CONFIG_PATTERNS)) return "config";
  if (matchesPatterns(relativePath, DOCS_PATTERNS)) return "docs";
  if (matchesPatterns(filename, STATE_PATTERNS)) return "state";

  return null;
}

/**
 * Classify a file given its relative path and content.
 * Returns null if the file is not considered a "logic file" worth tracking.
 */
export function classifyFile(
  relativePath: string,
  content: string
): ClassificationResult | null {
  const category = categorizeByPath(relativePath);
  if (!category) return null;

  const { signals: contentSignals, importance: contentImportance } =
    detectContentSignals(content);

  const signals: string[] = [...contentSignals];

  // Add path-based signals
  const segments = relativePath.split("/");
  if (segments.includes(".claude")) signals.push("in .claude/ directory");
  if (segments.includes("harnesses")) signals.push("in harnesses/ directory");
  if (segments.includes("prompts") || segments.includes("rules"))
    signals.push("in prompts/rules directory");

  // Determine final importance
  let importance: FileImportance = contentImportance;

  // CLAUDE.md and harness files are always critical
  const filename = segments[segments.length - 1];
  if (
    filename.toLowerCase() === "claude.md" ||
    filename.toLowerCase() === ".claude.md" ||
    filename.toLowerCase() === "harness.md"
  ) {
    importance = "critical";
    if (!signals.includes("core rules file")) signals.push("core rules file");
  }

  // .cursorrules is critical
  if (filename === ".cursorrules") {
    importance = "critical";
    if (!signals.includes("cursor IDE rules")) signals.push("cursor IDE rules");
  }

  return { category, importance, signals };
}
