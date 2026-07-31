-- WEBSITE-FIX: /buy-report purchase flow (dispatch 93fc7abd)
--
-- The $25 one-time Shapira report purchase has no subscription/customer_id
-- to hang off stripe_checkout_sessions (customer_id there is a required FK
-- to mcp_customers, which one-time anonymous report buyers never have).
-- This is a separate, additive queue: biddeed-checkout inserts a 'pending'
-- row at Checkout Session creation, the stripe webhook flips it to
-- 'paid'/'delivered' once checkout.session.completed fires for
-- metadata.product='s5_onetime'.
CREATE TABLE IF NOT EXISTS public.report_delivery_queue (
  id                    uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  case_number           text NOT NULL,
  county                text NOT NULL,
  customer_email        text NOT NULL,
  stripe_session_id     text,
  stripe_payment_intent text,
  status                text NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'paid', 'delivered', 'failed')),
  report_pdf_url        text,
  error                 text,
  created_at            timestamptz DEFAULT now(),
  delivered_at          timestamptz
);

CREATE INDEX IF NOT EXISTS report_delivery_queue_payment_intent_idx
  ON public.report_delivery_queue (stripe_payment_intent);

CREATE INDEX IF NOT EXISTS report_delivery_queue_session_idx
  ON public.report_delivery_queue (stripe_session_id);

-- Service-role only (biddeed-checkout + stripe webhook): RLS enabled with
-- zero policies means anon/authenticated get nothing, service_role bypasses
-- RLS as usual -- same posture as the billing-sensitive tables it sits next to.
ALTER TABLE public.report_delivery_queue ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.report_delivery_queue IS
  'WEBSITE-FIX (dispatch 93fc7abd): one-time $25 Shapira report purchases -- queued at biddeed-checkout session creation, resolved by the stripe webhook on checkout.session.completed for metadata.product=s5_onetime.';
