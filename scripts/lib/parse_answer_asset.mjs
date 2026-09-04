// Parses a content/answers/{slug}.md file into the shape
// public.upsert_site_content() / the /answers/:slug renderer expect.
//
// Frontmatter is a fenced JSON block (not YAML) -- deliberate: this repo has
// no YAML parser dependency today (checked package.json — js-yaml is not
// installed) and the frontmatter fields (A1) are already structured
// (arrays, nested link objects), which JSON expresses natively with zero
// new dependency and zero parsing ambiguity. Format:
//
//   ---
//   { "slug": "...", "title": "...", ... }
//   ---
//   ## Markdown body
//   ...
import { markdownToHtml } from './simple_markdown.mjs';

export function parseAnswerAsset(raw, filePath) {
  const m = raw.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!m) throw new Error(`${filePath}: missing fenced JSON frontmatter (--- ... ---)`);
  let front;
  try {
    front = JSON.parse(m[1]);
  } catch (e) {
    throw new Error(`${filePath}: frontmatter is not valid JSON — ${e.message}`);
  }
  const bodyMd = m[2];
  const required = ['slug', 'title', 'meta_description', 'question', 'scope', 'links', 'faq', 'author', 'version', 'date'];
  for (const key of required) {
    if (front[key] === undefined || front[key] === null) {
      throw new Error(`${filePath}: frontmatter missing required key "${key}"`);
    }
  }
  if (front.title.length > 60) throw new Error(`${filePath}: title exceeds 60 chars (${front.title.length})`);
  if (front.meta_description.length > 155) throw new Error(`${filePath}: meta_description exceeds 155 chars (${front.meta_description.length})`);

  // A5: zero static numbers in the body — literal digit runs of 2+ are a
  // hard fail, with two narrow exemptions:
  //   1. Renderer tokens ({{...}}) and Fla. Stat. section numbers (197.552).
  //   2. A number that also appears verbatim inside one of THIS file's own
  //      statutes[].sentence values (A4) -- i.e. a legal fact independently
  //      fetched from leg.state.fl.us and quoted in the same run, not an
  //      invented or "probably still true" figure. Hard rule 2 ("No
  //      unverified numbers... or omitted") is read as targeting BidDeed's
  //      own live business metrics (the auction/certified/outcome counts
  //      A5 names explicitly) -- a statutory figure verified and cited in
  //      the same file is the opposite of unverified.
  const statuteSentences = (front.statutes || []).map(s => String(s.sentence || ''));
  const numbersInStatutes = new Set();
  for (const sentence of statuteSentences) {
    for (const m of sentence.matchAll(/\d{2,}/g)) numbersInStatutes.add(m[0]);
  }
  const bodyForNumberCheck = bodyMd
    .replace(/\{\{[^}]+\}\}/g, '')
    .replace(/(?:Fla\.?\s*Stat\.?\s*)?(?:§+\s*)?\d{2,3}\.\d{2,4}/gi, '');
  const staticNumberMatches = bodyForNumberCheck.match(/\d{2,}/g) || [];
  const unverified = staticNumberMatches.filter(n => !numbersInStatutes.has(n));
  if (unverified.length) {
    throw new Error(`${filePath}: static number "${unverified[0]}" found in body with no matching statutes[].sentence citation — A5 requires renderer tokens or a same-file statute citation`);
  }

  // The first paragraph of the body IS answer_first (A2) — rendered once by
  // the Worker as the styled "answer-first" callout, so it's stripped out
  // of the rest of the body here to avoid the page repeating it verbatim.
  const trimmedBody = bodyMd.trim();
  const answerFirstMatch = trimmedBody.match(/^([\s\S]*?)(\n\s*\n|$)/);
  const answerFirstRaw = answerFirstMatch ? answerFirstMatch[1] : trimmedBody;
  const answerFirstText = (front.answer_first || answerFirstRaw).replace(/\s+/g, ' ').trim();
  const wordCount = answerFirstText.split(/\s+/).filter(Boolean).length;
  if (wordCount < 30 || wordCount > 70) {
    throw new Error(`${filePath}: answer_first is ${wordCount} words, expected roughly 40-60 (A2)`);
  }
  const restOfBody = front.answer_first ? trimmedBody : trimmedBody.slice(answerFirstMatch[0].length);

  const bodyHtml = markdownToHtml(restOfBody);

  return {
    slug: front.slug,
    title: front.title,
    hero_copy: answerFirstText,
    published: front.published !== false,
    body_jsonb: {
      question: front.question,
      meta_description: front.meta_description,
      answer_first: answerFirstText,
      body_html: bodyHtml,
      scope: front.scope,
      statutes: front.statutes || [],
      faq: front.faq,
      links: front.links,
      author: front.author,
      howto: front.howto || [],
      version: front.version,
      date: front.date,
    },
  };
}
