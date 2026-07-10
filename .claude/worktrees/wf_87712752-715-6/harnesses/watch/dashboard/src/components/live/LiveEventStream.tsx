import { useEffect, useRef } from 'react'
import { formatDistanceToNow } from 'date-fns'
import {
  FileEdit, Terminal, Eye, PenTool, FileText,
  Bell, StopCircle, Layers
} from 'lucide-react'
import { WatchEvent } from '../../lib/supabase'

interface LiveEventStreamProps {
  events: WatchEvent[]
  sessionId: string | null
}

const TOOL_COLORS: Record<string, string> = {
  Write: '#22C55E',
  Edit: '#3B82F6',
  Bash: '#F59E0B',
  Read: '#94A3B8',
  TodoWrite: '#A855F7',
  TodoRead: '#A855F7',
  WebFetch: '#06B6D4',
  WebSearch: '#06B6D4',
  Glob: '#EC4899',
  Grep: '#EC4899',
}

function ToolIcon({ toolName }: { toolName: string | null }) {
  const icons: Record<string, React.ReactNode> = {
    Write: <PenTool size={14} />,
    Edit: <FileEdit size={14} />,
    Bash: <Terminal size={14} />,
    Read: <Eye size={14} />,
    TodoWrite: <Layers size={14} />,
    TodoRead: <Layers size={14} />,
    Notification: <Bell size={14} />,
    Stop: <StopCircle size={14} />,
  }
  const icon = toolName ? (icons[toolName] ?? <FileText size={14} />) : <Bell size={14} />
  return icon
}

function EventRow({ event }: { event: WatchEvent }) {
  const color = event.tool_name ? (TOOL_COLORS[event.tool_name] ?? '#64748B') : '#64748B'

  return (
    <div
      className="slide-in flex gap-3 py-2 px-3 rounded-lg border-b"
      style={{ borderColor: 'rgba(30,58,95,0.2)' }}
    >
      {/* Tool icon */}
      <div
        className="w-6 h-6 rounded flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{ backgroundColor: `${color}20`, color }}
      >
        <ToolIcon toolName={event.tool_name} />
      </div>

      {/* Content */}
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
              {event.file_path.length > 40
                ? '…' + event.file_path.slice(-40)
                : event.file_path}
            </span>
          )}
        </div>
      </div>

      {/* Time */}
      <span
        className="text-xs flex-shrink-0 tabular-nums"
        style={{ color: 'rgba(148,163,184,0.5)' }}
      >
        {formatDistanceToNow(new Date(event.ts), { addSuffix: false })}
      </span>
    </div>
  )
}

export function LiveEventStream({ events, sessionId }: LiveEventStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  if (!sessionId) {
    return (
      <div
        className="flex items-center justify-center py-12 text-center rounded-xl border"
        style={{
          backgroundColor: 'var(--color-surface)',
          borderColor: 'rgba(30,58,95,0.4)',
        }}
      >
        <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Select a session above to see the live event stream.
        </p>
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div
        className="flex items-center justify-center py-12 rounded-xl border"
        style={{
          backgroundColor: 'var(--color-surface)',
          borderColor: 'rgba(30,58,95,0.4)',
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="pulse-dot w-2 h-2 rounded-full"
            style={{ backgroundColor: 'var(--color-success)' }}
          />
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Waiting for events…
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{
        backgroundColor: 'var(--color-surface)',
        borderColor: 'rgba(30,58,95,0.4)',
      }}
    >
      <div className="px-3 py-2 border-b flex items-center gap-2"
        style={{ borderColor: 'rgba(30,58,95,0.4)' }}
      >
        <span
          className="pulse-dot w-2 h-2 rounded-full"
          style={{ backgroundColor: 'var(--color-success)' }}
        />
        <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
          Live event stream — {events.length} events
        </span>
      </div>
      <div className="overflow-y-auto max-h-96 divide-y divide-transparent">
        {events.map(event => (
          <EventRow key={event.id} event={event} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
