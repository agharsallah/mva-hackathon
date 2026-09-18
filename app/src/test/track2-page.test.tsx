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
 *   5. the strategy timeline paints each phase the colour its own status maps to;
 *   6. every dictionary link resolves to an entry that exists in the one dictionary;
 *   7. the step-7 grading renders off the same fixture: the ladder matrix, the eleven
 *      shortlist rows the report may argue, the do-not table's caution block, the decoy
 *      chart's pre-registered 0.10 line, and F8 marked UNMEASURED.
 *
 * Counts are read off the committed fixture rather than typed in: a re-capture of
 * `/api/track2` changes them, and a test that hard-codes 3,766 rows fails for the wrong
 * reason when the only thing that happened is that the snapshot was rebuilt.
 *
 * The decoy exhibit draws through the shared `Plot` wrapper, so `plotly.js-dist-min` is
 * stubbed here — `vi.mock` is hoisted per file, which is why it cannot live in the harness.
 */

import { act, cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import type { Track2, Track2Lineage } from '../api/types';
import { modules } from '../app/modules';
import fixture from '../fixtures/data/track2.json';
import { entriesOf, loadDictionary } from '../lib/dictionary';
import { Track2LineageView } from '../pages/track2/LineageView';
import { mountModule, stubUnreachableFetch } from './testHarness';

vi.mock('plotly.js-dist-min', () => ({
  default: { react: vi.fn().mockResolvedValue(undefined), purge: vi.fn() },
}));

const track2 = modules.find((m) => m.id === 'track2')!;

/** The committed offline payload, so every count below is the fixture's own. */
const data = fixture as unknown as Track2;
const shortlist = data.shortlist ?? [];
const argue = shortlist.filter((r) => r.verdict === 'argue');
const group = (verdict: string) => (data.do_not ?? []).filter((r) => r.verdict === verdict);
const grouped = (n: number): string => n.toLocaleString('en-US');

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
      // A labelled PubMed id, in either spelling the app uses (`PMID:1234` in the card's
      // prose, `PMID 1234` in the step-7 links), including a run of them after one label
      // (`PMID 41749943 and 40421977`). The label is what makes it not a position.
      .replace(/PMID[: ]\s*\d+(?:\s*(?:,|and)\s*\d+)*/gi, '')
      .replace(/NCT\d+/g, '')
      .replace(/VCV\d+/g, '')
      .replace(/\b[0-9a-f]{12,}\b/g, '')
      .replace(/R-HSA-\d+/g, '')
      // Drug development codes: a molecule with no generic name yet is registered under one
      // (`PF-02341066` is crizotinib), and they are long enough to trip the coordinate check.
      .replace(/\b[A-Z]{2,5}-\d{4,}\b/g, '')
      // The decoy card's `picked_by` quotes its seed as an SQL string literal
      // (`md5(symbol || '20260918')`): a YYYYMMDD date in quotes, never a position.
      .replace(/'\d{8}'/g, '')
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
    expect(all.textContent).toContain(grouped(data.candidates.length));
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

  // The colour is the claim: `done` green, `open` blue (machinery that can run today),
  // `waiting` yellow (blocked on an oracle reply). Which statuses are *present* is the
  // fixture's business — the oracle has answered, so there is nothing waiting today — and
  // asserting a status that must exist would make this test about the plan, not the paint.
  it('paints every strategy phase the colour its own status maps to', async () => {
    await mountModule(track2);

    const TONE: Record<string, string> = { done: 'good', open: 'machinery', waiting: 'decision' };
    const phases = [...screen.getByTestId('strategy-phases').querySelectorAll('li[data-phase]')];
    expect(phases.length).toBe(data.strategy.length);

    const statuses = new Set(data.strategy.map((p) => p.status));
    expect(statuses.size).toBeGreaterThan(1);

    for (const phase of phases) {
      const status = phase.getAttribute('data-status')!;
      expect(Object.keys(TONE)).toContain(status);
      expect(phase.className).toContain(TONE[status]);
    }
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
    expect(text).toContain(grouped(data.candidates.length));
    expect(text).toContain(data.summary.card.gene);
    // …and the guide teaches the word rather than replacing it.
    expect(text).toContain('drug repurposing');
    expect(text).toContain('market-approved');
  }, 30000);

  it('draws the ladder matrix, with a rung cell per drug and the rung definitions', async () => {
    await mountModule(track2);

    const cells = [...document.querySelectorAll('[data-rung]')];
    expect(cells.length).toBeGreaterThan(0);
    // Rung 1 is "named, never submitted" and is deliberately not drawn.
    for (const c of cells) expect(Number(c.getAttribute('data-rung'))).toBeGreaterThan(1);

    // The four tones are the exhibit's whole argument; at least the two that separate a
    // curated result from an automated-only one have to be on the page.
    const tones = new Set(cells.map((c) => c.getAttribute('data-tone')));
    expect(tones.has('machinery')).toBe(true);
    expect([...tones].some((t) => t === 'good' || t === 'decision')).toBe(true);

    // The definitions come off the card, not out of the component.
    const defs = screen.getByTestId('rung-definitions');
    for (const rung of data.card.evidence_ladder!.rungs)
      expect(defs.textContent).toContain(rung.label);

    expect(screen.getByTestId('ladder-funnel').textContent).toContain('drugs by best rung');
  }, 30000);

  it('shortlists only the rows that carry a mechanism argument, each paper linked', async () => {
    await mountModule(track2);

    expect(argue.length).toBe(11);
    const table = screen.getByTestId('shortlist-argue');
    const rows = table.querySelectorAll('tbody tr');
    expect(rows.length).toBe(argue.length);
    expect(table.textContent).toContain(argue[0]!.drug_name);

    // Every cited paper opens on PubMed, and the visible text keeps the PMID label.
    const link = within(table).getAllByRole('link', { name: /^PMID / })[0]!;
    expect(link.getAttribute('href')).toMatch(/^https:\/\/pubmed\.ncbi\.nlm\.nih\.gov\/\d+\/$/);

    // The context-trial rows are real, explained, and collapsed until asked for.
    expect(screen.queryByTestId('shortlist-context')).toBeNull();
    await userEvent.click(
      screen.getByRole('button', { name: `show context-trial rows (${shortlist.length - 11})` }),
    );
    expect(screen.getByTestId('shortlist-context')).toBeTruthy();
  }, 30000);

  it("groups the do-not table by verdict and prints the card's anti-directions", async () => {
    await mountModule(track2);

    const caution = document.querySelector('[data-verdict="caution"]')!;
    expect(caution, 'no caution group in the do-not table').toBeTruthy();
    expect(caution.querySelectorAll('tbody tr').length).toBe(group('caution').length);
    expect(group('caution').length).toBeGreaterThan(0);

    const soc = document.querySelector('[data-verdict="standard of care"]')!;
    expect(soc.querySelectorAll('tbody tr').length).toBe(group('standard of care').length);

    const anti = screen.getByTestId('anti-directions');
    for (const a of data.card.anti_directions!)
      expect(anti.querySelector(`[data-anti="${a.id}"]`)).toBeTruthy();
  }, 30000);

  it('draws the decoy control with its pre-registered 0.10 line in the legend', async () => {
    await mountModule(track2);

    const figure = document.getElementById('decoy-control')!;
    expect(figure, 'no decoy exhibit on the page').toBeTruthy();
    expect(figure.textContent).toContain('0.10');
    // D4 is the tumour-context direction: a decoy reaches the same drugs through the same
    // clinical queries, so it is the one direction that is non-specific.
    expect(figure.textContent).toContain('D4');
    expect(figure.textContent).toMatch(/non-specific/);
    for (const d of data.decoys ?? []) expect(figure.textContent).toContain(d.symbol);
  }, 30000);

  it('marks F8 UNMEASURED and says so beside the table', async () => {
    await mountModule(track2);

    const f8 = data.card.measured_facts!.find((f) => f.id === 'F8')!;
    expect(f8.value).toMatch(/^UNMEASURED/);
    expect(screen.getAllByText('UNMEASURED').length).toBeGreaterThan(0);
    expect(screen.getByTestId('unmeasured-note').textContent).toContain('F8 is UNMEASURED');
  }, 30000);

  it('names paediatric evidence as a pointer, never a licence', async () => {
    await mountModule(track2);
    expect(screen.getByTestId('pediatric-caveat').textContent).toContain(
      'A pointer, never a licence',
    );
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
