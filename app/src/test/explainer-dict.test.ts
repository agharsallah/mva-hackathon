/**
 * Explainer chips link to the dictionary, and never to a word it does not have.
 *
 * Every page opens with `Explainer` terms — a one-sentence plain-English half per word.
 * `docs/dictionary.md` is the one glossary, so a chip whose term the dictionary defines must
 * carry `dict: '<slug>'` (rendered as "full definition →"), and every `dict` must name a real
 * entry. Both are checked here by reading the page sources: the chips are literal objects,
 * so a regex over `term: '…'` / `dict: '…'` is exact enough and needs no render.
 */

import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { entriesOf, findEntry, loadDictionary } from '../lib/dictionary';

const dictionary = await loadDictionary();
const slugs = new Set(entriesOf(dictionary).map((e) => e.slug));
const PAGES = path.resolve(__dirname, '../pages');

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((f) =>
    f.isDirectory()
      ? walk(path.join(dir, f.name))
      : f.name.endsWith('.tsx')
        ? [path.join(dir, f.name)]
        : [],
  );
}

interface Chip {
  file: string;
  term: string;
  dict?: string;
}

/** `term: 'x',` optionally followed by `dict: 'y',` — the shape every chip literal has. */
const CHIP = /term: '([^']+)',\s*(?:dict: '([^']+)',)?/g;

const chips: Chip[] = walk(PAGES).flatMap((file) =>
  [...readFileSync(file, 'utf8').matchAll(CHIP)].map((m) => ({
    file: path.relative(PAGES, file),
    term: m[1],
    dict: m[2],
  })),
);

describe('Explainer chips and the dictionary', () => {
  it('found the chips', () => {
    expect(chips.length).toBeGreaterThan(100);
  });

  it('every dict slug names a dictionary entry', () => {
    const bad = chips.filter((c) => c.dict && !slugs.has(c.dict));
    expect(bad).toEqual([]);
  });

  it('every chip whose term the dictionary defines links to it', () => {
    const unlinked = chips
      .filter((c) => !c.dict && findEntry(dictionary, c.term))
      .map((c) => `${c.file}: '${c.term}' → dict: '${findEntry(dictionary, c.term)!.slug}'`);
    expect(unlinked).toEqual([]);
  });
});
