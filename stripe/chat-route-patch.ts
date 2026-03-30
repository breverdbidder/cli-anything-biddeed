// Patch for: app/api/explorer/chat/route.ts in zonewise-web
// Issue: breverdbidder/cli-anything-biddeed#93
//
// Add these lines to the existing chat route:
// 1. Import checkAndIncrementLookup from '@/lib/stripe/paywall'
// 2. Read X-Session-Id header from the request
// 3. Before calling the LLM, run the paywall check
// 4. Return { paywall: true, checkoutUrl: '/api/stripe/checkout' } if blocked
//
// --- DIFF (apply to existing route.ts) ---
//
// + import { checkAndIncrementLookup } from '@/lib/stripe/paywall';
//
//   export async function POST(req: NextRequest) {
//     const body = await req.json();
// +   const sessionId = req.headers.get('x-session-id') ?? 'anonymous';
// +
// +   const paywall = await checkAndIncrementLookup(sessionId);
// +   if (!paywall.allowed) {
// +     return NextResponse.json(
// +       { paywall: true, checkoutUrl: '/api/stripe/checkout' },
// +       { status: 402 }
// +     );
// +   }
//
//     // ... existing LLM call ...
//   }
//
// Client-side (chat component) — add this after receiving the response:
//
//   const data = await res.json();
//   if (data.paywall) {
//     setShowPaywall(true);   // triggers <PaywallModal sessionId={sessionId} onClose={() => setShowPaywall(false)} />
//     return;
//   }

// This file is documentation/reference only — the actual patch is applied
// by the summit-stripe-paywall.yml workflow via heredoc on Hetzner.
export {};
