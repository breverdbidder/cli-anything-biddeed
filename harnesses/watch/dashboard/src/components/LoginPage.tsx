import { useState } from 'react'
import { Eye, Send, CheckCircle } from 'lucide-react'

interface LoginPageProps {
  signIn: (email: string) => Promise<{ error: Error | null }>
}

export function LoginPage({ signIn }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return

    setLoading(true)
    setError(null)

    const { error } = await signIn(email.trim())

    if (error) {
      setError('Could not send magic link. Check your email address.')
      setLoading(false)
    } else {
      setSent(true)
      setLoading(false)
    }
  }

  return (
    <div
      style={{ backgroundColor: 'var(--color-bg)' }}
      className="min-h-screen flex items-center justify-center p-4"
    >
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{ backgroundColor: 'var(--color-primary)' }}>
            <Eye size={32} style={{ color: 'var(--color-accent)' }} />
          </div>
          <h1 className="text-3xl font-bold" style={{ color: 'var(--color-text)' }}>
            Claude Watch
          </h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Everest Edition — Claude Code Observability
          </p>
        </div>

        {/* Card */}
        <div
          className="rounded-2xl border p-8"
          style={{
            backgroundColor: 'var(--color-surface)',
            borderColor: 'rgba(30,58,95,0.6)',
          }}
        >
          {sent ? (
            <div className="text-center py-4">
              <CheckCircle size={48} className="mx-auto mb-4" style={{ color: 'var(--color-success)' }} />
              <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
                Check your email
              </h2>
              <p style={{ color: 'var(--color-text-muted)' }}>
                Magic link sent to <strong style={{ color: 'var(--color-text)' }}>{email}</strong>.
                Click it to sign in.
              </p>
              <button
                onClick={() => { setSent(false); setEmail('') }}
                className="mt-6 text-sm underline"
                style={{ color: 'var(--color-accent)' }}
              >
                Use a different email
              </button>
            </div>
          ) : (
            <>
              <h2 className="text-xl font-semibold mb-1" style={{ color: 'var(--color-text)' }}>
                Sign in
              </h2>
              <p className="text-sm mb-6" style={{ color: 'var(--color-text-muted)' }}>
                Enter your email to receive a magic link.
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label
                    htmlFor="email"
                    className="block text-sm font-medium mb-1.5"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="ariel@biddeed.ai"
                    required
                    className="w-full px-4 py-3 rounded-lg border text-sm outline-none transition-colors"
                    style={{
                      backgroundColor: 'var(--color-bg)',
                      borderColor: 'rgba(148,163,184,0.2)',
                      color: 'var(--color-text)',
                    }}
                    onFocus={e => (e.target.style.borderColor = 'var(--color-accent)')}
                    onBlur={e => (e.target.style.borderColor = 'rgba(148,163,184,0.2)')}
                  />
                </div>

                {error && (
                  <p className="text-sm" style={{ color: 'var(--color-danger)' }}>{error}</p>
                )}

                <button
                  type="submit"
                  disabled={loading || !email.trim()}
                  className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-medium text-sm transition-opacity disabled:opacity-50"
                  style={{
                    backgroundColor: 'var(--color-accent)',
                    color: '#020617',
                  }}
                >
                  {loading ? (
                    <span>Sending…</span>
                  ) : (
                    <>
                      <Send size={16} />
                      Send Magic Link
                    </>
                  )}
                </button>
              </form>
            </>
          )}
        </div>

        <p className="text-center mt-6 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          BidDeed.AI — Everest Capital USA
        </p>
      </div>
    </div>
  )
}
