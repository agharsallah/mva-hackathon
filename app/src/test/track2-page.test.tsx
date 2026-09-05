/**
 * The Track 2 page, offline.
 *
 * Gate 2 already proves the module mounts and gate 3 that it is accessible. This file
 * asserts what is *specific* to a drug-repurposing report and what a generic smoke test
 * cannot see:
 *
 *   1. it mounts against the committed fixture with no console.error and no axe violation;
 *   2. **no genomic position reaches the DOM** — the mechanism card is coordinate-free by
 *      rule, and this page renders thousands of rows of public data around it, so the rule
 *      is worth re-checking here rather than assuming;
 *   3. the approved-only toggle actually filters, and is on by default (Track 2's rules
 *      admit market-approved drugs only, so the default is a claim, not a convenience);
 *   4. a linked iteration card links back into the submission dossier;
 *   5. the strategy timeline paints the phases that wait on the oracle yellow;
 *   6. every dictionary link resolves to an entry that exists in the one dictionary.
 *
 * No chart component is used — the two bar charts are inline SVG — so `plotly.js-dist-min`
 * is not stubbed here; nothing in the tree imports it.
 */

import { act, cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import type { Track2Lineage } from '../api/types';
import { modules } from '../app/modules';
import { entriesOf, loadDictionary } from '../lib/dictionary';
import { Track2LineageView } from '../pages/track2/LineageView';
import { mountModule, stubUnreachableFetch } from './testHarness';

const track2 = modules.find((m) => m.id === 'track2')!;

/**
 * A standalone digit run of seven or more — the shape a GRCh38 position takes.
 *
 * The identifiers this page legitimately renders are stripped first rather than excluded by
 * a lookaround, because they are *long*: `PMID:42483440`, `NCT02644460`, a 64-hex checksum,
 * an OMIM number, a drug development code like `PF-02341066`. What is left is prose and table
 * cells, where a seven-digit run could only be a coordinate.
 */
const STANDALONE_LONG_NUMBER = /(?<![A-Za-z0-9])\d{7,}(?![A-Za-z0-9])/;

function withoutKnownIds(text: string): string {
  return (
    text
      .replace(/PMID:\d+/g, '')
      .replace(/NCT\d+/g, '')
      .replace(/VCV\d+/g, '')
      .replace(/\b[0-9a-f]{12,}\b/g, '')
      .replace(/R-HSA-\d+/g, '')
      // Drug development codes: a molecule with no generic name yet is registered under one
      // (`PF-02341066` is crizotinib), and they are long enough to trip the coordinate check.
      .replace(/\b[A-Z]{2,5}-\d{4,}\b/g, '')
  );
}

afterEach(cleanup);
beforeEach(() => {
  stubUnreachableFetch();
});

describe('the Track 2 report', () => {
  it('mounts offline, without a single console.error', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { caught } = await mountModule(track2);
    expect(caught).toBeNull();

    expect(screen.getAllByText(/drug repurposing/i).length).toBeGreaterThan(0);
    // The page's whole framing, asserted rather than implied.
    expect(
      screen.getByText(/The final drug suggestion is produced once, after all Track 1 iterations/),
    ).toBeTruthy();

    expect(spy.mock.calls.map((c) => String(c[0]))).toEqual([]);
    spy.mockRestore();
  }, 30000);

  // Gate 3 runs axe over every module; this repeats it for Track 2 alone so a violation
  // introduced here fails a test named after this page rather than a generic one.
  it('has no axe violation', async () => {
    const { container } = await mountModule(track2);
    let results!: Awaited<ReturnType<typeof axe>>;
    await act(async () => {
      // jsdom has no layout engine, so contrast cannot be evaluated here — same exclusion
      // gate 3 makes, for the same environment reason.
      results = await axe(container, { rules: { 'color-contrast': { enabled: false } } });
    });
    const summary = results.violations
      .map((v) => `  [${v.impact}] ${v.id} (${v.nodes.length} node(s)) — ${v.help}`)
      .join('\n');
    expect(results.violations, `axe violations on Track 2:\n${summary}`).toEqual([]);
  }, 60000);

  it('renders no genomic position anywhere on the page', async () => {
    await mountModule(track2);
    const text = withoutKnownIds(document.body.textContent ?? '');
    expect(text.match(STANDALONE_LONG_NUMBER)?.[0] ?? null).toBeNull();
  }, 30000);

  it('filters to market-approved drugs by default, and shows the rest when asked', async () => {
    await mountModule(track2);

    const toggle = screen.getByRole('button', { name: 'approved only' });
    expect(toggle.getAttribute('aria-pressed')).toBe('true');

    // The tile reads off the same filter the table does, so it is the honest row counter.
    const shown = screen.getByText('rows shown').parentElement!.parentElement!;
    const approvedOnly = Number(shown.textContent!.replace(/[^\d]/g, '').slice(0, 4));
    expect(approvedOnly).toBeGreaterThan(0);

    await userEvent.click(toggle);
    expect(toggle.getAttribute('aria-pressed')).toBe('false');

    const all = screen.getByText('rows shown').parentElement!.parentElement!;
    expect(all.textContent).toContain('3,766');
    // Un-filtering can only ever add rows.
    expect(all.textContent).not.toBe(String(approvedOnly));
  }, 30000);

  it('links each linked iteration back into the submission dossier', async () => {
    await mountModule(track2);

    const cards = screen.getByTestId('linked-iterations');
    const link = within(cards).getByRole('link', { name: 'track1/iteration-1' });
    expect(link.getAttribute('href')).toBe('/submissions?it=track1/iteration-1');
    // The link is the shared hypotheses, not the folder — so they have to be on the card.
    expect(cards.textContent).toContain('H003');
  }, 30000);

  it('paints the oracle-blocked strategy phases yellow, and the finished ones green', async () => {
    await mountModule(track2);

    const phases = [...screen.getByTestId('strategy-phases').querySelectorAll('li[data-phase]')];
    expect(phases.length).toBeGreaterThan(3);

    const waiting = phases.filter((p) => p.getAttribute('data-status') === 'waiting');
    expect(waiting.length).toBeGreaterThan(0);
    for (const p of waiting) expect(p.className).toContain('decision');

    const done = phases.filter((p) => p.getAttribute('data-status') === 'done');
    expect(done.length).toBeGreaterThan(0);
    for (const p of done) expect(p.className).toContain('good');
  }, 30000);

  it('draws both bar charts and the lineage graph, each with an accessible name', async () => {
    await mountModule(track2);

    expect(document.querySelector('svg[aria-label*="seed targets"]')).toBeTruthy();
    expect(document.querySelector('svg[aria-label*="public source"]')).toBeTruthy();
    const graph = document.querySelector('svg[aria-label*="recorded derivations"]');
    expect(graph, 'no lineage graph rendered').toBeTruthy();
  }, 30000);

  it('walks Track 2 in six steps, every one of them read off the payload', async () => {
    await mountModule(track2);

    const guide = screen.getByTestId('beginner-guide');
    expect(guide.querySelectorAll('li').length).toBe(6);
    const text = guide.textContent ?? '';
    // The snapshot's own counts, not typed into the component.
    expect(text).toContain('3,766');
    expect(text).toContain('BUB1B');
    // …and the guide teaches the word rather than replacing it.
    expect(text).toContain('drug repurposing');
    expect(text).toContain('market-approved');
  }, 30000);

  it('links every technical term to an entry that exists in the one dictionary', async () => {
    await mountModule(track2);

    const slugs = [...document.querySelectorAll('a[href]')]
      .map((a) => a.getAttribute('href') ?? '')
      .filter((href) => href.includes('/learn#'))
      .map((href) => href.split('#')[1]!);
    expect(slugs.length).toBeGreaterThan(8);

    const dictionary = await loadDictionary();
    const known = new Set(entriesOf(dictionary).map((e) => e.slug));
    const missing = [...new Set(slugs)].filter((slug) => !known.has(slug));
    expect(missing, `dictionary has no entry for ${missing.join(', ')}`).toEqual([]);
  }, 30000);
});

describe('Track 2 lineage when the warehouse is unreachable', () => {
  const unreachable: Track2Lineage = {
    available: false,
    note: 'could not connect to the warehouse: connection refused',
    sources: [
      {
        kind: 'card',
        ref: 'ressources/track2/mechanism.json',
        version: 'v2',
        sha256: 'verified',
        note: 'the mechanism hand-off',
      },
    ],
    edges: [],
  };

  it('states the failure and still lists the roots read off disk', () => {
    render(
      <MemoryRouter>
        <Track2LineageView lineage={unreachable} source="fixture: test" />
      </MemoryRouter>,
    );

    expect(screen.getByText('Warehouse unreachable — lineage roots from disk only')).toBeTruthy();
    expect(screen.getByText(/connection refused/)).toBeTruthy();
    // The roots survive a dead database — an empty graph must not read as "no lineage".
    expect(screen.getByText('ressources/track2/mechanism.json')).toBeTruthy();
    expect(document.querySelector('svg[role="img"]')).toBeNull();
  });
});
