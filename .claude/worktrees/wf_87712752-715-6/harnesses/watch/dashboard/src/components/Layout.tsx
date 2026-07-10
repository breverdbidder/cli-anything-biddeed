import { Activity, ClipboardList, Brain, LogOut, Eye } from 'lucide-react'

export type TabId = 'live' | 'audit' | 'health'

interface LayoutProps {
  activeTab: TabId
  onTabChange: (tab: TabId) => void
  userEmail: string | undefined
  onSignOut: () => void
  children: React.ReactNode
}

const TABS = [
  { id: 'live' as TabId, label: 'Live', icon: Activity, dot: true },
  { id: 'audit' as TabId, label: 'Sessions', icon: ClipboardList, dot: false },
  { id: 'health' as TabId, label: 'Health', icon: Brain, dot: false },
]

export function Layout({ activeTab, onTabChange, userEmail, onSignOut, children }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: 'var(--color-bg)' }}>
      {/* Header */}
      <header
        className="sticky top-0 z-40 border-b flex items-center justify-between px-4 py-3"
        style={{
          backgroundColor: 'rgba(15,23,42,0.95)',
          borderColor: 'rgba(30,58,95,0.5)',
          backdropFilter: 'blur(8px)',
        }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: 'var(--color-primary)' }}
          >
            <Eye size={14} style={{ color: 'var(--color-accent)' }} />
          </div>
          <span className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>
            Claude Watch
          </span>
          <span
            className="hidden sm:inline text-xs px-2 py-0.5 rounded-full"
            style={{
              backgroundColor: 'rgba(30,58,95,0.5)',
              color: 'var(--color-text-muted)',
            }}
          >
            Everest Edition
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Desktop tab nav */}
          <nav className="hidden md:flex items-center gap-1">
            {TABS.map(tab => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => onTabChange(tab.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
                  style={{
                    backgroundColor: isActive ? 'rgba(30,58,95,0.6)' : 'transparent',
                    color: isActive ? 'var(--color-accent)' : 'var(--color-text-muted)',
                    borderBottom: isActive ? '2px solid var(--color-accent)' : '2px solid transparent',
                  }}
                >
                  <div className="relative">
                    <Icon size={15} />
                    {tab.dot && tab.id === 'live' && (
                      <span
                        className="pulse-dot absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full"
                        style={{ backgroundColor: 'var(--color-success)' }}
                      />
                    )}
                  </div>
                  {tab.label}
                </button>
              )
            })}
          </nav>

          {/* User + sign out */}
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {userEmail}
            </span>
            <button
              onClick={onSignOut}
              className="p-1.5 rounded-lg transition-colors hover:opacity-80"
              style={{ color: 'var(--color-text-muted)' }}
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>

      {/* Mobile bottom tab nav */}
      <nav
        className="md:hidden sticky bottom-0 z-40 border-t grid grid-cols-3"
        style={{
          backgroundColor: 'rgba(15,23,42,0.97)',
          borderColor: 'rgba(30,58,95,0.5)',
          backdropFilter: 'blur(8px)',
        }}
      >
        {TABS.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className="flex flex-col items-center gap-1 py-3 px-2 transition-colors"
              style={{
                color: isActive ? 'var(--color-accent)' : 'var(--color-text-muted)',
                borderTop: isActive ? '2px solid var(--color-accent)' : '2px solid transparent',
              }}
            >
              <div className="relative">
                <Icon size={20} />
                {tab.dot && tab.id === 'live' && (
                  <span
                    className="pulse-dot absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full"
                    style={{ backgroundColor: 'var(--color-success)' }}
                  />
                )}
              </div>
              <span className="text-xs font-medium">{tab.label}</span>
            </button>
          )
        })}
      </nav>
    </div>
  )
}
