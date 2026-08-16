-- ElevenLabs raw text-to-speech generation, scoped ONLY to /v1/text-to-speech/*.
-- Companion to elevenlabs_api_get/post/patch/post_long (all scoped to /v1/convai/*),
-- which cannot reach the TTS endpoint family. Reuses the existing 'elevenlabs_api_key'
-- vault secret -- no new secret required.
--
-- Binary safety: extensions.http_response.content (pgsql-http 1.6) and
-- net.http_response.body/content (pg_net 0.20.4) are both `text`, not `bytea` --
-- routing raw MP3 bytes through either would corrupt on server-encoding
-- conversion. Instead of fighting that, this calls ElevenLabs' own
-- /with-timestamps variant, which returns JSON with an `audio_base64` field
-- (ASCII-safe, round-trips through text with no corruption). We pass the
-- base64 string straight through unmodified.
CREATE OR REPLACE FUNCTION public.elevenlabs_tts_generate(
  p_voice_id text,
  p_text text,
  p_model_id text DEFAULT 'eleven_v3_conversational'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $function$
DECLARE
  v_key       text;
  v_resp      extensions.http_response;
  v_body      jsonb;
  v_audio_b64 text;
BEGIN
  SELECT decrypted_secret INTO v_key
  FROM vault.decrypted_secrets WHERE name = 'elevenlabs_api_key' LIMIT 1;

  SELECT * INTO v_resp FROM extensions.http((
    'POST',
    'https://api.elevenlabs.io/v1/text-to-speech/' || p_voice_id || '/with-timestamps',
    ARRAY[
      extensions.http_header('xi-api-key', v_key),
      extensions.http_header('Content-Type','application/json')
    ],
    'application/json',
    jsonb_build_object(
      'text', p_text,
      'model_id', p_model_id,
      'output_format', 'mp3_44100_128'
    )::text
  )::extensions.http_request);

  IF v_resp.status NOT IN (200, 201) THEN
    RETURN jsonb_build_object('error','tts_failed','status',v_resp.status,'body', v_resp.content);
  END IF;

  v_body := v_resp.content::jsonb;
  v_audio_b64 := v_body->>'audio_base64';

  IF v_audio_b64 IS NULL THEN
    RETURN jsonb_build_object('error','no_audio_base64_in_response','status',v_resp.status,'body', v_resp.content);
  END IF;

  RETURN jsonb_build_object(
    'audio_base64', v_audio_b64,
    'content_type', 'audio/mpeg',
    'bytes', octet_length(decode(v_audio_b64, 'base64'))
  );
END;
$function$;
