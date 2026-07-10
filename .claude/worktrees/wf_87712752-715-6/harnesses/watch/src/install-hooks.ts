// Claude Watch — Hook Installer
// Adds/removes Claude Code hooks in .claude/settings.json
// Zero shell execution policy: no child_process, no execSync

import * as fs from "fs";
import * as path from "path";

const WATCH_MARKER = "watch-ingest"; // identifier to detect existing watch hooks
const SUPABASE_URL =
  "https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/watch-ingest";

// Fire-and-forget curl command template
const HOOK_COMMAND = [
  `curl -sf -X POST ${SUPABASE_URL}`,
  `-H "Authorization: Bearer $WATCH_TOKEN"`,
  `-H "Content-Type: application/json"`,
  `-d "$(cat)"`,
  `>/dev/null 2>&1 &`,
].join(" \\\n  ");

const HOOK_TYPES = ["PostToolUse", "Notification", "Stop"] as const;

interface HookEntry {
  matcher?: string;
  hooks: Array<{
    type: string;
    command: string;
  }>;
}

interface Settings {
  hooks?: Record<string, HookEntry[]>;
  [key: string]: unknown;
}

function parseArgs(): { global: boolean; remove: boolean } {
  const args = process.argv.slice(2);
  return {
    global: args.includes("--global"),
    remove: args.includes("--remove"),
  };
}

function getSettingsPath(useGlobal: boolean): string {
  if (useGlobal) {
    const home = process.env.HOME || process.env.USERPROFILE || "";
    return path.join(home, ".claude", "settings.json");
  }
  return path.join(process.cwd(), ".claude", "settings.json");
}

function readSettings(settingsPath: string): Settings {
  try {
    const raw = fs.readFileSync(settingsPath, "utf8");
    return JSON.parse(raw) as Settings;
  } catch {
    return {};
  }
}

function writeSettings(settingsPath: string, settings: Settings): void {
  const dir = path.dirname(settingsPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + "\n", "utf8");
}

function isWatchHook(command: string): boolean {
  return command.includes(WATCH_MARKER);
}

function hookExists(settings: Settings, hookType: string): boolean {
  const hooksForType = settings.hooks?.[hookType];
  if (!hooksForType) return false;
  for (const entry of hooksForType) {
    for (const hook of entry.hooks || []) {
      if (isWatchHook(hook.command)) return true;
    }
  }
  return false;
}

function installHooks(settings: Settings): { added: number; skipped: number } {
  let added = 0;
  let skipped = 0;

  if (!settings.hooks) settings.hooks = {};

  for (const hookType of HOOK_TYPES) {
    if (hookExists(settings, hookType)) {
      console.log(`  [skip] ${hookType} hook already installed`);
      skipped++;
      continue;
    }

    if (!settings.hooks[hookType]) {
      settings.hooks[hookType] = [];
    }

    settings.hooks[hookType].push({
      matcher: "*",
      hooks: [
        {
          type: "command",
          command: HOOK_COMMAND,
        },
      ],
    } as HookEntry);

    console.log(`  [add]  ${hookType} hook`);
    added++;
  }

  return { added, skipped };
}

function removeHooks(settings: Settings): { removed: number } {
  let removed = 0;

  if (!settings.hooks) return { removed };

  for (const hookType of HOOK_TYPES) {
    const entries = settings.hooks[hookType];
    if (!entries) continue;

    const before = entries.length;

    // Filter out watch hook entries
    settings.hooks[hookType] = entries
      .map((entry) => ({
        ...entry,
        hooks: (entry.hooks || []).filter((h) => !isWatchHook(h.command)),
      }))
      .filter((entry) => entry.hooks.length > 0);

    // Remove the key if empty
    if (settings.hooks[hookType].length === 0) {
      delete settings.hooks[hookType];
    }

    const after = (settings.hooks[hookType] || []).length;
    if (before !== after) {
      console.log(`  [remove] ${hookType} hook`);
      removed++;
    }
  }

  return { removed };
}

function main(): void {
  const { global: useGlobal, remove } = parseArgs();
  const scope = useGlobal ? "global" : "project";
  const settingsPath = getSettingsPath(useGlobal);

  console.log(`Claude Watch Hook Installer`);
  console.log(`Scope: ${scope} (${settingsPath})`);
  console.log(`Action: ${remove ? "remove" : "install"}`);
  console.log("");

  // Warn if WATCH_TOKEN not set
  if (!process.env.WATCH_TOKEN) {
    console.warn(
      "WARNING: $WATCH_TOKEN env var is not set. Hooks will be installed but will not authenticate.\n" +
        "         Add WATCH_TOKEN to your shell profile after getting the token from Ariel.\n"
    );
  }

  const settings = readSettings(settingsPath);

  if (remove) {
    const { removed } = removeHooks(settings);
    writeSettings(settingsPath, settings);
    console.log(`\nDone. Removed ${removed} watch hook(s).`);
  } else {
    const { added, skipped } = installHooks(settings);
    writeSettings(settingsPath, settings);
    console.log(
      `\nDone. Added ${added} hook(s), skipped ${skipped} already-installed.`
    );

    if (added > 0) {
      console.log(
        "\nHooks will fire curl to Supabase watch-ingest on each Claude Code tool call."
      );
      console.log("Fire-and-forget: no latency added to Claude Code.\n");
    }
  }
}

main();
