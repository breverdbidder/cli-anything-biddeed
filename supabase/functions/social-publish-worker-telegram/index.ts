// supabase/functions/social-publish-worker-telegram/index.ts
//
// Reads pending 'telegram' rows from social_content_queue and posts them to
// a public Telegram channel via the existing bot (@BidDeedAI_bot). Much
// simpler than the LinkedIn worker -- no OAuth at all, just the bot token
// already in vault plus one new secret: the channel to post to.
//
// DORMANT until telegram_channel_id exists in vault. That value is set
// manually by Ariel once the channel exists and the bot has been added as
// an admin with "Post Messages" permission -- Telegram's Bot API has no
// method to create a channel programmatically, so that one step is
// necessarily manual, same shape as LinkedIn's OAuth click.
//
// telegram_channel_id can be either a numeric chat id or an @username
// (Telegram's sendMessage API accepts both interchangeably).
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
    // Deliberately the personal alerts chat (telegram_chat_id), NOT the
    // public channel this worker posts to -- failure alerts stay private.
    const token = await vaultSecret("telegram_bot_token");
    const chatId = await vaultSecret("telegram_chat_id");
    if (!token || !chatId) return;
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: `\u{1F6A8} social-publish-worker-telegram\n${context}\n${detail}`.slice(0, 4000) }),
    });
  } catch (_) { /* alerting must never throw */ }
}

async function postToChannel(content: string): Promise<{ ok: boolean; externalId?: string; error?: string }> {
  const botToken = await vaultSecret("telegram_bot_token");
  const channelId = await vaultSecret("telegram_channel_id");
  if (!botToken) return { ok: false, error: "telegram_bot_token not in vault" };
  if (!channelId) return { ok: false, error: "telegram_channel_id not in vault -- channel not yet created/configured" };

  const res = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: channelId,
      text: content,
      disable_web_page_preview: false,
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    return { ok: false, error: `Telegram API ${res.status}: ${errText}`.slice(0, 500) };
  }
  const data = await res.json();
  const externalId = data?.result?.message_id ? String(data.result.message_id) : undefined;
  return { ok: true, externalId };
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return new Response(JSON.stringify({ error: "POST required" }), { status: 405 });

  const channelId = await vaultSecret("telegram_channel_id");
  if (!channelId) {
    return new Response(JSON.stringify({
      ok: false,
      error: "Dormant: telegram_channel_id not in vault. Create the public channel, add @BidDeedAI_bot as admin with Post Messages permission, then set telegram_channel_id.",
    }), { status: 503, headers: { "Content-Type": "application/json" } });
  }

  const today = new Date().toISOString().slice(0, 10);
  const { data: pending, error } = await supabase
    .from("social_content_queue")
    .select("*")
    .eq("status", "pending")
    .eq("target_platform", "telegram")
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
    const r = await postToChannel(post.content_text);
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
