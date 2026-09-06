// GTM-22 S5 REPORT ENGINE — lien_survival.classify
// Real title/lien hierarchy per pencil_report_parity_spec section_no=7
// ("Lien survival analysis" — insured_report_field: "Which liens survive
// THIS sale type"). Backs the SIGNAL$ Property Report §16 Judgment &
// Encumbrance Summary Title Tier 2 content.
//
// THE SHARPEST UPL EDGE (s5_report_sections.judgment_encumbrance notes,
// pencil_report_parity_spec row 7 liability_note): output here is a
// STATUTE-CITED SURVIVAL CLASS per recorded item, never an owed-amount or
// lien-validity conclusion. Every classified item states which statute/
// doctrine governs and what class of lien it puts the item in — it never
// says a dollar amount is owed or that a lien is valid/invalid.
//
// foreclosure  -> recording-priority: liens recorded senior to the
//                 foreclosed instrument survive; liens junior to it
//                 (including the foreclosed lien itself) are extinguished
//                 by the judgment, per this case's own recorded lien
//                 position — not a generic rule applied blind to the file.
//                 EXCEPT property tax liens/certificates, which hold
//                 super-priority under Fla. Stat. §197.122 regardless of
//                 recording date (fix, issue #19661 pre-step 1).
// tax_deed     -> Fla. Stat. §197.552: most private liens are extinguished;
//                 governmental liens and certain liens (IRS liens under
//                 26 U.S.C. §7425, some HOA/COA claims under Fla. Stat.
//                 §720.3085/§718.116) may survive. Mechanic's liens under
//                 Fla. Stat. §713.07 relation-back may survive if recorded
//                 before the underlying assessment — that comparison
//                 requires an assessment date this table does not carry,
//                 so those are reported UNRESOLVED, never guessed.
import { get as defaultGet } from '../supabase.js';

const FORECLOSURE_BASIS = "Recording priority (Florida \"first in time, first in right\" doctrine) against this case's own recorded lien position at judgment";
const TAXDEED_BASIS = 'Fla. Stat. §197.552 (tax deed extinguishment), with mechanic\'s-lien relation-back under Fla. Stat. §713.07 where applicable';

const NO_DATA_STATEMENT = 'Insufficient recorded-document data on file to classify this lien\'s survival — recording date/priority not on file. Not classified as survives or extinguished.';

const SEARCHED_CLEAN_DISCLOSED_LIMITS = 'This was a name/case-index search against the county\'s recorded-document system, not exhaustive title abstraction — a lien recorded under a differently spelled name variant (e.g. an LLC\'s old name), or not yet indexed by the source system, would not appear here.';

// Distinguishes "a harvest ran for this case and found zero third-party
// liens" from "nothing was ever searched" — title_defects rows sharing this
// case_number/parcel_id (the case's own Ch.197/Lis-Pendens filings, written
// by the pre-auction harvesters) are proof a search executed even when
// lien_results (third-party liens found) has zero rows for the same subject.
// Without this check both states render the identical generic
// "insufficient recorded-document coverage" message, which is false for the
// searched-clean case: coverage exists, the search ran, it just found nothing.
async function checkSearchedClean({ case_number, parcel_id }, { get }) {
  const filters = [];
  if (case_number) filters.push(`case_number.eq.${encodeURIComponent(case_number)}`);
  if (parcel_id)   filters.push(`parcel_id.eq.${encodeURIComponent(parcel_id)}`);
  if (!filters.length) return { searched: false };
  const query = filters.length > 1 ? `or=(${filters.join(',')})` : filters[0].replace('.', '=');

  const rows = await get(`title_defects?${query}&select=defect_description&limit=1`).catch(() => null);
  if (!rows || rows.length === 0) return { searched: false };

  const desc = rows[0].defect_description || '';
  const sourceMatch = desc.match(/\(([^()]*)\)/);
  const source = sourceMatch ? sourceMatch[1].split(' -- ')[0].trim() : 'recorded-document search';
  return { searched: true, source };
}

function baseItem(lien) {
  return {
    lien_type: lien.lien_type || 'Pending — lien type not on file',
    creditor: lien.creditor || 'Pending — not on file',
    recording_date: lien.recording_date || null,
    book_page: lien.book_page || null,
    // amount-on-face (issue #20045): composer.js's max-bid deduction may
    // only subtract a surviving lien when its dollar amount is on the face
    // of the recorded instrument -- this was read from lien_results by
    // classify()'s own select= list but never surfaced on the returned
    // item, so the deduction logic downstream had no way to tell "$0 known"
    // from "amount not on file" apart from re-querying lien_results itself.
    amount: typeof lien.amount === 'number' ? lien.amount : null,
    source: lien.source || 'lien_results',
  };
}

// Fla. Stat. §197.122: property tax liens/certificates hold super-priority
// over every other recorded interest regardless of recording date. The
// foreclosure path below is otherwise pure recording-priority and has no
// other way to except a tax lien — without this check, a tax certificate
// recorded after the foreclosed instrument would be wrongly classified
// extinguished.
const TAX_LIEN_BASIS = 'Fla. Stat. §197.122';
function isPropertyTaxLien(lien) {
  const type = String(lien.lien_type || '').toLowerCase();
  return type.includes('tax lien') || type.includes('tax certificate') || type.includes('property tax');
}

// ── Foreclosure: recording-priority classification ─────────────────────────
function classifyForeclosureLien(lien) {
  const priority = String(lien.priority || '').toLowerCase();
  let survives, statutory_basis, statement;

  if (isPropertyTaxLien(lien)) {
    survives = true;
    statutory_basis = TAX_LIEN_BASIS;
    statement = `Per ${TAX_LIEN_BASIS}, a property tax lien/certificate holds super-priority over this foreclosure regardless of recording date — this lien class survives this foreclosure sale. This states statutory survival class only — it is not an opinion on amount owed or lien validity.`;
  } else if (priority === 'senior') {
    survives = true;
    statutory_basis = FORECLOSURE_BASIS;
    statement = `Per ${FORECLOSURE_BASIS}, this lien class survives this foreclosure sale. This states recording priority only — it is not an opinion on amount owed or lien validity.`;
  } else if (priority === 'junior') {
    survives = false;
    statutory_basis = FORECLOSURE_BASIS;
    statement = `Per ${FORECLOSURE_BASIS}, this lien class is extinguished by this foreclosure judgment/sale. This states recording priority only — it is not an opinion on amount owed or lien validity.`;
  } else if (typeof lien.survives_foreclosure === 'boolean' && lien.priority) {
    // The stored survives_foreclosure flag is only honored when this row's
    // own `priority` field carries SOME value (i.e. was actually populated
    // by a derivation step, even if not exactly 'senior'/'junior') — proof
    // this is a derived call, not a harvester column default. Live Pasco
    // rows demonstrate the default pattern this guards against: every row
    // ingested with survives_foreclosure=false, priority=null, amount=null —
    // a raw INSERT default, never a real priority derivation. A default must
    // never masquerade as a survival call; those fall to the UNRESOLVED
    // branch below instead of silently reporting "does not survive".
    survives = lien.survives_foreclosure;
    statutory_basis = FORECLOSURE_BASIS;
    statement = `Recorded lien data on file indicates this lien class ${survives ? 'survives' : 'does not survive'} this foreclosure sale (per recording priority). Book/page sequencing was not independently re-derived from this record alone — reported as recorded. Not an opinion on amount owed or lien validity.`;
  } else {
    survives = null;
    statutory_basis = null;
    statement = NO_DATA_STATEMENT;
  }

  return { ...baseItem(lien), survives, statutory_basis, statement };
}

// ── Tax deed: Fla. Stat. §197.552 classification ────────────────────────────
function classifyTaxDeedLien(lien) {
  const type = String(lien.lien_type || '').toLowerCase();
  let survives, statutory_basis, statement;

  if (!type) {
    survives = null;
    statutory_basis = null;
    statement = `Insufficient recorded-document data on file to classify this lien's survival under Fla. Stat. §197.552.`;
  } else if (type.includes('irs') || type.includes('federal tax')) {
    survives = true;
    statutory_basis = '26 U.S.C. §7425';
    statement = `Per 26 U.S.C. §7425, a federal tax lien is NOT extinguished by a Florida tax deed sale absent proper IRS notice — this lien class survives. This states statutory survival class only, not an opinion on amount owed or lien validity.`;
  } else if (type.includes('hoa') || type.includes('coa') || type.includes('association')) {
    survives = null;
    statutory_basis = 'Fla. Stat. §720.3085 / §718.116';
    statement = `Per Fla. Stat. §720.3085 / §718.116, survival of an HOA/COA claim through a tax deed sale is fact-dependent and not resolvable from recorded-document data alone — reported as UNRESOLVED, not as extinguished. This is not an opinion on amount owed or lien validity.`;
  } else if (type.includes('mechanic') || type.includes('construction')) {
    survives = null;
    statutory_basis = 'Fla. Stat. §713.07 (relation-back)';
    statement = `Per Fla. Stat. §713.07 relation-back, a mechanic's lien recorded before the underlying tax certificate's assessment date may survive this tax deed sale — this record does not carry the assessment date needed to make that comparison, so this item is reported as UNRESOLVED, not as extinguished. This is not an opinion on amount owed or lien validity.`;
  } else if (type.includes('governmental') || type.includes('municipal') || type.includes('code enforcement') || type.includes('county') || type.includes('state')) {
    survives = true;
    statutory_basis = 'Fla. Stat. §197.552';
    statement = `Per Fla. Stat. §197.552, this governmental lien class survives this tax deed sale. This states statutory survival class only, not an opinion on amount owed or lien validity.`;
  } else {
    survives = false;
    statutory_basis = 'Fla. Stat. §197.552';
    statement = `Per Fla. Stat. §197.552, this private lien class — not otherwise excepted by statute — is extinguished by this tax deed sale. This states statutory survival class only, not an opinion on amount owed or lien validity.`;
  }

  return { ...baseItem(lien), survives, statutory_basis, statement };
}

// classify({ case_number, parcel_id, sale_type }, { get }) — reads
// public.lien_results for the subject (matched by case_number OR
// parcel_id) and returns a per-item statute-cited survival classification.
// Returns { available: false, reason } rather than guessing when no
// recorded-document coverage exists for this parcel/case.
export async function classify({ case_number, parcel_id, sale_type } = {}, { get = defaultGet } = {}) {
  if (!case_number && !parcel_id) {
    return { available: false, reason: 'no case_number or parcel_id supplied', items: [], n_items: 0, statutory_basis: null };
  }

  const filters = [];
  if (case_number) filters.push(`case_number.eq.${encodeURIComponent(case_number)}`);
  if (parcel_id)   filters.push(`parcel_id.eq.${encodeURIComponent(parcel_id)}`);
  const query = filters.length > 1
    ? `or=(${filters.join(',')})`
    : filters[0].replace('.', '=');

  const rows = await get(
    `lien_results?${query}&select=lien_type,creditor,amount,recording_date,book_page,priority,survives_foreclosure,source`
  ).catch(() => null);

  if (!rows || rows.length === 0) {
    const searchState = await checkSearchedClean({ case_number, parcel_id }, { get });
    if (searchState.searched) {
      return {
        available: false,
        searched: true,
        reason: `Recorded-document search completed via ${searchState.source}; zero third-party lien instruments found. Disclosed limits: ${SEARCHED_CLEAN_DISCLOSED_LIMITS}`,
        items: [], n_items: 0, statutory_basis: null,
      };
    }
    return { available: false, searched: false, reason: 'no recorded-document coverage on file for this parcel/case', items: [], n_items: 0, statutory_basis: null };
  }

  const isTaxDeed = String(sale_type || '').toLowerCase() === 'tax_deed';
  const items = rows.map(isTaxDeed ? classifyTaxDeedLien : classifyForeclosureLien);

  return {
    available: true,
    sale_type: isTaxDeed ? 'tax_deed' : 'foreclosure',
    statutory_basis: isTaxDeed ? TAXDEED_BASIS : FORECLOSURE_BASIS,
    items,
    n_items: items.length,
  };
}
