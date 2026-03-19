import { useState } from 'react'
import { ChevronDown, ChevronRight, ExternalLink, FileText } from 'lucide-react'
import { WatchHealth } from '../../lib/supabase'

interface LogicFileTreeProps {
  files: WatchHealth[]
  repo: string
}

const CATEGORY_LABELS: Record<string, string> = {
  prompt: 'Prompts',
  rules: 'Rules',
  config: 'Config',
  docs: 'Docs',
  state: 'State',
}

const IMPORTANCE_BADGES: Record<string, { label: string; color: string; bg: string }> = {
  critical: { label: '● Critical', color: '#EF4444', bg: 'rgba(239,68,68,0.1)' },
  high: { label: '● High', color: '#F59E0B', bg: 'rgba(245,158,11,0.1)' },
  normal: { label: '○ Normal', color: '#94A3B8', bg: 'rgba(148,163,184,0.1)' },
}

const GITHUB_BASE = 'https://github.com/breverdbidder'

interface FileNodeProps {
  file: WatchHealth
  repo: string
}

function FileNode({ file, repo }: FileNodeProps) {
  const [expanded, setExpanded] = useState(false)
  const badge = IMPORTANCE_BADGES[file.importance]
  const githubUrl = `${GITHUB_BASE}/${repo}/blob/main/${file.file_path}`

  return (
    <div>
      <div
        className="flex items-center gap-2 py-1.5 px-2 rounded-lg cursor-pointer hover:opacity-80 transition-opacity"
        onClick={() => file.content_preview && setExpanded(e => !e)}
      >
        <FileText size={13} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
        <span
          className="text-xs font-mono flex-1 truncate"
          style={{ color: 'var(--color-text)' }}
          title={file.file_path}
        >
          {file.file_path}
        </span>
        <span
          className="text-xs px-1.5 py-0.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: badge.bg, color: badge.color }}
        >
          {badge.label}
        </span>
        {file.line_count && (
          <span className="text-xs flex-shrink-0" style={{ color: 'rgba(148,163,184,0.5)' }}>
            {file.line_count}L
          </span>
        )}
        <a
          href={githubUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={e => e.stopPropagation()}
          className="flex-shrink-0 hover:opacity-80"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <ExternalLink size={12} />
        </a>
      </div>
      {expanded && file.content_preview && (
        <div className="ml-6 mt-1 mb-2">
          <pre
            className="text-xs p-3 rounded-lg overflow-auto"
            style={{
              backgroundColor: 'rgba(2,6,23,0.8)',
              color: 'var(--color-text-muted)',
              maxHeight: '200px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {file.content_preview}
          </pre>
        </div>
      )}
    </div>
  )
}

interface CategorySectionProps {
  category: string
  files: WatchHealth[]
  repo: string
}

function CategorySection({ category, files, repo }: CategorySectionProps) {
  const [open, setOpen] = useState(true)
  const label = CATEGORY_LABELS[category] ?? category

  return (
    <div className="mb-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 w-full py-1.5 px-2 rounded-lg hover:opacity-80 transition-opacity"
        style={{ backgroundColor: 'rgba(30,58,95,0.2)' }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
          {label}
        </span>
        <span
          className="text-xs ml-auto"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {files.length}
        </span>
      </button>
      {open && (
        <div className="ml-2 mt-1">
          {files.map(f => (
            <FileNode key={f.id} file={f} repo={repo} />
          ))}
        </div>
      )}
    </div>
  )
}

export function LogicFileTree({ files, repo }: LogicFileTreeProps) {
  if (files.length === 0) {
    return (
      <div className="py-8 text-center" style={{ color: 'var(--color-text-muted)' }}>
        <p className="text-sm">No health data yet.</p>
        <p className="text-xs mt-1">Run the nightly health scan to populate this view.</p>
      </div>
    )
  }

  const categories = ['prompt', 'rules', 'config', 'docs', 'state']
  const byCategory: Record<string, WatchHealth[]> = {}
  for (const cat of categories) {
    byCategory[cat] = files.filter(f => f.category === cat)
  }

  return (
    <div>
      {categories
        .filter(cat => byCategory[cat].length > 0)
        .map(cat => (
          <CategorySection
            key={cat}
            category={cat}
            files={byCategory[cat]}
            repo={repo === 'All' ? files[0]?.repo ?? '' : repo}
          />
        ))}
    </div>
  )
}
