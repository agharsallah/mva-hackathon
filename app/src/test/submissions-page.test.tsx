/**
 * The Submissions page, offline.
 *
 * Gate 2 already proves the module mounts and gate 3 that it is accessible. This file
 * asserts the four things that are *specific* to a submission dossier and that a generic
 * smoke test cannot see:
 *
 *   1. the header identifies the file the organisers would receive — its state and the
 *      prefix of its sha256, because the file itself is deliberately not in the repository;
 *   2. the decode table paints the "full match at rank 1" row green, which is the repo's
 *      colour convention doing actual work: that row is the goal state;
 *   3. **no coordinate reaches the DOM** from the selectors exhibit — the page's whole
 *      reason to exist is that it shows the reasoning instead of the positions;
 *   4. an unreachable warehouse is stated, never rendered as an empty graph;
 *   5. an unspent oracle budget says so in the words the ledger uses.
 *
 * No chart is rendered on this page, so `plotly.js-dist-min` is not stubbed here — nothing
 * in the tree imports it.
 */

import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import type { SubmissionLineage } from '../api/types';
import { modules } from '../app/modules';
import { entriesOf, loadDictionary } from '../lib/dictionary';
import { LineageView } from '../pages/submissions/LineageView';
import { mountModule, stubUnreachableFetch } from './testHarness';

const submissions = modules.find((m) => m.id === 'submissions')!;

/**
 * A standalone digit run of seven or more — the shape a GRCh38 position takes.
 *
 * The lookarounds are the whole point: `VCV000533901` is a ClinVar accession and `rs6025`
 * an rsID, both of which legitimately appear in a row's notes and neither of which is a
 * coordinate. Requiring the run to be bounded by non-alphanumerics keeps the assertion
 * about positions rather than about digits.
 */
/** The page opens on the newest iteration (2, an empty draft); the dossier tests read iteration 1. */
const ITERATION_1 = '?it=track1%2Fiteration-1';

const STANDALONE_LONG_NUMBER = /(?<![A-Za-z0-9])\d{7,}(?![A-Za-z0-9])/;

afterEach(cleanup);
beforeEach(() => {
  stubUnreachableFetch();
});

describe('the submission dossier', () => {
  it('identifies the iteration by state and the prefix of its CSV sha256', async () => {
    const { caught } = await mountModule(submissions, ITERATION_1);
    expect(caught).toBeNull();

    // Iteration 1 was uploaded and answered, so its state badge says frozen.
    expect(screen.getAllByText('frozen').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^54854a6ef7a2/).length).toBeGreaterThan(0);
    // Said in the header tile and again in the page's own copy, so both are asserted at once.
    expect(screen.getAllByText(/never committed/).length).toBeGreaterThan(0);
  }, 20000);

  it('paints the full-match-at-rank-1 row of the decode table green', async () => {
    await mountModule(submissions, ITERATION_1);

    const toned = [...document.querySelectorAll('tr[data-tone]')];
    expect(toned.length).toBeGreaterThan(0);

    const winner = toned.find((tr) => {
      const cells = [...tr.querySelectorAll('td')];
      return cells.at(-1)?.textContent?.trim() === 'stop+missense';
    });
    expect(winner, 'no decode row whose survivor is exactly "stop+missense"').toBeTruthy();
    expect(winner!.getAttribute('data-tone')).toBe('good');

    // …and the "no match at all" row is red, so the convention is not green-everywhere.
    const noMatch = toned.find((tr) =>
      [...tr.querySelectorAll('td')].at(-1)?.textContent?.includes('neither'),
    );
    expect(noMatch?.getAttribute('data-tone')).toBe('broken');
  }, 20000);

  it('renders the selectors with no genomic position anywhere in them', async () => {
    await mountModule(submissions, ITERATION_1);

    const body = screen.getByTestId('selectors-body');
    const text = body.textContent ?? '';

    expect(text).toContain('gene = BUB1B AND consequence LIKE %stop_gained%');
    expect(text.match(STANDALONE_LONG_NUMBER)?.[0] ?? null).toBeNull();
    // The clause grammar is what replaces the coordinate, so it has to actually be there.
    expect(within(body).getAllByText(/AND/).length).toBeGreaterThan(0);
  }, 20000);

  it('draws the lineage graph and names both delivered inputs', async () => {
    await mountModule(submissions, ITERATION_1);

    // The clinical document and the delivered callset object are roots side by side — the form of
    // the rule that both delivered data sources are cross-referenced.
    expect(
      screen.getAllByText('s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz').length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText('ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md').length,
    ).toBeGreaterThan(0);

    const svg = document.querySelector('svg[aria-label*="recorded derivations"]');
    expect(svg, 'no lineage graph rendered').toBeTruthy();
    expect(svg!.getAttribute('aria-label')).toMatch(/recorded derivations/);
  }, 20000);

  it('lists the spent probe by its CSV digest, never by its payload', async () => {
    await mountModule(submissions, ITERATION_1);
    expect(screen.getByText(/^54854a6ef7a2…$/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/PROBAND01,chr/);
  }, 20000);
});

describe('lineage when the warehouse is unreachable', () => {
  const unreachable: SubmissionLineage = {
    available: false,
    note: 'could not connect to the warehouse: connection refused',
    sources: [
      {
        kind: 'raw',
        ref: 's3://mva/delivery/proband01.vcf.gz',
        version: 'v1',
        sha256: 'verified',
        note: 'the delivered callset',
      },
    ],
    edges: [],
  };

  it('states the failure and still lists the roots read off disk', () => {
    render(
      <MemoryRouter>
        <LineageView lineage={unreachable} source="fixture: test" />
      </MemoryRouter>,
    );

    expect(screen.getByText('Database unreachable — lineage roots from disk only')).toBeTruthy();
    expect(screen.getByText(/connection refused/)).toBeTruthy();
    // The roots survive a dead database — an empty graph must not read as "no lineage".
    expect(screen.getByText('s3://mva/delivery/proband01.vcf.gz')).toBeTruthy();
    expect(document.querySelector('svg[role="img"]')).toBeNull();
  });
});

describe('the beginner guide', () => {
  it('walks the iteration in six steps, every one of them read off the payload', async () => {
    await mountModule(submissions, ITERATION_1);

    const guide = screen.getByTestId('beginner-guide');
    const text = guide.textContent ?? '';

    // The counts are the fixture's own: 8 rows, 5 primary, 3 secondary.
    expect(text).toContain('8 rows');
    expect(text).toContain('5 are primary');
    expect(text).toContain('3 are');
    expect(guide.querySelectorAll('li').length).toBe(6);
    // The gene is read from the selectors, never typed into the component.
    expect(text).toContain('BUB1B');
    // …and it teaches the word rather than replacing it.
    expect(text).toContain('compound heterozygote');
    expect(text).toContain('two different broken copies of one gene');
  }, 20000);

  it('links every technical term to an entry that exists in the one dictionary', async () => {
    await mountModule(submissions, ITERATION_1);

    const guide = screen.getByTestId('beginner-guide');
    const slugs = [...guide.querySelectorAll('a[href]')]
      .map((a) => a.getAttribute('href') ?? '')
      .filter((href) => href.includes('/learn#'))
      .map((href) => href.split('#')[1]!);
    expect(slugs.length).toBeGreaterThan(8);

    const dictionary = await loadDictionary();
    const known = new Set(entriesOf(dictionary).map((e) => e.slug));
    const missing = slugs.filter((slug) => !known.has(slug));
    expect(missing, `dictionary has no entry for ${missing.join(', ')}`).toEqual([]);
  }, 30000);

  it('carries no genomic position — the guide quotes notes, so this is not free', async () => {
    await mountModule(submissions, ITERATION_1);
    const text = screen.getByTestId('beginner-guide').textContent ?? '';
    expect(text.match(STANDALONE_LONG_NUMBER)?.[0] ?? null).toBeNull();
  }, 20000);

  it('replaced the recipe disclosure with one line under the picker', async () => {
    await mountModule(submissions, ITERATION_1);
    expect(screen.queryByText('How the next iteration appears here')).toBeNull();
    expect(screen.getByText(/New iterations appear here automatically/)).toBeTruthy();
  }, 20000);
});

describe('a panel-judged iteration (Track 2)', () => {
  const ITERATION_T2 = '?it=track2%2Fiteration-1';

  it('renders the folder with no decode table, no CSV and no selectors', async () => {
    const { caught } = await mountModule(submissions, ITERATION_T2);
    expect(caught).toBeNull();

    // Track 2 has no scorer, so the three scored-submission sections are absent *by rule* —
    // and the page says which four things a panel gets instead, rather than drawing a gap.
    expect(
      screen.queryByRole('heading', { name: /What every possible reply would mean/ }),
    ).toBeNull();
    expect(screen.queryByRole('heading', { name: /What is being claimed/ })).toBeNull();
    expect(screen.queryByText(/decode table below is that design/)).toBeTruthy();
    expect(document.querySelectorAll('tr[data-tone]').length).toBe(0);

    const handover = screen.getByTestId('panel-handover');
    for (const item of ['the report (PDF)', 'the repository', 'a 3-minute video'])
      expect(handover.textContent).toContain(item);

    // The predictions-CSV tile is replaced, not emptied.
    expect(screen.getAllByText('panel').length).toBeGreaterThan(0);
  }, 20000);

  it('lists the deliverables the folder actually holds, and who contributed them', async () => {
    await mountModule(submissions, ITERATION_T2);

    const body = document.body.textContent ?? '';
    for (const file of [
      'report.md',
      'agharsallah_track2_report.pdf',
      'methods-form.json',
      'agharsallah_track2_methods_form.xlsx',
      'pitch-script.md',
      'README.md',
    ])
      expect(body, `no ${file} in the deliverables`).toContain(file);

    // The contributions table is the link back into the append-only record.
    expect(
      screen.getAllByRole('heading', { name: 'Which steps contributed' }).length,
    ).toBeGreaterThan(0);
    expect(body).toContain('iteration 2, step 7');
  }, 20000);

  it('walks a panel-judged folder in six steps, built from its own payload', async () => {
    await mountModule(submissions, ITERATION_T2);

    const guide = screen.getByTestId('beginner-guide');
    expect(guide.querySelectorAll('li').length).toBe(6);
    const text = guide.textContent ?? '';
    expect(text).toContain('Nothing here is scored by a program');
    expect(text).toContain('3-minute video');
    // Every number is the payload's own.
    expect(text).toContain('6 files');

    const slugs = [...guide.querySelectorAll('a[href]')]
      .map((a) => a.getAttribute('href') ?? '')
      .filter((href) => href.includes('/learn#'))
      .map((href) => href.split('#')[1]!);
    const dictionary = await loadDictionary();
    const known = new Set(entriesOf(dictionary).map((e) => e.slug));
    expect(slugs.filter((slug) => !known.has(slug))).toEqual([]);
  }, 30000);
});

describe('the two submission figures', () => {
  it('draws the rank ladder with one bar per submitted row, over the point tiers', async () => {
    await mountModule(submissions, ITERATION_1);

    const svg = document.querySelector('svg[aria-label*="rank-point tiers"]') as SVGElement | null;
    expect(svg, 'no rank ladder rendered').toBeTruthy();
    expect(svg!.querySelectorAll('g[data-rank]').length).toBe(8);
    // Ranks 2–5 are the alternative pairings, so they must still be primary (green) rows.
    expect(svg!.querySelector('g[data-rank="3"]')!.getAttribute('data-finding')).toBe('primary');
    expect(svg!.querySelector('g[data-rank="7"]')!.getAttribute('data-finding')).toBe('secondary');
    // The tier labels are the scorer's, printed where the reader can check them.
    expect(svg!.textContent).toContain('100 rank pts');
    expect(svg!.textContent).toContain('50 rank pts');
  }, 20000);

  it('splits the prior mass across the possible replies and prints the bits beside it', async () => {
    await mountModule(submissions, ITERATION_1);

    const svg = document.querySelector('svg[aria-label*="prior mass"]');
    expect(svg, 'no reply-odds bar rendered').toBeTruthy();
    const segments = [...svg!.querySelectorAll('rect[data-reply]')];
    // Only replies with prior mass are drawn: three of the seven under the derived priors.
    expect(segments.length).toBe(3);
    // Widest segment first: the expected reply is the one the design is betting on.
    expect(segments[0]!.getAttribute('data-reply')).toBe('stop+missense');

    expect(screen.getByTestId('reply-odds-summary').textContent).toContain(
      'expected information gain 0.963 bits',
    );
  }, 20000);
});
