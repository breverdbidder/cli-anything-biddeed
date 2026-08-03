-- Add Resend email alongside the existing GHA-dispatched Telegram alert in
-- check_secret_rotation_due(). Live function inspected via pg_get_functiondef before writing
-- this (CC_META_PROMPT §1.3) — it uses fire_workflow_dispatch() -> telegram-notify.yml, NOT a
-- direct vault.telegram_bot_token lookup like sweep_security_alerts(). That path is unchanged
-- here; this only adds an additional Resend call per due secret, same IF-guard style as the
-- sweep_security_alerts() email branch (20260803_alerts_email_security_sweep.sql).
--
-- NOT invoked live against the real registry as part of verifying this migration: 35 of 37
-- rows currently have last_rotated_at IS NULL (never tracked), so a real call would fire ~35
-- Telegram dispatches and ~35 emails in one burst — CC_META_PROMPT §3.1 dry-run-before-bulk-write.
-- Verified instead via an isolated one-off test exercising the identical net.http_post call
-- shape against a single synthetic row (see session report).

CREATE OR REPLACE FUNCTION public.check_secret_rotation_due()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  v_row RECORD;
  v_count integer := 0;
  v_dispatch jsonb;
  v_resend_key text;
  v_from_email text;
  v_to_email text;
  v_html text;
BEGIN
  SELECT decrypted_secret INTO v_resend_key FROM vault.decrypted_secrets WHERE name = 'resend_api_key';
  SELECT decrypted_secret INTO v_from_email FROM vault.decrypted_secrets WHERE name = 'alerts_from_email';
  SELECT decrypted_secret INTO v_to_email FROM vault.decrypted_secrets WHERE name = 'alerts_to_email';

  FOR v_row IN
    SELECT secret_name, service, rotation_method, last_rotated_at, next_due_at
    FROM public.secret_rotation_registry
    WHERE next_due_at < now() + INTERVAL '14 days'
       OR last_rotated_at IS NULL
    ORDER BY (last_rotated_at IS NULL) DESC, next_due_at NULLS FIRST
  LOOP
    v_count := v_count + 1;

    v_dispatch := public.fire_workflow_dispatch(
      'breverdbidder/cli-anything-biddeed',
      'telegram-notify.yml',
      'main',
      jsonb_build_object('message',
        '🔑 *Secret Rotation Due* — `' || v_row.secret_name || '` (' || v_row.service || ') ' ||
        CASE WHEN v_row.last_rotated_at IS NULL
          THEN 'has never been tracked as rotated'
          ELSE 'last rotated ' || (extract(day FROM now() - v_row.last_rotated_at))::text || ' days ago'
        END ||
        '. Due: ' || COALESCE(v_row.next_due_at::text, 'unknown') ||
        '. Method: ' || v_row.rotation_method
      )
    );

    INSERT INTO public.agent_ops_log (dispatch_id, task, status, evidence, severity)
    VALUES (
      'secret-rotation-check',
      'blast-radius-reduction-2026-08-03',
      'VERIFIED',
      'Alert fired for ' || v_row.secret_name || ': ' || v_dispatch::text,
      'warn'
    );

    IF v_resend_key IS NOT NULL AND v_to_email IS NOT NULL THEN
      v_html := format(
        '<h2 style="color:#d97706;">Secret Rotation Due — %s</h2>
        <table style="font-family:sans-serif;font-size:14px;">
          <tr><td><b>Secret:</b></td><td>%s</td></tr>
          <tr><td><b>Service:</b></td><td>%s</td></tr>
          <tr><td><b>Status:</b></td><td>%s</td></tr>
          <tr><td><b>Due:</b></td><td>%s</td></tr>
          <tr><td><b>Rotation method:</b></td><td>%s</td></tr>
        </table>
        <hr/><p style="color:#666;font-size:12px;">BidDeed.AI Secret Rotation Monitor — alerts@biddeed.ai</p>',
        v_row.secret_name,
        v_row.secret_name,
        v_row.service,
        CASE WHEN v_row.last_rotated_at IS NULL
          THEN 'never tracked as rotated'
          ELSE 'last rotated ' || (extract(day FROM now() - v_row.last_rotated_at))::text || ' days ago'
        END,
        COALESCE(v_row.next_due_at::text, 'unknown'),
        v_row.rotation_method
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
          'subject', format('🔑 Secret Rotation Due: %s', v_row.secret_name),
          'html', v_html
        )
      );
    END IF;
  END LOOP;

  RETURN jsonb_build_object('checked_at', now(), 'alerts_fired', v_count);
END;
$function$;
