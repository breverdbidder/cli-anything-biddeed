import { useState, useCallback } from 'react'
import { useAuth } from './hooks/useAuth'
import { useSessions } from './hooks/useSessions'
import { useRealtime } from './hooks/useRealtime'
import { LoginPage } from './components/LoginPage'
import { Layout, TabId } from './components/Layout'
import { LiveTab } from './components/live/LiveTab'
import { AuditTab } from './components/audit/AuditTab'
import { HealthTab } from './components/health/HealthTab'

export default function App() {
  const { session, user, loading, signIn, signOut } = useAuth()
  const [activeTab, setActiveTab] = useState<TabId>('live')

  const {
    activeSessions,
    setActiveSessions,
    completedSessions,
    loading: sessionsLoading,
    fetchCompletedSessions,
  } = useSessions()

  const { sessionEvents, allLiveEvents } = useRealtime(
    activeSessions,
    setActiveSessions,
    null
  )

  const handleFilterChange = useCallback(
    (filters: { repo: string; dateRange: '24h' | '7d' | '30d' }) => {
      fetchCompletedSessions({
        repo: filters.repo || undefined,
        dateRange: filters.dateRange,
      })
    },
    [fetchCompletedSessions]
  )

  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ backgroundColor: 'var(--color-bg)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-6 h-6 rounded-full border-2 border-t-transparent animate-spin"
            style={{ borderColor: 'var(--color-accent)', borderTopColor: 'transparent' }}
          />
          <span style={{ color: 'var(--color-text-muted)' }}>Loading…</span>
        </div>
      </div>
    )
  }

  if (!session) {
    return <LoginPage signIn={signIn} />
  }

  return (
    <Layout
      activeTab={activeTab}
      onTabChange={setActiveTab}
      userEmail={user?.email}
      onSignOut={signOut}
    >
      {activeTab === 'live' && (
        <LiveTab
          activeSessions={activeSessions}
          liveEvents={allLiveEvents}
        />
      )}
      {activeTab === 'audit' && (
        <AuditTab
          sessions={completedSessions}
          loading={sessionsLoading}
          onFilterChange={handleFilterChange}
        />
      )}
      {activeTab === 'health' && <HealthTab />}
    </Layout>
  )
}
