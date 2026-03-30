// Paywall middleware — session-based lookup counter
// Deployed to: lib/stripe/paywall.ts in zonewise-web
// Issue: breverdbidder/cli-anything-biddeed#93

import { createClient } from '@supabase/supabase-js';

const FREE_LOOKUPS = 3;

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export interface PaywallResult {
  allowed: boolean;
  lookupCount: number;
  isPro: boolean;
  lookupsRemaining: number;
}

/**
 * Check if a session is allowed to make a lookup.
 * Increments the counter if allowed.
 * Returns { allowed: false } after 3 free lookups for non-pro sessions.
 */
export async function checkAndIncrementLookup(sessionId: string): Promise<PaywallResult> {
  // Fetch current session record
  const { data: existing } = await supabase
    .from('paywall_sessions')
    .select('lookup_count, is_pro')
    .eq('session_id', sessionId)
    .single();

  const isPro = existing?.is_pro ?? false;
  const currentCount = existing?.lookup_count ?? 0;

  // Pro users: always allowed, still track count
  if (isPro) {
    await supabase.from('paywall_sessions').upsert({
      session_id: sessionId,
      lookup_count: currentCount + 1,
      is_pro: true,
      last_lookup_at: new Date().toISOString(),
    }, { onConflict: 'session_id' });

    return { allowed: true, lookupCount: currentCount + 1, isPro: true, lookupsRemaining: Infinity };
  }

  // Free tier: block at FREE_LOOKUPS
  if (currentCount >= FREE_LOOKUPS) {
    return { allowed: false, lookupCount: currentCount, isPro: false, lookupsRemaining: 0 };
  }

  // Increment and allow
  const newCount = currentCount + 1;
  await supabase.from('paywall_sessions').upsert({
    session_id: sessionId,
    lookup_count: newCount,
    is_pro: false,
    last_lookup_at: new Date().toISOString(),
  }, { onConflict: 'session_id' });

  return {
    allowed: true,
    lookupCount: newCount,
    isPro: false,
    lookupsRemaining: FREE_LOOKUPS - newCount,
  };
}

/**
 * Mark a session as pro after successful Stripe payment.
 */
export async function activateProSession(
  sessionId: string,
  stripeCustomerId: string,
  stripeSubId: string
): Promise<void> {
  await supabase.from('paywall_sessions').upsert({
    session_id: sessionId,
    is_pro: true,
    stripe_customer_id: stripeCustomerId,
    stripe_sub_id: stripeSubId,
    pro_since: new Date().toISOString(),
  }, { onConflict: 'session_id' });
}
