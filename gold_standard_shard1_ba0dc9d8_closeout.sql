-- Mandatory session close-out for Gold Standard shard-1 (dispatch ba0dc9d8: gulf/jefferson/pinellas).
-- criteria_passed reflects FRESH pencil_dod_evaluate_county() output re-run at session close, not the
-- session's self-report. pinellas moved 7/10 -> 10/10 (verified). gulf/jefferson letters worked this
-- session (gulf-I, jefferson-B/F) are confirmed dead ends pending human/external action; gulf H flipped
-- pass->fail mid-session on the pre-existing 48h freshness SLA (scraper-cadence issue, out of this
-- session's scope, not caused by any write made here).

UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{
    "gulf":      {"A": true, "B": true, "C": true, "D": true, "E": true, "F": true, "G": true, "H": false, "I": false, "J": true},
    "jefferson": {"A": true, "B": false, "C": true, "D": true, "E": true, "F": false, "G": true, "H": true, "I": true, "J": true},
    "pinellas":  {"A": true, "B": true, "C": true, "D": true, "E": true, "F": true, "G": true, "H": true, "I": true, "J": true}
  }'::jsonb,
  criteria_total = 10,
  exit_reason = 'completed_workqueue',
  session_end_at = now()
WHERE dispatch_id = 'ba0dc9d8-ec70-402f-9b1f-a35dab864033';
