// Paywall upgrade modal — shows after 3 free lookups
// Deployed to: components/PaywallModal.tsx in zonewise-web
// Issue: breverdbidder/cli-anything-biddeed#93

'use client';

import { useState } from 'react';

interface Props {
  onClose: () => void;
  sessionId: string;
}

export function PaywallModal({ onClose, sessionId }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpgrade() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/stripe/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        setError('Failed to start checkout. Please try again.');
        setLoading(false);
      }
    } catch {
      setError('Network error. Please try again.');
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#0f172a',
          border: '1px solid #1E3A5F',
          borderRadius: '12px',
          padding: '36px 40px',
          maxWidth: '420px',
          width: '90%',
          textAlign: 'center',
          fontFamily: 'Inter, sans-serif',
          color: '#f8fafc',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Icon */}
        <div style={{ fontSize: '40px', marginBottom: '12px' }}>🔒</div>

        {/* Heading */}
        <h2 style={{ margin: '0 0 8px', fontSize: '22px', fontWeight: 700, color: '#f8fafc' }}>
          You&apos;ve used your 3 free lookups
        </h2>

        {/* Sub-heading */}
        <p style={{ margin: '0 0 24px', color: '#94a3b8', fontSize: '15px', lineHeight: '1.5' }}>
          Upgrade to ZoneWise Pro for unlimited property lookups, zoning intelligence, and deal analysis.
        </p>

        {/* Pricing */}
        <div
          style={{
            background: '#1E3A5F',
            borderRadius: '8px',
            padding: '16px 20px',
            marginBottom: '24px',
          }}
        >
          <span style={{ fontSize: '32px', fontWeight: 800, color: '#F59E0B' }}>$15</span>
          <span style={{ color: '#94a3b8', fontSize: '15px' }}> / month</span>
          <p style={{ margin: '6px 0 0', color: '#cbd5e1', fontSize: '13px' }}>
            Unlimited lookups · Cancel anytime
          </p>
        </div>

        {/* Feature list */}
        <ul
          style={{
            listStyle: 'none',
            padding: 0,
            margin: '0 0 24px',
            textAlign: 'left',
            color: '#cbd5e1',
            fontSize: '14px',
          }}
        >
          {[
            'Unlimited property lookups',
            'Full zoning district details',
            'Permitted uses & setbacks',
            'Deal analysis (ARV × 70% formula)',
            'Brevard + Orange + Duval counties',
          ].map((feature) => (
            <li key={feature} style={{ marginBottom: '8px' }}>
              <span style={{ color: '#F59E0B', marginRight: '8px' }}>✓</span>
              {feature}
            </li>
          ))}
        </ul>

        {/* CTA */}
        <button
          onClick={handleUpgrade}
          disabled={loading}
          style={{
            width: '100%',
            padding: '14px 0',
            background: loading ? '#374151' : '#F59E0B',
            color: loading ? '#9ca3af' : '#0f172a',
            border: 'none',
            borderRadius: '8px',
            fontSize: '16px',
            fontWeight: 700,
            cursor: loading ? 'not-allowed' : 'pointer',
            marginBottom: '12px',
            transition: 'background 0.2s',
          }}
        >
          {loading ? 'Redirecting to Stripe…' : 'Upgrade to Pro — $15/mo'}
        </button>

        {error && (
          <p style={{ color: '#f87171', fontSize: '13px', marginBottom: '12px' }}>{error}</p>
        )}

        {/* Dismiss */}
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#64748b',
            cursor: 'pointer',
            fontSize: '13px',
          }}
        >
          Maybe later
        </button>
      </div>
    </div>
  );
}
