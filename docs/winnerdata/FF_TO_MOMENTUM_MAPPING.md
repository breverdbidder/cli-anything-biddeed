# Winner Data FF -> Momentum AMS (NowCerts) field mapping

**Status:** VERIFIED against the live `winnerdata` schema and the public NowCerts API
Postman collection. **Not** verified against a live NowCerts trial account — see
`NOWCERTS_MCP_AUDIT.md` and the LIVE VALIDATION section of the delivery issue for the
credential-gated end-to-end check.

## Schema note (rename completed 2026-08-26)

The parent issue (#19392) brief referenced a pending rename of the `summitleads` schema
to `winnerdata`. As of 2026-08-24 that rename had not landed (`summitleads` held all the
real tables; `winnerdata` existed but was empty). Issue #19486 (2026-08-26) finished it:
`ALTER SCHEMA summitleads RENAME TO winnerdata` ran live, preserving all rows/triggers/
views, and every function/pg_cron job that hardcoded `summitleads.*` was updated to
`winnerdata.*` in the same session. This document and the delivery module
(`pipelines/winnerdata/momentum_delivery.py`) now match the live schema exactly — no
outstanding schema-qualifier drift.

## Endpoint contract sourcing

The endpoint shapes below are **not** taken from `ReduceMyIns/nowcerts-mcp-server-v3` (the
repo the parent brief names as "ReduceMyIns/Nowcerts") — that repo is **empty on GitHub**
(0 bytes, no commits, created 2025-09-27, never pushed to). See `NOWCERTS_MCP_AUDIT.md` for
the full finding. Instead they are sourced from:

1. `ReduceMyIns/Nowcerts-API` — a public Postman collection (`NowCerts Api - Version:
   2.1.5`), the same "public Postman collection" the brief points to at api.nowcerts.com.
2. `ReduceMyIns/n8n-nodes-momentum` (MIT-licensed, real shipped code) — an n8n community
   node that calls the identical `/token`, `/Zapier/InsertProspect`, and
   `/Zapier/InsertTask` endpoints with the same body shapes, confirming the Postman
   collection isn't stale/aspirational.

## Auth

`POST {{BaseURL}}/token`, form-encoded: `grant_type=password&username=...&password=...&client_id=ngAuthApp`.
Response is a standard OAuth2 password-grant token (`access_token`, `refresh_token`).
Every subsequent call sends `Authorization: Bearer <access_token>`.

## Prospect fields (native — `POST /Zapier/InsertProspect`)

| FF key | SSOT | NowCerts field | Transform |
|---|---|---|---|
| `applicant.entity_name.value` | SL | `commercial_name` (business) or `first_name`+`last_name` (person) | Classified business/person by reusing the exact heuristic already in `scripts/winnerdata_render_batch.py`: `\bllc\b\|\binc\b\|\btrust\b\|\bcorp\b\|properties\|construction` (case-insensitive). Person names are split on `, ` (court-record `LAST, FIRST` convention) when both sides are ≤3 words; otherwise the FF's punctuation is stripped and the whole string goes into `first_name` with `last_name` blank (documented lossy fallback — see Residuals). |
| `property.address.value` | MCA | `address_line_1`, `city`, `state`, `zip_code` | Free-text `"STREET, CITY, STATE ZIP"` or `"CITY, STATE ZIP"` (vacant-land shape, no street) is split on commas; state/zip parsed from the trailing segment. This is the **auction-won property**, not a separate mailing address — see Design Decision below. |
| `applicant.contact_email.value` | SL | `email` | Direct. Empty string when null (NowCerts field, not nullable in the sample body). |
| `applicant.contact_phone.value` | SL | `phone_number` | Direct. Also the **delivery-gate signal** — see Gates below. |
| *(constant)* | — | `active` | Always `true`. |
| `product_line` | — | `referral_source` | `f"Winner Data: {product_line}"` — free-text field, no enum in the public contract. |
| *(derived)* | — | `type`, `insuredType` | `2` for business, `1` for person. **INFERRED** — the public Postman sample hardcodes `1` with no enum documentation; `2` for business is an assumption, not verified against a live account. Flagged for confirmation in Phase 5 live validation. |

### Design decision: property address vs. mailing address

The FF carries `applicant.mailing_address` (source FLP, null in all 20 sampled leads —
FLP's owner-address field isn't populated for these parcels) and `property.address` (the
auction-won property, source MCA, always populated). NowCerts' Prospect record has exactly
one address. For a landlord/dwelling policy the risk address (the newly-acquired property)
is what the producer and Quotelinq need front-and-center to prefill a quote — so
`property.address` is used for the Prospect's address fields. If `applicant.mailing_address`
is ever populated by a future FLP source, this should become an `InsuredLocation/Insert`
call instead so the two addresses don't collide; that endpoint exists in the public
collection but is out of scope for this delivery bridge (see Non-Goals).

## Producer task (native — `POST /Zapier/InsertTask`)

| FF key | NowCerts field | Transform |
|---|---|---|
| *(constant + entity_name)* | `title` | `f"Quote-ready Winner Data lead: {entity_name}"` — literal format required by the parent issue's DoD. |
| `producer_message_draft` | `description` | Direct — this is already the producer's call-opener script, unchanged. |
| `readiness_score` | `priority` | `"high"` when `readiness_score >= 70`, else `"medium"`. |
| *(constant)* | `status` | `"New"`. |
| *(constant)* | `completion` | `0`. |
| *(post-insert)* | `insured_database_id` | The `databaseId` returned by `InsertProspect`, threaded into the task body. |

## Everything else -> custom fields (`POST /SimpleCustomField/Insert`, one call per field)

The public NowCerts contract has no native Prospect columns for property characteristics,
purchase context, buyer history, or compliance flags — `SimpleCustomField/Insert` (keyed by
`insuredDatabaseId`, the same ID returned from `InsertProspect`) is the only way to attach
this data so it's visible to the producer and available to Quotelinq prefill. Every field
below carries its FF SSOT tag straight through into the custom field's `text` label.

| FF path | SSOT | Custom field label |
|---|---|---|
| `lead_id` | — | `Winner Data Lead ID` (traceability key back to `winnerdata.leads`) |
| `id` | — | `Winner Data FF ID` (traceability key back to the FF artifact) |
| `property.county.value` | MCA | `Property County` |
| `property.parcel_id.value` | SL | `Parcel ID` |
| `property.address.value` | MCA | `Property Address (Full)` |
| `property.year_built.value` | FLP | `Year Built` |
| `property.sqft.value` | FLP | `Square Footage` |
| `property.num_buildings.value` | FLP | `Number of Buildings` |
| `property.construction_class.value` | FLP | `Construction Class` |
| `property.dor_use_code.value` | FLP | `DOR Use Code` |
| `property.zone_code.value` | FLP | `Zone Code` |
| `property.just_value.value` | FLP | `Just Value` |
| `property.improved.value` | FLP | `Improved` |
| `property.occupancy_status.value` | PC | `Occupancy Status` |
| `purchase.sale_type.value` | MCA | `Sale Type` |
| `purchase.sold_amount.value` | MCA | `Sold Amount` |
| `purchase.auction_date.value` | MCA | `Auction Date` |
| `purchase.case_number.value` | MCA | `Case Number` |
| `buyer_profile.total_wins.value` | ABP | `Buyer Total Wins` |
| `buyer_profile.total_deployed.value` | ABP | `Buyer Total Deployed` |
| `buyer_profile.counties_active.value` | ABP | `Buyer Counties Active` |
| `buyer_profile.is_repeat_investor.value` | ABP | `Is Repeat Investor` |
| `bundle_doctrine.umbrella_quote_requested` | derived | `Umbrella Quote Requested` |
| `bundle_doctrine.umbrella_quote_reason` | derived | `Umbrella Quote Reason` |
| `bundle_doctrine.umbrella_limit` | derived | `Umbrella Limit` |
| `bundle_doctrine.flood_if_indicated` | derived | `Flood If Indicated` |
| `bundle_doctrine.flood_basis` | derived | `Flood Basis` |
| `bundle_doctrine.commercial_bop_if_applicable` | derived | `Commercial BOP If Applicable` |
| `bundle_doctrine.builders_risk_if_renovation` | derived | `Builders Risk If Renovation` |
| `bundle_doctrine.master_policy_conversation` | derived | `Master Policy Conversation` |
| `must_quote` | derived | `Must Quote` (JSON-encoded array) |
| `readiness_score` | derived | `Readiness Score` |
| `missing_required_fields` | derived | `Missing Required Fields` (JSON-encoded array) |
| `product_line` | derived | `Product Line` |
| `compliance.consent_status` | derived | `Consent Status` |
| `compliance.compliance_flag` | derived | `Compliance Flag` |
| `compliance.dnc_scrubbed` | derived | `DNC Scrubbed` |
| `compliance.outbound_lane` | derived | `Outbound Lane` |

`bundle_doctrine.auto_bundle` (always the literal string `"ask_on_call_only"`) is
intentionally **dropped** — it's a static instruction to the producer, not data, and is
already implied by every task landing as a manual producer task rather than an automated
quote submission.

Null-valued fields are skipped entirely (no custom field call for a field the FF marked
missing) rather than sent as an empty-string custom field — an empty custom field would be
indistinguishable from "checked and confirmed empty" versus "never populated," which would
silently destroy the FF's null-vs-unknown distinction that `property.improved`'s own
doctrine note is built around.

## Unmappable fields (explicit disposition)

| FF field | Disposition |
|---|---|
| `schema_version`, `generated_at` | Dropped. Pipeline metadata, not producer- or carrier-relevant. |
| `applicant.mailing_address` | Dropped when null (always null in the 20-lead sample — FLP has no owner-address source populated yet). If populated in future data, route to `InsuredLocation/Insert` instead of overloading the Prospect's single address (see Design Decision above) — not implemented in this delivery bridge (Non-Goal). |
| `applicant.contact_name` | Dropped — duplicates `entity_name` in every sampled FF; the template's own generator sets both to the same value. |
| `org_id` | Carried in `meta` for internal dedupe/logging use only, not sent to NowCerts (no agency-multi-tenant field in the public Prospect contract). |

## Delivery gate (standing deliverability rule)

Two conditions block delivery to Momentum entirely — the FF is still fully transformed
for the fixtures artifact (so the payload can be inspected/audited), but `deliver()` never
calls NowCerts:

1. **`property.num_buildings.value == 0`** (FLP-confirmed vacant land) — `reason:
   "vacant_land"`. Note this is distinct from `num_buildings` being `null` (FLP has no row
   for the parcel at all, an unknown, not a confirmed vacancy) — nulls are **not** gated.
2. **`applicant.contact_phone.value` is null** — `reason: "non_tracerfy_verified_phone"`.
   **INFERRED**: the `winnerdata` schema has no dedicated "Tracerfy-verified" boolean
   column. `contact_phone` in this template is sourced exclusively as `"SL"` (per
   `sources_legend`: "winnerdata.leads / Tracerfy skip-trace data already purchased"), so
   a non-null value is the only signal this schema exposes that Tracerfy resolved a real
   number for the lead. If a future schema change adds an explicit verification column or
   timestamp, gate on that directly instead of phone-presence.

Live distribution across the 20 currently-filled FFs (`winnerdata/intake/*.json`,
2026-08-24): **4 eligible** (PAFFORD_PROPERTIES_CONSTRUCTION ×2, RANDY_COUNTS, ROJOPA_LLC),
**2 vacant_land** (DAVID_RABEN_ANABEL_LEWIS, HAMMOCK_REAL_ESTATE_DEVELOPMENT_LLC), **14
non_tracerfy_verified_phone**. See `docs/winnerdata/payload_fixtures/*.nowcerts.json` for
the per-lead `_delivery_gate` block.

## Idempotency

Search-first: `GET /CustomersList?$filter=(phone eq '<phone>' or email eq '<email>')` (the
public contract has no prospect-only list endpoint — `CustomersList` is the general
insured/prospect listing endpoint), then compare the FF's normalized entity name
(`normalize_name()` — uppercase, strip everything but `[A-Z0-9 ]`) against each candidate's
`commercialName` or `firstName + lastName`. A match skips the insert and logs
`momentum_skipped_duplicate` with the existing record's `databaseId`; a miss inserts and
logs `momentum_delivered`. `PAFFORD_PROPERTIES_CONSTRUCTION-001` and `-002` in the current
batch share the same normalized name + phone (same buyer, two properties) — the second
delivery run against a warm Momentum DB would skip on that pair, exactly the duplicate case
the parent issue's negative test requires.

## Residuals (known limitations, not fixed in this pass)

- Entity-type classification inherits the existing house heuristic's blind spots (e.g.
  `"GENFI MINISTRIES INCORPORATED"` doesn't match `\binc\b` as a whole word and is
  classified `person`; `"...TRUSTEE OF ZIVKO PSP"` doesn't match `\btrust\b` for the same
  reason). Reused verbatim for consistency with `scripts/winnerdata_render_batch.py`
  rather than diverging with a second, different classifier — flagged here rather than
  silently fixed, since improving it is a cross-cutting change outside this issue's scope.
- Multi-party leads (`"RILEY CHRISTOPHER D / KELLEY MATTHEW W"`) are delivered as a single
  Prospect with the full string as `first_name`/`last_name` fallback — NowCerts' `agents`/
  `csRs` array fields exist in the Postman sample but there's no analogous "additional
  named insureds" array on `InsertProspect` in the public contract to split multi-party
  buyers into linked records.
- `type`/`insuredType` enum values (`1`/`2`) are INFERRED, not confirmed live (see table
  above) — first item to verify in Phase 5 live validation once trial credentials exist.
