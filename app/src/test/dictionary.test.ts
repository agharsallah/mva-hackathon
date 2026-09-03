/**
 * The generated dictionary holds together.
 *
 * `pnpm dictionary:check` proves the JSON matches the markdown; these tests prove the JSON
 * has the shape the Learn page and the Explainer rely on — every anchor unique and
 * resolvable, every figure present, every chapter in reading order. A dictionary edit that
 * breaks a deep link fails here, not in a reader's browser.
 */

import { describe, expect, it } from 'vitest';

import {
  chapterOfAnchor,
  type Dictionary,
  entriesOf,
  figureUrl,
  findEntry,
  loadDictionary,
} from '../lib/dictionary';

const dictionary: Dictionary = await loadDictionary();
const blocks = dictionary.chapters.flatMap((c) => c.blocks);
const entries = entriesOf(dictionary);

describe('the generated dictionary', () => {
  it('is what the generator says it is', () => {
    expect(dictionary.source).toBe('docs/dictionary.md');
    expect(dictionary.counts.chapters).toBe(dictionary.chapters.length);
    expect(dictionary.counts.entries).toBe(entries.length);
    expect(entries.length).toBeGreaterThan(400);
  });

  it('numbers its chapters 1..n in reading order', () => {
    expect(dictionary.chapters.map((c) => c.number)).toEqual(
      dictionary.chapters.map((_, i) => i + 1),
    );
  });

  it('gives every anchor exactly one owner', () => {
    const anchors = [
      ...dictionary.chapters.map((c) => c.id),
      ...blocks.flatMap((b) =>
        b.kind === 'entry' ? [b.slug] : b.kind === 'subheading' ? [b.id] : [],
      ),
    ];
    const seen = new Set<string>();
    const dupes = anchors.filter((a) => (seen.has(a) ? true : (seen.add(a), false)));
    expect(dupes).toEqual([]);
    expect(anchors.every((a) => /^[\p{Letter}\p{Number}-]+$/u.test(a))).toBe(true);
  });

  it('resolves every internal link it emits', () => {
    const targets = new Set(
      dictionary.chapters.flatMap((c) => [
        c.id,
        ...c.blocks.flatMap((b) => (b.kind === 'subheading' ? [b.id] : [])),
      ]),
    );
    const html = blocks
      .map((b) => ('html' in b ? b.html : '') + ('legendHtml' in b ? (b.legendHtml ?? '') : ''))
      .join('\n');
    const hrefs = [...html.matchAll(/href="#([^"]+)"/g)].map((m) => m[1]);
    expect(hrefs.length).toBeGreaterThan(0);
    expect(hrefs.filter((h) => !targets.has(h))).toEqual([]);
  });

  it('ships a URL for every figure the markdown embeds', () => {
    const missing = blocks
      .filter((b) => b.kind === 'figure')
      .map((b) => (b.kind === 'figure' ? b.file : ''))
      .filter((file) => figureUrl(file) === undefined);
    expect(missing).toEqual([]);
  });

  it('starts every definition after the em dash, not with the term repeated', () => {
    const repeated = entries.filter((e) => e.html.startsWith(`<p><strong>${e.term}</strong>`));
    expect(repeated).toEqual([]);
    expect(entries.every((e) => e.html.startsWith('<p>'))).toBe(true);
  });

  it('gives every figure and diagram a legend', () => {
    // The one ASCII block without a legend is a data-file excerpt (the mmCIF `atom_site`
    // loop), read as a table rather than a picture; pictures all carry one.
    const naked = blocks.filter(
      (b) => (b.kind === 'figure' || b.kind === 'mermaid') && !b.legendHtml,
    );
    expect(naked).toEqual([]);
  });

  it('looks up a term by name or alias, and finds its chapter from any anchor', () => {
    const allele = findEntry(dictionary, 'allele');
    expect(allele?.slug).toBe('allele');
    expect(chapterOfAnchor(dictionary, 'allele')?.number).toBe(1);
    expect(findEntry(dictionary, 'bp')?.slug).toBe('base-pair-bp');
    expect(chapterOfAnchor(dictionary, dictionary.chapters[3].id)?.number).toBe(4);
    expect(chapterOfAnchor(dictionary, 'no-such-anchor')).toBeUndefined();
  });
});
