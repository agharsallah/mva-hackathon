/**
 * Every entry knows when it arrived, and its `*Context:*` metadata points somewhere real.
 *
 * `dictionary.test.ts` proves the generated JSON has the shape the Learn page renders.
 * This file proves the *metadata* half of an entry holds: a `firstSeen` date on all of them
 * (git's answer, or an explicit one in the markdown), `related` slugs that resolve to entries
 * that exist, `see` targets that are anchors or absolute URLs, and — for the terms this
 * iteration introduced — a named source file.
 *
 * The generator refuses an unresolvable `related` or a missing `source:` file, so a failure
 * here means the committed JSON is stale: run `pnpm dictionary`.
 */

import { describe, expect, it } from 'vitest';

import { type Dictionary, entriesOf, loadDictionary } from '../lib/dictionary';

const dictionary: Dictionary = await loadDictionary();
const entries = entriesOf(dictionary);
const slugs = new Set(entries.map((e) => e.slug));
const bySlug = new Map(entries.map((e) => [e.slug, e]));

/** The terms added when the submission iteration became a first-class thing. */
const ITERATION_TERMS = [
  'clinical-dataset',
  'submission-iteration',
  'selector-submission',
  'folder-gate',
  'coordinate-gate',
  'frozen-iteration',
  'scorer-cross-check',
  'audit-trail',
  'methodology-entry',
];

describe('entry metadata', () => {
  it('dates every entry as YYYY-MM-DD', () => {
    const undated = entries.filter((e) => !/^\d{4}-\d{2}-\d{2}$/.test(e.firstSeen ?? ''));
    expect(undated.map((e) => e.term)).toEqual([]);
  });

  it('dates nothing in the future', () => {
    const today = new Date().toISOString().slice(0, 10);
    expect(entries.filter((e) => e.firstSeen > today).map((e) => e.term)).toEqual([]);
  });

  it('counts the context lines it shipped', () => {
    const withContext = entries.filter(
      (e) => e.context || e.source || e.related?.length || e.see?.length,
    );
    expect(withContext.length).toBe(dictionary.counts.contexts);
    expect(withContext.length).toBeGreaterThanOrEqual(20);
  });

  it('resolves every related slug to an entry, and never to itself', () => {
    const broken = entries.flatMap((e) =>
      (e.related ?? [])
        .filter((slug) => !slugs.has(slug) || slug === e.slug)
        .map((slug) => `${e.slug} → ${slug}`),
    );
    expect(broken).toEqual([]);
  });

  it('points every see target at an anchor on this page or an absolute URL', () => {
    const bad = entries.flatMap((e) =>
      (e.see ?? [])
        .filter((t) => !(t.startsWith('#') ? slugs.has(t.slice(1)) : /^https?:\/\//.test(t)))
        .map((t) => `${e.slug} → ${t}`),
    );
    expect(bad).toEqual([]);
  });

  /**
   * A `source:` names where the term came from. The dictionary's own rule allows three
   * kinds — "the methodology entry, paper, file or tool that introduced it" — so a source
   * is a comma-separated list whose every item is either a repo-relative path or a `PMID`
   * citation. The rule was a single-path regex until chapter 23 landed terms whose origin
   * genuinely is a publication (mitotic slippage, the standard of care) or two files at
   * once (the decoy card: the module *and* the entry). Widened rather than suppressed: an
   * item that is neither a path nor a PMID still fails.
   */
  const SOURCE_ITEM = /^(?:[\w.@-]+\/\S+|PMID\s*\d+(?:\s*\([^)]*\))?|\d{6,9})$/;

  it('names a repo-relative path or a citation for every source an entry declares', () => {
    const bad = entries.filter(
      (e) =>
        e.source &&
        !e.source
          .split(',')
          .map((part) => part.trim())
          .every((part) => SOURCE_ITEM.test(part)),
    );
    expect(bad.map((e) => `${e.slug}: ${e.source}`)).toEqual([]);
  });

  it('gives the iteration terms a definition, an example, a source and related entries', () => {
    for (const slug of ITERATION_TERMS) {
      const entry = bySlug.get(slug);
      expect(entry, `missing entry ${slug}`).toBeDefined();
      expect(entry!.html.length, slug).toBeGreaterThan(80);
      expect(entry!.exampleHtml, slug).toContain('<em>');
      expect(entry!.source, slug).toBeTruthy();
      expect(entry!.related?.length ?? 0, slug).toBeGreaterThan(2);
      expect(entry!.firstSeen, slug).toBe('2026-09-05');
    }
  });

  it('leans the new scoring terms on the words that were already there', () => {
    expect(bySlug.get('scorer-cross-check')?.related).toContain('f-max');
    expect(bySlug.get('selector-submission')?.source).toBe('src/mva/warehouse/submission_spec.py');
    expect(bySlug.get('coordinate-gate')?.related).toContain('selector-submission');
    expect(bySlug.get('clinical-dataset')?.related).toContain('hpo-human-phenotype-ontology');
  });
});
