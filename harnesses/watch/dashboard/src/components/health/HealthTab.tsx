import { useState, useEffect } from 'react'
import { supabase, WatchHealth } from '../../lib/supabase'
import { RepoSelector } from './RepoSelector'
import { LogicFileTree } from './LogicFileTree'
import { ChangeTimeline } from './ChangeTimeline'
import { HealthScoreCard } from './HealthScoreCard'

const REPOS = ['biddeed-ai', 'biddeed-ai-ui', 'cli-anything-biddeed', 'zonewise-scraper-v4', 'zonewise-web']

export function HealthTab() {
  const [selectedRepo, setSelectedRepo] = useState('All')
  const [files, setFiles] = useState<WatchHealth[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadHealth = async () => {
      setLoading(true)

      // Fetch latest scan per file (using distinct on repo+file_path)
      let query = supabase
        .from('watch_health')
        .select('*')
        .eq('scan_type', 'nightly')
        .order('scanned_at', { ascending: false })
        .limit(2000)

      if (selectedRepo !== 'All') {
        query = query.eq('repo', selectedRepo)
      }

      const { data } = await query

      if (data) {
        // Deduplicate: keep latest per repo+file_path
        const seen = new Set<string>()
        const deduped = (data as WatchHealth[]).filter(f => {
          const key = `${f.repo}::${f.file_path}`
          if (seen.has(key)) return false
          seen.add(key)
          return true
        })
        setFiles(deduped)
      }
      setLoading(false)
    }

    loadHealth()
  }, [selectedRepo])

  const displayedFiles = selectedRepo === 'All'
    ? files
    : files.filter(f => f.repo === selectedRepo)

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          CLAUDE.md Ecosystem Health
        </h2>
        <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          {files.length} logic files
        </span>
      </div>

      <RepoSelector selected={selectedRepo} onChange={setSelectedRepo} />

      {loading ? (
        <div className="py-8 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Loading health data…
        </div>
      ) : (
        <>
          {/* Score cards — per repo if All selected */}
          {selectedRepo === 'All' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {REPOS.map(repo => {
                const repoFiles = files.filter(f => f.repo === repo)
                return repoFiles.length > 0 ? (
                  <HealthScoreCard key={repo} repo={repo} files={repoFiles} />
                ) : null
              })}
            </div>
          )}

          {/* Change timeline */}
          <ChangeTimeline files={displayedFiles} />

          {/* Logic file tree */}
          <div
            className="rounded-xl border p-4"
            style={{
              backgroundColor: 'var(--color-surface)',
              borderColor: 'rgba(30,58,95,0.4)',
            }}
          >
            <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text)' }}>
              Logic Files
              {selectedRepo !== 'All' && ` — ${selectedRepo}`}
            </h3>
            {selectedRepo === 'All' ? (
              REPOS.map(repo => {
                const repoFiles = displayedFiles.filter(f => f.repo === repo)
                if (repoFiles.length === 0) return null
                return (
                  <div key={repo} className="mb-4">
                    <h4
                      className="text-xs font-bold mb-2 px-2 py-1 rounded"
                      style={{
                        color: 'var(--color-accent)',
                        backgroundColor: 'rgba(30,58,95,0.3)',
                      }}
                    >
                      {repo}
                    </h4>
                    <LogicFileTree files={repoFiles} repo={repo} />
                  </div>
                )
              })
            ) : (
              <LogicFileTree files={displayedFiles} repo={selectedRepo} />
            )}
          </div>
        </>
      )}
    </div>
  )
}
