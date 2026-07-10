import { useState, useEffect } from 'react'
import { WatchSession, WatchEvent } from '../../lib/supabase'
import { SessionTable } from './SessionTable'
import { SessionTimeline } from './SessionTimeline'
import { FilterBar } from './FilterBar'
import { fetchSessionEvents, fetchDistinctRepos } from '../../hooks/useSessions'

interface AuditTabProps {
  sessions: WatchSession[]
  loading: boolean
  onFilterChange: (filters: { repo: string; dateRange: '24h' | '7d' | '30d' }) => void
}

export function AuditTab({ sessions, loading, onFilterChange }: AuditTabProps) {
  const [selectedSession, setSelectedSession] = useState<WatchSession | null>(null)
  const [events, setEvents] = useState<WatchEvent[]>([])
  const [eventsLoading, setEventsLoading] = useState(false)
  const [repos, setRepos] = useState<string[]>([])
  const [selectedRepo, setSelectedRepo] = useState('')
  const [dateRange, setDateRange] = useState<'24h' | '7d' | '30d'>('7d')
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetchDistinctRepos().then(setRepos)
  }, [])

  useEffect(() => {
    onFilterChange({ repo: selectedRepo, dateRange })
  }, [selectedRepo, dateRange, onFilterChange])

  const handleSelectSession = async (session: WatchSession) => {
    setSelectedSession(session)
    setEventsLoading(true)
    const data = await fetchSessionEvents(session.id)
    setEvents(data)
    setEventsLoading(false)
  }

  // Filter by search
  const filteredSessions = search
    ? sessions.filter(s =>
        s.repo.toLowerCase().includes(search.toLowerCase()) ||
        s.id.includes(search)
      )
    : sessions

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          Session Audit
        </h2>
        <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          {sessions.length} sessions
        </span>
      </div>

      {/* Filter bar */}
      <div
        className="p-3 rounded-xl border"
        style={{
          backgroundColor: 'var(--color-surface)',
          borderColor: 'rgba(30,58,95,0.4)',
        }}
      >
        <FilterBar
          repos={repos}
          selectedRepo={selectedRepo}
          onRepoChange={setSelectedRepo}
          dateRange={dateRange}
          onDateRangeChange={setDateRange}
          search={search}
          onSearchChange={setSearch}
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="py-8 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Loading sessions…
        </div>
      ) : (
        <SessionTable
          sessions={filteredSessions}
          onSelect={handleSelectSession}
          selectedId={selectedSession?.id ?? null}
        />
      )}

      {/* Session detail */}
      {selectedSession && (
        <div>
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text)' }}>
            Session Detail: {selectedSession.repo} — {selectedSession.id.slice(0, 16)}…
          </h3>
          <SessionTimeline
            session={selectedSession}
            events={events}
            loading={eventsLoading}
          />
        </div>
      )}
    </div>
  )
}
