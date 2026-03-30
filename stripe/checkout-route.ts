// Stripe checkout session route
// Deployed to: app/api/stripe/checkout/route.ts in zonewise-web
// Issue: breverdbidder/cli-anything-biddeed#93

import { NextRequest, NextResponse } from 'next/server';
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: '2024-06-20',
});

const BASE_URL = process.env.NEXT_PUBLIC_URL ?? 'https://zonewise.ai';

export async function POST(req: NextRequest) {
  const { sessionId } = await req.json().catch(() => ({}));

  if (!sessionId) {
    return NextResponse.json({ error: 'sessionId required' }, { status: 400 });
  }

  const checkoutSession = await stripe.checkout.sessions.create({
    payment_method_types: ['card'],
    line_items: [
      {
        price_data: {
          currency: 'usd',
          product_data: {
            name: 'ZoneWise Pro',
            description: 'Unlimited property lookups — cancel anytime',
            images: [`${BASE_URL}/logo.png`],
          },
          unit_amount: 1500, // $15.00
          recurring: { interval: 'month' },
        },
        quantity: 1,
      },
    ],
    mode: 'subscription',
    success_url: `${BASE_URL}/chat?success=1&sid={CHECKOUT_SESSION_ID}`,
    cancel_url: `${BASE_URL}/chat`,
    metadata: { zonewise_session_id: sessionId },
    allow_promotion_codes: true,
  });

  return NextResponse.json({ url: checkoutSession.url });
}
