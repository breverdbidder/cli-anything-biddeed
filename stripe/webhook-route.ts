// Stripe webhook handler
// Deployed to: app/api/stripe/webhook/route.ts in zonewise-web
// Issue: breverdbidder/cli-anything-biddeed#93
// IMPORTANT: Add to next.config.js: api: { bodyParser: false } is NOT needed for App Router —
// raw body is accessed via req.text() below.

import { NextRequest, NextResponse } from 'next/server';
import Stripe from 'stripe';
import { activateProSession } from '@/lib/stripe/paywall';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: '2024-06-20',
});

export async function POST(req: NextRequest) {
  const body = await req.text();
  const sig = req.headers.get('stripe-signature');

  if (!sig) {
    return NextResponse.json({ error: 'Missing stripe-signature' }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!);
  } catch (err) {
    console.error('[stripe/webhook] signature verification failed:', err);
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 });
  }

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.CheckoutSession;
      const zonewiseSessionId = session.metadata?.zonewise_session_id;

      if (zonewiseSessionId && session.subscription) {
        await activateProSession(
          zonewiseSessionId,
          session.customer as string,
          session.subscription as string
        );
        console.log(`[stripe/webhook] Pro activated for session ${zonewiseSessionId}`);
      }
      break;
    }

    case 'customer.subscription.deleted': {
      // Optionally revoke pro access on cancellation
      // For now, keep pro status — handle churn separately
      break;
    }

    default:
      console.log(`[stripe/webhook] Unhandled event type: ${event.type}`);
  }

  return NextResponse.json({ received: true });
}
