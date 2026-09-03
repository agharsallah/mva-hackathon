#!/usr/bin/env node
/**
 * The dictionary generator.
 *
 * `docs/dictionary.md` is the one glossary in this repository and the rule is that it is
 * never duplicated. The app's Learn page therefore does not *copy* it — this script reads the
 * markdown at build time and writes the structured form the page renders:
 *
 *   src/lib/dictionary/dictionary.generated.json   chapters → blocks (entries, figures,
 *                                                  mermaid sources, code, prose), each entry
 *                                                  with a stable slug the app can deep-link
 *   src/lib/dictionary/assets/*.svg                the diagrams the markdown embeds, copied
 *                                                  byte-for-byte so Vite can serve them (the
 *                                                  dev server refuses files outside app/)
 *
 * Run `pnpm dictionary` after editing the markdown. `pnpm dictionary:check` fails if either
 * committed artifact has drifted from what this script would write, and it fails on a
 * dictionary cross-link (`[phasing](#4-inheritance…)`) that names a heading which no longer
 * exists — so the source document gets a link check it never had.
 *
 * What counts as an entry: a paragraph that opens with `**term**` followed by an em dash.
 * Italic lines under it (`*Example: …*`) are the example. Anything else — a bold sentence, a
 * table, a list, a blockquote that is not a Legend — is prose and rendered as it stands.
 */

import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { toString as mdToString } from 'mdast-util-to-string';
import rehypeStringify from 'rehype-stringify';
import remarkGfm from 'remark-gfm';
import remarkParse from 'remark-parse';
import remarkRehype from 'remark-rehype';
import { unified } from 'unified';

const APP = dirname(fileURLToPath(new URL('.', import.meta.url)));
const REPO = resolve(APP, '..');
const SOURCE = 'docs/dictionary.md';
const SOURCE_PATH = join(REPO, SOURCE);
const OUT_DIR = join(APP, 'src/lib/dictionary');
const JSON_OUT = join(OUT_DIR, 'dictionary.generated.json');
const ASSETS_OUT = join(OUT_DIR, 'assets');
/** Relative `.md` links in the source resolve to the repository on GitHub. */
const REPO_BLOB = 'https://github.com/agharsallah/mva-hackathon/blob/main/';

const check = process.argv.includes('--check');

// --- slugs ------------------------------------------------------------------------------

/**
 * GitHub's heading anchor: lowercase, punctuation removed, spaces to hyphens. The dictionary's
 * own cross-links were written against GitHub's rendering, so chapter ids must match it —
 * `## 4. Inheritance — how the answer is shaped` → `4-inheritance--how-the-answer-is-shaped`.
 */
function githubSlug(text) {
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

// --- markdown → html ----------------------------------------------------------------------

const parser = unified().use(remarkParse).use(remarkGfm);
const renderer = unified().use(remarkRehype).use(rehypeStringify);

/** Render one or more mdast nodes to an HTML string. */
function html(nodes) {
  const root = { type: 'root', children: Array.isArray(nodes) ? nodes : [nodes] };
  return String(renderer.stringify(renderer.runSync(root))).trim();
}

/** The raw source text a node came from. */
function sourceOf(node, source) {
  return source.slice(node.position.start.offset, node.position.end.offset);
}

/** Walk a tree, calling `fn` on every node. */
function visit(node, fn) {
  fn(node);
  for (const child of node.children ?? []) visit(child, fn);
}

/**
 * Rewrite links so they work from the app: a `#heading` stays a same-page anchor (validated
 * against the chapter ids), a relative `.md` file becomes its GitHub URL, and a stale anchor
 * is an error — the generator is the dictionary's link checker.
 */
function rewriteLinks(tree, chapterIds, problems, where) {
  visit(tree, (node) => {
    if (node.type !== 'link') return;
    const url = node.url;
    if (url.startsWith('#')) {
      if (!chapterIds.has(url.slice(1))) problems.push(`${where}: unresolved link ${url}`);
      return;
    }
    if (/^[a-z]+:/.test(url)) return;
    const [file, hash] = url.split('#');
    node.url = REPO_BLOB + join('docs', file).replace(/\\/g, '/') + (hash ? `#${hash}` : '');
  });
}

// --- block classification ------------------------------------------------------------------

/** `**term** — definition`, possibly with `**alias**` before the dash. */
function asEntry(paragraph, source, usedSlugs) {
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

  // The definition is every line until the first line that is a bare italic; the example is
  // that line and everything after it.
  const lines = sourceOf(paragraph, source).split('\n');
  const split = lines.findIndex((l, i) => i > 0 && /^\*(?!\*)/.test(l));
  const definition = (split < 0 ? lines : lines.slice(0, split)).join('\n');
  const example = split < 0 ? '' : lines.slice(split).join('\n');

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
  };
}

/**
 * Remove `**term** (aliases) — ` from the front of a definition: the app renders the term as
 * the card's heading, so the body starts at the definition proper.
 */
function stripHead(paragraph) {
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

function isLegend(node) {
  if (node.type !== 'blockquote') return false;
  const p = node.children[0];
  const s = p?.children?.[0];
  return s?.type === 'strong' && mdToString(s).trim() === 'Legend';
}

/** Blocks a Legend can attach to. */
const FIGURE_KINDS = new Set(['figure', 'mermaid', 'code']);

// --- the walk ------------------------------------------------------------------------------

function build() {
  const source = readFileSync(SOURCE_PATH, 'utf8');
  const tree = parser.parse(source);
  const problems = [];

  const chapterIds = new Set();
  for (const node of tree.children) {
    if (node.type === 'heading' && node.depth === 2) chapterIds.add(githubSlug(mdToString(node)));
  }

  const dictionary = { chapters: [] };
  const intro = [];
  const usedSlugs = new Set();
  const assets = new Set();
  let chapter = null;

  for (const node of tree.children) {
    const line = node.position.start.line;
    const where = `${SOURCE}:${line}`;

    if (node.type === 'heading' && node.depth === 1) continue;
    if (node.type === 'thematicBreak') continue;

    if (node.type === 'heading' && node.depth === 2) {
      const title = mdToString(node);
      const m = title.match(/^(\d+)\.\s+(.*)$/);
      if (!m) problems.push(`${where}: chapter heading without a number: "${title}"`);
      chapter = {
        number: m ? Number(m[1]) : dictionary.chapters.length + 1,
        id: githubSlug(title),
        title: m ? m[2] : title,
        blocks: [],
      };
      dictionary.chapters.push(chapter);
      continue;
    }

    const blocks = chapter ? chapter.blocks : intro;
    const last = blocks[blocks.length - 1];

    if (node.type === 'heading') {
      const text = mdToString(node);
      blocks.push({ kind: 'subheading', id: githubSlug(text), text });
      continue;
    }

    if (node.type === 'code') {
      if (node.lang === 'mermaid') blocks.push({ kind: 'mermaid', source: node.value });
      else blocks.push({ kind: 'code', text: node.value });
      continue;
    }

    if (isLegend(node)) {
      if (!last || !FIGURE_KINDS.has(last.kind)) {
        problems.push(`${where}: Legend with no figure, diagram or code block above it`);
        continue;
      }
      rewriteLinks(node, chapterIds, problems, where);
      // Drop the bold "Legend" label and the dash: the app renders its own label.
      const p = node.children[0];
      p.children.shift();
      if (p.children[0]?.type === 'text')
        p.children[0].value = p.children[0].value.replace(/^\s*—\s*/, '');
      last.legendHtml = html(node.children);
      continue;
    }

    if (
      node.type === 'paragraph' &&
      node.children.length === 1 &&
      node.children[0].type === 'image'
    ) {
      const img = node.children[0];
      const file = basename(img.url);
      if (!img.url.startsWith('assets/') || !existsSync(join(REPO, 'docs', img.url))) {
        problems.push(`${where}: image not under docs/assets: ${img.url}`);
      }
      assets.add(file);
      blocks.push({ kind: 'figure', file, alt: img.alt ?? '' });
      continue;
    }

    if (node.type === 'paragraph') {
      const entry = asEntry(node, source, usedSlugs);
      if (entry) {
        const definitionTree = parser.parse(entry.definition);
        stripHead(definitionTree.children[0]);
        const exampleTree = entry.example ? parser.parse(entry.example) : null;
        rewriteLinks(definitionTree, chapterIds, problems, where);
        if (exampleTree) rewriteLinks(exampleTree, chapterIds, problems, where);
        blocks.push({
          kind: 'entry',
          slug: entry.slug,
          term: entry.term,
          aliases: entry.aliases,
          html: html(definitionTree.children),
          exampleHtml: exampleTree ? html(exampleTree.children) : '',
        });
        continue;
      }
      // A bare italic paragraph straight after an entry continues its example.
      const only = node.children.length === 1 && node.children[0].type === 'emphasis';
      if (only && last?.kind === 'entry') {
        rewriteLinks(node, chapterIds, problems, where);
        last.exampleHtml = [last.exampleHtml, html(node)].filter(Boolean).join('\n');
        continue;
      }
    }

    // Everything else — prose paragraphs, tables, lists, non-legend quotes — renders as is.
    rewriteLinks(node, chapterIds, problems, where);
    blocks.push({ kind: 'prose', html: html(node) });
  }

  const entries = dictionary.chapters.flatMap((c) => c.blocks.filter((b) => b.kind === 'entry'));
  const out = {
    source: SOURCE,
    generator: 'app/tools/gen-dictionary.mjs',
    intro: intro.filter((b) => b.kind === 'prose'),
    counts: {
      chapters: dictionary.chapters.length,
      entries: entries.length,
      figures: dictionary.chapters.flatMap((c) => c.blocks).filter((b) => b.kind === 'figure')
        .length,
      diagrams: dictionary.chapters.flatMap((c) => c.blocks).filter((b) => b.kind === 'mermaid')
        .length,
    },
    chapters: dictionary.chapters,
  };
  return { out, assets: [...assets].sort(), problems };
}

// --- write / check -------------------------------------------------------------------------

function main() {
  const { out, assets, problems } = build();
  if (problems.length) {
    for (const p of [...new Set(problems)]) console.error(`gen-dictionary: ${p}`);
    process.exit(1);
  }

  const json = JSON.stringify(out, null, 2) + '\n';
  const wanted = new Map([[JSON_OUT, json]]);
  for (const file of assets)
    wanted.set(join(ASSETS_OUT, file), readFileSync(join(REPO, 'docs/assets', file), 'utf8'));

  if (check) {
    let drift = 0;
    for (const [path, content] of wanted) {
      const current = existsSync(path) ? readFileSync(path, 'utf8') : null;
      if (current !== content) {
        console.error(
          `gen-dictionary: ${path.replace(APP + '/', '')} is out of date — run \`pnpm dictionary\``,
        );
        drift++;
      }
    }
    const stray = existsSync(ASSETS_OUT)
      ? readdirSync(ASSETS_OUT).filter((f) => !assets.includes(f))
      : [];
    for (const f of stray) {
      console.error(
        `gen-dictionary: src/lib/dictionary/assets/${f} is no longer referenced by ${SOURCE}`,
      );
      drift++;
    }
    if (drift) process.exit(1);
    console.log(
      `gen-dictionary: up to date (${out.counts.entries} entries, ${assets.length} figures)`,
    );
    return;
  }

  mkdirSync(ASSETS_OUT, { recursive: true });
  for (const [path, content] of wanted) writeFileSync(path, content);
  console.log(
    `gen-dictionary: wrote ${out.counts.chapters} chapters, ${out.counts.entries} entries, ` +
      `${assets.length} figures, ${out.counts.diagrams} diagrams`,
  );
}

main();
