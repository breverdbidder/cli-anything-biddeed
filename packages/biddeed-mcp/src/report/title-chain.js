// GTM-22 S5 REPORT ENGINE — Title Tier 3 (title search / chain of title),
// issue #20045. Backs SIGNAL$ §16's Tier 3 status line by reading the
// already-pulled public.title_chain_pull/title_chain_owner/title_chain_gap
// tables (docs/plans/title-chain-pull-P1-build-brief.md's result model,
// applied to Brevard by scripts/brevard_title_chain_tier3.py) — never pulls
// a chain itself at render time.
//
// Two_owner depth is inherently partial by design (P1 brief section 2), so
// this never reports "complete" — only how far the pull got and how many
// gaps remain, per the issue's own DoD ("Pending — Title Tier 3: chain
// pulled to <date>, <n> gaps unresolved — a partial with numbers, not a
// bare Pending").
import { get as defaultGet } from '../supabase.js';

export async function buildTitleChain({ parcel_id, county } = {}, { get = defaultGet } = {}) {
  if (!parcel_id || !county) return null;

  // county=ilike, not eq: multi_county_auctions stores county lowercase
  // ('brevard'), while title_chain_pull follows the P1 brief's Title Case
  // convention ('Brevard') — case-insensitive match avoids a silent
  // false-negative between the two naming conventions.
  const pulls = await get(
    `title_chain_pull?parcel_id=eq.${encodeURIComponent(parcel_id)}&county=ilike.${encodeURIComponent(county)}&select=id,as_of_date,pulled_at,status&order=pulled_at.desc&limit=1`
  ).catch(() => null);
  const pull = pulls?.[0];
  if (!pull) return null;

  const [owners, gaps] = await Promise.all([
    get(`title_chain_owner?pull_id=eq.${pull.id}&select=seq,owner_name,deed_type,deed_date,honesty_marker&order=seq.asc`).catch(() => []),
    get(`title_chain_gap?pull_id=eq.${pull.id}&select=id,reason,honesty_marker`).catch(() => []),
  ]);

  return {
    as_of_date: (pull.as_of_date || pull.pulled_at || '').slice(0, 10) || null,
    status: pull.status,
    owners: owners || [],
    n_owners: owners?.length || 0,
    gaps: gaps || [],
    n_gaps: gaps?.length || 0,
  };
}
