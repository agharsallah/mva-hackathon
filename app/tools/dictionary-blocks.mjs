/**
 * What a markdown node in `docs/dictionary.md` *means*.
 *
 * One bounded concern: the entry syntax. `gen-dictionary.mjs` walks the document and decides
 * where each block goes; this module answers the smaller question it asks at every step —
 * is this paragraph an entry, and if so what are its term, aliases, definition, example and
 * `*Context:*` line? Anchors live here too, because a slug is part of that syntax.
 */

import { toString as mdToString } from 'mdast-util-to-string';

import { isContextLine } from './dictionary-context.mjs';

// --- slugs ------------------------------------------------------------------------------

/**
 * GitHub's heading anchor: lowercase, punctuation removed, spaces to hyphens. The dictionary's
 * own cross-links were written against GitHub's rendering, so chapter ids must match it —
 * `## 4. Inheritance — how the answer is shaped` → `4-inheritance--how-the-answer-is-shaped`.
 */
export function githubSlug(text) {
  return text
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number} -]/gu, '')
    .replace(/ /g, '-');
}

/** Term slug, same rule as `src/lib/sections.ts` so anchors look alike app-wide. */
function termSlug(text) {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^\p{Letter}\p{Number}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

/** The raw source text a node came from. */
export function sourceOf(node, source) {
  return source.slice(node.position.start.offset, node.position.end.offset);
}

/** Walk a tree, calling `fn` on every node. */
export function visit(node, fn) {
  fn(node);
  for (const child of node.children ?? []) visit(child, fn);
}

// --- block classification ------------------------------------------------------------------

/** `**term** — definition`, possibly with `**alias**` before the dash. */
export function asEntry(paragraph, source, usedSlugs) {
  const [first] = paragraph.children;
  if (!first || first.type !== 'strong') return null;
  const text = mdToString(paragraph);
  const dash = text.indexOf(' — ');
  if (dash < 0) return null;
  const head = text.slice(0, dash);
  const term = mdToString(first);
  if (!head.startsWith(term)) return null;

  // Aliases: every other bold run before the dash, plus the slash-separated names.
  const aliases = new Set();
  for (const child of paragraph.children) {
    if (child === first) continue;
    if (child.type === 'strong') aliases.add(mdToString(child));
    if (child.type === 'text' && child.value.includes(' — ')) break;
  }
  for (const part of term.split(/\s*\/\s*/)) {
    const clean = part.replace(/\s*\(.*\)\s*$/, '').trim();
    if (clean && clean !== term) aliases.add(clean);
  }
  const paren = term.match(/\(([^)]+)\)/);
  if (paren) aliases.add(paren[1].trim());

  // The definition is every line until the first line that is a bare italic. The italic tail
  // is the example, up to the line that opens `*Context:` — that one and the rest are the
  // entry's metadata.
  const lines = sourceOf(paragraph, source).split('\n');
  const split = lines.findIndex((l, i) => i > 0 && /^\*(?!\*)/.test(l));
  const tail = split < 0 ? [] : lines.slice(split);
  const ctxAt = tail.findIndex((l) => isContextLine(l));
  const definition = (split < 0 ? lines : lines.slice(0, split)).join('\n');
  const example = (ctxAt < 0 ? tail : tail.slice(0, ctxAt)).join('\n');
  const context = ctxAt < 0 ? '' : tail.slice(ctxAt).join('\n');

  let slug = termSlug(term);
  let n = 2;
  while (usedSlugs.has(slug)) slug = `${termSlug(term)}-${n++}`;
  usedSlugs.add(slug);

  return {
    kind: 'entry',
    slug,
    term,
    aliases: [...aliases].filter((a) => a !== term),
    definition,
    example,
    context,
  };
}

/**
 * Remove `**term** (aliases) — ` from the front of a definition: the app renders the term as
 * the card's heading, so the body starts at the definition proper.
 */
export function stripHead(paragraph) {
  const kids = paragraph.children;
  while (kids.length) {
    const k = kids[0];
    if (k.type === 'text' && k.value.includes(' — ')) {
      k.value = k.value.slice(k.value.indexOf(' — ') + 3);
      if (!k.value) kids.shift();
      return;
    }
    kids.shift();
  }
}

export function isLegend(node) {
  if (node.type !== 'blockquote') return false;
  const p = node.children[0];
  const s = p?.children?.[0];
  return s?.type === 'strong' && mdToString(s).trim() === 'Legend';
}

/** Blocks a Legend can attach to. */
export const FIGURE_KINDS = new Set(['figure', 'mermaid', 'code']);
