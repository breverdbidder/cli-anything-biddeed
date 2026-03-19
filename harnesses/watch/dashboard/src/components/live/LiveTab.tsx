import { useState, useEffect } from 'react'
import { WatchSession, WatchEvent } from '../../lib/supabase'
import { ActiveSessionCards } from './ActiveSessionCards'
import { LiveEventStream } from './LiveEventStream'
import { ToolFrequencyChart } from './ToolFrequencyChart'
import { fetchSessionEvents } from '../../hooks/useSessions'

interface LiveTabProps {
  activeSessions: WatchSession[]
  liveEvents: WatchEvent[]
}

export function LiveTab({ activeSessions, liveEvents }: LiveTabProps) {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [historicEvents, setHistoricEvents] = useState<WatchEvent[]>([])

  // Auto-select first active session
  useEffect(() => {
    if (!selectedSessionId && activeSessions.length > 0) {
      setSelectedSessionId(activeSessions[0].id)
    }
  }, [activeSessions, selectedSessionId])

  // Load historic events when session selected
  useEffect(() => {
    if (!selectedSessionId) return
    fetchSessionEvents(selectedSessionId).then(setHistoricEvents)
  }, [selectedSessionId])

  const selectedSession = activeSessions.find(s => s.id === selectedSessionId)

  // Merge historic + live, deduplicate
  const liveForSession = liveEvents.filter(e => e.session_id === selectedSessionId)
  const seenIds = new Set(historicEvents.map(e => e.id))
  const newLive = liveForSession.filter(e => !seenIds.has(e.id))
  const allEvents = [...historicEvents, ...newLive]

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          Active Sessions
        </h2>
        <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          {activeSessions.length} active
        </span>
      </div>

      <ActiveSessionCards
        sessions={activeSessions}
        selectedId={selectedSessionId}
        onSelect={setSelectedSessionId}
      />

      {selectedSession && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <LiveEventStream events={allEvents} sessionId={selectedSessionId} />
          </div>
          <div>
            <ToolFrequencyChart breakdown={selectedSession.tool_breakdown} />
          </div>
        </div>
      )}

      {!selectedSession && activeSessions.length === 0 && (
        <div />
      )}

      {!selectedSession && activeSessions.length > 0 && (
        <LiveEventStream events={[]} sessionId={null} />
      )}
    </div>
  )
}
