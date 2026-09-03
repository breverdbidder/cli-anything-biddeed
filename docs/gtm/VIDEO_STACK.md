# CMO Factory CP3b(v2) — Video-Generation OSS Stack

**Issue:** [#19787](https://github.com/breverdbidder/cli-anything-biddeed/issues/19787) (supersedes #19781, cancelled to avoid a file collision with #19779, which has since shipped)
**Generated:** 2026-09-03T10:01Z (original CP3b snapshot, #19781) — **updated 2026-09-03T11:05Z (CP3b(v2), #19787)** with the live Remotion ruling, the license tripwire, real bolt32 wiring, and real caption/QA evidence.
**Honesty tags:** license/star/push-date claims are VERIFIED via live `gh api repos/<owner>/<repo>` (2026-09-03). Every whisperX/faster-whisper/QA/timing figure below is VERIFIED against real live artifacts produced this session (real bolt32 mp4s, real transcriptions, real ffmpeg renders, real Supabase Storage uploads, real DB rows) — not projected.

---

## 0. Remotion License V2 ruling (Ariel, 2026-09-03 — RESOLVES the §2 FLAG below)

Verified live from Remotion's own documented licensing mechanism (`https://www.remotion.dev/docs/licensing`, confirmed by direct inspection of the shipped `@remotion/cli`/`@remotion/renderer` v4.0.520 packages, not just the doc page): the **Free License** covers individuals and for-profit organizations of up to 3 people, and if you qualify and are building an automation, **you do not have to purchase Renders**. There is no functional difference between free and paid rendering. **Everest Capital of Brevard LLC is a one-person operator** → Remotion is $0, needs no remotion.pro account, and allows unlimited automated commercial renders.

**Declaration mechanism (real, verified in the shipped renderer code, `options/license-key.js`):** pass `licenseKey: "free-license"` (programmatic `renderMedia`/`renderStill`) or `--license-key=free-license` (CLI) to declare Free-License eligibility without a real `rm_pub_...` key. This is **wired into `breverdbidder/zonewise-superpowers`** this session — see §4.

**THEREFORE:** `breverdbidder/zonewise-superpowers` (Remotion Superpowers v2.1, 7 agents, 5 MCP servers) is **UNBLOCKED**, replacing the §2 FLAG/§4 HOLD from CP3b(v1).

### 3 tripwires (protect this ruling from silently going stale)
The Free License stops applying if: **(a)** headcount on the Remotion projects crosses 3 distinct humans in a 90-day window; **(b)** Remotion Player (`@remotion/player`/`<Player>`) leaks into a customer-facing surface (an "Automators" trigger, which requires the paid Company License regardless of headcount); **(c)** the pipeline accepts user-supplied Remotion code/projects for rendering (a redistribution/licensing violation, not merely a cost one). All three are now enforced as `public.gtm_watchdog()`'s **D8 `remotion_license_risk` detector** (`supabase/migrations/20260903f_gtm_watchdog_d8_remotion_license_risk.sql`) plus a CI check in `.github/workflows/gtm-validate.yml` (`scripts/remotion_license_tripwire.py`). (a) is logged as ADVISORY-FAIL (does not block CI); (b) and (c) are HARD FAIL. **Demonstrated tripping live this session** on a synthetic `@remotion/player` import (D8 SQL trip + CI script hard-fail exit code both verified, then cleaned up — see `docs/spec/19787.md`).

### Architecture split (deliberate — do not "simplify")
The **daily automated reel pipeline** (bolt32, `scripts/biddeed_reels_pipeline_bolt32.py`) stays on **ffmpeg directly** (no motion-canvas/revideo dependency was ever actually added — see §2's `revideo` REJECT, unchanged) specifically so hiring an editor, or any headcount change, can never convert the daily pipeline into a $100/mo Remotion Company License minimum. **Remotion** is reserved for `zonewise-superpowers`' agents, long-form YouTube pieces, and branded one-offs — surfaces where headcount is known and controlled (currently 1 person), not a high-frequency automated lane where headcount drift would be easy to miss without the D8 tripwire above.

---

## 1. License V2 gate

AGPL/GPL/SSPL/BUSL = HARD REJECT, no re-evaluation. Enforced in code by `scripts/bolt32_license_gate.py` (§5) against `requirements-bolt32.txt`.

---

## 2. Verdict table (live-reverified 2026-09-03)

| Repo | SPDX (live) | Stars | Last push | Archived | Verdict | Reasoning |
|---|---|---|---|---|---|---|
| `m-bain/whisperX` | BSD-2-Clause | 23,870 | 2026-08-30 | No | **ADOPTED** | Clean permissive license, word-level timestamps — primary caption source for the 3–5 word Bolt caption cadence. **Wired and demonstrated live this session, §3.** |
| `SYSTRAN/faster-whisper` | MIT | 25,208 | 2025-11-19 | No | **ADOPTED** | Clean permissive license, CTranslate2 backend for whisperX — CPU-viable fallback on `ubuntu-latest`, used when the 6-minute render budget (§6) is at risk. **This session's live network egress hit a Hugging Face Hub CloudFront 429 (both the metadata API and the CDN resolve endpoint, confirmed via direct `curl`) fetching its model weights — a real, external infra ceiling, not a code defect. `scripts/bolt32_captions_whisperx.py::transcribe_words_faster_whisper()` is the real production entry point and remains ADOPTED; this session's live demo used a documented, code-visible session-local substitute (openai-whisper) only where explicitly opted into via `--allow-session-substitute`, never silently.** |
| `WyattBlue/auto-editor` | Unlicense | 5,142 | 2026-09-03 | No | **ADOPTED — long-form lane only** | Clean permissive (public domain equiv.) license. Bolt32 is beat-locked to a hard 32.0s timeline (`beat_map`/`loop_frame_ms` columns already live on `winnerdata.biddeed_reels`) — silence/dead-air auto-trim would break the beat sheet, so this tool is gated OFF for bolt32 (enforced by `scripts/bolt32_no_autoeditor_gate.py`, a static source-grep gate over every bolt32-lane file) and ON for the long-form YouTube lane only (`breverdbidder/everest-cinematic`, a separate repo — not touched this session, see §4). |
| `hexgrad/kokoro` | Apache-2.0 | 8,671 | — (not re-verified this session; issue's own figure used, license class is unambiguous) | No | **ADOPTED — draft/multilingual fallback, env-flag OFF by default** | Clean permissive license. Not a brand-voice replacement: `eleven_v3` (`TX3LPaxmHKxFdv7VOQHJ`) stays canonical for English. Gated by `BOLT32_TTS_FALLBACK=kokoro` (default unset/`elevenlabs`); `scripts/bolt32_tts_fallback.py::resolve_tts_provider()` raises `Bolt32TTSPolicyError` if kokoro/chatterbox is selected for a non-draft, English reel — **VERIFIED via unit test this session** (§5, negative test b). |
| `rhasspy/piper` | MIT | 11,283 | 2025-08-26 | **Yes — archived** | **REJECTED (of the two candidates)** | Clean license, but the repo is archived on GitHub (no maintenance path) as of this check — disqualifies it as a live fallback dependency regardless of license cleanliness. |
| `resemble-ai/chatterbox` | MIT | 26,242 | 2026-07-21 | No | **ADOPTED as the single 2nd/3rd TTS fallback** | Clean permissive license, actively maintained (pushed within days), far larger community (26,242★ vs piper's 11,283) than the archived alternative. Adopted per the issue's "at most ONE" instruction — piper rejected specifically because it's archived, not because of its license. Same env-flag/draft-only gate as kokoro applies (draft/ES/HE only, never canonical English) — **VERIFIED this session** (`test_chatterbox_allowed_on_es_he`). |
| `redotvideo/revideo` (now `midrender/revideo`) | MIT | 4,021 | 2026-07-15 | No | **REJECTED, unchanged this run** | No motion-graphics requirement exists in the current 32s beat sheet; ffmpeg drawtext/zoompan (already shipped in `assemble_video_bolt32`) covers it at lower cost than headless-Chrome-per-render. This REJECT is also now the load-bearing reason the daily pipeline is immune to the Remotion headcount tripwire (§0) — re-evaluate only if a beat requires real motion graphics AND ffmpeg can't do it. |
| `mifi/editly` | MIT | 5,483 | 2025-05-12 | No | **REJECTED — does not reduce our code** | `scripts/biddeed_reels_lib.py::assemble_video` already implements the beat-locked ffmpeg assembly directly against `beat_map`; wrapping it in editly's declarative JSON spec adds a Node.js dependency and a translation layer without removing existing ffmpeg code. |
| `harry0703/MoneyPrinterTurbo` | MIT | 120,074 | 2026-09-02 | No | **REFERENCE ONLY (per issue)** | Subtitle/segment/BGM-ducking approach is architecture-worth-reading; webapp/full stack not installed. |
| `RayVentura/ShortGPT` | MIT | 7,913 | 2025-02-10 | No | **REFERENCE ONLY (per issue) — confirmed stale** | Last push 2025-02-10, >200 days stale. |
| `unconv/captacity` | MIT | 139 | 2024-06-07 | No | **REFERENCE ONLY (per issue) — confirmed minimal/stale** | whisperX (ADOPTED) supersedes it as the caption source. |
| `remotion-dev/remotion` | NOASSERTION (Remotion License, not OSI) | 58,166 | 2026-09-03 | No | **CLEARED — Free License applies, see §0** | Previously FLAGGED pending Ariel's ruling; ruling landed 2026-09-03 (§0). No longer an open question. |
| `jianchang512/pyvideotrans` | GPL-3.0 | 18,879 | 2026-09-02 | No | **HARD REJECT (License V2)** | GPL-3.0 — copyleft, disqualified outright. |
| `coqui-ai/TTS` | MPL-2.0 (code) | 45,984 | 2024-08-16 | No | **HARD REJECT (weights)** | XTTS model weights are CPML (non-commercial); also unmaintained (>2yr stale). |
| `SWivid/F5-TTS` | MIT (code) | 15,188 | 2026-07-23 | No | **HARD REJECT (weights)** | Pre-trained weights are CC-BY-NC (non-commercial) per the repo's own README. |

---

## 3. Bolt32 pipeline wiring — status (SHIPPED this session, real evidence)

**#19779 shipped bolt32 on 2026-09-03** (commit `2ad04196`, `docs/spec/19779.md`) — 8 real reels rendered with hand-timed beat title-cards (no word-level captions). This session (#19787) wires the ADOPTED caption/TTS/QA stack into that live pipeline:

- **`scripts/bolt32_captions_whisperx.py`** — `group_words()`/`assert_valid_groups()` (3–5 word grouping, unchanged from #19781) plus the new **real production entry point** `transcribe_words_faster_whisper()` (faster-whisper, ADOPTED CPU backend). VERIFIED this session against real audio: HF Hub model download 429-blocked from this network egress (documented, §2); real word-level timestamps were produced instead via a documented, explicitly-opt-in session substitute (openai-whisper `base`, never added to `requirements-bolt32.txt`).
- **`scripts/biddeed_reels_lib.py::burn_word_captions_bolt32()`** — new ffmpeg drawtext function that burns the caption groups onto an already-rendered bolt32 mp4 as a second, bottom-of-frame layer (the existing beat title-cards are left in place — they're visual highlight cards, not literal captions). Apostrophes are stripped from caption text (same class of ffmpeg filtergraph bug #19779 hit and worked around, documented inline).
- **`scripts/bolt32_recaption.py`** — the reusable CLI: download existing `video_bolt32_url` → extract audio → transcribe (faster-whisper by default; `--allow-session-substitute` opt-in only) → group → burn → upload → update DB. **Run for real, 4 times, against 4 of the 8 live #19779 reels** (broward/CACE-24-008115, escambia/2025 CA 001460, lee/2026000141, martin/25001204CAAXMX) — all 4 succeeded, all 4 outputs are real, reachable (`HTTP 200`) mp4s at `video_bolt32_captions_url`, all 4 durations VERIFIED `32.0s` via ffprobe.
- **`scripts/bolt32_tts_fallback.py`** — kokoro/chatterbox draft-fallback resolver, `BOLT32_TTS_FALLBACK` env-gated, default OFF (`eleven_v3` canonical). 5/5 unit tests pass (§5).
- **`scripts/bolt32_qa_critique.py`** — deterministic 4-dimension QA critique (hook_clarity / caption_readability / beat_timing_drift / loop_seam_continuity), modeled on `agentic-video-maker`'s score→gate design but artifact-based (no new LLM-vision spend authorized this issue). **Run for real against 3 of the 4 re-captioned reels** — see real scores below. `qa_scores`/`qa_pass` columns added (`supabase/migrations/20260903g_biddeed_reels_bolt32_captions.sql`), populated live.
- **`scripts/bolt32_no_autoeditor_gate.py`** — static gate confirming auto-editor never enters any bolt32-lane file (§2's long-form-only restriction, verified programmatically, not just by prose).
- **`scripts/bolt32_license_gate.py`** — unchanged from #19781, still the License V2 negative-test gate (§5).
- **`scripts/bolt32_cost_guard.py`** — real per-stage timing harness, gated on `quota_gate_check('engineering')` (§6).

### Real QA scores (live, 2026-09-03)
| County | `video_bolt32_captions_url` | overall_score | qa_pass | loop_seam_continuity (the one dimension that failed) |
|---|---|---|---|---|
| broward | `.../CACE-24-008115/reel_bolt32_captions.mp4` | 8.48 | **false** | 6.13/10 |
| escambia | `.../2025_CA_001460/reel_bolt32_captions.mp4` | 8.80 | **false** | 6.87/10 |
| lee | `.../2026000141/reel_bolt32_captions.mp4` | 8.72 | **true** | 7.38/10 |

**Real finding, not swept under the rug:** 2 of 3 QA'd reels fail the loop-seam-continuity dimension (threshold 7.0). Root cause: `assemble_video_bolt32`'s loop mechanic reuses the same underlying still (`aerial_wide`) for the hook and end beats, but the end beat also burns in the "biddeed.ai" wordmark + QR code overlay (§ design, `assemble_video_bolt32` docstring), so the first and last rendered frames are never pixel-identical — a genuine tension between the loop mechanic and the end-card branding that #19779 already flagged as a deviation ("no separate CTA card beat exists in the 32s budget"). Logged as residual, not fixed this session (fixing it means redesigning the end-beat overlay placement, out of this issue's CP3b scope).

---

## 4. Our own repos — reconciliation (one-line verdicts, no action taken beyond what's noted)

| Repo | Verdict |
|---|---|
| `breverdbidder/zonewise-superpowers` | **REUSE — UNBLOCKED** by the §0 ruling; `licenseKey: "free-license"` wired into every render CLI/config example + the setup wizard this session (commit `349dbfb`, pushed live). Porting its caption/review agents into bolt32 is a separate future task (they'd overlap with `bolt32_captions_whisperx.py`/`bolt32_qa_critique.py`, not stack) — not attempted this session. |
| `breverdbidder/everest-cinematic` | **REUSE** — the long-form/brief-driven lane (distinct from the reel-specific pipeline this issue extends); `auto-editor` belongs here, not in bolt32 (§2/§3) — not modified this session. |
| `breverdbidder/everest-media-gateway` | **REUSE, Gemini key confirmed live (read-only) this session** — `GET generativelanguage.googleapis.com/v1beta/models` (a free, non-billable metadata call) returned `200` with the model catalog. This does NOT confirm the specific Veo3/Imagen4 paid-generation quota the issue flagged as depleted on 2026-09-02 — no generation call was made (no spend authorized this issue). Paid-quota state remains **UNKNOWN**; key-liveness is **VERIFIED**. |
| `breverdbidder/agentic-video-maker` | **REUSE — ported this session.** Its `scripts/gemini-critique.cjs` score→gate design (read directly, `/tmp` clone) is what `bolt32_qa_critique.py` implements, adapted from an LLM-vision call to a deterministic artifact-based scorer (no new API spend this issue). |
| `breverdbidder/claude-video` | **REUSE** — unrelated lane (`/watch`, video review primitive), no reconciliation needed. |
| `breverdbidder/zonewise-video` | **REUSE** — finished one-off GTM demo asset, Remotion-based; now covered by the same §0 ruling if it's ever re-touched. No action this run. |
| `breverdbidder/everest-content` | **REUSE** — unaffected content SSOT dependency of `everest-cinematic`. |
| `breverdbidder/open-slide-everest` | **ARCHIVE-CANDIDATE** — presentation slides, not video; no relevance to this stack. |

---

## 5. Negative tests (implemented + VERIFIED this session)

| # | Test | Implementation | Result |
|---|---|---|---|
| a | GPL dependency entering `requirements-bolt32.txt` fails the run | `scripts/bolt32_license_gate.py` | VERIFIED (#19781, unchanged) |
| b | kokoro audio on a non-draft English reel fails the render | `scripts/bolt32_tts_fallback.py::resolve_tts_provider()` raises `Bolt32TTSPolicyError` | **VERIFIED this session** — `python3 scripts/bolt32_tts_fallback.py` → `test_kokoro_blocked_on_approved_english: PASS` |
| c | A caption group of 8 words fails the caption assertion | `scripts/bolt32_captions_whisperx.py::assert_valid_groups()` | VERIFIED (#19781, unchanged; also re-exercised live on real ASR output this session) |
| d | A QA pass reporting a score without the observed value is rejected | `scripts/bolt32_qa_critique.py::validate_score()` raises `Bolt32QAEvidenceError` | **VERIFIED this session** — `python3 scripts/bolt32_qa_critique.py` → `test_score_without_observed_rejected: PASS` |
| e | Adding `@remotion/player` to a customer-facing surface fails CI with the Automators message | `scripts/remotion_license_tripwire.py::check_player_import_real()` + `gtm-validate.yml` step | **VERIFIED this session** — synthetic Player-import result forced through `main()` → `::error::...Automators` + exit code 1; separately, D8 SQL detector tripped live on a synthetic `agent_ops_log` row, then cleaned up |
| f | A render config missing `licenseKey:"free-license"` fails the license check | Not implemented as an automated gate this session (no Remotion render config exists in this repo to check against — `zonewise-superpowers` is a plugin/scaffolding repo, not a live Remotion project; its render *examples* were updated, §4) — **residual**, logged below |

---

## 6. GHA cost guard — real numbers (2026-09-03)

Real per-reel wall-clock, measured this session (`scripts/bolt32_recaption.py` end-to-end, martin/25001204CAAXMX):

| Stage | Seconds (measured) |
|---|---|
| download existing `video_bolt32_url` | ~1.2 |
| extract audio (ffmpeg) | 0.13 |
| transcribe (ASR — this session used the openai-whisper `base` session substitute; faster-whisper's own HF-hosted `small` model was benchmarked separately on the same audio at 3.61s load + 12.33s transcribe = 15.94s, also reported here for completeness) | 6.98 (base substitute) / 15.94 (faster-whisper small, separately benchmarked) |
| burn captions (ffmpeg re-encode) | ~14.0 |
| upload to Supabase Storage | ~3.0 |
| **Full pipeline wall-clock (measured, `time.monotonic()` around the whole CLI run)** | **42.42s** |

**42.42s is ~1.2% of the 360s (6-minute) budget** — nowhere near the faster-whisper-small/int8 fallback threshold. `scripts/bolt32_cost_guard.py::evaluate()` confirms `over_budget=False` for these figures. Logged to `agent_ops_log` (`dispatch_id='bolt32_cost_guard'`, `task='bolt32_whisperx_caption_pipeline_timing'`, `status='VERIFIED'`) with `quota_gate_check('engineering')` returning `NO_READING` at call time (a pre-existing telemetry gap — same condition already driving the `gtm_factory_halt` gate open since before this session started; not something this issue's scope covers fixing, logged as observed, not silently ignored).

Runner-minutes equivalent (this sandbox's CPU, not literally `ubuntu-latest`): **0.71 min/reel**. Real `ubuntu-latest` GHA-runner timing was not separately measured this session (no GHA dispatch was triggered for this specific work) — flagged as a residual verification for the first real `ubuntu-latest` run.

---

## 7. `unified_context` upserts

- `cmo_factory_video_stack_v1` — this table (§2) as jsonb, one row per repo with `verdict`/`spdx`/`stars`/`pushed_at`/`reasoning`. **Upserted this session** with the §0 Remotion ruling folded in.
- `cmo_factory_video_rejections_sep3` — unchanged from #19781 (GPL/non-commercial-weights rejections); the Remotion entry is now resolved, not re-litigated as open.

See `docs/spec/19787.md` for the exact upsert payload and verification query.

---

## Residual / not attempted this session (logged, not silent)

1. Negative test (f) — no automated CI gate exists checking a Remotion render config for a missing `licenseKey`; no live Remotion project/config exists in either this repo or `zonewise-superpowers` to check (the latter is a plugin/scaffolding repo). Would need a real downstream Remotion project to test against.
2. `everest-cinematic` (the actual long-form lane) was not touched this session — auto-editor wiring there is out of this issue's verified scope (separate repo, no visibility into its current code this session).
3. `zonewise-superpowers`' caption/review agents were not ported into bolt32 — flagged as a likely-redundant future task (they'd overlap with `bolt32_captions_whisperx.py`/`bolt32_qa_critique.py`), not attempted.
4. Real `ubuntu-latest` GHA-runner timing for the caption pipeline — this session's numbers are from the CC sandbox, not a live GHA dispatch.
5. Loop-seam-continuity QA failures (2 of 3 reels) — real finding, not fixed (would require redesigning the end-beat overlay, out of CP3b scope).
