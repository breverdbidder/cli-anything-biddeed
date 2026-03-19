import { formatDistanceToNow } from 'date-fns'
import { WatchHealth } from '../../lib/supabase'

interface HealthScoreCardProps {
  repo: string
  files: WatchHealth[]
}

export function HealthScoreCard({ repo, files }: HealthScoreCardProps) {
  if (files.length === 0) return null

  const critical = files.filter(f => f.importance === 'critical').length
  const high = files.filter(f => f.importance === 'high').length
  const lastScan = files.reduce((latest, f) => {
    return f.scanned_at > latest ? f.scanned_at : latest
  }, files[0].scanned_at)

  const hoursAgo = (Date.now() - new Date(lastScan).getTime()) / 3600000
  const scanColor = hoursAgo < 24 ? '#22C55E' : hoursAgo < 72 ? '#F59E0B' : '#EF4444'

  return (
    <div
      className="rounded-xl border p-4"
      style={{
        backgroundColor: 'var(--color-surface)',
        borderColor: 'rgba(30,58,95,0.4)',
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{repo}</h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
            Last scan: {formatDistanceToNow(new Date(lastScan), { addSuffix: true })}
          </p>
        </div>
        <div
          className="w-2 h-2 rounded-full mt-1"
          style={{ backgroundColor: scanColor }}
        />
      </div>
      <div className="flex gap-4">
        <div>
          <p className="text-xl font-bold" style={{ color: 'var(--color-text)' }}>{files.length}</p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>logic files</p>
        </div>
        {critical > 0 && (
          <div>
            <p className="text-xl font-bold" style={{ color: '#EF4444' }}>{critical}</p>
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>critical</p>
          </div>
        )}
        {high > 0 && (
          <div>
            <p className="text-xl font-bold" style={{ color: '#F59E0B' }}>{high}</p>
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>high</p>
          </div>
        )}
      </div>
    </div>
  )
}
