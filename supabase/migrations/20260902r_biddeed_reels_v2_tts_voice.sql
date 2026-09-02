-- BidDeed Reels v2 (issue #19752) -- directive #4 (Ariel, 2026-09-02 21:16
-- EDT): v2's first render used the v1 Flash TTS path with no way to prove
-- otherwise. Add explicit columns so every v2 row records which model/voice
-- actually generated its audio -- verifiable via SQL, not just claimed.

begin;

alter table winnerdata.biddeed_reels
  add column if not exists tts_model text,
  add column if not exists voice_id text;

comment on column winnerdata.biddeed_reels.tts_model is
  'ElevenLabs model_id used for this row''s voiceover, e.g. eleven_v3. Directive #4: every v2 render must be eleven_v3.';
comment on column winnerdata.biddeed_reels.voice_id is
  'ElevenLabs voice_id used for this row''s voiceover -- one consistent brand voice across all reels per directive #4.';

commit;
