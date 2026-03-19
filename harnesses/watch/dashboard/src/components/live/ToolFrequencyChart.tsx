import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

interface ToolFrequencyChartProps {
  breakdown: Record<string, number>
}

const TOOL_COLORS: Record<string, string> = {
  Write: '#22C55E',
  Edit: '#3B82F6',
  Bash: '#F59E0B',
  Read: '#94A3B8',
  TodoWrite: '#A855F7',
  TodoRead: '#A855F7',
  Glob: '#EC4899',
  Grep: '#EC4899',
  WebFetch: '#06B6D4',
}

export function ToolFrequencyChart({ breakdown }: ToolFrequencyChartProps) {
  const data = Object.entries(breakdown)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, count]) => ({ name, count }))

  if (data.length === 0) return null

  return (
    <div
      className="rounded-xl border p-4"
      style={{
        backgroundColor: 'var(--color-surface)',
        borderColor: 'rgba(30,58,95,0.4)',
      }}
    >
      <p className="text-xs font-medium mb-3" style={{ color: 'var(--color-text-muted)' }}>
        Tool Usage
      </p>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={60}
            tick={{ fontSize: 11, fill: '#94A3B8' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0F172A',
              border: '1px solid rgba(30,58,95,0.6)',
              borderRadius: '8px',
              fontSize: '12px',
              color: '#E2E8F0',
            }}
            cursor={{ fill: 'rgba(30,58,95,0.3)' }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={TOOL_COLORS[entry.name] ?? '#334155'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
