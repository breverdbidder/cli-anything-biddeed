import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
  realtime: {
    params: {
      eventsPerSecond: 10,
    },
  },
})

export type Database = {
  public: {
    Tables: {
      watch_sessions: {
        Row: WatchSession
      }
      watch_events: {
        Row: WatchEvent
      }
      watch_health: {
        Row: WatchHealth
      }
    }
  }
}

export interface WatchSession {
  id: string
  repo: string
  branch: string | null
  started_at: string
  ended_at: string | null
  status: 'active' | 'completed' | 'stale'
  summary: string | null
  event_count: number
  tool_breakdown: Record<string, number>
}

export interface WatchEvent {
  id: number
  session_id: string
  ts: string
  hook_type: 'PostToolUse' | 'Notification' | 'Stop'
  tool_name: string | null
  file_path: string | null
  input_data: Record<string, unknown> | null
  output_data: string | null
  diff: string | null
  duration_ms: number | null
}

export interface WatchHealth {
  id: number
  scanned_at: string
  scan_type: 'nightly' | 'session_start'
  repo: string
  file_path: string
  category: 'prompt' | 'rules' | 'config' | 'docs' | 'state'
  content_hash: string
  signals: string[]
  importance: 'critical' | 'high' | 'normal'
  line_count: number | null
  size_bytes: number | null
  content_preview: string | null
}
