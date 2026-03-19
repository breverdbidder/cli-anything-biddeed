interface DiffViewerProps {
  diff: string | null
  oldString?: string | null
  newString?: string | null
}

export function DiffViewer({ diff, oldString, newString }: DiffViewerProps) {
  if (!diff && !oldString && !newString) return null

  // Parse diff string or build from old/new
  if (diff) {
    const lines = diff.split('\n')
    return (
      <div
        className="rounded-lg overflow-auto text-xs font-mono"
        style={{ backgroundColor: 'rgba(2,6,23,0.8)', maxHeight: '300px' }}
      >
        <div className="p-3 space-y-0.5">
          {lines.map((line, i) => {
            let bg = 'transparent'
            let color = 'var(--color-text-muted)'
            if (line.startsWith('+') && !line.startsWith('+++')) {
              bg = 'rgba(34,197,94,0.1)'
              color = '#4ADE80'
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              bg = 'rgba(239,68,68,0.1)'
              color = '#F87171'
            } else if (line.startsWith('@@')) {
              color = '#60A5FA'
            }
            return (
              <div
                key={i}
                className="px-2 rounded whitespace-pre-wrap break-all leading-5"
                style={{ backgroundColor: bg, color }}
              >
                {line || ' '}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // Simple old/new view
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {oldString && (
        <div>
          <p className="text-xs mb-1" style={{ color: '#F87171' }}>Removed</p>
          <pre
            className="text-xs p-3 rounded-lg overflow-auto"
            style={{
              backgroundColor: 'rgba(239,68,68,0.08)',
              color: '#F87171',
              maxHeight: '200px',
            }}
          >
            {oldString}
          </pre>
        </div>
      )}
      {newString && (
        <div>
          <p className="text-xs mb-1" style={{ color: '#4ADE80' }}>Added</p>
          <pre
            className="text-xs p-3 rounded-lg overflow-auto"
            style={{
              backgroundColor: 'rgba(34,197,94,0.08)',
              color: '#4ADE80',
              maxHeight: '200px',
            }}
          >
            {newString}
          </pre>
        </div>
      )}
    </div>
  )
}
