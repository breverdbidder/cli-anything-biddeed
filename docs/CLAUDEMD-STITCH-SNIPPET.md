# ── StitchWise V2 Pipeline (added 2026-03-25) ──

## Stitch Integration
```mermaid
graph LR
    BG[BrandGuard] -->|brand_kit.json| PW[PromptWise]
    PW -->|gemini-optimized prompt| SW[StitchWise V2]
    SW -->|SDK call| API[stitch.googleapis.com/mcp]
    API -->|HTML+screenshot| DS[DesignScore]
    DS -->|score≥8.5| CC[Claude Code]
    DS -->|score<8.5| PW
    CC -->|deploy| CF[Cloudflare Pages]
```

## Stitch Config
```yaml
sdk: "@google/stitch-sdk"
mcp: "@_davideast/stitch-mcp proxy"
auth: GEMINI_API_KEY (env)
budget: 300 gen/mo (350 limit - 50 reserve)
circuit_breaker: 3 retries/design
brand: navy=#1E3A5F, orange=#F59E0B, bg=#020617, font=Inter
commands: generate | list | export | dashboard | landing
```
