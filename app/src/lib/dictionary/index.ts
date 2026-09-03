/**
 * The dictionary, as the app reads it.
 *
 * `docs/dictionary.md` is the one glossary in the repository. `tools/gen-dictionary.mjs`
 * turns it into `dictionary.generated.json` (chapters of blocks) and copies its diagrams into
 * `assets/`; this module is the typed door to both. The JSON is ~270 kB, so it is only ever
 * `import()`ed — a visitor who never opens the Learn page downloads none of it — and the
 * figure URLs come from a Vite glob so a new diagram in the markdown needs no code change.
 *
 * Nothing here knows about React or routes: a component maps blocks to elements, and the
 * Explainer links a term by its `slug` (`/learn#allele`).
 */

/** `**term** — definition`, the unit of the dictionary. */
export interface EntryBlock {
  kind: 'entry';
  /** Stable anchor: `/learn#<slug>`. Derived from the term with `lib/sections.slugify`. */
  slug: string;
  term: string;
  /** Other names the search should answer to: slash-separated parts, bracketed short forms. */
  aliases: string[];
  /** The definition, as HTML, starting after the em dash. */
  html: string;
  /** The `*Example: …*` lines, as HTML; empty when the entry has none. */
  exampleHtml: string;
}

/** An SVG from `docs/assets/`, copied into `assets/`. */
export interface FigureBlock {
  kind: 'figure';
  file: string;
  alt: string;
  legendHtml?: string;
}

/** A ```mermaid block, rendered in the browser by `pages/learn/Mermaid.tsx`. */
export interface MermaidBlock {
  kind: 'mermaid';
  source: string;
  legendHtml?: string;
}

/** A ```text block — the hand-drawn ASCII diagrams. */
export interface CodeBlock {
  kind: 'code';
  text: string;
  legendHtml?: string;
}

/** A paragraph, table, list or quote that is not an entry. */
export interface ProseBlock {
  kind: 'prose';
  html: string;
}

/** A `###` heading inside a chapter. */
export interface SubheadingBlock {
  kind: 'subheading';
  id: string;
  text: string;
}

export type Block =
  EntryBlock | FigureBlock | MermaidBlock | CodeBlock | ProseBlock | SubheadingBlock;

export interface Chapter {
  /** 1-based, in reading order — the dictionary is ordered so each word uses only words above it. */
  number: number;
  /** GitHub's heading anchor, so the markdown's own cross-links resolve unchanged. */
  id: string;
  title: string;
  blocks: Block[];
}

export interface Dictionary {
  source: string;
  generator: string;
  intro: ProseBlock[];
  counts: { chapters: number; entries: number; figures: number; diagrams: number };
  chapters: Chapter[];
}

/** The generated JSON, loaded on demand. */
export async function loadDictionary(): Promise<Dictionary> {
  const mod = await import('./dictionary.generated.json');
  return mod.default as Dictionary;
}

/**
 * Figure file name → served URL. `import.meta.glob` is resolved at build time, so every SVG
 * in `assets/` gets its own hashed URL and none is inlined into a JS chunk.
 */
const FIGURE_URLS = import.meta.glob('./assets/*.svg', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>;

export function figureUrl(file: string): string | undefined {
  return FIGURE_URLS[`./assets/${file}`];
}

/** Every entry, in reading order. */
export function entriesOf(d: Dictionary): EntryBlock[] {
  return d.chapters.flatMap((c) => c.blocks.filter((b): b is EntryBlock => b.kind === 'entry'));
}

/** The chapter an anchor lives in: a chapter id, a subheading id or an entry slug. */
export function chapterOfAnchor(d: Dictionary, anchor: string): Chapter | undefined {
  return d.chapters.find(
    (c) =>
      c.id === anchor ||
      c.blocks.some(
        (b) =>
          (b.kind === 'entry' && b.slug === anchor) || (b.kind === 'subheading' && b.id === anchor),
      ),
  );
}

/** Case-insensitive lookup by term or alias — what the Explainer's `dict` check uses. */
export function findEntry(d: Dictionary, name: string): EntryBlock | undefined {
  const wanted = name.trim().toLowerCase();
  return entriesOf(d).find(
    (e) => e.term.toLowerCase() === wanted || e.aliases.some((a) => a.toLowerCase() === wanted),
  );
}
