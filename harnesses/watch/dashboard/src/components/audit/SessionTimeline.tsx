import { useState } from 'react'
import { format } from 'date-fns'
import {
  FileEdit, Terminal, Eye, PenTool, FileText, ChevronDown, ChevronUp,
  Bell, StopCircle, Layers, Globe, Search
} from 'lucide-react'
import { WatchEvent, WatchSession } from '../../lib/supabase'
import { DiffViewer } from './DiffViewer'

interface SessionTimelineProps {
  session: WatchSession
  events: WatchEvent[]
  loading: boolean
}

const TOOL_COLORS: Record<string, string> = {
  Write: '#22C55E',
  Edit: '#3B82F6',
  Bash: '#F59E0B',
  Read: '#94A3B8',
  TodoWrite: '#A855F7',
  TodoRead: '#A855F7',
  Glob: '#EC4899',
  Grep: '#EC4899',
  WebFetch: '#06B6D4',
  WebSearch: '#06B6D4',
  Notification: '#64748B',
  Stop: '#EF4444',
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  Write: <PenTool size={12} />,
  Edit: <FileEdit size={12} />,
  Bash: <Terminal size={12} />,
  Read: <Eye size={12} />,
  TodoWrite: <Layers size={12} />,
  TodoRead: <Layers size={12} />,
  Glob: <Search size={12} />,
  Grep: <Search size={12} />,
  WebFetch: <Globe size={12} />,
  WebSearch: <Globe size={12} />,
  Notification: <Bell size={12} />,
  Stop: <StopCircle size={12} />,
}

function EventNode({ event }: { event: WatchEvent }) {
  const [expanded, setExpanded] = useState(false)
  const color = TOOL_COLORS[event.tool_name ?? ''] ?? '#64748B'
  const icon = TOOL_ICONS[event.tool_name ?? ''] ?? <FileText size={12} />
  const hasDetail = event.diff || event.input_data || event.output_data

  return (
    <div className="flex gap-4 relative">
      {/* Timeline line */}
      <div className="flex flex-col items-center">
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 z-10"
          style={{ backgroundColor: `${color}20`, color, border: `1.5px solid ${color}40` }}
        >
          {icon}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 pb-4 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold" style={{ color }}>
                {event.tool_name ?? event.hook_type}
              </span>
              {event.file_path && (
                <span
                  className="text-xs font-mono truncate"
                  style={{ color: 'var(--color-text-muted)' }}
                  title={event.file_path}
                >
                  {event.file_path.length > 50 ? '…' + event.file_path.slice(-50) : event.file_path}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-xs font-mono" style={{ color: 'rgba(148,163,184,0.5)' }}>
              {format(new Date(event.ts), 'HH:mm:ss')}
            </span>
            {hasDetail && (
              <button
                onClick={() => setExpanded(e => !e)}
                style={{ color: 'var(--color-text-muted)' }}
              >
                {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            )}
          </div>
        </div>

        {expanded && (
          <div className="mt-2 space-y-2">
            {event.diff && (
              <DiffViewer diff={event.diff} />
            )}
            {!event.diff && event.input_data && Boolean((event.input_data as Record<string, unknown>).old_string) && (
              <DiffViewer
                diff={null}
                oldString={String((event.input_data as Record<string, unknown>).old_string ?? '')}
                newString={String((event.input_data as Record<string, unknown>).new_string ?? '')}
              />
            )}
            {event.output_data && (
              <div>
                <p className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Output</p>
                <pre
                  className="text-xs p-3 rounded-lg overflow-auto"
                  style={{
                    backgroundColor: 'rgba(2,6,23,0.8)',
                    color: 'var(--color-text-muted)',
                    maxHeight: '150px',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                  }}
                >
                  {event.output_data.slice(0, 2000)}
                  {event.output_data.length > 2000 ? '\n…[truncated]' : ''}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function SessionTimeline({ session, events, loading }: SessionTimelineProps) {
  if (loading) {
    return (
      <div className="py-8 text-center" style={{ color: 'var(--color-text-muted)' }}>
        Loading events…
      </div>
    )
  }

  return (
    <div
      className="rounded-xl border p-4"
      style={{
        backgroundColor: 'var(--color-surface)',
        borderColor: 'rgba(30,58,95,0.4)',
      }}
    >
      {/* Summary */}
      <div className="mb-4 p-3 rounded-lg" style={{ backgroundColor: 'rgba(30,58,95,0.2)' }}>
        <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-text)' }}>
          {session.summary ?? `${session.event_count} events in ${session.repo}`}
        </p>
        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {format(new Date(session.started_at), 'MMM d, HH:mm')}
          {session.ended_at && ` → ${format(new Date(session.ended_at), 'HH:mm')}`}
        </p>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div
          className="absolute left-3.5 top-0 bottom-0 w-px"
          style={{ backgroundColor: 'rgba(30,58,95,0.4)' }}
        />
        <div className="space-y-0">
          {events.map(event => (
            <EventNode key={event.id} event={event} />
          ))}
        </div>
        {events.length === 0 && (
          <p className="text-sm text-center py-4" style={{ color: 'var(--color-text-muted)' }}>
            No events recorded.
          </p>
        )}
      </div>
    </div>
  )
}
