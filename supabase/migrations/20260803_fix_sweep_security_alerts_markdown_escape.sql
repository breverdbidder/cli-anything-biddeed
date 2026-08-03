-- sweep_security_alerts() sent Telegram messages with parse_mode:'Markdown'
-- but interpolated raw event_type/platform values (e.g. 'canary_triggered',
-- 'auth_failure', 'rate_limit_hit') which contain unescaped underscores.
-- Telegram's legacy Markdown parser treats a lone '_' as an unterminated
-- italic entity and rejects the whole message with HTTP 400
-- ("can't parse entities"). Nearly every value allowed by
-- security_events_event_type_check contains an underscore, so this broke
-- every P0/P1 alert, not just the vault-empty case this migration's sibling
-- (20260803_telegram_vault_sync_whitelist.sql) fixed. Verified live: with
-- real vault creds in place, the Telegram call now authenticates (no longer
-- skipped) but 400s on this exact parse error. Fix: drop parse_mode and the
-- bold markers — plain text renders fine and needs no escaping regardless
-- of what characters future event_type/platform values contain.
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
    v_msg := format(E'\U0001F6A8 BidDeed Security Alert\nSeverity: %s\nType: %s\nPlatform: %s\nPath: %s\nAction: %s\nTime: %s UTC',
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
        body := jsonb_build_object('chat_id', v_chat_id, 'text', v_msg)
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
