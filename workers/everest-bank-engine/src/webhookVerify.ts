// Plaid webhook JWT verification, per Plaid's documented algorithm
// (https://plaid.com/docs/api/webhooks/webhook-verification/): the JWT's `kid` selects a
// per-key-rotation ES256 public key fetched (and cached) via /webhook_verification_key/get,
// the signature is verified with Web Crypto, `iat` must be within 5 minutes, and the payload's
// `request_body_sha256` must match a SHA-256 of the exact raw request body.

import type { Env } from "./env";
import { plaidClient } from "./plaid";

interface CachedKey {
  jwk: JsonWebKey;
  expiredAt: string | null;
}

const keyCache = new Map<string, CachedKey>();

function base64UrlDecode(input: string): Uint8Array {
  const pad = input.length % 4 === 0 ? "" : "=".repeat(4 - (input.length % 4));
  const base64 = input.replace(/-/g, "+").replace(/_/g, "/") + pad;
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

async function sha256Hex(data: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function verifyPlaidWebhook(
  env: Env,
  request: Request,
  rawBody: string
): Promise<{ ok: boolean; reason?: string }> {
  const jwtToken = request.headers.get("Plaid-Verification");
  if (!jwtToken) return { ok: false, reason: "missing Plaid-Verification header" };

  const parts = jwtToken.split(".");
  if (parts.length !== 3) return { ok: false, reason: "malformed JWT" };
  const [headerB64, payloadB64, sigB64] = parts;

  let header: { kid?: string; alg?: string };
  let payload: { iat?: number; request_body_sha256?: string };
  try {
    header = JSON.parse(new TextDecoder().decode(base64UrlDecode(headerB64)));
    payload = JSON.parse(new TextDecoder().decode(base64UrlDecode(payloadB64)));
  } catch {
    return { ok: false, reason: "unparseable JWT" };
  }
  if (!header.kid) return { ok: false, reason: "no kid in JWT header" };

  let cached = keyCache.get(header.kid);
  if (!cached) {
    const client = plaidClient(env);
    const resp = await client.webhookVerificationKeyGet({ key_id: header.kid });
    const key = resp.data.key as unknown as JsonWebKey & { expired_at?: string | null };
    cached = { jwk: key, expiredAt: key.expired_at ?? null };
    keyCache.set(header.kid, cached);
  }
  if (cached.expiredAt) return { ok: false, reason: "verification key expired, refetch required" };

  const cryptoKey = await crypto.subtle.importKey(
    "jwk",
    cached.jwk,
    { name: "ECDSA", namedCurve: "P-256" },
    false,
    ["verify"]
  );

  const signedData = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const signature = base64UrlDecode(sigB64);
  const valid = await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, cryptoKey, signature, signedData);
  if (!valid) return { ok: false, reason: "signature invalid" };

  if (payload.iat && Date.now() / 1000 - payload.iat > 5 * 60) {
    return { ok: false, reason: "token expired (iat > 5min)" };
  }

  const bodyHash = await sha256Hex(new TextEncoder().encode(rawBody));
  if (bodyHash !== payload.request_body_sha256) {
    return { ok: false, reason: "body hash mismatch" };
  }

  return { ok: true };
}
