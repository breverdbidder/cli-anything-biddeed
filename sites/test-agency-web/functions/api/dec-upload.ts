// Cloudflare Pages Function: POST /api/dec-upload
//
// Secondary/fallback intake path (issue #19602 Task 1) for prospects who
// won't or can't complete the Canopy Connect one-click carrier pull.
// Accepts a declarations-page file (PDF/JPG/PNG) plus minimal contact info,
// stores the file in Supabase Storage, and writes a protection_partners_intake
// row with source='dec_upload'. This codebase does NOT parse or OCR the
// file -- the row is flagged payload.needs_manual_review=true for a human
// to open it. Canopy's own DecSight product does that extraction when their
// hosted "Document Upload" sharing path is configured (see
// DecUploadWidget.astro, which routes there instead of here when
// PUBLIC_CANOPY_DEC_UPLOAD_URL is set -- this endpoint is the fallback of
// the fallback).
import { createClient } from "@supabase/supabase-js";

interface Env {
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE: string;
  SUPABASE_TABLE: string;
  SUPABASE_STORAGE_BUCKET: string;
}

const ALLOWED_TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);
const MAX_BYTES = 10 * 1024 * 1024; // 10MB -- comfortably fits a scanned dec page

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const { request, env } = context;

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return jsonResponse({ error: "Invalid multipart/form-data body." }, 400);
  }

  const file = form.get("file");
  const name = form.get("name")?.toString().trim() || "";
  const phone = form.get("phone")?.toString().trim() || "";
  const email = form.get("email")?.toString().trim() || "";

  const errors: string[] = [];
  if (!phone) errors.push("phone is required");

  if (!(file instanceof File)) {
    errors.push("file is required");
  } else {
    if (file.size === 0) errors.push("file is empty");
    if (!ALLOWED_TYPES.has(file.type)) {
      errors.push(`file type "${file.type || "unknown"}" is not permitted -- PDF, JPG, or PNG only`);
    }
    if (file.size > MAX_BYTES) {
      errors.push(`file is ${file.size} bytes, which exceeds the ${MAX_BYTES}-byte cap`);
    }
  }

  if (errors.length > 0) {
    // Validation failed -- return before touching Storage or the DB. Zero
    // writes on a rejected file type or oversized file, per DoD item 4.
    return jsonResponse({ error: "Validation failed", details: errors }, 400);
  }

  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE || !env.SUPABASE_TABLE || !env.SUPABASE_STORAGE_BUCKET) {
    console.error("[dec-upload.ts] Missing SUPABASE_URL, SUPABASE_SERVICE_ROLE, SUPABASE_TABLE, or SUPABASE_STORAGE_BUCKET env var");
    return jsonResponse({ error: "Server is not configured to accept uploads right now." }, 500);
  }

  const uploadedFile = file as File;
  const submittedAt = new Date().toISOString();
  const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE, {
    auth: { persistSession: false },
  });

  const safeName = uploadedFile.name.replace(/[^a-zA-Z0-9._-]/g, "_").slice(-100);
  const objectPath = `${crypto.randomUUID()}-${safeName}`;

  const { error: storageError } = await supabase.storage
    .from(env.SUPABASE_STORAGE_BUCKET)
    .upload(objectPath, uploadedFile, { contentType: uploadedFile.type, upsert: false });

  if (storageError) {
    console.error("[dec-upload.ts] Supabase Storage upload failed:", storageError.message);
    return jsonResponse({ error: "Could not save your file. Please try the quote form instead." }, 500);
  }

  const ip =
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("X-Forwarded-For") ||
    null;

  const { data, error } = await supabase
    .from(env.SUPABASE_TABLE)
    .insert({
      payload: {
        schema_version: "1.0",
        generated_at: submittedAt,
        applicant: {
          entity_name: { value: name || null, source: "dec_upload_form" },
          contact_phone: { value: phone, source: "dec_upload_form" },
          contact_email: { value: email || null, source: "dec_upload_form" },
        },
        dec_page: {
          storage_bucket: env.SUPABASE_STORAGE_BUCKET,
          storage_path: objectPath,
          file_name: uploadedFile.name,
          file_type: uploadedFile.type,
          file_size: uploadedFile.size,
        },
        needs_manual_review: true,
      },
      consent: {
        basis: "dec_page_upload",
        ip,
        submitted_at: submittedAt,
        user_agent: request.headers.get("User-Agent") || null,
      },
      source: "dec_upload",
      status: "new",
    })
    .select("id")
    .single();

  if (error) {
    console.error("[dec-upload.ts] Supabase insert failed:", error.message);
    // Best-effort: the file already landed in Storage, but the row failed.
    // Do not attempt to delete the upload -- that risk (silent data loss on
    // a second transient failure) is worse than an orphaned Storage object
    // a human can find later.
    return jsonResponse({ error: "Could not save your request. Please call us instead." }, 500);
  }

  return jsonResponse({ ok: true, id: data.id }, 200);
};
