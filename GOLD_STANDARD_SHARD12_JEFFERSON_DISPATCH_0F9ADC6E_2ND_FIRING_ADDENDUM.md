# Gold Standard shard-12: jefferson — 2nd firing addendum

dispatch_id: 0f9adc6e-3318-4b04-b0bd-119b07405d40 (same dispatch, re-fired)
mode: ULTRALOOP native (ultracode opt-in this turn — Workflow fan-out: 3 blind finders + 3 independent
adversarial refuters)

## Result: still unchanged at 8/10 (A,C,D,E,G,H,I,J PASS; B,F FAIL). No new lever found. BLANK > WRONG.

### Live state at start of this firing (`pencil_dod_evaluate_county('jefferson')`)
Identical to the original session report: B FAIL metric=null [verified=0 closed_sold=0], F FAIL
metric=null [tier1_sold=0 closed_sold=0], auctions_total=3. No drift since the first firing — the
underlying blocker (case 25-CA-164 sold_amount is unavailable from any independent source) has not
resolved on its own.

### What this firing did differently
Rather than re-attempt the 4 sources already refuted in this dispatch's first firing (Civitek OCRS,
myfloridacounty ORI, qpublic 403, jeffersonclerk PDF — all still genuinely blocked, not re-tested), I
checked 9 additional avenues before concluding, the last 3 via a dedicated adversarial Workflow
(3 blind finder agents + 3 independent refuter agents, each doing live re-fetches, one via headless
Playwright to rule out curl-only false negatives):

1. **FL GIO cadastral SALE_PRC1/SALE_YR1 fields** — queried live: 0/0/blank. `ASMNT_YR=2025` — this
   dataset is last year's DOR tax roll and structurally predates the 2026-06-25 sale. Not a processing
   lag, a wrong-dataset problem; will not resolve until (at earliest) the 2027 NAL refresh.
2. **jeffersonclerk.com direct records-search / official-records pages** — no in-house search tool;
   both routes funnel only to the already-blocked myfloridacounty.com/orisearch/33.
3. **floridaparcels.com** — third-party aggregator, mirrors the same stale DOR snapshot.
4. **Jefferson County Clerk surplus/unclaimed-funds list** — does not exist on jeffersonclerk.com
   (some FL clerks, e.g. Sumter/Columbia, publish one; Jefferson does not).
5. **RealtyTrac / Zillow / Redfin / floridacourtaccess.org** — RealtyTrac shows only a stale
   pre-foreclosure listing price ($157,174, not a sold amount); Zillow 403s; Redfin 405s; 
   floridacourtaccess.org requires paid account registration before any search — none is a usable
   free independent source.
6. **Pre-Turnstile API/feed probe on Civitek OCRS + myfloridacounty** — no unguarded JSON/sitemap/RSS
   endpoint exists on either vendor; Turnstile is embedded in page HTML before search on Civitek;
   myfloridacounty's orisearch is a recorded-instruments index (deeds/liens), not a court-case-
   disposition index, so it structurally could not carry a Certificate of Title sale price even if
   unblocked.
7. **archive.org Wayback CDX** for jeffersonclerk.com / civitekflorida.com / myfloridacounty.com — 50+
   Civitek snapshots and 2000+ jeffersonclerk URLs inspected; every foreclosure/tax-deed document
   found is a pre-sale "Pending Sales" PDF; zero results/disposition/certificate-of-title pages were
   ever archived for any case.
8. **Jefferson County Property Appraiser's own ArcGIS org** (`bcrouch_JCPA`, distinct from the FL GIO
   statewide layer) — genuinely new, correctly located, live, reachable (HTTP 200), confirmed to
   contain the exact target parcel. But its 131 layers carry zero sale-price/sale-date/grantor/grantee
   fields (geometry + ownership + tax-district + mass-appraisal fields only); `FIRSTOWNER` still shows
   the pre-sale owner, confirming the appraiser hasn't processed the sale yet either.
9. **fltreasurehunt.gov (FL DFS unclaimed property)** — reachable (not WAF-blocked, contra an initial
   finder claim corrected by its refuter), but a client-side SPA unqueryable via curl, and structurally
   too early regardless: FL's statutory surplus-funds reporting lag to the state is ~1 year, this sale
   is 1 month old.

All 3 refuter agents returned **NOT_VIABLE, 3/3, unanimous** after independently re-fetching every
candidate (one used a real headless-Chromium/Playwright session specifically to rule out curl-only
false negatives on Zillow/Redfin/Civitek). No genuinely viable new source survived adversarial
verification. No sold_amount was fabricated.

### Verification protocol followed
- `pencil_dod_evaluate_county('jefferson')` re-run live before and after this firing's work — identical
  both times, pasted above.
- 2 new rows written to `gold_standard_ultraloop_audit` (ids 8100, 8101; `dispatch_id=0f9adc6e...`,
  `letter=B`/`F`, `survived=false`, `ultraloop_mode=native`), carrying the full 9-source evidence list
  and the 3/3 unanimous refuter verdicts, so this second exhaustion pass is on record and won't be
  silently re-attempted without genuinely new evidence.
- `gold_standard_loop()`/`gold_standard_certify()` not run — jefferson is not close to 10/10 (2 FAIL
  letters, same root cause) and the parallel-fleet rule defaults to per-county evaluation when other
  shards' mid-flight status isn't confirmed (this session did not check).

### Escalation status: unchanged from the original session report
Same two options, still outside this session's authority: a paid court/official-records API (not
covered by the existing ARM-2 pre-authorization, which is scoped to retail-comps for criterion J), or
a one-time manual CAPTCHA solve to seed this single fact (jefferson is low-volume — 3 total auctions —
so per-case manual seeding may be more practical than building unattended infrastructure that cannot
be wired to a cron per the WIRING MANDATE).

### Honesty Protocol tags
- 9 additional avenues checked and refuted this firing, 3/3 independent adversarial verdicts NOT_VIABLE:
  **VERIFIED** (live re-fetches by both finders and refuters, evidence in `gold_standard_ultraloop_audit`
  ids 8100/8101).
- No sold_amount/winning-bidder recoverable from any of the 9 sources: **VERIFIED**.
- Paid-API or manual-solve remain the only real unblock levers: **INFERRED** (unchanged from the
  original session report — no new information this firing changes that assessment).
