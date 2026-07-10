import { useState } from 'react'
import { formatDistanceToNow, format } from 'date-fns'
import { ChevronDown, ChevronUp, ArrowUpDown } from 'lucide-react'
import { WatchSession } from '../../lib/supabase'

interface SessionTableProps {
  sessions: WatchSession[]
  onSelect: (session: WatchSession) => void
  selectedId: string | null
}

type SortKey = 'started_at' | 'event_count' | 'repo'
type SortDir = 'asc' | 'desc'

const STATUS_STYLES: Record<string, { bg: string; color: string }> = {
  active: { bg: 'rgba(34,197,94,0.15)', color: '#4ADE80' },
  completed: { bg: 'rgba(59,130,246,0.15)', color: '#60A5FA' },
  stale: { bg: 'rgba(148,163,184,0.15)', color: '#94A3B8' },
}

function ToolBreakdownBar({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0)
  if (total === 0) return null
  const colors: Record<string, string> = {
    Write: '#22C55E', Edit: '#3B82F6', Bash: '#F59E0B', Read: '#64748B',
  }
  const topTools = Object.entries(breakdown)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
  return (
    <div className="flex gap-1 items-center">
      {topTools.map(([tool, count]) => (
        <div key={tool} className="flex items-center gap-0.5">
          <span
            className="w-2 h-2 rounded-sm flex-shrink-0"
            style={{ backgroundColor: colors[tool] ?? '#334155' }}
          />
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {count}
          </span>
        </div>
      ))}
    </div>
  )
}

function duration(started: string, ended: string | null): string {
  if (!ended) return '—'
  const diff = Math.floor((new Date(ended).getTime() - new Date(started).getTime()) / 1000)
  const m = Math.floor(diff / 60)
  const s = diff % 60
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export function SessionTable({ sessions, onSelect, selectedId }: SessionTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('started_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 20

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('desc') }
  }

  const sorted = [...sessions].sort((a, b) => {
    let cmp = 0
    if (sortKey === 'started_at') cmp = a.started_at.localeCompare(b.started_at)
    else if (sortKey === 'event_count') cmp = a.event_count - b.event_count
    else if (sortKey === 'repo') cmp = a.repo.localeCompare(b.repo)
    return sortDir === 'asc' ? cmp : -cmp
  })

  const paged = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)

  const SortBtn = ({ k, label }: { k: SortKey; label: string }) => (
    <button
      onClick={() => toggleSort(k)}
      className="flex items-center gap-1 text-xs font-medium"
      style={{ color: sortKey === k ? 'var(--color-accent)' : 'var(--color-text-muted)' }}
    >
      {label}
      <ArrowUpDown size={12} />
    </button>
  )

  return (
    <div>
      <div className="overflow-x-auto rounded-xl border" style={{ borderColor: 'rgba(30,58,95,0.4)' }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: 'rgba(15,23,42,0.8)', borderBottom: '1px solid rgba(30,58,95,0.4)' }}>
              <th className="text-left px-4 py-3"><SortBtn k="repo" label="Repo" /></th>
              <th className="text-left px-4 py-3"><SortBtn k="started_at" label="Started" /></th>
              <th className="text-left px-4 py-3 hidden sm:table-cell">
                <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Duration</span>
              </th>
              <th className="text-left px-4 py-3"><SortBtn k="event_count" label="Events" /></th>
              <th className="text-left px-4 py-3 hidden md:table-cell">
                <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Tools</span>
              </th>
              <th className="text-left px-4 py-3">
                <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Status</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {paged.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  No sessions found.
                </td>
              </tr>
            )}
            {paged.map(session => {
              const isSelected = session.id === selectedId
              const statusStyle = STATUS_STYLES[session.status] ?? STATUS_STYLES.stale
              return (
                <tr
                  key={session.id}
                  onClick={() => onSelect(session)}
                  className="cursor-pointer transition-colors"
                  style={{
                    backgroundColor: isSelected ? 'rgba(30,58,95,0.3)' : 'transparent',
                    borderBottom: '1px solid rgba(30,58,95,0.2)',
                  }}
                  onMouseEnter={e => {
                    if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'rgba(30,58,95,0.15)'
                  }}
                  onMouseLeave={e => {
                    if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'
                  }}
                >
                  <td className="px-4 py-3">
                    <span className="font-medium" style={{ color: 'var(--color-text)' }}>{session.repo}</span>
                    {session.branch && (
                      <span className="block text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
                        {session.branch}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span style={{ color: 'var(--color-text-muted)' }}>
                      {formatDistanceToNow(new Date(session.started_at), { addSuffix: true })}
                    </span>
                    <span className="block text-xs" style={{ color: 'rgba(148,163,184,0.5)' }}>
                      {format(new Date(session.started_at), 'MMM d, HH:mm')}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell" style={{ color: 'var(--color-text-muted)' }}>
                    {duration(session.started_at, session.ended_at)}
                  </td>
                  <td className="px-4 py-3" style={{ color: 'var(--color-text)' }}>
                    {session.event_count}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <ToolBreakdownBar breakdown={session.tool_breakdown} />
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="text-xs px-2 py-0.5 rounded-full font-medium"
                      style={statusStyle}
                    >
                      {session.status}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {sorted.length} sessions
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1 text-xs rounded-lg border disabled:opacity-40"
              style={{
                borderColor: 'rgba(30,58,95,0.4)',
                color: 'var(--color-text-muted)',
                backgroundColor: 'var(--color-surface)',
              }}
            >
              <ChevronDown size={14} className="rotate-90" />
            </button>
            <span className="px-3 py-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {page + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page === totalPages - 1}
              className="px-3 py-1 text-xs rounded-lg border disabled:opacity-40"
              style={{
                borderColor: 'rgba(30,58,95,0.4)',
                color: 'var(--color-text-muted)',
                backgroundColor: 'var(--color-surface)',
              }}
            >
              <ChevronUp size={14} className="rotate-90" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
