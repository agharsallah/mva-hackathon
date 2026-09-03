/**
 * The section registry (`lib/sections.ts`) — the store every mounted `Section` announces
 * itself to, and the only thing the "On this page" rail and the ⌘K palette read to know
 * what a page contains. Two properties are load-bearing and neither is visible from a
 * component test:
 *
 *   1. `slugify` is the anchor generator. Two sections whose titles differ only in
 *      punctuation must not collide, and a slug must stay a legal URL fragment and a legal
 *      DOM id — it is written into `href="#…"` and into `<section id="…">`.
 *   2. `list()` returns document order, not insertion order. The rail reads top to bottom,
 *      but React's effect order is mount order, and a page that renders a section
 *      conditionally re-registers it later — so ordering has to come from the DOM.
 *
 * This file talks to the store directly rather than through a render: the ordering property
 * is a claim about `compareDocumentPosition`, and registering in reverse is not something a
 * React tree lets you do on purpose.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import { sectionRegistry, slugify } from '../lib/sections';

// ── slugify ─────────────────────────────────────────────────────────────────────────────

describe('slugify', () => {
  it('lowercases and turns spaces into single hyphens', () => {
    expect(slugify('Zygosity Split')).toBe('zygosity-split');
    expect(slugify('  Spaced   Out  ')).toBe('spaced-out');
  });

  it('drops a trailing question mark rather than leaving a dangling hyphen', () => {
    expect(slugify('Which candidate genes have evidence?')).toBe(
      'which-candidate-genes-have-evidence',
    );
  });

  it('collapses every punctuation run to one hyphen', () => {
    // An apostrophe is punctuation like any other, so `caller's` splits into `caller-s`.
    // That is a *stable* mapping — the anchor it produces is what `Callset.tsx`'s section
    // gets today — not an accident: the point of the assertion is that it never changes
    // silently, because a changed slug is a broken `#anchor` in every doc that links it.
    expect(slugify("What survived the caller's filters")).toBe(
      'what-survived-the-caller-s-filters',
    );
    expect(slugify('Depth, VAF & the 0.5 line')).toBe('depth-vaf-the-0-5-line');
  });

  it('never emits a leading or trailing hyphen', () => {
    expect(slugify('…leading and trailing punctuation…')).toBe('leading-and-trailing-punctuation');
    expect(slugify('!!!')).toBe('');
  });

  it('caps the slug at 80 characters', () => {
    const slug = slugify('a'.repeat(200));
    expect(slug).toHaveLength(80);
    expect(slugify(`${'word '.repeat(40)}tail`)).toHaveLength(80);
  });

  it('yields an ASCII, URL-safe fragment for an accented title', () => {
    // The property that actually matters for an `href="#…"` and a DOM id: whatever comes
    // out is [a-z0-9-] only.
    expect(slugify('Résumé of the Ünïcödé Ärt')).toMatch(/^[a-z0-9-]*$/);
    expect(slugify('Cobertura del genoma — 1 Mb')).toMatch(/^[a-z0-9-]*$/);
  });

  it('folds an accented letter to its base letter instead of hyphenating the accent', () => {
    expect(slugify('Résumé of the Coverage')).toBe('resume-of-the-coverage');
    expect(slugify('Ünïcödé Ärt')).toBe('unicode-art');
  });
});

// ── the store ───────────────────────────────────────────────────────────────────────────

function detached(id: string): HTMLElement {
  const el = document.createElement('section');
  el.id = id;
  document.body.append(el);
  return el;
}

afterEach(() => {
  sectionRegistry.list().forEach((s) => sectionRegistry.unregister(s.id));
  document.body.replaceChildren();
});

describe('sectionRegistry', () => {
  it('bumps the version and notifies subscribers on register and unregister', () => {
    const notify = vi.fn();
    const unsubscribe = sectionRegistry.subscribe(notify);
    const before = sectionRegistry.version();

    sectionRegistry.register({ id: 'one', title: 'One', el: detached('one') });
    expect(notify).toHaveBeenCalledTimes(1);
    expect(sectionRegistry.version()).toBe(before + 1);

    sectionRegistry.unregister('one');
    expect(notify).toHaveBeenCalledTimes(2);
    expect(sectionRegistry.version()).toBe(before + 2);

    unsubscribe();
    sectionRegistry.register({ id: 'two', title: 'Two', el: detached('two') });
    expect(notify).toHaveBeenCalledTimes(2);
  });

  it('does not bump the version when unregistering an id that was never registered', () => {
    const notify = vi.fn();
    const unsubscribe = sectionRegistry.subscribe(notify);
    const before = sectionRegistry.version();

    sectionRegistry.unregister('never-registered');

    expect(notify).not.toHaveBeenCalled();
    expect(sectionRegistry.version()).toBe(before);
    unsubscribe();
  });

  it('re-registering the same id replaces the entry instead of duplicating it', () => {
    const first = detached('dup');
    sectionRegistry.register({ id: 'dup', title: 'First title', el: first });
    sectionRegistry.register({ id: 'dup', title: 'Second title', el: first });

    expect(sectionRegistry.list()).toHaveLength(1);
    expect(sectionRegistry.list()[0]?.title).toBe('Second title');
  });

  it('lists sections in document order, not registration order', () => {
    // Appended top-to-bottom…
    const top = detached('top');
    const middle = detached('middle');
    const bottom = detached('bottom');

    // …registered bottom-to-top, which is what a conditionally-rendered section does.
    sectionRegistry.register({ id: 'bottom', title: 'Bottom', el: bottom });
    sectionRegistry.register({ id: 'middle', title: 'Middle', el: middle });
    sectionRegistry.register({ id: 'top', title: 'Top', el: top });

    expect(sectionRegistry.list().map((s) => s.id)).toEqual(['top', 'middle', 'bottom']);
  });

  it('drops an unregistered section from the list and keeps the rest in order', () => {
    const a = detached('a');
    const b = detached('b');
    const c = detached('c');
    sectionRegistry.register({ id: 'a', title: 'A', el: a });
    sectionRegistry.register({ id: 'b', title: 'B', el: b });
    sectionRegistry.register({ id: 'c', title: 'C', el: c });

    sectionRegistry.unregister('b');

    expect(sectionRegistry.list().map((s) => s.id)).toEqual(['a', 'c']);
  });

  it('hands back the title and element it was given, so the rail needs no DOM lookup', () => {
    const el = detached('only');
    sectionRegistry.register({ id: 'only', title: 'Zygosity split', el });

    expect(sectionRegistry.list()).toEqual([{ id: 'only', title: 'Zygosity split', el }]);
  });
});
