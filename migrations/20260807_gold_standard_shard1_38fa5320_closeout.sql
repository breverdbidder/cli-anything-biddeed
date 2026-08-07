-- GOLD STANDARD SHARD-1 dispatch 38fa5320 — SESSION CLOSE-OUT
-- chat_session: architect-20260807T160000
-- Per MANDATORY SESSION CLOSE-OUT protocol in issue brief.

SET statement_timeout = 0;

UPDATE public.gold_standard_campaign
SET
    criteria_passed = '{
        "A": true,
        "B": true,
        "C": true,
        "D": true,
        "E": true,
        "F": true,
        "G": true,
        "H": true,
        "I": false,
        "J": true
    }'::jsonb,
    criteria_total  = 10,
    exit_reason     = 'certified_partial',
    session_end_at  = now()
WHERE dispatch_id = '38fa5320-cf86-4666-a42e-296022118f63';

-- Fallback: if dispatch_id lookup misses, try matching by the most recent processing dispatch
-- (per the close-out template in the brief):
UPDATE public.gold_standard_campaign
SET
    criteria_passed = '{
        "A": true, "B": true, "C": true, "D": true, "E": true,
        "F": true, "G": true, "H": true, "I": false, "J": true
    }'::jsonb,
    criteria_total  = 10,
    exit_reason     = 'certified_partial',
    session_end_at  = now()
WHERE dispatch_id = (
    SELECT id FROM public.summit_chat_dispatch
    WHERE state = 'processing'
    ORDER BY updated_at DESC
    LIMIT 1
)
AND NOT EXISTS (
    SELECT 1 FROM public.gold_standard_campaign
    WHERE dispatch_id = '38fa5320-cf86-4666-a42e-296022118f63'
      AND session_end_at IS NOT NULL
);
