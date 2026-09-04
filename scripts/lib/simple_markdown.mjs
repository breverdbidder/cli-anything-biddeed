// Minimal markdown -> HTML converter for content/answers/*.md bodies.
// Intentionally small: this repo's answer assets are hand-authored with a
// narrow subset (##, paragraphs, - / 1. lists, **bold**, [text](url)) --
// not a general CommonMark implementation, no new dependency.

function inline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}

export function markdownToHtml(md) {
  const lines = String(md || '').replace(/\r\n/g, '\n').split('\n');
  const out = [];
  let listType = null; // 'ul' | 'ol' | null
  let para = [];

  function flushPara() {
    if (para.length) {
      out.push(`<p>${inline(para.join(' ').trim())}</p>`);
      para = [];
    }
  }
  function closeList() {
    if (listType) { out.push(`</${listType}>`); listType = null; }
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) { flushPara(); closeList(); continue; }
    const h2 = line.match(/^##\s+(.*)$/);
    if (h2) { flushPara(); closeList(); out.push(`<h2>${inline(h2[1])}</h2>`); continue; }
    const ul = line.match(/^[-*]\s+(.*)$/);
    if (ul) {
      flushPara();
      if (listType !== 'ul') { closeList(); out.push('<ul>'); listType = 'ul'; }
      out.push(`<li>${inline(ul[1])}</li>`);
      continue;
    }
    const ol = line.match(/^\d+\.\s+(.*)$/);
    if (ol) {
      flushPara();
      if (listType !== 'ol') { closeList(); out.push('<ol>'); listType = 'ol'; }
      out.push(`<li>${inline(ol[1])}</li>`);
      continue;
    }
    closeList();
    para.push(line);
  }
  flushPara();
  closeList();
  return out.join('\n');
}
