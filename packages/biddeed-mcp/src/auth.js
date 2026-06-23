import { createHash } from 'crypto';
import { get, patch } from './supabase.js';
import { TIER_RANK, STREAM_GATE } from './constants.js';

// Cache validated keys for 5 min to avoid per-call DB round-trips
const cache = new Map(); // hash → { record, expiresAt }
const CACHE_TTL_MS = 5 * 60 * 1000;

function hashKey(apiKey) {
  return createHash('sha256').update(apiKey).digest('hex');
}

export async function validateKey(apiKey) {
  if (!apiKey) throw new AuthError('BIDDEED_API_KEY not set — pass env var to npx biddeed-mcp');

  const hash = hashKey(apiKey);
  const cached = cache.get(hash);
  if (cached && cached.expiresAt > Date.now()) return cached.record;

  const rows = await get(`mcp_api_keys?key_hash=eq.${hash}&limit=1`);
  if (!rows.length) throw new AuthError('Invalid API key');

  const record = rows[0];
  if (!record.is_active) throw new AuthError('API key deactivated — contact support@biddeed.ai');
  if (record.expires_at && new Date(record.expires_at) < new Date()) {
    throw new AuthError('API key expired — renew at biddeed.ai/dashboard');
  }

  cache.set(hash, { record, expiresAt: Date.now() + CACHE_TTL_MS });

  // Update last_used_at + call_count async (non-blocking)
  patch('mcp_api_keys', `key_hash=eq.${hash}`, {
    last_used_at: new Date().toISOString(),
    call_count: record.call_count + 1,
  }).catch(() => {});

  return record;
}

export function assertTier(customerRecord, streamId) {
  const required = STREAM_GATE[streamId];
  const customerRank = TIER_RANK[customerRecord.tier] ?? 0;
  const requiredRank = TIER_RANK[required] ?? 0;
  if (customerRank < requiredRank) {
    throw new AuthError(
      `Stream ${streamId} requires ${required} tier — current tier: ${customerRecord.tier}. Upgrade at biddeed.ai/upgrade`
    );
  }
}

export class AuthError extends Error {
  constructor(message) {
    super(message);
    this.name = 'AuthError';
    this.isAuthError = true;
  }
}

// Resolve API key from env (stdio) or explicit param (HTTP)
export function resolveApiKey(envKey) {
  const key = envKey || process.env.BIDDEED_API_KEY || process.env.ZONEWISE_API_KEY;
  if (!key) throw new AuthError('API key required. Set BIDDEED_API_KEY env var.');
  return key;
}
