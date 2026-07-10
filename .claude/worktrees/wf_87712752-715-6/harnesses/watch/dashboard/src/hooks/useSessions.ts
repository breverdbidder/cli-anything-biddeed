import { useState, useEffect, useCallback } from 'react'
import { supabase, WatchSession, WatchEvent } from '../lib/supabase'

interface SessionFilters {
  repo?: string
  dateRange?: '24h' | '7d' | '30d'
  toolName?: string
  filePath?: string
}

export function useSessions() {
  const [activeSessions, setActiveSessions] = useState<WatchSession[]>([])
  const [completedSessions, setCompletedSessions] = useState<WatchSession[]>([])
  const [loading, setLoading] = useState(true)

  const fetchActiveSessions = useCallback(async () => {
    const { data } = await supabase
      .from('watch_sessions')
      .select('*')
      .eq('status', 'active')
      .order('started_at', { ascending: false })
    if (data) setActiveSessions(data as WatchSession[])
  }, [])

  const fetchCompletedSessions = useCallback(async (filters: SessionFilters = {}) => {
    setLoading(true)
    let query = supabase
      .from('watch_sessions')
      .select('*')
      .neq('status', 'active')
      .order('started_at', { ascending: false })
      .limit(100)

    if (filters.repo) query = query.eq('repo', filters.repo)

    if (filters.dateRange) {
      const cutoffs = { '24h': 1, '7d': 7, '30d': 30 }
      const days = cutoffs[filters.dateRange]
      const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString()
      query = query.gte('started_at', cutoff)
    }

    const { data } = await query
    if (data) setCompletedSessions(data as WatchSession[])
    setLoading(false)
  }, [])

  useEffect(() => {
    Promise.all([fetchActiveSessions(), fetchCompletedSessions()]).finally(() =>
      setLoading(false)
    )
  }, [fetchActiveSessions, fetchCompletedSessions])

  return {
    activeSessions,
    setActiveSessions,
    completedSessions,
    loading,
    fetchActiveSessions,
    fetchCompletedSessions,
  }
}

export async function fetchSessionEvents(sessionId: string): Promise<WatchEvent[]> {
  const { data } = await supabase
    .from('watch_events')
    .select('*')
    .eq('session_id', sessionId)
    .order('ts', { ascending: true })
    .limit(500)
  return (data as WatchEvent[]) ?? []
}

export async function fetchDistinctRepos(): Promise<string[]> {
  const { data } = await supabase
    .from('watch_sessions')
    .select('repo')
    .order('repo')
  if (!data) return []
  const repos = [...new Set(data.map((d: { repo: string }) => d.repo))]
  return repos
}
