import { useState, useEffect, useRef } from 'react'
import { supabase, WatchSession, WatchEvent } from '../lib/supabase'

const MAX_EVENTS = 200

export function useRealtime(
  activeSessions: WatchSession[],
  setActiveSessions: React.Dispatch<React.SetStateAction<WatchSession[]>>,
  selectedSessionId: string | null
) {
  const [liveEvents, setLiveEvents] = useState<WatchEvent[]>([])
  const channelRef = useRef<ReturnType<typeof supabase.channel> | null>(null)

  useEffect(() => {
    if (channelRef.current) {
      supabase.removeChannel(channelRef.current)
    }

    const channel = supabase
      .channel('watch-live', { config: { broadcast: { self: true } } })
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'watch_events' },
        (payload) => {
          const event = payload.new as WatchEvent
          setLiveEvents(prev => {
            const next = [event, ...prev]
            return next.slice(0, MAX_EVENTS)
          })
          // Update session card event count
          setActiveSessions(prev =>
            prev.map(s =>
              s.id === event.session_id
                ? {
                    ...s,
                    event_count: s.event_count + 1,
                    tool_breakdown: {
                      ...s.tool_breakdown,
                      [event.tool_name ?? 'unknown']:
                        (s.tool_breakdown[event.tool_name ?? 'unknown'] ?? 0) + 1,
                    },
                  }
                : s
            )
          )
        }
      )
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'watch_sessions' },
        (payload) => {
          const session = payload.new as WatchSession
          setActiveSessions(prev => {
            if (prev.find(s => s.id === session.id)) return prev
            return [session, ...prev]
          })
        }
      )
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'watch_sessions' },
        (payload) => {
          const updated = payload.new as WatchSession
          setActiveSessions(prev => {
            if (updated.status !== 'active') {
              return prev.filter(s => s.id !== updated.id)
            }
            return prev.map(s => (s.id === updated.id ? updated : s))
          })
        }
      )
      .subscribe()

    channelRef.current = channel

    return () => {
      supabase.removeChannel(channel)
    }
  }, [setActiveSessions])

  // Filter events for selected session
  const sessionEvents = selectedSessionId
    ? liveEvents.filter(e => e.session_id === selectedSessionId)
    : liveEvents

  return { sessionEvents, allLiveEvents: liveEvents }
}
