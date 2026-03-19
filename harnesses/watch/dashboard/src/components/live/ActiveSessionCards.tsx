import { useEffect, useState } from 'react'
import { GitBranch, Zap, FileText, Hash } from 'lucide-react'
import { WatchSession } from '../../lib/supabase'

interface ActiveSessionCardsProps {
  sessions: WatchSession[]
  selectedId: string | null
  onSelect: (id: string) => void
}

function LiveTimer({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState('')

  useEffect(() => {
    const update = () => {
      const diff = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)
      const h = Math.floor(diff / 3600)
      const m = Math.floor((diff % 3600) / 60)
      const s = diff % 60
      if (h > 0) setElapsed(`${h}h ${m}m`)
      else if (m > 0) setElapsed(`${m}m ${s}s`)
      else setElapsed(`${s}s`)
    }
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [startedAt])

  return <span>{elapsed}</span>
}

function TopTools({ breakdown }: { breakdown: Record<string, number> }) {
  const top = Object.entries(breakdown)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
  if (top.length === 0) return null
  return (
    <div className="flex gap-1 flex-wrap">
      {top.map(([tool, count]) => (
        <span
          key={tool}
          className="text-xs px-1.5 py-0.5 rounded"
          style={{
            backgroundColor: 'rgba(30,58,95,0.5)',
            color: 'var(--color-text-muted)',
          }}
        >
          {tool} {count}
        </span>
      ))}
    </div>
  )
}

export function ActiveSessionCards({ sessions, selectedId, onSelect }: ActiveSessionCardsProps) {
  if (sessions.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center py-16 px-8 text-center rounded-xl border"
        style={{
          backgroundColor: 'var(--color-surface)',
          borderColor: 'rgba(30,58,95,0.4)',
        }}
      >
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
          style={{ backgroundColor: 'rgba(30,58,95,0.3)' }}
        >
          <Zap size={24} style={{ color: 'var(--color-text-muted)' }} />
        </div>
        <p className="font-medium mb-1" style={{ color: 'var(--color-text)' }}>
          No active sessions
        </p>
        <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Claude Code will appear here when running with hooks installed.
        </p>
      </div>
    )
  }

  return (
    <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
      {sessions.map(session => {
        const isSelected = session.id === selectedId
        return (
          <button
            key={session.id}
            onClick={() => onSelect(session.id)}
            className="text-left p-4 rounded-xl border transition-all"
            style={{
              backgroundColor: isSelected ? 'rgba(30,58,95,0.4)' : 'var(--color-surface)',
              borderColor: isSelected ? 'var(--color-accent)' : 'rgba(30,58,95,0.4)',
            }}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-2 mb-3">
              <div className="flex items-center gap-2 min-w-0">
                <span
                  className="pulse-dot w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: 'var(--color-success)' }}
                />
                <span
                  className="font-semibold text-sm truncate"
                  style={{ color: 'var(--color-text)' }}
                >
                  {session.repo}
                </span>
              </div>
              <span
                className="text-xs flex-shrink-0 font-mono"
                style={{ color: 'var(--color-accent)' }}
              >
                <LiveTimer startedAt={session.started_at} />
              </span>
            </div>

            {/* Branch */}
            {session.branch && (
              <div className="flex items-center gap-1.5 mb-2">
                <GitBranch size={12} style={{ color: 'var(--color-text-muted)' }} />
                <span className="text-xs font-mono truncate" style={{ color: 'var(--color-text-muted)' }}>
                  {session.branch}
                </span>
              </div>
            )}

            {/* Stats row */}
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center gap-1">
                <Hash size={12} style={{ color: 'var(--color-text-muted)' }} />
                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {session.event_count} events
                </span>
              </div>
            </div>

            {/* Tool breakdown */}
            <TopTools breakdown={session.tool_breakdown} />

            {/* Session ID */}
            <p
              className="text-xs font-mono mt-2 truncate"
              style={{ color: 'rgba(148,163,184,0.4)' }}
            >
              {session.id.slice(0, 16)}…
            </p>
          </button>
        )
      })}
    </div>
  )
}
