-- Multi-window chat rate limiting (minute/hour/day/week) + LLM tier routing.
-- Extends the existing 15/minute-only chat_rate_check with hourly/daily/weekly
-- caps and a usage tier used by the Worker to pick free/standard/heavy LLM routing.

CREATE OR REPLACE FUNCTION public.chat_rate_check_v2(p_ip text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_minute_key text;
  v_hour_key text;
  v_day_key text;
  v_week_key text;
  v_minute_hits int;
  v_hour_hits int;
  v_day_hits int;
  v_week_hits int;
  -- Limits
  v_limit_minute int := 15;   -- 15/minute (existing)
  v_limit_hour int := 30;     -- 30/hour
  v_limit_day int := 100;     -- 100/day
  v_limit_week int := 300;    -- 300/week
BEGIN
  v_minute_key := p_ip || ':m:' || (floor(extract(epoch from now()) / 60))::bigint::text;
  v_hour_key   := p_ip || ':h:' || (floor(extract(epoch from now()) / 3600))::bigint::text;
  v_day_key    := p_ip || ':d:' || to_char(now(), 'YYYYMMDD');
  v_week_key   := p_ip || ':w:' || to_char(date_trunc('week', now()), 'YYYYMMDD');

  -- Upsert all four windows atomically
  INSERT INTO chat_rate_limit (ip_window, hits) VALUES (v_minute_key, 1)
    ON CONFLICT (ip_window) DO UPDATE SET hits = chat_rate_limit.hits + 1
    RETURNING chat_rate_limit.hits INTO v_minute_hits;
  INSERT INTO chat_rate_limit (ip_window, hits) VALUES (v_hour_key, 1)
    ON CONFLICT (ip_window) DO UPDATE SET hits = chat_rate_limit.hits + 1
    RETURNING chat_rate_limit.hits INTO v_hour_hits;
  INSERT INTO chat_rate_limit (ip_window, hits) VALUES (v_day_key, 1)
    ON CONFLICT (ip_window) DO UPDATE SET hits = chat_rate_limit.hits + 1
    RETURNING chat_rate_limit.hits INTO v_day_hits;
  INSERT INTO chat_rate_limit (ip_window, hits) VALUES (v_week_key, 1)
    ON CONFLICT (ip_window) DO UPDATE SET hits = chat_rate_limit.hits + 1
    RETURNING chat_rate_limit.hits INTO v_week_hits;

  RETURN jsonb_build_object(
    'allowed', (v_minute_hits <= v_limit_minute AND v_hour_hits <= v_limit_hour AND v_day_hits <= v_limit_day AND v_week_hits <= v_limit_week),
    'minute_hits', v_minute_hits, 'minute_limit', v_limit_minute,
    'hour_hits', v_hour_hits, 'hour_limit', v_limit_hour,
    'day_hits', v_day_hits, 'day_limit', v_limit_day,
    'week_hits', v_week_hits, 'week_limit', v_limit_week,
    'tier', CASE
      WHEN v_day_hits <= 10 THEN 'free'       -- 0-10/day: Gemini Flash
      WHEN v_day_hits <= 50 THEN 'standard'   -- 11-50/day: Haiku
      ELSE 'heavy'                             -- 50+/day: Haiku + warn
    END
  );
END;
$$;
GRANT EXECUTE ON FUNCTION public.chat_rate_check_v2(text) TO anon;

-- GC now handles all four window-key formats plus the legacy (no-type-prefix) keys
-- left over from chat_rate_check, each with a retention window sized to its bucket.
CREATE OR REPLACE FUNCTION public.chat_rate_gc() RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  DELETE FROM chat_rate_limit WHERE
    (ip_window LIKE '%:m:%' AND created_at < NOW() - INTERVAL '10 minutes') OR
    (ip_window LIKE '%:h:%' AND created_at < NOW() - INTERVAL '2 hours') OR
    (ip_window LIKE '%:d:%' AND created_at < NOW() - INTERVAL '25 hours') OR
    (ip_window LIKE '%:w:%' AND created_at < NOW() - INTERVAL '8 days') OR
    -- Legacy format (no window type prefix): delete after 10 minutes
    (ip_window NOT LIKE '%:m:%' AND ip_window NOT LIKE '%:h:%' AND
     ip_window NOT LIKE '%:d:%' AND ip_window NOT LIKE '%:w:%' AND
     created_at < NOW() - INTERVAL '10 minutes');
END;
$$;
