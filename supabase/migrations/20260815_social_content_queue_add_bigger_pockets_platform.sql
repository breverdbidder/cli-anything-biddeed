-- social_content_queue.target_platform CHECK constraint currently only allows
-- linkedin_personal, linkedin_company, reddit, telegram. Issue #19079 asks for
-- a bigger_pockets draft queue; widen the constraint additively (no rows
-- touched, no existing values removed).
ALTER TABLE public.social_content_queue
  DROP CONSTRAINT social_content_queue_target_platform_check;

ALTER TABLE public.social_content_queue
  ADD CONSTRAINT social_content_queue_target_platform_check
  CHECK (target_platform = ANY (ARRAY[
    'linkedin_personal'::text,
    'linkedin_company'::text,
    'reddit'::text,
    'telegram'::text,
    'bigger_pockets'::text
  ]));
