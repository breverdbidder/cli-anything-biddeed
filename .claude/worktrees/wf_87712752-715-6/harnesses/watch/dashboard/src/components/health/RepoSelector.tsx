const REPOS = [
  'All',
  'biddeed-ai',
  'biddeed-ai-ui',
  'cli-anything-biddeed',
  'zonewise-scraper-v4',
  'zonewise-web',
]

interface RepoSelectorProps {
  selected: string
  onChange: (repo: string) => void
}

export function RepoSelector({ selected, onChange }: RepoSelectorProps) {
  return (
    <div className="overflow-x-auto -mx-1">
      <div className="flex gap-1 pb-1 min-w-max px-1">
        {REPOS.map(repo => {
          const isActive = selected === repo
          return (
            <button
              key={repo}
              onClick={() => onChange(repo)}
              className="px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all"
              style={{
                backgroundColor: isActive ? 'var(--color-primary)' : 'var(--color-surface)',
                color: isActive ? 'var(--color-accent)' : 'var(--color-text-muted)',
                border: `1px solid ${isActive ? 'var(--color-primary)' : 'rgba(30,58,95,0.4)'}`,
              }}
            >
              {repo}
            </button>
          )
        })}
      </div>
    </div>
  )
}
