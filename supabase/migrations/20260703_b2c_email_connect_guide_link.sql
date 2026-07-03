-- SPRINT4 D1: link the Connect-in-Claude custom-connector guide from the
-- B2C activation email.
-- dispatch_id: 34fcdc82-77b1-467c-aa74-2cef23ddb3bf
--
-- The 'en' row in b2c_email_templates (added by 20260702_b2c_outbox_drain.sql)
-- is the only non-stub locale; b2c_render_email_template() falls back to it
-- for he/ru/fr/zh, so updating 'en' alone reaches every locale currently
-- issuing activation emails. Guide lives at
-- https://breverdbidder.github.io/everest-battle-cards/biddeed-mcp/start/connect/
-- (verified live, HTTP 200 + content check, 2026-07-03).
--
-- Idempotent: the WHERE clause skips rows that already contain the link, so
-- re-running this file is a no-op on a second pass.

UPDATE public.b2c_email_templates
SET body_template = replace(
      body_template,
      'Full install steps: biddeed.ai/mcp/install',
      'Full install steps: biddeed.ai/mcp/install

Prefer Claude.ai over a config file? Add BidDeed as a custom connector in under 3 minutes:
https://breverdbidder.github.io/everest-battle-cards/biddeed-mcp/start/connect/'
    ),
    updated_at = now()
WHERE locale = 'en'
  AND body_template NOT LIKE '%everest-battle-cards/biddeed-mcp/start/connect%';
