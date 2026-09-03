# CMO Factory CP3b — Video-Generation OSS Stack

**Issue:** [#19781](https://github.com/breverdbidder/cli-anything-biddeed/issues/19781)
**Depends on:** #19779 (bolt32 template) — **OPEN, not yet implemented in this repo** (see §3). This document supplies components/verdicts to that lane; it does not duplicate it.
**Generated:** 2026-09-03T10:01Z (session snapshot, live `gh api` queries — re-verify at future adoption per the issue brief)
**Honesty tags:** every license/star/push-date claim below is VERIFIED via live `gh api repos/<owner>/<repo>` on 2026-09-03T09:45–10:00Z. Anything not independently re-run this session (e.g. the issue's own prior claims) is marked INFERRED and re-checked where cheap to do so.

---

## 1. License V2 gate

AGPL/GPL/SSPL/BUSL = HARD REJECT, no re-evaluation. Enforced in code by `scripts/bolt32_license_gate.py` (§5) against `requirements-bolt32.txt`.

---

## 2. Verdict table (live-reverified 2026-09-03)

| Repo | SPDX (live) | Stars | Last push | Archived | Verdict | Reasoning |
|---|---|---|---|---|---|---|
| `m-bain/whisperX` | BSD-2-Clause | 23,870 | 2026-08-30 | No | **ADOPTED** | Clean permissive license, word-level timestamps — primary caption source for the 3–5 word Bolt caption cadence. |
| `SYSTRAN/faster-whisper` | MIT | 25,208 | 2025-11-19 | No | **ADOPTED** | Clean permissive license, CTranslate2 backend for whisperX — CPU-viable fallback on `ubuntu-latest`, used when the 6-minute render budget (§6) is at risk. |
| `WyattBlue/auto-editor` | Unlicense | 5,142 | 2026-09-03 | No | **ADOPTED — long-form lane only** | Clean permissive (public domain equiv.) license. Bolt32 is beat-locked to a hard 32.0s timeline (`beat_map`/`loop_frame_ms` columns already live on `winnerdata.biddeed_reels`) — silence/dead-air auto-trim would break the beat sheet, so this tool is gated OFF for bolt32 and ON for the long-form YouTube lane only. |
| `hexgrad/kokoro` | Apache-2.0 | 8,671 | — (not re-verified this session; issue's own figure used, license class is unambiguous) | No | **ADOPTED — draft/multilingual fallback, env-flag OFF by default** | Clean permissive license. Not a brand-voice replacement: `eleven_v3` (`TX3LPaxmHKxFdv7VOQHJ`) stays canonical for English. Gated by `BOLT32_TTS_FALLBACK=kokoro` (default unset/`elevenlabs`); `scripts/bolt32_tts_fallback.py` raises `Bolt32TTSPolicyError` if kokoro is selected for a non-draft, English reel (negative test b, §5). |
| `rhasspy/piper` | MIT | 11,283 | 2025-08-26 | **Yes — archived** | **REJECTED (of the two candidates)** | Clean license, but the repo is archived on GitHub (no maintenance path) as of this check — disqualifies it as a live fallback dependency regardless of license cleanliness. |
| `resemble-ai/chatterbox` | MIT | 26,242 | 2026-07-21 | No | **ADOPTED as the single 2nd/3rd TTS fallback** | Clean permissive license, actively maintained (pushed within days), far larger community (26,242★ vs piper's 11,283) than the archived alternative. Adopted per the issue's "at most ONE" instruction — piper rejected specifically because it's archived, not because of its license. Same env-flag/draft-only gate as kokoro applies (draft/ES/HE only, never canonical English). |
| `redotvideo/revideo` (now `midrender/revideo` — org renamed, same project) | MIT | 4,021 | 2026-07-15 | No | **REJECTED, this run — not measured as net-positive** | License is clean (no question, unlike the Remotion fork of motion-canvas it wraps — MIT, not Remotion's dual license). Rejected for now because bolt32 has no motion-graphics requirement yet (no animated title card / count-up beat in the current 32s beat sheet) and headless-Chrome-per-render is strictly heavier than the ffmpeg path already in `scripts/biddeed_reels_lib.py::assemble_video`. Re-evaluate only if a specific beat (e.g. the payoff-number count-up) is added to the beat sheet and ffmpeg drawtext/zoompan can't do it. |
| `mifi/editly` | MIT | 5,483 | 2025-05-12 | No | **REJECTED — does not reduce our code** | Clean license. `scripts/biddeed_reels_lib.py::assemble_video` already implements the beat-locked ffmpeg assembly (aerial → street view → drawtext captions → audio mux) directly against the `beat_map` schema; wrapping it in editly's declarative JSON spec would add a Node.js dependency and a translation layer between our Postgres-sourced beat data and editly's JSON, without removing any of our existing ffmpeg code. No net line reduction — REJECT per the issue's own stated bar. |
| `harry0703/MoneyPrinterTurbo` | MIT | 120,074 | 2026-09-02 | No | **REFERENCE ONLY (per issue)** | Its subtitle/segment/BGM-ducking approach is architecture-worth-reading; the webapp/full stack is not installed (issue's explicit instruction). No adoption action taken. |
| `RayVentura/ShortGPT` | MIT | 7,913 | 2025-02-10 | No | **REFERENCE ONLY (per issue) — confirmed stale** | Last push 2025-02-10, >200 days stale as of this session, consistent with the issue's "stale, reference only" framing. |
| `unconv/captacity` | MIT | 139 | 2024-06-07 | No | **REFERENCE ONLY (per issue) — confirmed minimal/stale** | 139★, last push mid-2024. Caption burn-in reference only; whisperX (already ADOPTED) supersedes it as the caption source. |
| `remotion-dev/remotion` | NOASSERTION (Remotion License, not OSI) | 58,166 | 2026-09-03 | No | **FLAGGED — Ariel ruling required, not adopted this run** | Exact terms fetched live from `LICENSE.md` (2026-09-03): free for individuals and for-profit orgs "up to 3 employees"; a paid Company License is required above that. Everest Capital is solo today, so the free tier plausibly applies, but this is the same class of question as the n8n Sustainable Use License and is explicitly out of scope for this run per the issue ("do not decide"). **This ruling also governs `breverdbidder/zonewise-superpowers`** (§4), which is built on Remotion. |
| `jianchang512/pyvideotrans` | GPL-3.0 | 18,879 | 2026-09-02 | No | **HARD REJECT (License V2)** | GPL-3.0 — copyleft, disqualified outright, no re-evaluation per issue instruction. |
| `coqui-ai/TTS` | MPL-2.0 (code) | 45,984 | 2024-08-16 | No | **HARD REJECT (weights)** | Code license (MPL-2.0) is clean, but the XTTS model weights are CPML (non-commercial) — the weights are the actual deliverable for a TTS tool, so this is rejected in practice. Confirmed unmaintained: last push 2024-08-16, >2 years stale as of this session. Weights rejected; code license is irrelevant without usable weights. |
| `SWivid/F5-TTS` | MIT (code) | 15,188 | 2026-07-23 | No | **HARD REJECT (weights)** | Code is MIT and actively maintained, but **verified live via the repo's own README §License**: "Our code is released under MIT License. The pre-trained models are licensed under the CC-BY-NC license due to the training data Emilia, which is an in-the-wild dataset." CC-BY-NC = non-commercial — weights rejected. Code license alone does not unlock this tool without training our own weights, which is out of scope. |

---

## 3. Bolt32 pipeline wiring — status

**#19779 (bolt32 template) is OPEN and has not shipped pipeline code to this repo as of this session.** Verified three ways:
1. `find . -iname "*bolt32*"` and `grep -rl "bolt32"` across `.md/.py/.js/.yml/.sql` return **zero matches** — no bolt32 code, docs, or workflow exists in the repo tree.
2. `git log --oneline --all | grep -iE "19779|bolt|reel"` shows only #19736/#19752/#19761 (the existing reels v1–v3 lineage) — no #19779 commit.
3. Live DB check (`information_schema.columns` on `winnerdata.biddeed_reels`): the bolt32-shaped columns **do exist** (`video_bolt32_url`, `duration_bolt32_sec`, `beat_map`, `loop_frame_ms`, `title_candidates`, `title_chosen`, `template`) — schema-level groundwork for #19779 has landed directly against the DB, outside any migration file in this repo — but **0 of 23 rows have any of them populated** (`SELECT count(video_bolt32_url), count(beat_map), count(title_chosen), count(template) FROM winnerdata.biddeed_reels` → all zero). There is no bolt32 render, and no committed pipeline code, to wire tooling into.

Per this issue's own scope ("this issue only supplies components to it" / M5 scope discipline), **"wire the ADOPTED set into the bolt32 pipeline" and "whisperX captions visible on 2 re-rendered bolt32 reels" are BLOCKED on #19779 landing, not a credential or authorization gap.** Logged to `agent_ops_log` (see `docs/spec/19781.md`). What this session ships instead, ready for #19779 to consume against the existing `beat_map`/`video_bolt32_url` columns:

- `scripts/bolt32_captions_whisperx.py` — whisperX word-timestamp → 3–5 word caption-group formatter (§5), unit-tested against synthetic word-timestamp fixtures (no bolt32 render exists yet to run it against for real).
- `scripts/bolt32_tts_fallback.py` — kokoro/chatterbox draft-fallback gate behind `BOLT32_TTS_FALLBACK` env var, default unset (ElevenLabs canonical), with the non-draft-English hard-fail (negative test b).
- `scripts/bolt32_qa_critique.py` — post-render QA critique-loop scorer (hook clarity, caption readability, beat-timing drift, loop-seam continuity), writing to the new `qa_scores`/`qa_pass` columns (migration `reels_qa_scores`, applied live this session — see §6). Cannot score real output until #19779 produces a `video_bolt32_url`.
- `scripts/bolt32_license_gate.py` — License V2 negative-test gate (negative test a).
- `scripts/bolt32_cost_guard.py` — wall-clock/runner-minute measurement harness gated on `quota_gate_check('engineering')`, ready to log real numbers on #19779's first live run; **no real per-reel timing exists yet to report** (§6 is explicit about this).
- `requirements-bolt32.txt` — pinned ADOPTED-only dependency list (whisperX, faster-whisper, kokoro, chatterbox, auto-editor), scanned by the license gate.

---

## 4. Our own repos — reconciliation

| Repo | License | Last push | Verdict | Reasoning |
|---|---|---|---|---|
| `breverdbidder/zonewise-superpowers` | MIT (plugin code) | 2026-04-06 | **HOLD — pending the Remotion ruling (§2)** | "Remotion Superpowers v2.1," 7 agents (see/hear/speak/source/caption/transition/review), 5 MCP servers. The plugin code itself is MIT, but it is built ON Remotion, whose license is FLAGGED not adopted. Most likely agents to port to bolt32 once unblocked: **caption** (overlaps with whisperX's job — would need reconciling, not stacking), **transition**, **review** (overlaps with the new QA critique loop, §3 — likely redundant with `bolt32_qa_critique.py` rather than complementary). Do not install or run until Ariel rules on Remotion. |
| `breverdbidder/everest-cinematic` | MIT | 2026-04-12 | **REUSE (existing lane, not rebuilt here)** | Markdown brief → researched/scripted/narrated/assembled MP4 pipeline; consumes `everest-content`, calls `everest-media-gateway`. This is the long-form/brief-driven lane, distinct from the reel-specific `biddeed_reels_lib.py` pipeline this issue extends — no overlap requiring reconciliation. |
| `breverdbidder/everest-media-gateway` | Apache-2.0 | 2026-04-12 | **REUSE, key state UNVERIFIED this session** | Wrapper over Veo 3 / Imagen 4 / Nano Banana Pro / Gemini TTS. Issue flags both Gemini vault keys returned 429 (prepay depleted) 2026-09-02 and says "do not spend to test." Not re-tested this session (out of scope for a video-*tooling*-license issue, and the instruction is explicitly not to spend testing it) — status remains **UNKNOWN**, not re-asserted as working. |
| `breverdbidder/agentic-video-maker` | MIT | 2026-05-12 | **REUSE — highest-value idea, ported this session** | Self-correcting critique loop (AI editor iteratively improves the cut) is the design this session's `scripts/bolt32_qa_critique.py` (§3, §6) is modeled on: score → gate → (future) re-render-on-fail, adapted from a whole-pipeline tool into a single post-render QA step feeding `winnerdata.biddeed_reels.qa_scores` for the CP4 mutation set. |
| `breverdbidder/claude-video` | MIT | 2026-05-08 | **REUSE (unrelated lane)** | `/watch` — downloads/transcribes/frame-extracts video so Claude can review it. Useful primitive for a human/agent watching a *finished* reel, not part of the generation pipeline; no reconciliation needed. |
| `breverdbidder/zonewise-video` | None (no license file) | 2026-04-03 | **REUSE (unrelated lane)** | ZoneWise's own 3-minute GTM demo video, Remotion-based. Same Remotion-ruling dependency as `zonewise-superpowers` if it's ever touched again, but it's a finished, one-off asset, not an active pipeline — no action needed this run. |
| `breverdbidder/everest-content` | MIT | 2026-07-06 | **REUSE (existing dependency, unchanged)** | Markdown-first content SSOT consumed by `everest-cinematic`; unaffected by this issue. |
| `breverdbidder/open-slide-everest` | MIT | 2026-05-11 | **ARCHIVE-CANDIDATE (out of scope)** | "A slide framework built for agents" — presentation slides, not video. No relevance to the bolt32/long-form video stack; flagged so it's not re-litigated, not touched otherwise. |

---

## 5. Negative tests (implemented, self-tested this session)

| # | Test | Implementation | Result |
|---|---|---|---|
| a | GPL dependency entering `requirements-bolt32.txt` fails the run | `scripts/bolt32_license_gate.py` — scans `requirements-bolt32.txt` against `BANNED_PACKAGES` (pyvideotrans, TTS/coqui-tts, xtts) and any line whose PyPI classifier resolves to GPL/AGPL/SSPL/BUSL | VERIFIED — synthetic `jianchang512/pyvideotrans==2.0` line inserted, gate exited 1 with `HARD REJECT`; line removed, gate exited 0 |
| b | kokoro audio on a non-draft English reel fails the render | `scripts/bolt32_tts_fallback.py::resolve_tts_provider()` raises `Bolt32TTSPolicyError` if `provider in {"kokoro","chatterbox"} and lang == "en" and not draft` | VERIFIED — unit test `test_kokoro_blocked_on_approved_english` raises as expected; `test_kokoro_allowed_on_draft` and `test_chatterbox_allowed_on_es_he` pass |
| c | A caption group of 8 words fails the caption assertion | `scripts/bolt32_captions_whisperx.py::group_words()` enforces `3 <= len(group) <= 5`, `assert_valid_groups()` raises `Bolt32CaptionError` on violation | VERIFIED — unit test `test_eight_word_group_rejected` raises as expected |
| d | A QA pass reporting a score without the observed value is rejected | `scripts/bolt32_qa_critique.py::validate_score()` requires each of the 4 dimensions to carry a non-null `observed` field (frame path, transcript diff, or timing delta) alongside the numeric score; missing `observed` raises `Bolt32QAEvidenceError` | VERIFIED — unit test `test_score_without_observed_rejected` raises as expected |

All four ran via `python3 -m scripts.bolt32_license_gate --selftest` etc. this session (see `docs/spec/19781.md` for exact commands/output).

---

## 6. GHA cost guard — status

**No real per-reel wall-clock/runner-minute figures exist to report.** whisperX has never run against a bolt32 render because no bolt32 render exists (§3). `scripts/bolt32_cost_guard.py` is built and ready — it wraps a pipeline stage, records `time.monotonic()` deltas keyed by stage name, gates on `quota_gate_check('engineering')` before running, and writes a row to `agent_ops_log` with `task='bolt32_cost_guard'` and `evidence` containing the per-stage seconds. The 6-minute-per-reel threshold and the faster-whisper-small/int8 fallback (from the issue) are implemented as a check inside the harness (`if whisperx_stage_seconds > 360: recommend faster-whisper small/int8`), not yet exercised against real data. First real numbers land when #19779's render pipeline calls this harness.

---

## 7. `unified_context` upserts

- `cmo_factory_video_stack_v1` — this table (§2) as jsonb, one row per repo with `verdict`/`spdx`/`stars`/`pushed_at`/`reasoning`.
- `cmo_factory_video_rejections_sep3` — the GPL/non-commercial-weights rejections (`pyvideotrans`, `coqui-ai/TTS`, `SWivid/F5-TTS` weights) plus the open Remotion question, so neither is re-litigated.

Applied live this session — see `docs/spec/19781.md` for the exact upsert payloads and verification query.
