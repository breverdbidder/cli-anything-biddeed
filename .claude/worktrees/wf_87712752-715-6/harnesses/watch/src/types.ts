// Claude Watch — Shared TypeScript Types
// Zero shell execution policy: no child_process, no execSync

export type HookType = "PostToolUse" | "Notification" | "Stop";

export interface HookPayload {
  session_id: string;
  type: HookType;
  tool_name?: string;
  project_path?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
}

export type SessionStatus = "active" | "completed" | "stale";

export interface WatchSession {
  id: string;
  repo: string;
  branch?: string;
  started_at: string;
  ended_at?: string;
  status: SessionStatus;
  summary?: string;
  event_count: number;
  tool_breakdown: Record<string, number>;
}

export type HookTypeLiteral = "PostToolUse" | "Notification" | "Stop";

export interface WatchEvent {
  id: number;
  session_id: string;
  ts: string;
  hook_type: HookTypeLiteral;
  tool_name?: string;
  file_path?: string;
  input_data?: Record<string, unknown>;
  output_data?: string;
  diff?: string;
  duration_ms?: number;
}

export type FileCategory = "prompt" | "rules" | "config" | "docs" | "state";
export type FileImportance = "critical" | "high" | "normal";
export type ScanType = "nightly" | "session_start";

export interface ClassificationResult {
  category: FileCategory;
  importance: FileImportance;
  signals: string[];
}

export interface LogicFile {
  filePath: string;
  category: FileCategory;
  importance: FileImportance;
  signals: string[];
  contentHash: string;
  lineCount: number;
  sizeBytes: number;
  contentPreview: string;
}

export interface HealthScanResult {
  repo: string;
  scanType: ScanType;
  scannedAt: string;
  files: LogicFile[];
}

export interface WatchHealth {
  id: number;
  scanned_at: string;
  scan_type: ScanType;
  repo: string;
  file_path: string;
  category: FileCategory;
  content_hash: string;
  signals: string[];
  importance: FileImportance;
  line_count: number;
  size_bytes: number;
  content_preview: string;
}
