import { Search, Filter } from 'lucide-react'

interface FilterBarProps {
  repos: string[]
  selectedRepo: string
  onRepoChange: (repo: string) => void
  dateRange: '24h' | '7d' | '30d'
  onDateRangeChange: (range: '24h' | '7d' | '30d') => void
  search: string
  onSearchChange: (s: string) => void
}

const DATE_RANGES = [
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
] as const

const inputStyle = {
  backgroundColor: 'var(--color-surface)',
  borderColor: 'rgba(148,163,184,0.15)',
  color: 'var(--color-text)',
}

export function FilterBar({
  repos,
  selectedRepo,
  onRepoChange,
  dateRange,
  onDateRangeChange,
  search,
  onSearchChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Filter size={14} style={{ color: 'var(--color-text-muted)' }} />

      {/* Repo selector */}
      <select
        value={selectedRepo}
        onChange={e => onRepoChange(e.target.value)}
        className="text-sm px-3 py-1.5 rounded-lg border outline-none"
        style={inputStyle}
      >
        <option value="">All repos</option>
        {repos.map(r => (
          <option key={r} value={r}>{r}</option>
        ))}
      </select>

      {/* Date range */}
      <div className="flex rounded-lg border overflow-hidden" style={{ borderColor: 'rgba(148,163,184,0.15)' }}>
        {DATE_RANGES.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => onDateRangeChange(value)}
            className="px-3 py-1.5 text-sm transition-colors"
            style={{
              backgroundColor: dateRange === value ? 'var(--color-primary)' : 'var(--color-surface)',
              color: dateRange === value ? 'var(--color-accent)' : 'var(--color-text-muted)',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* File search */}
      <div className="flex items-center gap-2 flex-1 min-w-48">
        <Search size={14} style={{ color: 'var(--color-text-muted)' }} />
        <input
          type="text"
          placeholder="Search file path…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          className="flex-1 text-sm bg-transparent outline-none placeholder:opacity-50"
          style={{ color: 'var(--color-text)' }}
        />
      </div>
    </div>
  )
}
