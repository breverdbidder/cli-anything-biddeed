-- FLEET Gemini second-lane pilot: evidence table for gemini-runner.yml executions.
-- Populated by gemini-runner.yml on every run so the DoD gate
-- (SELECT count(*) >= 1 FROM fleet_lane_pilot WHERE lane='gemini' AND status='success')
-- can be checked without reading GHA logs.

CREATE TABLE IF NOT EXISTS public.fleet_lane_pilot (
  id           BIGSERIAL PRIMARY KEY,
  run_id       TEXT NOT NULL,
  task         TEXT NOT NULL,
  lane         TEXT NOT NULL CHECK (lane IN ('claude','gemini')),
  status       TEXT NOT NULL CHECK (status IN ('success','failure')),
  tokens_note  TEXT,
  completed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fleet_lane_pilot_lane_status ON public.fleet_lane_pilot(lane, status);
CREATE INDEX IF NOT EXISTS idx_fleet_lane_pilot_run_id ON public.fleet_lane_pilot(run_id);

GRANT INSERT, SELECT ON public.fleet_lane_pilot TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.fleet_lane_pilot_id_seq TO service_role;
