import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { format, subDays, differenceInDays } from 'date-fns'
import { WatchHealth } from '../../lib/supabase'

interface ChangeTimelineProps {
  files: WatchHealth[]
}

const REPOS = [
  'biddeed-ai',
  'biddeed-ai-ui',
  'cli-anything-biddeed',
  'zonewise-scraper-v4',
  'zonewise-web',
]

const IMPORTANCE_COLORS: Record<string, string> = {
  critical: '#EF4444',
  high: '#F59E0B',
  normal: '#60A5FA',
}

interface DataPoint {
  x: number
  y: number
  importance: string
  file_path: string
  repo: string
  scanned_at: string
}

interface TooltipProps {
  active?: boolean
  payload?: Array<{ payload: DataPoint }>
}

function CustomTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div
      className="text-xs p-2 rounded-lg border"
      style={{
        backgroundColor: '#0F172A',
        borderColor: 'rgba(30,58,95,0.6)',
        color: '#E2E8F0',
      }}
    >
      <p className="font-medium">{d.file_path}</p>
      <p style={{ color: 'var(--color-text-muted)' }}>
        {format(new Date(d.scanned_at), 'MMM d, HH:mm')}
      </p>
      <p style={{ color: IMPORTANCE_COLORS[d.importance] }}>{d.importance}</p>
    </div>
  )
}

export function ChangeTimeline({ files }: ChangeTimelineProps) {
  const now = Date.now()
  const cutoff = subDays(now, 90)

  const data: DataPoint[] = files
    .filter(f => new Date(f.scanned_at) >= cutoff)
    .map(f => ({
      x: differenceInDays(new Date(f.scanned_at), cutoff),
      y: REPOS.indexOf(f.repo),
      importance: f.importance,
      file_path: f.file_path,
      repo: f.repo,
      scanned_at: f.scanned_at,
    }))
    .filter(d => d.y >= 0)

  if (data.length === 0) {
    return (
      <div className="py-6 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
        No change data in the last 90 days.
      </div>
    )
  }

  return (
    <div
      className="rounded-xl border p-4"
      style={{
        backgroundColor: 'var(--color-surface)',
        borderColor: 'rgba(30,58,95,0.4)',
      }}
    >
      <p className="text-xs font-medium mb-3" style={{ color: 'var(--color-text-muted)' }}>
        Logic File Changes — Last 90 Days
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <XAxis
            type="number"
            dataKey="x"
            domain={[0, 90]}
            tick={{ fontSize: 10, fill: '#94A3B8' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => format(subDays(now, 90 - v), 'MMM d')}
            ticks={[0, 15, 30, 45, 60, 75, 90]}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[-0.5, REPOS.length - 0.5]}
            tick={{ fontSize: 10, fill: '#94A3B8' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => REPOS[Math.round(v)]?.split('-')[0] ?? ''}
            ticks={REPOS.map((_, i) => i)}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(30,58,95,0.3)' }} />
          <Scatter data={data}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={IMPORTANCE_COLORS[entry.importance] ?? '#60A5FA'}
                opacity={0.8}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      {/* Legend */}
      <div className="flex gap-4 justify-end mt-1">
        {Object.entries(IMPORTANCE_COLORS).map(([level, color]) => (
          <div key={level} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{level}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
