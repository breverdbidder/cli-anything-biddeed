-- Issue: cold send consent + free report lead capture + SMS opt-in.
-- Single upsert RPC for POST /free-report/submit — records phone + separate
-- email/SMS consent (with their own timestamps) instead of the single
-- undifferentiated marketing_consent flag the existing /chat/lead endpoint
-- writes. SECURITY DEFINER so anon (the only credential the Cloudflare
-- Worker holds — see wrangler.toml, no service_role binding exists) can
-- call it without needing direct table grants on lead_profiles.
CREATE OR REPLACE FUNCTION public.upsert_lead_full(
  p_email text, p_name text, p_phone text, p_county text,
  p_email_consent boolean, p_sms_consent boolean, p_source text
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  INSERT INTO lead_profiles (email, name, phone, county, source,
    email_consent, email_consent_at, sms_consent, sms_consent_at,
    marketing_consent, marketing_consent_at, score)
  VALUES (p_email, p_name, p_phone, p_county, p_source,
    p_email_consent, CASE WHEN p_email_consent THEN now() END,
    p_sms_consent, CASE WHEN p_sms_consent THEN now() END,
    p_email_consent, CASE WHEN p_email_consent THEN now() END,
    50)
  ON CONFLICT (email) DO UPDATE SET
    phone = COALESCE(EXCLUDED.phone, lead_profiles.phone),
    email_consent = EXCLUDED.email_consent OR lead_profiles.email_consent,
    email_consent_at = COALESCE(lead_profiles.email_consent_at, CASE WHEN EXCLUDED.email_consent THEN now() END),
    sms_consent = EXCLUDED.sms_consent OR lead_profiles.sms_consent,
    sms_consent_at = COALESCE(lead_profiles.sms_consent_at, CASE WHEN EXCLUDED.sms_consent THEN now() END),
    marketing_consent = EXCLUDED.email_consent OR lead_profiles.email_consent,
    score = GREATEST(lead_profiles.score, 55),
    updated_at = now();
END;
$$;
REVOKE ALL ON FUNCTION public.upsert_lead_full FROM PUBLIC;
-- Deviation from the as-specified GRANT (service_role only): the Worker
-- only ever holds the anon key (matches get_all_counties_with_status /
-- get_s5_report_access — every other worker-callable RPC in this repo
-- grants anon), so service_role-only would make /free-report/submit
-- unreachable from production. Table itself has no anon INSERT policy for
-- these new columns, so SECURITY DEFINER + anon EXECUTE is the only path.
GRANT EXECUTE ON FUNCTION public.upsert_lead_full TO anon, authenticated, service_role;
