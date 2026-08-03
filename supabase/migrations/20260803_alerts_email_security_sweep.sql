-- Add Resend email alongside existing Telegram send in sweep_security_alerts().
-- Live function inspected via pg_get_functiondef before writing this (CC_META_PROMPT §1.3) —
-- current committed migration history has no CREATE for this function (it was applied directly
-- to the live DB in an earlier session and never landed in a migration file); this file both
-- documents and extends the live definition so `main` stops drifting from prod.
--
-- Email branch mirrors the existing Telegram IF-guard exactly: skip silently (not error) if
-- resend_api_key / alerts_to_email aren't present, same as the pre-existing Telegram guard.
-- Additive only — Telegram behavior, event selection (p0/p1, 15min window, LIMIT 10), and
-- alerted_at bookkeeping are unchanged from the live function.

CREATE OR REPLACE FUNCTION public.sweep_security_alerts()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $function$
DECLARE
  v_event record;
  v_token text;
  v_chat_id text;
  v_resend_key text;
  v_from_email text;
  v_to_email text;
  v_msg text;
  v_html text;
BEGIN
  SELECT decrypted_secret INTO v_token FROM vault.decrypted_secrets WHERE name = 'telegram_bot_token';
  SELECT decrypted_secret INTO v_chat_id FROM vault.decrypted_secrets WHERE name = 'telegram_chat_id';
  SELECT decrypted_secret INTO v_resend_key FROM vault.decrypted_secrets WHERE name = 'resend_api_key';
  SELECT decrypted_secret INTO v_from_email FROM vault.decrypted_secrets WHERE name = 'alerts_from_email';
  SELECT decrypted_secret INTO v_to_email FROM vault.decrypted_secrets WHERE name = 'alerts_to_email';

  IF v_token IS NULL OR v_chat_id IS NULL THEN
    RAISE WARNING 'sweep_security_alerts: vault missing telegram_bot_token or telegram_chat_id — Telegram leg skipped';
  END IF;

  FOR v_event IN
    SELECT * FROM public.security_events
    WHERE severity IN ('p0','p1')
    AND created_at > NOW() - INTERVAL '15 minutes'
    AND (alerted_at IS NULL)
    ORDER BY created_at DESC
    LIMIT 10
  LOOP
    v_msg := format(E'🚨 *BidDeed Security Alert*\n*Severity:* %s\n*Type:* %s\n*Platform:* %s\n*Path:* %s\n*Action:* %s\n*Time:* %s UTC',
      upper(v_event.severity), v_event.event_type,
      coalesce(v_event.platform,'unknown'),
      coalesce(v_event.request_path,'n/a'),
      coalesce(v_event.auto_action_taken, 'none'),
      to_char(v_event.created_at, 'YYYY-MM-DD HH24:MI:SS')
    );

    IF v_token IS NOT NULL AND v_chat_id IS NOT NULL THEN
      PERFORM net.http_post(
        url := format('https://api.telegram.org/bot%s/sendMessage', v_token),
        headers := '{"Content-Type":"application/json"}'::jsonb,
        body := jsonb_build_object('chat_id', v_chat_id, 'text', v_msg, 'parse_mode', 'Markdown')
      );
    END IF;

    IF v_resend_key IS NOT NULL AND v_to_email IS NOT NULL THEN
      v_html := format(
        '<h2 style="color:%s;">BidDeed Security Alert — %s</h2>
        <table style="font-family:sans-serif;font-size:14px;">
          <tr><td><b>Severity:</b></td><td>%s</td></tr>
          <tr><td><b>Event Type:</b></td><td>%s</td></tr>
          <tr><td><b>Platform:</b></td><td>%s</td></tr>
          <tr><td><b>Path:</b></td><td>%s</td></tr>
          <tr><td><b>Action Taken:</b></td><td>%s</td></tr>
          <tr><td><b>Time:</b></td><td>%s UTC</td></tr>
        </table>
        <hr/><p style="color:#666;font-size:12px;">BidDeed.AI Security Monitor — alerts@biddeed.ai</p>',
        CASE WHEN v_event.severity = 'p0' THEN '#dc2626' ELSE '#d97706' END,
        upper(v_event.severity),
        upper(v_event.severity),
        v_event.event_type,
        coalesce(v_event.platform,'unknown'),
        coalesce(v_event.request_path,'n/a'),
        coalesce(v_event.auto_action_taken,'none'),
        to_char(v_event.created_at, 'YYYY-MM-DD HH24:MI:SS')
      );

      PERFORM net.http_post(
        url := 'https://api.resend.com/emails',
        headers := jsonb_build_object(
          'Authorization', 'Bearer ' || v_resend_key,
          'Content-Type', 'application/json'
        ),
        body := jsonb_build_object(
          'from', coalesce(v_from_email, 'BidDeed.AI Alerts <alerts@biddeed.ai>'),
          'to', jsonb_build_array(v_to_email),
          'subject', format('🚨 %s Security Alert: %s', upper(v_event.severity), v_event.event_type),
          'html', v_html
        )
      );
    END IF;

    UPDATE public.security_events SET alerted_at = NOW() WHERE id = v_event.id;
  END LOOP;
END;
$function$;
