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
 * Italic lines under it (`*Example: …*`) are the example, and an italic line starting
 * `*Context:` is the entry's metadata — parsed by `dictionary-context.mjs`, whose header
 * documents the micro-format. Anything else — a bold sentence, a table, a list, a blockquote
 * that is not a Legend — is prose and rendered as it stands.
 *
 * Every entry also carries a `firstSeen` date — explicit in the Context line, else the date
 * already committed in the JSON, else git's answer, else today. `dictionary-context.mjs` owns
 * that rule; `pnpm dictionary --rederive-dates` drops the carried dates and re-asks git.
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

import {
  asEntry,
  FIGURE_KINDS,
  githubSlug,
  isLegend,
  sourceOf,
  stripHead,
  visit,
} from './dictionary-blocks.mjs';
import {
  committedDates,
  dateEntries,
  gitFirstSeen,
  isContextLine,
  parseContextLine,
  resolveContextMeta,
  today,
} from './dictionary-context.mjs';

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
/** Ignore the dates already committed and re-derive every one of them from git. */
const rederiveDates = process.argv.includes('--rederive-dates');

// --- markdown → html ----------------------------------------------------------------------

const parser = unified().use(remarkParse).use(remarkGfm);
const renderer = unified().use(remarkRehype).use(rehypeStringify);

/** Render one or more mdast nodes to an HTML string. */
function html(nodes) {
  const root = { type: 'root', children: Array.isArray(nodes) ? nodes : [nodes] };
  return String(renderer.stringify(renderer.runSync(root))).trim();
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

// --- the walk ------------------------------------------------------------------------------

function build() {
  const source = readFileSync(SOURCE_PATH, 'utf8');
  const tree = parser.parse(source);
  const problems = [];
  /** slug → an explicit `first seen` from a Context line, and the raw `related`/`see` items. */
  const meta = new Map();

  const chapterIds = new Set();
  for (const node of tree.children) {
    if (node.type === 'heading' && node.depth === 2) chapterIds.add(githubSlug(mdToString(node)));
  }

  const dictionary = { chapters: [] };
  const intro = [];
  const usedSlugs = new Set();
  const assets = new Set();
  let chapter = null;

  /**
   * Attach one `*Context: …*` line to an entry block. The free-text lead renders through the
   * same remark pipeline as a definition, so its links get the same check; `related` and `see`
   * are kept raw here and resolved once every slug is known.
   */
  function attachContext(block, raw, where) {
    const ctx = parseContextLine(raw);
    if (ctx.lead) {
      const leadTree = parser.parse(ctx.lead);
      rewriteLinks(leadTree, chapterIds, problems, where);
      block.context = html(leadTree.children);
    }
    if (ctx.source) block.source = ctx.source;
    if (ctx.related.length) block.related = [];
    if (ctx.see.length) block.see = [];
    meta.set(block.slug, { ...ctx, where });
  }

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
        const block = {
          kind: 'entry',
          slug: entry.slug,
          term: entry.term,
          aliases: entry.aliases,
          html: html(definitionTree.children),
          exampleHtml: exampleTree ? html(exampleTree.children) : '',
        };
        if (entry.context) attachContext(block, entry.context, where);
        blocks.push(block);
        continue;
      }
      // A bare italic paragraph straight after an entry continues its example — unless it
      // opens `*Context:`, in which case it is that entry's metadata line.
      const only = node.children.length === 1 && node.children[0].type === 'emphasis';
      if (only && last?.kind === 'entry') {
        const raw = sourceOf(node, source);
        if (isContextLine(raw)) attachContext(last, raw, where);
        else {
          rewriteLinks(node, chapterIds, problems, where);
          last.exampleHtml = [last.exampleHtml, html(node)].filter(Boolean).join('\n');
        }
        continue;
      }
    }

    // Everything else — prose paragraphs, tables, lists, non-legend quotes — renders as is.
    rewriteLinks(node, chapterIds, problems, where);
    blocks.push({ kind: 'prose', html: html(node) });
  }

  const entries = dictionary.chapters.flatMap((c) => c.blocks.filter((b) => b.kind === 'entry'));

  resolveContextMeta({
    entries,
    chapters: dictionary.chapters,
    meta,
    problems,
    repo: REPO,
    repoBlob: REPO_BLOB,
  });
  dateEntries({
    entries,
    meta,
    previous: rederiveDates ? new Map() : committedDates(JSON_OUT),
    fromGit: gitFirstSeen(REPO, SOURCE),
    now: today(),
  });

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
      /** Entries carrying a `*Context:*` line — the metadata footer the Learn page renders. */
      contexts: entries.filter((e) => meta.has(e.slug)).length,
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
  const provisional = out.chapters
    .flatMap((c) => c.blocks)
    .filter((b) => b.kind === 'entry' && b.firstSeenProvisional).length;
  console.log(
    `gen-dictionary: wrote ${out.counts.chapters} chapters, ${out.counts.entries} entries, ` +
      `${assets.length} figures, ${out.counts.diagrams} diagrams, ` +
      `${out.counts.contexts} context lines (${provisional} dates not yet in git)`,
  );
}

main();
