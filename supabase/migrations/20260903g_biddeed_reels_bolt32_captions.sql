-- CMO FACTORY CP3b(v2) (issue #19787) -- tracks the whisperX/faster-whisper
-- word-level caption burn-in (scripts/bolt32_captions_whisperx.py::group_words
-- + biddeed_reels_lib.py::burn_word_captions_bolt32), separate from
-- video_bolt32_url (the beat-title-card render from #19779) so neither
-- overwrites the other -- same additive-columns pattern #19779 used for
-- video_bolt32_url/duration_bolt32_sec.

begin;

alter table winnerdata.biddeed_reels
  add column if not exists video_bolt32_captions_url text,
  add column if not exists captions_source text,          -- 'faster_whisper' (production) | 'openai_whisper_session_substitute' (documented one-off, HF Hub unreachable)
  add column if not exists captions_groups jsonb,          -- group_words() output: [{"text","start","end","words"}]
  add column if not exists captions_model text,            -- e.g. 'small'/'base' etc
  add column if not exists captions_generated_at timestamptz,
  add column if not exists qa_scores jsonb,                -- issue #19787 post-render QA critique loop (bolt32_qa_critique.py)
  add column if not exists qa_pass boolean;

commit;
