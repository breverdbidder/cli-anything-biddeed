# docs/spec/ — second link of the artifact chain

One `<issue-number>.md` per dispatched issue, written by CC before it exits
(mandate M6 in docs/intent/MANDATES.md) using TEMPLATE.md. If a spec exists at
dispatch time the wrapper feeds it to CC after the intent and before the body.

Why: intent + spec together must let a fresh agent (new context window, no chat
history) continue the work. The 2026-09-01 FF incident had no artifact between
"what Ariel wanted" and "what CC shipped" — this is that artifact.

Versioning: git only. Never overwrite a prior session's spec; append a dated
"## Session <date>" block.
