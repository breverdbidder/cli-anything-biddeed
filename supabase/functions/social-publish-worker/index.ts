// supabase/functions/social-publish-worker/index.ts
//
// Reads approved rows from social_content_queue and posts them to LinkedIn.
// Dormant (returns 503, does nothing) until linkedin_access_token exists in
// vault -- i.e. until Ariel completes the one-time OAuth authorization via
// linkedin-oauth-callback.
//
// APPROVAL GATE (added issue #19789, M1/M8 fix): this worker used to publish
// any status='pending' row unconditionally the moment a token existed ("No
// content review gate here by design"). That was a live M1/M8 violation --
// once OAuth landed it would have posted to Ariel's PERSONAL LinkedIn
// profile (author is a urn:li:person:, not an organization) with zero
// human review. It now also requires approved_at IS NOT NULL, set only by
// Ariel's approve click in the LMS, same contract as winnerdata.ff_batches.
// Separately, target_platform='linkedin_personal' predates CP3g's
// requirement that LinkedIn posting go through a company page
// (w_organization_social) -- see docs/gtm/DISTRIBUTION_LANE.md for that
// still-open reclassification; this worker is left targeting the personal
// profile for now because migrating it needs a new OAuth grant this
// session has no way to obtain, not because personal-profile posting is
// endorsed going forward.
//
// Run on a schedule (GHA cron). Every attempt updates the row's status so
// nothing is retried silently forever; failures alert via Telegram.
//
// scheduled_for pacing (added issue #19088): a row is only picked up once
// scheduled_for <= today. Existing/county_snapshot rows default to
// yesterday at insert time, so this is a no-op for them -- only rows that
// explicitly set a future scheduled_for (e.g. property_spotlight) are held
// back.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const MAX_RETRIES = 3;

async function vaultSecret(name: string): Promise<string | null> {
  const { data, error } = await supabase.rpc("vault_secret", { p_name: name });
  if (!error && data) return String(data);
  return null;
}

async function alertFailure(context: string, detail: string) {
  try {
    const token = await vaultSecret("telegram_bot_token");
    const chatId = await vaultSecret("telegram_chat_id");
    if (!token || !chatId) return;
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: `\u{1F6A8} social-publish-worker\n${context}\n${detail}`.slice(0, 4000) }),
    });
  } catch (_) { /* alerting must never throw */ }
}

async function getLinkedInAuthorUrn(accessToken: string): Promise<string | null> {
  // The /v2/userinfo endpoint (OpenID Connect) resolves the authenticated
  // member's own ID -- required to build the author URN for a personal post.
  const res = await fetch("https://api.linkedin.com/v2/userinfo", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.sub ? `urn:li:person:${data.sub}` : null;
}

async function postToLinkedIn(content: string): Promise<{ ok: boolean; externalId?: string; error?: string }> {
  const accessToken = await vaultSecret("linkedin_access_token");
  if (!accessToken) return { ok: false, error: "linkedin_access_token not in vault -- not yet authorized" };

  const authorUrn = await getLinkedInAuthorUrn(accessToken);
  if (!authorUrn) return { ok: false, error: "could not resolve LinkedIn author URN -- token may be expired" };

  const res = await fetch("https://api.linkedin.com/v2/ugcPosts", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
      "X-Restli-Protocol-Version": "2.0.0",
    },
    body: JSON.stringify({
      author: authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": {
          shareCommentary: { text: content },
          shareMediaCategory: "NONE",
        },
      },
      visibility: { "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC" },
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    return { ok: false, error: `LinkedIn API ${res.status}: ${errText}`.slice(0, 500) };
  }
  const externalId = res.headers.get("x-restli-id") ?? undefined;
  return { ok: true, externalId };
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return new Response(JSON.stringify({ error: "POST required" }), { status: 405 });

  const accessToken = await vaultSecret("linkedin_access_token");
  if (!accessToken) {
    return new Response(JSON.stringify({
      ok: false,
      error: "Dormant: linkedin_access_token not in vault. Complete OAuth via linkedin-oauth-callback first.",
    }), { status: 503, headers: { "Content-Type": "application/json" } });
  }

  const today = new Date().toISOString().slice(0, 10);
  const { data: pending, error } = await supabase
    .from("social_content_queue")
    .select("*")
    .eq("status", "pending")
    .eq("target_platform", "linkedin_personal")
    .not("approved_at", "is", null)
    .lt("retry_count", MAX_RETRIES)
    .lte("scheduled_for", today)
    .order("created_at", { ascending: true })
    .limit(10);

  if (error) {
    await alertFailure("queue read failed", error.message);
    return new Response(JSON.stringify({ ok: false, error: error.message }), { status: 500 });
  }

  const results = [];
  for (const post of pending ?? []) {
    const r = await postToLinkedIn(post.content_text);
    if (r.ok) {
      await supabase.from("social_content_queue").update({
        status: "published",
        external_post_id: r.externalId ?? null,
        published_at: new Date().toISOString(),
        last_attempt_at: new Date().toISOString(),
      }).eq("id", post.id);
      results.push({ id: post.id, ok: true });
    } else {
      const newRetryCount = post.retry_count + 1;
      const finalStatus = newRetryCount >= MAX_RETRIES ? "failed" : "pending";
      await supabase.from("social_content_queue").update({
        status: finalStatus,
        error_message: r.error,
        retry_count: newRetryCount,
        last_attempt_at: new Date().toISOString(),
      }).eq("id", post.id);
      if (finalStatus === "failed") {
        await alertFailure(`post ${post.id} exhausted retries`, r.error ?? "unknown");
      }
      results.push({ id: post.id, ok: false, error: r.error });
    }
  }

  return new Response(JSON.stringify({ ok: true, processed: results.length, results }), {
    headers: { "Content-Type": "application/json" },
  });
});
