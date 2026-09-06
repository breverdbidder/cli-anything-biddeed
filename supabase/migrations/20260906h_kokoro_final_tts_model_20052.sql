-- GTM-6 (#20052) -- Ariel's binding decision (chat 2026-09-06, decision #1):
-- "Kokoro English audio is APPROVED as the launch-week voice. No ElevenLabs
-- spend." Work item B promotes 20 qa_pass=true kokoro EN draft variants to
-- is_draft=false/render_mode='final' while explicitly KEEPING
-- tts_model='kokoro' (never re-synthesized with ElevenLabs).
--
-- reel_variants_draft_tts_model_check (added #19793, migration
-- 20260903h_bolt32_draft_lane_cadence.sql) predates this decision and
-- forbids exactly that state: CHECK ((is_draft=false AND tts_model<>
-- 'kokoro') OR (is_draft=true AND tts_model='kokoro')) -- live-confirmed
-- this session (pg_get_constraintdef). Any UPDATE flipping is_draft to
-- false on a kokoro row would violate it as originally written.
--
-- Minimal relaxation, not a removal: a draft row (is_draft=true) still
-- MUST carry tts_model='kokoro' (unchanged -- #19793's "a draft can never
-- be mistaken for eleven_v3" guarantee). A FINAL row (is_draft=false) may
-- now carry tts_model IN ('eleven_v3','kokoro') -- both are legitimate
-- launch voices per this decision -- but never null (a final render must
-- always record which model actually spoke).

begin;

alter table winnerdata.reel_variants
    drop constraint if exists reel_variants_draft_tts_model_check;
alter table winnerdata.reel_variants
    add constraint reel_variants_draft_tts_model_check
    check (
        (is_draft = false and tts_model in ('eleven_v3', 'kokoro'))
        or
        (is_draft = true and tts_model = 'kokoro')
    );

commit;
