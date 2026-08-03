-- Service-role key rotation (leaked key found by Gitleaks 104x in git history).
-- Copies the new key from its temporary vault name to the canonical name
-- entirely server-side, so the raw value never has to pass through a chat
-- session, the Management API, or a shell command (GTM-22D CREDENTIAL HANDLING).
-- The function is self-dropping: callers remove it immediately after use.

CREATE OR REPLACE FUNCTION public.__rotate_vault_secret_once(source_name text, dest_name text)
RETURNS uuid
SECURITY DEFINER
SET search_path = public, vault
LANGUAGE plpgsql
AS $$
DECLARE
  v_id uuid;
  v_val text;
BEGIN
  SELECT decrypted_secret INTO v_val FROM vault.decrypted_secrets WHERE name = source_name;
  IF v_val IS NULL THEN
    RAISE EXCEPTION 'source secret % not found', source_name;
  END IF;

  DELETE FROM vault.secrets WHERE name = dest_name;
  SELECT vault.create_secret(v_val, dest_name) INTO v_id;

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.__rotate_vault_secret_once(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.__rotate_vault_secret_once(text, text) TO postgres, service_role;
