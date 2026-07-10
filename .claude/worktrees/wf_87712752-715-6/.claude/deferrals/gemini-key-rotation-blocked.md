---
priority: P2
status: deferred
owner: ariel
blocker: google-project-access-denied
dependency: google-cloud-console
minutes: 10
tags: [cred, rotation, cliproxy, gemini]
created: 2026-04-14
---

# Gemini key rotation blocked on Google project access

## Status (2026-04-14 verified)
- Currently-installed key in cliproxy: the Dify-extracted key from earlier this session — WORKING (smoke test passed at 35min container uptime, response HEALTH_OK, model gemini-2.5-flash, 6in/23out tokens)
- New key created in AI Studio, stored in GH secrets GEMINI_API_KEY and GOOGLE_API_KEY: REJECTED by Google with 403 PERMISSION_DENIED — "Your project has been denied access. Please contact support."

## Root cause
The new key was created in a Google Cloud project (likely zonewise.ai) that has Generative Language API disabled or restricted at the project/billing level. Same failure mode as the original GH_GEMINI_API_KEY and GH_GOOGLE_API_KEY from earlier in the session.

## Why old key still works
The old Dify-decrypted key comes from a DIFFERENT Google Cloud project (whatever Dify was originally configured with weeks ago), which has the Generative Language API enabled.

## Fix paths

### Path A — fastest (2 min)
1. https://aistudio.google.com/apikey
2. Click "Create API key" → in the project dropdown, select "Create API key in new project" (creates a fresh default Google Cloud project with the API auto-enabled)
3. Test the new key in AI Studio playground — send one prompt, confirm it works
4. Update GH secrets GEMINI_API_KEY + GOOGLE_API_KEY with the working key
5. Update the same key in Dify admin UI → Model Provider → Gemini
6. Signal "key rotated" → Claude re-runs cliproxy-key-rotate workflow

### Path B — enable API on existing project (~5 min)
1. https://console.cloud.google.com/apis/library/generativelanguage.googleapis.com
2. Select the project you are in from the top-right dropdown
3. Click ENABLE if not already
4. If already enabled, check billing — make sure a billing account is linked to this project
5. Retry key creation from AI Studio

## Do NOT do
- Do NOT force a rotation attempt until path A or B is verified
- Doing so would REPLACE the working key with a broken one and kill SUMMIT immediately
- Do NOT delete the currently-working Dify key from AI Studio (if you created the new one in AI Studio, the old one is in Dify project — leave it)
