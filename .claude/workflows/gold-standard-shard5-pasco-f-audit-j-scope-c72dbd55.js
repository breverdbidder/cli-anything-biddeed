export const meta = {
  name: 'pasco-f-audit-and-j-scope',
  description: 'Adversarially verify F circular-denominator finding for pasco; investigate J ghost-fill blast radius fleet-wide (read-only)',
  phases: [
    { title: 'Verify F' },
    { title: 'Investigate J scope' },
  ],
}

phase('Verify F')
const SUPA_CONTEXT = `
You have Supabase env vars SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY available in your shell.
Query via PostgREST REST API using curl or python3+httpx, e.g.:
curl -s "$SUPABASE_URL/rest/v1/<table>?<filters>" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
Use header "Prefer: count=exact" with a HEAD request to get exact row counts cheaply (Content-Range response header).
Do NOT print the key value itself in your output.
`

const verifyPrompt = `${SUPA_CONTEXT}
Independently determine the TRUE coverage of Gold Standard criterion F ("tier1 sold-amount verification >=95% of closed") for county=pasco.

Background: the live evaluator RPC public.pencil_dod_evaluate_county('pasco') reports F as
"tier1_sold=58 closed_sold=58" -> 100.0% PASS. This is suspicious because it mirrors criterion B's
already-confirmed circular-denominator bug (B's "closed_sold=58" was found to equal the row count of
tax_deed_outcomes itself, not the true closed-auction universe).

Your job: compute F's TRUE denominator independently, from first principles, using multi_county_auctions
for county=pasco. Determine the count of auctions that are genuinely closed (use the auction_status field;
values of interest are likely 'sold', 'closed', 'redeemed' -- confirm by querying distinct values and counts
yourself, don't take this list on faith). That is the TRUE denominator for "how many closed auctions should
have a verified sold amount".

Then determine the TRUE numerator: how many of those genuinely-closed rows carry a real independently-verified
tier1 sold amount (check the tier1_sold_amount column, and cross-reference against the county_3p tax_deed_outcomes
table's winning_bid values to confirm these aren't fabricated/circular).

Report: true numerator, true denominator, true percentage, and an explicit verdict: does the live F=100.0%
claim survive being reproduced from true first principles, or is it a circular-denominator artifact
(numerator and denominator both equal to the same closed-loop count, e.g. tax_deed_outcomes row count) like B?
Show your exact queries and counts. Be blunt if it's the same bug.`

const verifyFinding = await agent(verifyPrompt, { label: 'verify-F', phase: 'Verify F' })

const refuterPrompt = `${SUPA_CONTEXT}
You are an ADVERSARIAL REFUTER. Your only goal is to try to break the following claim about Gold Standard
criterion F for county=pasco. Do not assume it is correct. Run your own fresh live queries against
multi_county_auctions and tax_deed_outcomes for county=pasco -- do not reuse any numbers below, recompute
them yourself from scratch.

CLAIM TO REFUTE:
"""
${verifyFinding}
"""

Specifically try to find any of these failure modes in the claim: wrong table/column used, wrong filter,
off-by-one, miscounted auction_status values, confusing 'tier1_sold_amount not null' with genuinely-verified
(vs. carried-over/estimated) amounts, or any reason the true F percentage might actually be within the
EVALUATOR V6 95-105% pass band after all.

Report a clear verdict: SURVIVES (the circular-denominator finding holds up, true F coverage is genuinely
far outside 95-105%) or DOES NOT SURVIVE (the original claim was wrong, and explain exactly why with your
own numbers). Cite your own query results as evidence either way.`

const refuterFinding = await agent(refuterPrompt, { label: 'refute-F', phase: 'Verify F' })

phase('Investigate J scope')
const jScopePrompt = `${SUPA_CONTEXT}
READ-ONLY investigation, do not write/update/delete anything.

Background: a prior audit found that in county=pasco, roughly 100 of 643 fresh bid_decisions rows are
"ghost-fill" -- byte-identical ARV=124000.0, max_bid=33200.0, CMA values, factor scores, and near-identical
timestamps stamped across unrelated properties in different cities, all carrying arv_source (or a similar
provenance column) referencing 'shapira_formula_shard9_j_gen'. This looks like a batch-fill script that
fabricated deal-triangle data rather than computing it per-property, violating the never-fabricate guardrail.

Your job: query the bid_decisions table (and any provenance/source column you find on it, e.g. arv_source,
data_source, or similar -- inspect the table schema first via a small sample row) FLEET-WIDE (not just pasco)
to size the blast radius of this fabrication signature. Specifically:
1. Confirm the exact column name that identifies the shard9_j_gen generator run.
2. Count total bid_decisions rows fleet-wide carrying that provenance value.
3. Break the count down by county.
4. Sample a few rows from 2-3 different counties and confirm whether the ARV/max_bid/CMA values really are
   byte-identical duplicates across unrelated properties (report a couple of concrete examples: case_number/
   property + values, to prove it rather than just asserting it).

Report the findings as: total affected rows, counties affected (with per-county counts), and 2-3 concrete
duplicate examples as evidence. This is pure investigation to size the problem before any fix is attempted --
do not attempt any fix or cleanup.`

const jScope = await agent(jScopePrompt, { label: 'j-scope-investigation', phase: 'Investigate J scope' })

return { verifyFinding, refuterFinding, jScope }
