-- winnerdata.owner_portfolio: one row per (owner_key, parcel), enumerating a
-- resolved owner's FULL held book across fl_parcels (auction wins + prior
-- holdings), not just the parcel they won at auction. See issue: Identity
-- cascade + PORTFOLIO Fact Finder (2026-08-25), supersedes #19447 delivery.
--
-- linked_via records HOW this parcel was attached to the owner_key so every
-- merge is auditable:
--   exact_name          -- fl_parcels.own_name exact-normalized match to the
--                           resolved buyer/principal name
--   affiliate_own_addr   -- same normalized own_addr1+own_city as the anchor
--                           entity, PLUS a second corroborator (shared_principal
--                           column populated) -- own_addr1 match alone is never
--                           sufficient per the no-strangers-merge rule
--   shared_principal      -- linked via a Sunbiz principal/manager/officer name
--                           shared with another entity in the same portfolio

create schema if not exists winnerdata;

create table if not exists winnerdata.owner_portfolio (
    id bigint generated always as identity primary key,
    owner_key text not null,                 -- stable slug for the resolved operator, e.g. normalized anchor entity name
    entity_name_raw text not null,            -- fl_parcels.own_name as stored for this row
    county text not null,
    co_no integer not null,
    parcel_id text not null,
    address text,
    dor_uc text,
    no_buldng integer,
    jv numeric,
    coastal_flood_indicator text not null default 'UNKNOWN',  -- flood_zones has real polygon coverage only for Brevard (229 rows) as of 2026-08-25 -- honest UNKNOWN elsewhere, never guessed
    acquisition_source text not null default 'prior_holding' check (acquisition_source in ('auction_win','prior_holding')),
    linked_via text not null check (linked_via in ('exact_name','affiliate_own_addr','shared_principal')),
    linked_via_detail text,                   -- e.g. the shared principal name, or the corroborating own_addr1 string
    batch_id text not null,
    case_number text,                          -- populated only for the acquisition_source='auction_win' row
    created_at timestamptz not null default now(),
    unique (owner_key, co_no, parcel_id)
);

create index if not exists idx_owner_portfolio_owner_key on winnerdata.owner_portfolio (owner_key);
create index if not exists idx_owner_portfolio_batch on winnerdata.owner_portfolio (batch_id);
